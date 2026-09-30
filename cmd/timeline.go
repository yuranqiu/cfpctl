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

type timelineEvent struct {
	Date     time.Time
	Name     string
	Event    string // "abstract", "submission"
	CCF      string
	DaysLeft int
}

var timelineCmd = &cobra.Command{
	Use:   "timeline",
	Short: "Show a visual timeline of upcoming deadlines",
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

		maxDays := 180
		if within != "" {
			maxDays = parseWithin(within)
		}

		var events []timelineEvent
		for _, c := range confs {
			for _, fd := range c.AllFutureDeadlines(now) {
				prefix := c.Name
				if fd.CycleName != "" {
					prefix = fmt.Sprintf("%s %s", c.Name, fd.CycleName)
				}
				if fd.TrackName != "" {
					prefix = fmt.Sprintf("%s [%s]", prefix, fd.TrackName)
				}

				if fd.Track.Abstract != nil && fd.Track.Abstract.After(now) {
					days := model.DaysRemaining(*fd.Track.Abstract, now)
					if days <= maxDays {
						events = append(events, timelineEvent{
							Date:     *fd.Track.Abstract,
							Name:     prefix,
							Event:    "abstract",
							CCF:      c.Rank.CCF,
							DaysLeft: days,
						})
					}
				}

				if fd.Track.Deadline.After(now) {
					days := model.DaysRemaining(fd.Track.Deadline, now)
					if days <= maxDays {
						events = append(events, timelineEvent{
							Date:     fd.Track.Deadline,
							Name:     prefix,
							Event:    "submission",
							CCF:      c.Rank.CCF,
							DaysLeft: days,
						})
					}
				}
			}
		}

		sort.Slice(events, func(i, j int) bool {
			return events[i].Date.Before(events[j].Date)
		})

		if len(events) == 0 {
			fmt.Println()
			fmt.Println(ui.CrossStyle.Render("✗") + " No upcoming events in the given timeframe.")
			fmt.Println()
			return nil
		}

		fmt.Println()
		fmt.Println(ui.TitleStyle.Render("📆 Deadline Timeline"))
		if field != "" || ccf != "" {
			filterDesc := []string{}
			if ccf != "" {
				filterDesc = append(filterDesc, fmt.Sprintf("CCF %s", ccf))
			}
			if field != "" {
				filterDesc = append(filterDesc, field)
			}
			fmt.Printf(ui.DimStyle.Render("   Filtered by: %s")+"\n", strings.Join(filterDesc, ", "))
		}
		fmt.Println()

		printTimeline(events, now)
		fmt.Println()
		return nil
	},
}

func init() {
	timelineCmd.Flags().String("ccf", "", "Filter by CCF rank (A/B/C)")
	timelineCmd.Flags().String("field", "", "Filter by field (comma-separated)")
	timelineCmd.Flags().String("within", "", "Time window (e.g., 90d, 6m). Default: 6m")
	rootCmd.AddCommand(timelineCmd)
}

func printTimeline(events []timelineEvent, now time.Time) {
	if len(events) == 0 {
		return
	}

	type monthGroup struct {
		label  string
		events []timelineEvent
	}

	var groups []monthGroup
	var currentMonth time.Month = -1
	var currentYear int = -1

	for _, e := range events {
		m := e.Date.Month()
		y := e.Date.Year()
		if m != currentMonth || y != currentYear {
			groups = append(groups, monthGroup{
				label:  e.Date.Format("Jan 2006"),
				events: []timelineEvent{e},
			})
			currentMonth = m
			currentYear = y
		} else {
			groups[len(groups)-1].events = append(groups[len(groups)-1].events, e)
		}
	}

	for gi, g := range groups {
		fmt.Println(ui.HeaderStyle.Render(g.label))
		fmt.Println(ui.DimStyle.Render("│"))

		for ei, e := range g.events {
			isLast := ei == len(g.events)-1
			connector := "├─"
			if isLast {
				connector = "└─"
			}

			dayStr := fmt.Sprintf("%02d", e.Date.Day())

			eventType := ui.DimStyle.Render(e.Event)
			nameStyled := e.Name

			switch e.Event {
			case "abstract":
				eventType = ui.MutedStyle.Render("abstract")
			case "submission":
				if e.DaysLeft <= 7 {
					eventType = ui.UrgentStyle.Render("⚡ SUBMISSION")
					nameStyled = ui.UrgentStyle.Render(e.Name)
				} else if e.DaysLeft <= 30 {
					eventType = ui.SoonStyle.Render("● submission")
				} else {
					eventType = ui.SafeStyle.Render("○ submission")
				}
			}

			daysStr := ui.StyleDaysLeft(e.DaysLeft)
			ccfStr := ui.StyleCCF(e.CCF)

			fmt.Printf("%s %s  %-4s %-26s %-12s %s\n",
				ui.DimStyle.Render(connector),
				dayStr,
				ccfStr,
				nameStyled,
				eventType,
				daysStr,
			)

			if !isLast {
				fmt.Println(ui.DimStyle.Render("│"))
			}
		}

		if gi < len(groups)-1 {
			fmt.Println(ui.DimStyle.Render("│"))
		}
	}
}
