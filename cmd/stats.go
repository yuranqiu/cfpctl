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

var statsCmd = &cobra.Command{
	Use:   "stats",
	Short: "Show conference database statistics",
	RunE: func(cmd *cobra.Command, args []string) error {
		s, err := store.New()
		if err != nil {
			return fmt.Errorf("loading data: %w", err)
		}

		now := time.Now()
		confs := s.All()

		totalConfs := len(confs)
		verifiedCount := 0
		withTracks := 0
		withAcceptRate := 0
		withRollingReview := 0
		fieldCounts := make(map[string]int)
		ccfCounts := map[string]int{"A": 0, "B": 0, "C": 0}

		var deadlinesIn30Days int
		var deadlinesIn90Days int
		var ccfAIn30Days int

		for _, c := range confs {
			if c.Verified {
				verifiedCount++
			}
			if c.AcceptRate != "" {
				withAcceptRate++
			}
			if c.RollingReview != nil {
				withRollingReview++
			}
			hasTracks := false
			for _, cyc := range c.Cycles {
				if len(cyc.Tracks) > 0 {
					hasTracks = true
					break
				}
			}
			if hasTracks {
				withTracks++
			}

			for _, f := range c.Fields {
				fieldCounts[f]++
			}
			if c.Rank.CCF != "" {
				ccfCounts[c.Rank.CCF]++
			}

			for _, fd := range c.AllFutureDeadlines(now) {
				days := model.DaysRemaining(fd.Track.Deadline, now)
				if days <= 30 {
					deadlinesIn30Days++
					if c.Rank.CCF == "A" {
						ccfAIn30Days++
					}
				}
				if days <= 90 {
					deadlinesIn90Days++
				}
			}
		}

		fmt.Println()
		fmt.Println(ui.TitleStyle.Render("📊 cfpctl Database Statistics"))
		fmt.Println()

		// Overview
		fmt.Println(ui.SectionHeader("Overview"))
		fmt.Printf("  Total conferences:  %d\n", totalConfs)
		fmt.Printf("  Verified:           %s\n", ui.CheckStyle.Render(fmt.Sprintf("%d (%.0f%%)", verifiedCount, float64(verifiedCount)/float64(totalConfs)*100)))
		fmt.Printf("  Multi-track:        %d\n", withTracks)
		fmt.Printf("  Acceptance rates:   %d\n", withAcceptRate)
		fmt.Printf("  Rolling review:     %d\n", withRollingReview)
		fmt.Println()

		// CCF Distribution
		fmt.Println(ui.SectionHeader("CCF Distribution"))
		fmt.Printf("  %s  %s  %s\n",
			ui.StyleCCF("A")+fmt.Sprintf(": %-4d", ccfCounts["A"]),
			ui.StyleCCF("B")+fmt.Sprintf(": %-4d", ccfCounts["B"]),
			ui.StyleCCF("C")+fmt.Sprintf(": %-4d", ccfCounts["C"]))
		fmt.Println()

		// Upcoming
		fmt.Println(ui.SectionHeader("Upcoming Deadlines"))
		fmt.Printf("  Next 30 days:  %d", deadlinesIn30Days)
		if ccfAIn30Days > 0 {
			fmt.Printf(" (%s)\n", ui.UrgentStyle.Render(fmt.Sprintf("%d CCF-A", ccfAIn30Days)))
		} else {
			fmt.Println()
		}
		fmt.Printf("  Next 90 days:  %d\n", deadlinesIn90Days)
		fmt.Println()

		// Top fields
		fmt.Println(ui.SectionHeader("Top Research Fields"))
		type fieldEntry struct {
			name  string
			count int
		}
		var fields []fieldEntry
		for name, count := range fieldCounts {
			fields = append(fields, fieldEntry{name, count})
		}
		sort.Slice(fields, func(i, j int) bool {
			return fields[i].count > fields[j].count
		})
		limit := 10
		if len(fields) < limit {
			limit = len(fields)
		}
		for i := 0; i < limit; i++ {
			bar := ""
			for b := 0; b < fields[i].count/2; b++ {
				bar += "█"
			}
			fmt.Printf("  %-18s %3d  %s\n",
				fields[i].name, fields[i].count,
				ui.DimStyle.Render(bar))
		}
		fmt.Println()

		return nil
	},
}

func init() {
	rootCmd.AddCommand(statsCmd)
}
