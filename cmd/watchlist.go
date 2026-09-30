package cmd

import (
	"fmt"
	"time"

	"github.com/cfpctl/cfpctl/internal/model"
	"github.com/cfpctl/cfpctl/internal/store"
	"github.com/cfpctl/cfpctl/internal/ui"
	"github.com/cfpctl/cfpctl/internal/watchlist"
	"github.com/spf13/cobra"
)

var watchlistCmd = &cobra.Command{
	Use:     "watchlist",
	Aliases: []string{"wl"},
	Short:   "Show your watched conferences and their deadlines",
	RunE: func(cmd *cobra.Command, args []string) error {
		wl, err := watchlist.Load()
		if err != nil {
			return fmt.Errorf("loading watchlist: %w", err)
		}

		if len(wl.Entries) == 0 {
			fmt.Println()
			fmt.Println(ui.MutedStyle.Render("Your watchlist is empty."))
			fmt.Println(ui.DimStyle.Render("Use 'cfpctl watch <conference>' to add conferences."))
			fmt.Println()
			return nil
		}

		s, err := store.New()
		if err != nil {
			return fmt.Errorf("loading data: %w", err)
		}

		now := time.Now()

		fmt.Println()
		fmt.Println(ui.TitleStyle.Render("👁 Watchlist"))
		fmt.Println()

		widths := []int{24, 20, 12, 8}
		fmt.Println(ui.TableHeader([]string{"CONFERENCE", "EVENT", "DEADLINE", "LEFT"}, widths))
		fmt.Println(ui.SeparatorLine(72))

		for _, entry := range wl.Entries {
			conf := s.GetBySlug(entry.Slug)
			if conf == nil {
				fmt.Printf("%s  %s\n",
					ui.PadRight(entry.Slug, widths[0]),
					ui.DimStyle.Render("(unknown)"))
				continue
			}

			fds := conf.AllFutureDeadlines(now)
			if len(fds) == 0 {
				fmt.Printf("%s  %s\n",
					ui.PadRight(conf.Name, widths[0]),
					ui.DimStyle.Render("(no upcoming)"))
				continue
			}

			printedName := false
			for _, fd := range fds {
				nameDisplay := ""
				if !printedName {
					nameDisplay = conf.Name
					printedName = true
				}

				eventLabel := fd.TrackName
				if eventLabel == "" {
					eventLabel = fd.CycleName
				}
				if eventLabel == "" {
					eventLabel = "submission"
				} else {
					eventLabel += " sub"
				}

				if fd.Track.Abstract != nil {
					days := model.DaysRemaining(*fd.Track.Abstract, now)
					daysStr := fmt.Sprintf("%dd", days)
					styledDays := ui.StyleDaysLeft(days)
					daysPadded := ui.PadRight(styledDays, widths[3]+len(styledDays)-len(daysStr))

					absEvent := eventLabel
					if fd.TrackName != "" {
						absEvent = fd.TrackName + " abs"
					} else if fd.CycleName != "" {
						absEvent = fd.CycleName + " abs"
					}

					absName := ""
					if !printedName {
						absName = conf.Name
						printedName = true
					}

					fmt.Printf("%s  %s  %s  %s\n",
						ui.PadRight(absName, widths[0]),
						ui.PadRight(absEvent, widths[1]),
						ui.PadRight(fd.Track.Abstract.Format("Jan 02"), widths[2]),
						daysPadded,
					)
				}

				days := model.DaysRemaining(fd.Track.Deadline, now)
				daysStr := fmt.Sprintf("%dd", days)
				styledDays := ui.StyleDaysLeft(days)
				daysPadded := ui.PadRight(styledDays, widths[3]+len(styledDays)-len(daysStr))

				fmt.Printf("%s  %s  %s  %s\n",
					ui.PadRight(nameDisplay, widths[0]),
					ui.PadRight(eventLabel, widths[1]),
					ui.PadRight(fd.Track.Deadline.Format("Jan 02"), widths[2]),
					daysPadded,
				)
			}
		}

		fmt.Println()
		return nil
	},
}

func init() {
	rootCmd.AddCommand(watchlistCmd)
}
