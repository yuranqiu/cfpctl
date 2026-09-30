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
	Verified bool
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
		yearFilter, _ := cmd.Flags().GetInt("year")

		maxDays := 365
		if within != "" {
			maxDays = parseWithin(within)
		}

		var entries []upcomingEntry
		for _, c := range confs {
			// If --year is set, show all deadlines for that year (including past)
			if yearFilter > 0 {
				for _, cyc := range c.Cycles {
					pc, err := model.ParseCycle(cyc)
					if err != nil {
						continue
					}
					for _, t := range pc.Tracks {
						if t.Deadline.Year() != yearFilter {
							continue
						}
						name := c.Name
						if pc.Name != "" {
							name = fmt.Sprintf("%s %s", c.Name, pc.Name)
						}
						if t.Name != "" {
							name = fmt.Sprintf("%s [%s]", name, t.Name)
						}
						days := model.DaysRemaining(t.Deadline, now)
						entries = append(entries, upcomingEntry{
							Name:     name,
							CCF:      c.Rank.CCF,
							Deadline: t.Deadline,
							DaysLeft: days,
							Verified: c.Verified,
						})
					}
				}
			} else {
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
						Verified: c.Verified,
					})
				}
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
		if yearFilter > 0 {
			fmt.Printf(ui.TitleStyle.Render("📅 Deadlines for %d")+"\n", yearFilter)
		} else {
			fmt.Println(ui.TitleStyle.Render("📅 Upcoming Deadlines"))
		}
		fmt.Println()

		widths := []int{34, 5, 12, 8}
		fmt.Println(ui.TableHeader([]string{"NAME", "CCF", "DEADLINE", "LEFT"}, widths))
		fmt.Println(ui.SeparatorLine(70))

		unverifiedCount := 0
		for _, e := range entries {
			daysStr := fmt.Sprintf("%dd", e.DaysLeft)
			styledDays := ui.StyleDaysLeft(e.DaysLeft)
			daysPadded := ui.PadRight(styledDays, widths[3]+len(styledDays)-len(daysStr))

			vMark := ""
			if !e.Verified {
				vMark = ui.SoonStyle.Render(" ⚠")
				unverifiedCount++
			}

			fmt.Printf("%s  %s  %s  %s%s\n",
				ui.PadRight(e.Name, widths[0]),
				ui.StyleCCF(e.CCF),
				ui.PadRight(e.Deadline.Format("Jan 02"), widths[2]),
				daysPadded,
				vMark,
			)
		}

		fmt.Println()
		fmt.Printf(ui.MutedStyle.Render("%d deadlines in the next %d days"), len(entries), maxDays)
		if unverifiedCount > 0 {
			fmt.Printf(ui.SoonStyle.Render("  (%d unverified ⚠)")+"\n", unverifiedCount)
		} else {
			fmt.Println()
		}
		return nil
	},
}

func init() {
	upcomingCmd.Flags().String("ccf", "", "Filter by CCF rank (A/B/C)")
	upcomingCmd.Flags().String("field", "", "Filter by field (comma-separated)")
	upcomingCmd.Flags().String("within", "", "Show deadlines within duration (e.g., 30d, 90d, 6m)")
	upcomingCmd.Flags().Int("year", 0, "Show deadlines for a specific year (e.g., --year 2025)")
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
