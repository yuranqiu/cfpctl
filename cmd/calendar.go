package cmd

import (
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/cfpctl/cfpctl/internal/calendar"
	"github.com/cfpctl/cfpctl/internal/store"
	"github.com/cfpctl/cfpctl/internal/ui"
	"github.com/cfpctl/cfpctl/internal/watchlist"
	"github.com/spf13/cobra"
)

var calendarCmd = &cobra.Command{
	Use:   "calendar",
	Short: "Export deadlines to iCalendar (.ics) format",
	Long: `Generate .ics calendar files for import into Apple Calendar, Google Calendar, Outlook, etc.

Examples:
  cfpctl calendar export                    # Export watchlist deadlines
  cfpctl calendar export --all              # Export all conferences
  cfpctl calendar export --field ai         # Export AI conferences
  cfpctl calendar export -o my.ics          # Custom output file
  cfpctl calendar export --remind 30d,14d,7d,1d  # Custom reminders`,
}

var calendarExportCmd = &cobra.Command{
	Use:   "export",
	Short: "Export deadlines to an .ics file",
	RunE: func(cmd *cobra.Command, args []string) error {
		output, _ := cmd.Flags().GetString("output")
		all, _ := cmd.Flags().GetBool("all")
		ccf, _ := cmd.Flags().GetString("ccf")
		field, _ := cmd.Flags().GetString("field")
		remindStr, _ := cmd.Flags().GetString("remind")

		// Parse reminder durations
		alarms := parseReminders(remindStr)

		s, err := store.New()
		if err != nil {
			return fmt.Errorf("loading data: %w", err)
		}

		now := time.Now()
		var allEvents []calendar.Event

		if all || ccf != "" || field != "" {
			// Filter mode
			var fields []string
			if field != "" {
				fields = splitFields(field)
			}
			confs := s.Filter(ccf, fields)
			for _, c := range confs {
				allEvents = append(allEvents, calendar.ConferenceToEvents(&c, now, alarms)...)
			}
		} else {
			// Watchlist mode (default)
			wl, err := watchlist.Load()
			if err != nil {
				return fmt.Errorf("loading watchlist: %w", err)
			}
			if len(wl.Entries) == 0 {
				fmt.Println(ui.MutedStyle.Render("Watchlist is empty. Use --all to export all conferences."))
				fmt.Println(ui.DimStyle.Render("Or add conferences with: cfpctl watch <conference>"))
				return nil
			}
			for _, entry := range wl.Entries {
				conf := s.GetBySlug(entry.Slug)
				if conf == nil {
					continue
				}
				allEvents = append(allEvents, calendar.ConferenceToEvents(conf, now, alarms)...)
			}
		}

		if len(allEvents) == 0 {
			fmt.Println(ui.CrossStyle.Render("✗") + " No upcoming events to export.")
			return nil
		}

		calName := "cfpctl Deadlines"
		if field != "" {
			calName = fmt.Sprintf("cfpctl — %s", field)
		}

		ics := calendar.GenerateICS(allEvents, calName)

		if output == "" {
			output = "deadlines.ics"
		}

		if err := os.WriteFile(output, []byte(ics), 0o644); err != nil {
			return fmt.Errorf("writing %s: %w", output, err)
		}

		fmt.Println()
		fmt.Printf("%s Exported %d events to %s\n", ui.CheckStyle.Render("✓"), len(allEvents), ui.HeaderStyle.Render(output))
		fmt.Println()
		fmt.Println(ui.DimStyle.Render("Import this file into your calendar app:"))
		fmt.Println(ui.DimStyle.Render("  • macOS:    open " + output))
		fmt.Println(ui.DimStyle.Render("  • Linux:    xdg-open " + output))
		fmt.Println(ui.DimStyle.Render("  • Windows:  start " + output))
		fmt.Println(ui.DimStyle.Render("  • Google:   Settings → Import & Export → Upload .ics"))
		fmt.Println()

		return nil
	},
}

func init() {
	calendarExportCmd.Flags().StringP("output", "o", "", "Output file path (default: deadlines.ics)")
	calendarExportCmd.Flags().Bool("all", false, "Export all conferences (not just watchlist)")
	calendarExportCmd.Flags().String("ccf", "", "Filter by CCF rank")
	calendarExportCmd.Flags().String("field", "", "Filter by field (comma-separated)")
	calendarExportCmd.Flags().String("remind", "30d,14d,7d,1d", "Reminder intervals before deadline")

	calendarCmd.AddCommand(calendarExportCmd)
	rootCmd.AddCommand(calendarCmd)
}

func parseReminders(s string) []time.Duration {
	if s == "" {
		return nil
	}
	parts := strings.Split(s, ",")
	var durations []time.Duration
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p == "" {
			continue
		}
		days := parseWithin(p)
		if days > 0 {
			durations = append(durations, -time.Duration(days)*24*time.Hour)
		}
	}
	return durations
}
