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

var compareCmd = &cobra.Command{
	Use:   "compare <conf1> <conf2> [conf3...]",
	Short: "Compare multiple conferences side by side",
	Long: `Display a side-by-side comparison of conferences including deadlines,
acceptance rates, locations, and other key information.

Examples:
  cfpctl compare iclr neurips icml
  cfpctl compare usenix-security ccs ndss`,
	Args: cobra.MinimumNArgs(2),
	RunE: func(cmd *cobra.Command, args []string) error {
		s, err := store.New()
		if err != nil {
			return fmt.Errorf("loading data: %w", err)
		}

		now := time.Now()
		var confs []confData
		for _, arg := range args {
			c := s.GetBySlug(arg)
			if c == nil {
				fmt.Printf("%s Conference not found: %s\n", ui.CrossStyle.Render("✗"), arg)
				continue
			}
			cd := confData{conf: c}
			cd.next = c.NextDeadline(now)
			confs = append(confs, cd)
		}

		if len(confs) < 2 {
			return fmt.Errorf("need at least 2 valid conferences to compare")
		}

		fmt.Println()
		fmt.Println(ui.TitleStyle.Render("📊 Conference Comparison"))
		fmt.Println()

		// Calculate column width
		colWidth := 24
		for _, cd := range confs {
			nameLen := len(cd.conf.Name) + 2
			if nameLen > colWidth {
				colWidth = nameLen
			}
		}
		if colWidth > 30 {
			colWidth = 30
		}

		// Header row
		header := ui.PadRight("", 16)
		for _, cd := range confs {
			header += "  " + ui.HeaderStyle.Render(ui.PadRight(cd.conf.Name, colWidth))
		}
		fmt.Println(header)
		fmt.Println(ui.SeparatorLine(16 + (colWidth+2)*len(confs)))

		// Rows
		printCompareRow("CCF", confs, colWidth, func(cd confData) string {
			return ui.StyleCCF(cd.conf.Rank.CCF)
		})
		printCompareRow("CORE", confs, colWidth, func(cd confData) string {
			return cd.conf.Rank.CORE
		})
		printCompareRow("Field", confs, colWidth, func(cd confData) string {
			return strings.Join(cd.conf.Fields, ", ")
		})
		printCompareRow("Location", confs, colWidth, func(cd confData) string {
			loc := cd.conf.Location
			if loc == "" || loc == "TBD" {
				return ui.DimStyle.Render("TBD")
			}
			if len(loc) > colWidth {
				return loc[:colWidth-3] + "..."
			}
			return loc
		})
		printCompareRow("Acceptance", confs, colWidth, func(cd confData) string {
			if cd.conf.AcceptRate != "" {
				return cd.conf.AcceptRate
			}
			return ui.DimStyle.Render("-")
		})
		printCompareRow("Verified", confs, colWidth, func(cd confData) string {
			if cd.conf.Verified {
				return ui.CheckStyle.Render("✓ Yes")
			}
			return ui.SoonStyle.Render("⚠ No")
		})
		printCompareRow("Rolling Review", confs, colWidth, func(cd confData) string {
			if cd.conf.RollingReview != nil {
				return ui.SoonStyle.Render("🔄 " + cd.conf.RollingReview.Name)
			}
			return ui.DimStyle.Render("-")
		})

		fmt.Println(ui.SeparatorLine(16 + (colWidth+2)*len(confs)))

		// Next deadline
		printCompareRow("Next Deadline", confs, colWidth, func(cd confData) string {
			if cd.next != nil {
				days := model.DaysRemaining(cd.next.Deadline, now)
				return fmt.Sprintf("%s (%s)", cd.next.Deadline.Format("2006-01-02"), ui.StyleDaysLeft(days))
			}
			return ui.DimStyle.Render("-")
		})
		printCompareRow("Abstract", confs, colWidth, func(cd confData) string {
			if cd.next != nil && cd.next.Abstract != nil {
				return cd.next.Abstract.Format("2006-01-02")
			}
			return ui.DimStyle.Render("-")
		})
		printCompareRow("Notification", confs, colWidth, func(cd confData) string {
			if cd.next != nil && cd.next.Notification != nil {
				return cd.next.Notification.Format("2006-01-02")
			}
			return ui.DimStyle.Render("-")
		})
		printCompareRow("Homepage", confs, colWidth, func(cd confData) string {
			url := cd.conf.Homepage
			if len(url) > colWidth {
				url = url[:colWidth-3] + "..."
			}
			return ui.LinkStyle.Render(url)
		})

		fmt.Println()
		return nil
	},
}

func init() {
	rootCmd.AddCommand(compareCmd)
}

func printCompareRow(label string, confs []confData, colWidth int, getValue func(confData) string) {
	row := ui.PadRight(label+":", 16)
	for _, cd := range confs {
		val := getValue(cd)
		row += "  " + ui.PadRight(val, colWidth)
	}
	fmt.Println(row)
}

type confData struct {
	conf *model.Conference
	next *model.ParsedTrack
}
