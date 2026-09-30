package cmd

import (
	"fmt"
	"strings"

	"github.com/cfpctl/cfpctl/internal/store"
	"github.com/cfpctl/cfpctl/internal/ui"
	"github.com/spf13/cobra"
)

var listCmd = &cobra.Command{
	Use:   "list",
	Short: "List all conferences in the database",
	RunE: func(cmd *cobra.Command, args []string) error {
		s, err := store.New()
		if err != nil {
			return fmt.Errorf("loading data: %w", err)
		}

		ccf, _ := cmd.Flags().GetString("ccf")
		field, _ := cmd.Flags().GetString("field")

		var fields []string
		if field != "" {
			fields = splitFields(field)
		}

		confs := s.Filter(ccf, fields)

		fmt.Println()
		fmt.Println(ui.TitleStyle.Render("📋 All Conferences"))
		fmt.Println()

		widths := []int{24, 20, 5, 6, 20}
		fmt.Println(ui.TableHeader([]string{"NAME", "SLUG", "CCF", "CORE", "FIELDS"}, widths))
		fmt.Println(ui.SeparatorLine(80))

		for _, c := range confs {
			name := ui.PadRight(c.Name, widths[0])
			slug := ui.PadRight(c.Slug, widths[1])
			ccfStyled := ui.StyleCCF(c.Rank.CCF)
			ccfPadded := ui.PadRight(ccfStyled, widths[2]+len(ccfStyled)-len(c.Rank.CCF))
			core := ui.PadRight(c.Rank.CORE, widths[3])
			fieldsStr := ui.DimStyle.Render(strings.Join(c.Fields, ", "))

			fmt.Printf("%s  %s  %s  %s  %s\n", name, slug, ccfPadded, core, fieldsStr)
		}

		fmt.Println()
		fmt.Printf(ui.MutedStyle.Render("%d conferences")+"\n", len(confs))
		return nil
	},
}

func init() {
	listCmd.Flags().String("ccf", "", "Filter by CCF rank (A/B/C)")
	listCmd.Flags().String("field", "", "Filter by field (comma-separated)")
	rootCmd.AddCommand(listCmd)
}
