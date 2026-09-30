package cmd

import (
	"fmt"
	"sort"
	"strings"
	"time"

	"github.com/cfpctl/cfpctl/internal/model"
	"github.com/cfpctl/cfpctl/internal/store"
	"github.com/cfpctl/cfpctl/internal/ui"
	"github.com/spf13/cobra"
)

type planWindow struct {
	Month       string
	Conferences []planEntry
}

type planEntry struct {
	Name     string
	CCF      string
	Event    string
	Date     time.Time
	DaysLeft int
}

var planCmd = &cobra.Command{
	Use:   "plan",
	Short: "Plan your submission strategy across conferences",
	RunE: func(cmd *cobra.Command, args []string) error {
		s, err := store.New()
		if err != nil {
			return fmt.Errorf("loading data: %w", err)
		}

		field, _ := cmd.Flags().GetString("field")
		ccf, _ := cmd.Flags().GetString("ccf")
		next, _ := cmd.Flags().GetString("next")

		if field == "" {
			return fmt.Errorf("--field is required (e.g., --field ai,security)")
		}

		fields := splitFields(field)
		confs := s.Filter(ccf, fields)
		now := time.Now()

		maxDays := 180
		if next != "" {
			maxDays = parseWithin(next)
		}

		var entries []planEntry
		for _, c := range confs {
			for _, fd := range c.AllFutureDeadlines(now) {
				name := c.Name
				if fd.CycleName != "" {
					name = fmt.Sprintf("%s %s", c.Name, fd.CycleName)
				}
				if fd.TrackName != "" {
					name = fmt.Sprintf("%s [%s]", name, fd.TrackName)
				}

				if fd.Track.Abstract != nil && fd.Track.Abstract.After(now) {
					days := model.DaysRemaining(*fd.Track.Abstract, now)
					if days <= maxDays {
						entries = append(entries, planEntry{
							Name: name, CCF: c.Rank.CCF, Event: "abstract",
							Date: *fd.Track.Abstract, DaysLeft: days,
						})
					}
				}

				if fd.Track.Deadline.After(now) {
					days := model.DaysRemaining(fd.Track.Deadline, now)
					if days <= maxDays {
						entries = append(entries, planEntry{
							Name: name, CCF: c.Rank.CCF, Event: "submission",
							Date: fd.Track.Deadline, DaysLeft: days,
						})
					}
				}
			}
		}

		if len(entries) == 0 {
			fmt.Println()
			fmt.Println(ui.CrossStyle.Render("✗") + " No submission windows found.")
			fmt.Println()
			return nil
		}

		sort.Slice(entries, func(i, j int) bool {
			return entries[i].Date.Before(entries[j].Date)
		})

		windows := groupByMonth(entries)

		fmt.Println()
		fmt.Println(ui.TitleStyle.Render("📋 Submission Plan"))
		filterParts := []string{fmt.Sprintf("field=%s", strings.Join(fields, ","))}
		if ccf != "" {
			filterParts = append(filterParts, fmt.Sprintf("CCF=%s", ccf))
		}
		filterParts = append(filterParts, fmt.Sprintf("next=%dd", maxDays))
		fmt.Printf(ui.DimStyle.Render("   Filters: %s")+"\n", strings.Join(filterParts, ", "))
		fmt.Println()

		printPlan(windows)
		fmt.Println()

		totalSub, totalAbs := 0, 0
		for _, e := range entries {
			if e.Event == "submission" {
				totalSub++
			} else {
				totalAbs++
			}
		}
		fmt.Printf(ui.MutedStyle.Render("   %d submission deadlines, %d abstract deadlines across %d months")+"\n",
			totalSub, totalAbs, len(windows))
		fmt.Println()
		return nil
	},
}

func init() {
	planCmd.Flags().String("field", "", "Research field(s) — required")
	planCmd.Flags().String("ccf", "", "Filter by CCF rank")
	planCmd.Flags().String("next", "6m", "Planning horizon. Default: 6m")
	rootCmd.AddCommand(planCmd)
}

func groupByMonth(entries []planEntry) []planWindow {
	var windows []planWindow
	var currentMonth time.Month = -1
	var currentYear int = -1
	for _, e := range entries {
		m, y := e.Date.Month(), e.Date.Year()
		if m != currentMonth || y != currentYear {
			windows = append(windows, planWindow{Month: e.Date.Format("Jan 2006"), Conferences: []planEntry{e}})
			currentMonth, currentYear = m, y
		} else {
			windows[len(windows)-1].Conferences = append(windows[len(windows)-1].Conferences, e)
		}
	}
	return windows
}

func printPlan(windows []planWindow) {
	for wi, w := range windows {
		fmt.Println(ui.HeaderStyle.Render(fmt.Sprintf("  %s", w.Month)))
		fmt.Println(ui.DimStyle.Render("  ─────────────────────────────────────"))
		for _, e := range w.Conferences {
			icon := "○"
			eventStyle := ui.SafeStyle
			if e.Event == "abstract" {
				icon = "◇"
				eventStyle = ui.MutedStyle
			}
			daysStr := fmt.Sprintf("%dd", e.DaysLeft)
			styledDays := ui.StyleDaysLeft(e.DaysLeft)
			daysPadded := ui.PadRight(styledDays, 8+len(styledDays)-len(daysStr))
			fmt.Printf("  %s %-4s %-28s %-12s %s\n",
				eventStyle.Render(icon), ui.StyleCCF(e.CCF), e.Name, eventStyle.Render(e.Event), daysPadded)
		}
		if wi < len(windows)-1 {
			fmt.Println()
		}
	}
}
