package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/cfpctl/cfpctl/internal/model"
	"github.com/cfpctl/cfpctl/internal/store"
	"github.com/cfpctl/cfpctl/internal/ui"
	"github.com/spf13/cobra"
)

// snapshotEntry stores a deadline snapshot for change detection.
type snapshotEntry struct {
	Slug     string `json:"slug"`
	Cycle    string `json:"cycle"`
	Track    string `json:"track"`
	Deadline string `json:"deadline"`
	Abstract string `json:"abstract,omitempty"`
}

var diffCmd = &cobra.Command{
	Use:   "diff",
	Short: "Detect deadline changes since last update",
	Long: `Compare current deadlines against the last saved snapshot.

Shows which conferences have changed their deadlines since you last ran
'cfpctl diff' or 'cfpctl update'. This helps catch silent deadline changes.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		s, err := store.New()
		if err != nil {
			return fmt.Errorf("loading data: %w", err)
		}

		configDir, err := os.UserConfigDir()
		if err != nil {
			configDir = "."
		}
		snapshotFile := filepath.Join(configDir, "cfpctl", "deadline_snapshot.json")

		now := time.Now()

		// Build current snapshot
		current := buildSnapshot(s, now)

		// Load previous snapshot
		previous, err := loadSnapshot(snapshotFile)
		if err != nil {
			// No previous snapshot — save current and report
			fmt.Println()
			fmt.Println(ui.TitleStyle.Render("📊 Deadline Diff"))
			fmt.Println()
			fmt.Println(ui.MutedStyle.Render("No previous snapshot found."))
			fmt.Println(ui.DimStyle.Render("Saving current deadlines as baseline."))
			fmt.Println()
			if err := saveSnapshot(snapshotFile, current); err != nil {
				return fmt.Errorf("saving snapshot: %w", err)
			}
			fmt.Printf("%s Baseline saved (%d deadlines)\n", ui.CheckStyle.Render("✓"), len(current))
			fmt.Println(ui.DimStyle.Render("Run 'cfpctl diff' again after updating to see changes."))
			fmt.Println()
			return nil
		}

		// Compare
		changes := compareSnapshots(previous, current)

		fmt.Println()
		fmt.Println(ui.TitleStyle.Render("📊 Deadline Changes Detected"))
		fmt.Println()

		if len(changes) == 0 {
			fmt.Println(ui.CheckStyle.Render("✓") + " No deadline changes since last check.")
			fmt.Println()
		} else {
			for _, ch := range changes {
				switch ch.kind {
				case "changed":
					fmt.Printf("  %s %s %s\n",
						ui.UrgentStyle.Render("⚠ CHANGED"),
						ui.HeaderStyle.Render(ch.name),
						ui.DimStyle.Render(fmt.Sprintf("(%s)", ch.track)))
					fmt.Printf("      %s → %s\n",
						ui.CrossStyle.Render(ch.oldDate),
						ui.CheckStyle.Render(ch.newDate))
				case "added":
					fmt.Printf("  %s %s %s\n",
						ui.SafeStyle.Render("+ NEW"),
						ui.HeaderStyle.Render(ch.name),
						ui.DimStyle.Render(fmt.Sprintf("(%s)", ch.track)))
					fmt.Printf("      Deadline: %s\n", ui.SafeStyle.Render(ch.newDate))
				case "removed":
					fmt.Printf("  %s %s %s\n",
						ui.SoonStyle.Render("- REMOVED"),
						ui.HeaderStyle.Render(ch.name),
						ui.DimStyle.Render(fmt.Sprintf("(%s)", ch.track)))
					fmt.Printf("      Was: %s\n", ui.DimStyle.Render(ch.oldDate))
				}
				fmt.Println()
			}
			fmt.Printf(ui.MutedStyle.Render("%d change(s) detected")+"\n", len(changes))
			fmt.Println()
		}

		// Save current as new baseline
		if err := saveSnapshot(snapshotFile, current); err != nil {
			return fmt.Errorf("saving snapshot: %w", err)
		}

		return nil
	},
}

func init() {
	rootCmd.AddCommand(diffCmd)
}

type change struct {
	kind    string // "changed", "added", "removed"
	name    string
	track   string
	oldDate string
	newDate string
}

func snapshotKey(e snapshotEntry) string {
	return e.Slug + "|" + e.Cycle + "|" + e.Track
}

func buildSnapshot(s *store.Store, now time.Time) []snapshotEntry {
	var entries []snapshotEntry
	for _, c := range s.All() {
		for _, fd := range c.AllFutureDeadlines(now) {
			e := snapshotEntry{
				Slug:     c.Slug,
				Cycle:    fd.CycleName,
				Track:    fd.TrackName,
				Deadline: fd.Track.Deadline.Format(time.RFC3339),
			}
			if fd.Track.Abstract != nil {
				e.Abstract = fd.Track.Abstract.Format(time.RFC3339)
			}
			entries = append(entries, e)
		}
	}
	return entries
}

func loadSnapshot(path string) ([]snapshotEntry, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var entries []snapshotEntry
	if err := json.Unmarshal(data, &entries); err != nil {
		return nil, err
	}
	return entries, nil
}

func saveSnapshot(path string, entries []snapshotEntry) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(entries, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0o644)
}

func compareSnapshots(prev, curr []snapshotEntry) []change {
	prevMap := make(map[string]snapshotEntry)
	for _, e := range prev {
		prevMap[snapshotKey(e)] = e
	}
	currMap := make(map[string]snapshotEntry)
	for _, e := range curr {
		currMap[snapshotKey(e)] = e
	}

	var changes []change

	// Check for changed and added
	for key, c := range currMap {
		displayName := c.Slug
		displayTrack := c.Track
		if displayTrack == "" {
			displayTrack = c.Cycle
		}
		if displayTrack == "" {
			displayTrack = "main"
		}

		if p, ok := prevMap[key]; ok {
			if p.Deadline != c.Deadline {
				changes = append(changes, change{
					kind:    "changed",
					name:    displayName,
					track:   displayTrack,
					oldDate: formatDate(p.Deadline),
					newDate: formatDate(c.Deadline),
				})
			}
		} else {
			changes = append(changes, change{
				kind:    "added",
				name:    displayName,
				track:   displayTrack,
				newDate: formatDate(c.Deadline),
			})
		}
	}

	// Check for removed
	for key, p := range prevMap {
		if _, ok := currMap[key]; !ok {
			displayName := p.Slug
			displayTrack := p.Track
			if displayTrack == "" {
				displayTrack = p.Cycle
			}
			if displayTrack == "" {
				displayTrack = "main"
			}
			changes = append(changes, change{
				kind:    "removed",
				name:    displayName,
				track:   displayTrack,
				oldDate: formatDate(p.Deadline),
			})
		}
	}

	return changes
}

func formatDate(iso string) string {
	t, err := time.Parse(time.RFC3339, iso)
	if err != nil {
		return iso
	}
	return t.Format("2006-01-02")
}

// Ensure model is used (for AllFutureDeadlines)
var _ = (*model.Conference)(nil).AllFutureDeadlines
