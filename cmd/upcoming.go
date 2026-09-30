package cmd

import (
	"fmt"
	"sort"
	"time"

	"github.com/cfpctl/cfpctl/internal/model"
	"github.com/cfpctl/cfpctl/internal/store"
	"github.com/cfpctl/cfpctl/internal/ui"
	"github.com/spf13/cobra"
)

type upcomingEntry struct {
	Name     string
	CCF      string
	Deadline time.Time
	DaysLeft int
}

var upcomingCmd = &cobra.Command{
	Use:   "upcoming",
	Short: "Show upcoming conference deadlines",
	RunE: func(cmd *cobra.Command, args []string) error {
		s, err := store.New()
		if err != nil {
			return fmt.Errorf("loading data: %w", err)
		}

		ccf, _ := cmd.Flags().GetString("ccf")
		field, _ := cmd.Flags().GetString("field")
		within, _ := cmd.Flags().GetString("within")

		var fields []string
		if field != "" {
			fields = splitFields(field)
		}

		confs := s.Filter(ccf, fields)
		now := time.Now()

		maxDays := 365
		if within != "" {
			maxDays = parseWithin(within)
		}

		var entries []upcomingEntry
		for _, c := range confs {
			for _, fd := range c.AllFutureDeadlines(now) {
				days := model.DaysRemaining(fd.Track.Deadline, now)
				if days > maxDays {
					continue
				}
				name := c.Name
				if fd.CycleName != "" {
					name = fmt.Sprintf("%s %s", c.Name, fd.CycleName)
				}
				if fd.TrackName != "" {
					name = fmt.Sprintf("%s [%s]", name, fd.TrackName)
				}
				entries = append(entries, upcomingEntry{
					Name:     name,
					CCF:      c.Rank.CCF,
					Deadline: fd.Track.Deadline,
					DaysLeft: days,
				})
			}
		}

		sort.Slice(entries, func(i, j int) bool {
			return entries[i].Deadline.Before(entries[j].Deadline)
		})

		if len(entries) == 0 {
			fmt.Println()
			fmt.Println(ui.CrossStyle.Render("✗") + " No upcoming deadlines found with the given filters.")
			fmt.Println()
			return nil
		}

		fmt.Println()
		fmt.Println(ui.TitleStyle.Render("📅 Upcoming Deadlines"))
		fmt.Println()

		widths := []int{34, 5, 12, 8}
		fmt.Println(ui.TableHeader([]string{"NAME", "CCF", "DEADLINE", "LEFT"}, widths))
		fmt.Println(ui.SeparatorLine(70))

		for _, e := range entries {
			daysStr := fmt.Sprintf("%dd", e.DaysLeft)
			styledDays := ui.StyleDaysLeft(e.DaysLeft)
			daysPadded := ui.PadRight(styledDays, widths[3]+len(styledDays)-len(daysStr))

			fmt.Printf("%s  %s  %s  %s\n",
				ui.PadRight(e.Name, widths[0]),
				ui.StyleCCF(e.CCF),
				ui.PadRight(e.Deadline.Format("Jan 02"), widths[2]),
				daysPadded,
			)
		}

		fmt.Println()
		fmt.Printf(ui.MutedStyle.Render("%d deadlines in the next %d days")+"\n", len(entries), maxDays)
		return nil
	},
}

func init() {
	upcomingCmd.Flags().String("ccf", "", "Filter by CCF rank (A/B/C)")
	upcomingCmd.Flags().String("field", "", "Filter by field (comma-separated)")
	upcomingCmd.Flags().String("within", "", "Show deadlines within duration (e.g., 30d, 90d, 6m)")
	rootCmd.AddCommand(upcomingCmd)
}

func parseWithin(s string) int {
	if len(s) == 0 {
		return 365
	}
	n := 0
	for _, ch := range s[:len(s)-1] {
		if ch >= '0' && ch <= '9' {
			n = n*10 + int(ch-'0')
		}
	}
	unit := s[len(s)-1]
	switch unit {
	case 'd', 'D':
		return n
	case 'm', 'M':
		return n * 30
	case 'y', 'Y':
		return n * 365
	default:
		return n
	}
}
