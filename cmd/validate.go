package cmd

import (
	"fmt"

	"github.com/cfpctl/cfpctl/internal/ui"
	"github.com/cfpctl/cfpctl/internal/validate"
	"github.com/spf13/cobra"
)

var validateCmd = &cobra.Command{
	Use:   "validate",
	Short: "Validate conference data files against schema rules",
	Long: `Check embedded YAML data files, or files in --data-dir, for correctness.

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

		dataDir, err := cmd.Flags().GetString("data-dir")
		if err != nil {
			return err
		}
		var result *validate.Result
		if cmd.Flags().Changed("data-dir") {
			if dataDir == "" {
				return fmt.Errorf("--data-dir must not be empty")
			}
			result = validate.ValidateDir(dataDir)
		} else {
			result = validate.ValidateAll()
		}
		fmt.Print(result.Summary())
		fmt.Println()

		if len(result.Errors) > 0 {
			return fmt.Errorf("data validation failed: %d error(s)", len(result.Errors))
		}
		return nil
	},
}

func init() {
	validateCmd.Flags().String("data-dir", "", "Validate root-level YAML files in this directory instead of embedded data")
	rootCmd.AddCommand(validateCmd)
}
