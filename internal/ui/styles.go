package ui

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// Color palette
var (
	ColorPrimary   = lipgloss.Color("#7C3AED") // purple
	ColorSecondary = lipgloss.Color("#06B6D4") // cyan
	ColorSuccess   = lipgloss.Color("#10B981") // green
	ColorWarning   = lipgloss.Color("#F59E0B") // amber
	ColorDanger    = lipgloss.Color("#EF4444") // red
	ColorMuted     = lipgloss.Color("#6B7280") // gray
	ColorWhite     = lipgloss.Color("#FFFFFF")
	ColorDim       = lipgloss.Color("#9CA3AF")
)

// Reusable styles
var (
	TitleStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(ColorPrimary)

	HeaderStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(ColorSecondary)

	CCFStyle = map[string]lipgloss.Style{
		"A": lipgloss.NewStyle().Bold(true).Foreground(ColorDanger),
		"B": lipgloss.NewStyle().Bold(true).Foreground(ColorWarning),
		"C": lipgloss.NewStyle().Bold(true).Foreground(ColorSuccess),
	}

	UrgentStyle = lipgloss.NewStyle().Bold(true).Foreground(ColorDanger)
	SoonStyle   = lipgloss.NewStyle().Bold(true).Foreground(ColorWarning)
	SafeStyle   = lipgloss.NewStyle().Foreground(ColorSuccess)
	DimStyle    = lipgloss.NewStyle().Foreground(ColorDim)
	MutedStyle  = lipgloss.NewStyle().Foreground(ColorMuted)

	BorderStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(ColorPrimary).
			Padding(0, 1)

	SectionStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(ColorSecondary).
			MarginTop(1)

	LinkStyle = lipgloss.NewStyle().
			Foreground(ColorSecondary).
			Underline(true)

	CheckStyle = lipgloss.NewStyle().Foreground(ColorSuccess)
	CrossStyle = lipgloss.NewStyle().Foreground(ColorDanger)
)

// StyleCCF returns a styled CCF rank string.
func StyleCCF(rank string) string {
	if s, ok := CCFStyle[strings.ToUpper(rank)]; ok {
		return s.Render(rank)
	}
	return MutedStyle.Render(rank)
}

// StyleDaysLeft returns a styled days-remaining string based on urgency.
func StyleDaysLeft(days int) string {
	s := fmt.Sprintf("%dd", days)
	switch {
	case days <= 7:
		return UrgentStyle.Render(s)
	case days <= 30:
		return SoonStyle.Render(s)
	default:
		return SafeStyle.Render(s)
	}
}

// SectionHeader renders a section title with a line underneath.
func SectionHeader(title string) string {
	line := strings.Repeat("─", 50)
	return SectionStyle.Render(title) + "\n" + DimStyle.Render(line)
}

// PadRight pads a string to the given width with spaces.
func PadRight(s string, width int) string {
	if len(s) >= width {
		return s
	}
	return s + strings.Repeat(" ", width-len(s))
}

// TableRow renders a single table row with column widths.
func TableRow(cols []string, widths []int, styles []lipgloss.Style) string {
	var parts []string
	for i, col := range cols {
		w := 10
		if i < len(widths) {
			w = widths[i]
		}
		padded := PadRight(col, w)
		if i < len(styles) {
			parts = append(parts, styles[i].Render(padded))
		} else {
			parts = append(parts, padded)
		}
	}
	return strings.Join(parts, "  ")
}

// TableHeader renders a header row with dimmed style.
func TableHeader(cols []string, widths []int) string {
	styles := make([]lipgloss.Style, len(cols))
	for i := range styles {
		styles[i] = HeaderStyle
	}
	return TableRow(cols, widths, styles)
}

// SeparatorLine returns a thin separator.
func SeparatorLine(width int) string {
	return DimStyle.Render(strings.Repeat("─", width))
}
