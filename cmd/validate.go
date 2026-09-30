package cmd

import (
	"fmt"
	"os"

	"github.com/cfpctl/cfpctl/internal/ui"
	"github.com/cfpctl/cfpctl/internal/validate"
	"github.com/spf13/cobra"
)

var validateCmd = &cobra.Command{
	Use:   "validate",
	Short: "Validate conference data files against schema rules",
	Long: `Check all embedded YAML data files for correctness.

Validates:
  • Required fields (name, slug, fields, homepage, cycles)
  • Slug uniqueness and format (lowercase, hyphens)
  • CCF rank values (A/B/C)
  • Time format parsing for all deadlines
  • Cycle completeness

Useful for CI pipelines and data contributors.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		fmt.Println()
		fmt.Println(ui.TitleStyle.Render("🔍 Data Validation"))
		fmt.Println()

		result := validate.ValidateAll()
		fmt.Print(result.Summary())
		fmt.Println()

		if len(result.Errors) > 0 {
			os.Exit(1)
		}
		return nil
	},
}

func init() {
	rootCmd.AddCommand(validateCmd)
}
