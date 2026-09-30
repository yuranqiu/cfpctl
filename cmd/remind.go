package cmd

import (
	"fmt"
	"os"
	"strings"
	"text/tabwriter"
	"time"

	"github.com/cfpctl/cfpctl/internal/remind"
	"github.com/cfpctl/cfpctl/internal/store"
	"github.com/cfpctl/cfpctl/internal/ui"
	"github.com/spf13/cobra"
)

var remindCmd = &cobra.Command{
	Use:   "remind",
	Short: "Manage deadline reminders",
	Long: `Configure and view deadline reminders for watched conferences.

Examples:
  cfpctl remind set iclr --before 30d,14d,7d,1d
  cfpctl remind remove iclr
  cfpctl remind list
  cfpctl remind check`,
}

var remindSetCmd = &cobra.Command{
	Use:   "set <conference>",
	Short: "Set reminder intervals for a conference",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		before, _ := cmd.Flags().GetString("before")
		if before == "" {
			return fmt.Errorf("--before is required (e.g., --before 30d,14d,7d,1d)")
		}

		s, err := store.New()
		if err != nil {
			return fmt.Errorf("loading data: %w", err)
		}

		conf := s.GetBySlug(args[0])
		if conf == nil {
			return fmt.Errorf("conference not found: %s", args[0])
		}

		intervals := strings.Split(before, ",")
		for i := range intervals {
			intervals[i] = strings.TrimSpace(intervals[i])
		}

		cfg, err := remind.Load()
		if err != nil {
			return fmt.Errorf("loading reminders: %w", err)
		}

		cfg.Set(conf.Slug, intervals)
		if err := cfg.Save(); err != nil {
			return fmt.Errorf("saving reminders: %w", err)
		}

		fmt.Println()
		fmt.Printf("%s Reminders set for %s: %s\n",
			ui.CheckStyle.Render("✓"),
			ui.HeaderStyle.Render(conf.Name),
			ui.DimStyle.Render(strings.Join(intervals, ", ")))
		fmt.Println()
		return nil
	},
}

var remindRemoveCmd = &cobra.Command{
	Use:   "remove <conference>",
	Short: "Remove reminders for a conference",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		cfg, err := remind.Load()
		if err != nil {
			return fmt.Errorf("loading reminders: %w", err)
		}

		cfg.Remove(args[0])
		if err := cfg.Save(); err != nil {
			return fmt.Errorf("saving reminders: %w", err)
		}

		fmt.Println()
		fmt.Printf("%s Reminders removed for %s\n", ui.CrossStyle.Render("✗"), ui.DimStyle.Render(args[0]))
		fmt.Println()
		return nil
	},
}

var remindListCmd = &cobra.Command{
	Use:   "list",
	Short: "List all configured reminders",
	RunE: func(cmd *cobra.Command, args []string) error {
		cfg, err := remind.Load()
		if err != nil {
			return fmt.Errorf("loading reminders: %w", err)
		}

		if len(cfg.Entries) == 0 {
			fmt.Println()
			fmt.Println(ui.MutedStyle.Render("No reminders configured."))
			fmt.Println(ui.DimStyle.Render("Use: cfpctl remind set <conference> --before 30d,14d,7d,1d"))
			fmt.Println()
			return nil
		}

		s, err := store.New()
		if err != nil {
			return fmt.Errorf("loading data: %w", err)
		}

		fmt.Println()
		fmt.Println(ui.TitleStyle.Render("⏰ Configured Reminders"))
		fmt.Println()

		w := tabwriter.NewWriter(os.Stdout, 0, 4, 2, ' ', 0)
		fmt.Fprintln(w, "CONFERENCE\tINTERVALS")
		for _, e := range cfg.Entries {
			name := e.Slug
			if conf := s.GetBySlug(e.Slug); conf != nil {
				name = conf.Name
			}
			fmt.Fprintf(w, "%s\t%s\n", name, strings.Join(e.Before, ", "))
		}
		w.Flush()
		fmt.Println()
		return nil
	},
}

var remindCheckCmd = &cobra.Command{
	Use:   "check",
	Short: "Show upcoming reminders that are due soon",
	RunE: func(cmd *cobra.Command, args []string) error {
		cfg, err := remind.Load()
		if err != nil {
			return fmt.Errorf("loading reminders: %w", err)
		}

		if len(cfg.Entries) == 0 {
			fmt.Println(ui.MutedStyle.Render("No reminders configured."))
			return nil
		}

		s, err := store.New()
		if err != nil {
			return fmt.Errorf("loading data: %w", err)
		}

		now := time.Now()
		type reminderHit struct {
			ConfName string
			Event    string
			Date     time.Time
			In       string
			Urgent   bool
		}

		var hits []reminderHit

		for _, entry := range cfg.Entries {
			conf := s.GetBySlug(entry.Slug)
			if conf == nil {
				continue
			}

			durations := remind.ParseBefore(entry.Before)

			for _, fd := range conf.AllFutureDeadlines(now) {
				label := fd.CycleName
				if label == "" {
					label = "Submission"
				}
				if fd.TrackName != "" {
					label = fmt.Sprintf("%s [%s]", label, fd.TrackName)
				}

				for _, dur := range durations {
					reminderTime := fd.Track.Deadline.Add(-dur)
					diff := reminderTime.Sub(now)

					if diff >= -3*24*time.Hour && diff <= 3*24*time.Hour {
						inStr := "today"
						urgent := true
						if diff > 24*time.Hour {
							inStr = fmt.Sprintf("in %dd", int(diff.Hours()/24))
							urgent = false
						} else if diff < -24*time.Hour {
							inStr = fmt.Sprintf("%dd ago", int(-diff.Hours()/24))
							urgent = true
						}

						hits = append(hits, reminderHit{
							ConfName: conf.Name,
							Event:    fmt.Sprintf("%s deadline", label),
							Date:     fd.Track.Deadline,
							In:       inStr,
							Urgent:   urgent,
						})
					}
				}
			}
		}

		fmt.Println()
		fmt.Println(ui.TitleStyle.Render("🔔 Reminder Check"))
		fmt.Println()

		if len(hits) == 0 {
			fmt.Println(ui.SafeStyle.Render("✓") + " No reminders due right now.")
			fmt.Println()
			return nil
		}

		for _, h := range hits {
			icon := "⚠️"
			style := ui.SoonStyle
			if h.Urgent {
				icon = "🚨"
				style = ui.UrgentStyle
			}
			fmt.Printf("  %s %s — %s (%s)\n",
				icon,
				style.Render(h.ConfName),
				h.Event,
				h.In,
			)
		}
		fmt.Println()
		return nil
	},
}

func init() {
	remindSetCmd.Flags().String("before", "", "Reminder intervals (e.g., 30d,14d,7d,1d)")

	remindCmd.AddCommand(remindSetCmd)
	remindCmd.AddCommand(remindRemoveCmd)
	remindCmd.AddCommand(remindListCmd)
	remindCmd.AddCommand(remindCheckCmd)
	rootCmd.AddCommand(remindCmd)
}
