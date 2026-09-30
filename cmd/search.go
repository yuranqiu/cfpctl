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

var searchCmd = &cobra.Command{
	Use:   "search <keyword>",
	Short: "Search conferences by name, slug, or field",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		s, err := store.New()
		if err != nil {
			return fmt.Errorf("loading data: %w", err)
		}

		results := s.Search(args[0])
		if len(results) == 0 {
			fmt.Println()
			fmt.Println(ui.CrossStyle.Render("✗") + " No conferences found matching: " + ui.HeaderStyle.Render(args[0]))
			fmt.Println()
			return nil
		}

		now := time.Now()

		fmt.Println()
		fmt.Printf(ui.TitleStyle.Render("🔍 Search Results for \"%s\"")+"\n", args[0])
		fmt.Println()

		widths := []int{24, 5, 14, 8}
		fmt.Println(ui.TableHeader([]string{"NAME", "CCF", "NEXT DEADLINE", "LEFT"}, widths))
		fmt.Println(ui.SeparatorLine(60))

		for _, c := range results {
			deadline := "-"
			left := "-"
			if nd := c.NextDeadline(now); nd != nil {
				deadline = nd.Deadline.Format("Jan 02")
				days := model.DaysRemaining(nd.Deadline, now)
				left = ui.StyleDaysLeft(days)
				leftPadded := ui.PadRight(left, widths[3]+len(left)-len(fmt.Sprintf("%dd", days)))
				fmt.Printf("%s  %s  %s  %s\n",
					ui.PadRight(c.Name, widths[0]),
					ui.StyleCCF(c.Rank.CCF),
					ui.PadRight(deadline, widths[2]),
					leftPadded,
				)
			} else {
				fmt.Printf("%s  %s  %s  %s\n",
					ui.PadRight(c.Name, widths[0]),
					ui.StyleCCF(c.Rank.CCF),
					ui.PadRight(deadline, widths[2]),
					ui.DimStyle.Render(left),
				)
			}
		}

		fmt.Println()
		fmt.Printf(ui.MutedStyle.Render("%d results")+"\n", len(results))
		return nil
	},
}

func init() {
	rootCmd.AddCommand(searchCmd)
}

func splitFields(s string) []string {
	parts := strings.Split(s, ",")
	var result []string
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			result = append(result, p)
		}
	}
	return result
}

func joinFields(fields []string) string {
	return strings.Join(fields, ", ")
}
