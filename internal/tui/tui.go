package tui

import (
	"fmt"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/cfpctl/cfpctl/internal/model"
	"github.com/cfpctl/cfpctl/internal/store"
	"github.com/cfpctl/cfpctl/internal/watchlist"
)

// Styles
var (
	titleStyle    = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#7C3AED"))
	selectedStyle = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#FFFFFF")).Background(lipgloss.Color("#7C3AED"))
	normalStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("#D1D5DB"))
	dimStyle      = lipgloss.NewStyle().Foreground(lipgloss.Color("#6B7280"))
	ccfAStyle     = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#EF4444"))
	ccfBStyle     = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#F59E0B"))
	ccfCStyle     = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#10B981"))
	urgentStyle   = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#EF4444"))
	soonStyle     = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#F59E0B"))
	safeStyle     = lipgloss.NewStyle().Foreground(lipgloss.Color("#10B981"))
	helpStyle     = lipgloss.NewStyle().Foreground(lipgloss.Color("#6B7280"))
	searchStyle   = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#06B6D4"))
)

type confItem struct {
	conf     model.Conference
	deadline *model.ParsedTrack
	daysLeft int
}

type Model struct {
	store     *store.Store
	items     []confItem
	filtered  []confItem
	cursor    int
	search    string
	searching bool
	width     int
	height    int
	watchlist *watchlist.WatchList
	showDetail bool
	detailConf *model.Conference
}

func NewModel() (Model, error) {
	s, err := store.New()
	if err != nil {
		return Model{}, err
	}
	wl, _ := watchlist.Load()

	m := Model{
		store:     s,
		watchlist: wl,
		width:     80,
		height:    24,
	}

	now := time.Now()
	for _, c := range s.All() {
		item := confItem{conf: c}
		if nd := c.NextDeadline(now); nd != nil {
			item.deadline = nd
			item.daysLeft = model.DaysRemaining(nd.Deadline, now)
		}
		m.items = append(m.items, item)
	}
	m.filtered = m.items

	return m, nil
}

func (m Model) Init() tea.Cmd {
	return nil
}

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		return m, nil

	case tea.KeyMsg:
		if m.showDetail {
			return m.updateDetail(msg)
		}
		if m.searching {
			return m.updateSearch(msg)
		}
		return m.updateList(msg)
	}
	return m, nil
}

func (m Model) updateList(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "q", "ctrl+c":
		return m, tea.Quit
	case "/":
		m.searching = true
		m.search = ""
		return m, nil
	case "enter":
		if len(m.filtered) > 0 {
			m.detailConf = &m.filtered[m.cursor].conf
			m.showDetail = true
		}
		return m, nil
	case "w":
		if len(m.filtered) > 0 {
			slug := m.filtered[m.cursor].conf.Slug
			if m.watchlist.Contains(slug) {
				m.watchlist.Remove(slug)
			} else {
				m.watchlist.Add(slug)
			}
			m.watchlist.Save()
		}
		return m, nil
	case "up", "k":
		if m.cursor > 0 {
			m.cursor--
		}
	case "down", "j":
		if m.cursor < len(m.filtered)-1 {
			m.cursor++
		}
	case "g":
		m.cursor = 0
	case "G":
		m.cursor = len(m.filtered) - 1
	}
	return m, nil
}

func (m Model) updateSearch(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "esc":
		m.searching = false
		if m.search == "" {
			m.filtered = m.items
			m.cursor = 0
		}
		return m, nil
	case "enter":
		m.searching = false
		return m, nil
	case "backspace":
		if len(m.search) > 0 {
			m.search = m.search[:len(m.search)-1]
			m.applyFilter()
		}
	default:
		if len(msg.String()) == 1 {
			m.search += msg.String()
			m.applyFilter()
		}
	}
	return m, nil
}

func (m Model) updateDetail(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "q", "esc", "backspace":
		m.showDetail = false
		m.detailConf = nil
	}
	return m, nil
}

func (m *Model) applyFilter() {
	kw := strings.ToLower(m.search)
	if kw == "" {
		m.filtered = m.items
	} else {
		var f []confItem
		for _, item := range m.items {
			if strings.Contains(strings.ToLower(item.conf.Name), kw) ||
				strings.Contains(strings.ToLower(item.conf.Slug), kw) {
				f = append(f, item)
			}
		}
		m.filtered = f
	}
	m.cursor = 0
}

func (m Model) View() string {
	if m.showDetail && m.detailConf != nil {
		return m.renderDetail()
	}
	return m.renderList()
}

func (m Model) renderList() string {
	var b strings.Builder

	// Title
	b.WriteString(titleStyle.Render("  📋 cfpctl — Conference Explorer"))
	b.WriteString("\n")

	// Search bar
	if m.searching {
		b.WriteString(searchStyle.Render(fmt.Sprintf("  🔍 %s█", m.search)))
	} else {
		b.WriteString(dimStyle.Render("  [/] Search  [Enter] Detail  [w] Watch  [q] Quit"))
	}
	b.WriteString("\n\n")

	// List
	listHeight := m.height - 6
	if listHeight < 5 {
		listHeight = 5
	}

	startIdx := 0
	if m.cursor >= listHeight {
		startIdx = m.cursor - listHeight + 1
	}

	for i := startIdx; i < len(m.filtered) && i < startIdx+listHeight; i++ {
		item := m.filtered[i]
		name := item.conf.Name
		ccf := item.conf.Rank.CCF
		left := "-"

		if item.deadline != nil {
			left = fmt.Sprintf("%dd", item.daysLeft)
		}

		watched := ""
		if m.watchlist.Contains(item.conf.Slug) {
			watched = " 👁"
		}

		line := fmt.Sprintf("  %-28s %-5s %6s%s", name, ccf, left, watched)

		if i == m.cursor {
			b.WriteString(selectedStyle.Render(fmt.Sprintf("▸ %s", line)))
		} else {
			b.WriteString(normalStyle.Render(fmt.Sprintf("  %s", line)))
		}
		b.WriteString("\n")
	}

	if len(m.filtered) == 0 {
		b.WriteString(dimStyle.Render("  No conferences found."))
		b.WriteString("\n")
	}

	// Footer
	b.WriteString("\n")
	b.WriteString(helpStyle.Render(fmt.Sprintf("  %d/%d conferences", len(m.filtered), len(m.items))))

	return b.String()
}

func (m Model) renderDetail() string {
	c := m.detailConf
	now := time.Now()
	var b strings.Builder

	b.WriteString(titleStyle.Render(fmt.Sprintf("  %s", strings.ToUpper(c.Name))))
	b.WriteString("\n")
	b.WriteString(dimStyle.Render("  " + strings.Repeat("─", 50)))
	b.WriteString("\n\n")

	b.WriteString(fmt.Sprintf("  CCF: %s  |  Field: %s\n", styleCCF(c.Rank.CCF), strings.Join(c.Fields, ", ")))
	if c.Verified {
		b.WriteString("  Status: ✓ Verified\n")
	} else {
		b.WriteString("  Status: ⚠ Unverified\n")
	}
	b.WriteString("\n")

	for _, cyc := range c.Cycles {
		pc, err := model.ParseCycle(cyc)
		if err != nil || len(pc.Tracks) == 0 {
			continue
		}
		cycleName := pc.Name
		if cycleName == "" {
			cycleName = "Default"
		}
		b.WriteString(searchStyle.Render(fmt.Sprintf("  ▸ %s", cycleName)))
		b.WriteString("\n")

		for _, t := range pc.Tracks {
			label := t.Name
			if label == "" {
				label = "Main"
			}
			b.WriteString(fmt.Sprintf("    └─ %s\n", label))
			if t.Abstract != nil {
				b.WriteString(fmt.Sprintf("       Abstract:     %s\n", t.Abstract.Format("2006-01-02")))
			}
			remaining := t.Deadline.Sub(now)
			if remaining > 0 {
				b.WriteString(fmt.Sprintf("       Submission:   %s  (%s)\n",
					t.Deadline.Format("2006-01-02"), model.FormatDuration(remaining)))
			} else {
				b.WriteString(fmt.Sprintf("       Submission:   %s  (passed)\n", t.Deadline.Format("2006-01-02")))
			}
			if t.Notification != nil {
				b.WriteString(fmt.Sprintf("       Notification: %s\n", t.Notification.Format("2006-01-02")))
			}
		}
		b.WriteString("\n")
	}

	b.WriteString(helpStyle.Render("  [Esc/q] Back"))
	return b.String()
}

func styleCCF(rank string) string {
	switch rank {
	case "A":
		return ccfAStyle.Render(rank)
	case "B":
		return ccfBStyle.Render(rank)
	case "C":
		return ccfCStyle.Render(rank)
	default:
		return dimStyle.Render(rank)
	}
}

// Run starts the TUI application.
func Run() error {
	m, err := NewModel()
	if err != nil {
		return err
	}
	p := tea.NewProgram(m, tea.WithAltScreen())
	_, err = p.Run()
	return err
}
