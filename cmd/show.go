package cmd

import (
	"fmt"
	"strings"
	"time"

	"github.com/cfpctl/cfpctl/internal/model"
	"github.com/cfpctl/cfpctl/internal/store"
	"github.com/cfpctl/cfpctl/internal/ui"
	"github.com/spf13/cobra"
)

var showCmd = &cobra.Command{
	Use:   "show <conference>",
	Short: "Show detailed information about a conference",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		s, err := store.New()
		if err != nil {
			return fmt.Errorf("loading data: %w", err)
		}

		conf := s.GetBySlug(args[0])
		if conf == nil {
			return fmt.Errorf("conference not found: %s\nUse 'cfpctl search %s' to find the correct slug", args[0], args[0])
		}

		now := time.Now()
		printConferenceDetail(conf, now)
		return nil
	},
}

func init() {
	rootCmd.AddCommand(showCmd)
}

func printConferenceDetail(c *model.Conference, now time.Time) {
	sep := strings.Repeat("─", 50)

	fmt.Println()
	fmt.Println(ui.TitleStyle.Render(fmt.Sprintf("%s %d", strings.ToUpper(c.Name), nextYear(c, now))))
	fmt.Println(ui.DimStyle.Render(sep))
	fmt.Println()

	if c.Rank.CCF != "" {
		fmt.Printf("  %-12s %s\n", ui.MutedStyle.Render("CCF:"), ui.StyleCCF(c.Rank.CCF))
	}
	if c.Rank.CORE != "" {
		fmt.Printf("  %-12s %s\n", ui.MutedStyle.Render("CORE:"), ui.HeaderStyle.Render(c.Rank.CORE))
	}
	fmt.Printf("  %-12s %s\n", ui.MutedStyle.Render("Field:"), joinFields(c.Fields))
	if c.Location != "" && c.Location != "TBD" {
		fmt.Printf("  %-12s %s\n", ui.MutedStyle.Render("Location:"), c.Location)
	}
	fmt.Println()

	fmt.Println(ui.SectionHeader("Submission Cycles"))
	fmt.Println()

	nextDL := c.NextDeadline(now)

	for _, cyc := range c.Cycles {
		pc, err := model.ParseCycle(cyc)
		if err != nil || len(pc.Tracks) == 0 {
			continue
		}

		cycleName := pc.Name
		if cycleName == "" {
			cycleName = "Default"
		}

		hasMultipleTracks := len(pc.Tracks) > 1 || (len(pc.Tracks) == 1 && pc.Tracks[0].Name != "")

		if hasMultipleTracks {
			fmt.Println(ui.HeaderStyle.Render(fmt.Sprintf("  ▸ %s", cycleName)))
			for _, t := range pc.Tracks {
				isNext := nextDL != nil && t.Deadline.Equal(nextDL.Deadline)
				trackLabel := t.Name
				if trackLabel == "" {
					trackLabel = "Main"
				}
				if isNext {
					fmt.Println(ui.UrgentStyle.Render(fmt.Sprintf("    └─ %s ← NEXT", trackLabel)))
				} else {
					fmt.Println(ui.DimStyle.Render(fmt.Sprintf("    └─ %s", trackLabel)))
				}
				printTrackTimes(t, now, isNext)
			}
		} else {
			// Single unnamed track — display as before
			t := pc.Tracks[0]
			isNext := nextDL != nil && t.Deadline.Equal(nextDL.Deadline)
			label := cycleName
			if isNext {
				label = fmt.Sprintf("%s ← NEXT", cycleName)
				fmt.Println(ui.UrgentStyle.Render(fmt.Sprintf("  ▸ %s", label)))
			} else {
				fmt.Println(ui.HeaderStyle.Render(fmt.Sprintf("  ▸ %s", label)))
			}
			printTrackTimes(t, now, isNext)
		}
		fmt.Println()
	}

	if c.Homepage != "" || c.CFP != "" {
		fmt.Println(ui.SectionHeader("Links"))
		fmt.Println()
		if c.Homepage != "" {
			fmt.Printf("  🏠 %s\n", ui.LinkStyle.Render(c.Homepage))
		}
		if c.CFP != "" {
			fmt.Printf("  📄 %s\n", ui.LinkStyle.Render(c.CFP))
		}
		fmt.Println()
	}
}

func printTrackTimes(t model.ParsedTrack, now time.Time, isNext bool) {
	if t.Abstract != nil {
		fmt.Printf("      %-14s %s\n",
			ui.MutedStyle.Render("Abstract"),
			t.Abstract.Format("2006-01-02"))
	}

	deadlineStr := t.Deadline.Format("2006-01-02")
	if isNext {
		remaining := t.Deadline.Sub(now)
		deadlineStr = fmt.Sprintf("%s  (%s)", t.Deadline.Format("2006-01-02"), model.FormatDuration(remaining))
		fmt.Printf("      %-14s %s\n",
			ui.MutedStyle.Render("Submission"),
			ui.UrgentStyle.Render(deadlineStr))
	} else {
		fmt.Printf("      %-14s %s\n",
			ui.MutedStyle.Render("Submission"),
			deadlineStr)
	}

	if t.Notification != nil {
		fmt.Printf("      %-14s %s\n",
			ui.MutedStyle.Render("Notification"),
			t.Notification.Format("2006-01-02"))
	}
}

func nextYear(c *model.Conference, now time.Time) int {
	if nd := c.NextDeadline(now); nd != nil {
		return nd.Deadline.Year()
	}
	return now.Year() + 1
}
