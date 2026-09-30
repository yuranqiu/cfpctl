package cmd

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/cfpctl/cfpctl/internal/ui"
	"github.com/spf13/cobra"
)

const (
	dataRepoURL = "https://github.com/yuranqiu/cfpctl-data"
	rawBaseURL  = "https://raw.githubusercontent.com/yuranqiu/cfpctl-data/main"
)

var dataFiles = []string{
	"ai.yaml", "graphics.yaml", "theory.yaml", "database.yaml",
	"systems.yaml", "hci.yaml", "interdisciplinary.yaml",
	"network.yaml", "security.yaml", "software.yaml",
}

var updateCmd = &cobra.Command{
	Use:   "update",
	Short: "Update the local conference database from cfpctl-data",
	Long: fmt.Sprintf(`Download the latest conference data from %s.

Fetches YAML data files from the remote repository and caches them locally.
The embedded data is always available as fallback.`, dataRepoURL),
	RunE: func(cmd *cobra.Command, args []string) error {
		force, _ := cmd.Flags().GetBool("force")

		fmt.Println()
		fmt.Println(ui.TitleStyle.Render("🔄 Updating conference data..."))
		fmt.Println()

		configDir, err := os.UserConfigDir()
		if err != nil {
			configDir = "."
		}
		cacheDir := filepath.Join(configDir, "cfpctl", "data")
		cacheFile := filepath.Join(configDir, "cfpctl", "last_update")

		if !force {
			if data, err := os.ReadFile(cacheFile); err == nil {
				lastUpdate, parseErr := time.Parse(time.RFC3339, string(data))
				if parseErr == nil && time.Since(lastUpdate) < 24*time.Hour {
					ago := time.Since(lastUpdate).Round(time.Hour)
					fmt.Printf("%s Data is up to date (last updated %s ago)\n",
						ui.CheckStyle.Render("✓"), ago)
					fmt.Println(ui.DimStyle.Render("  Use --force to update anyway."))
					fmt.Println()
					return nil
				}
			}
		}

		if err := os.MkdirAll(cacheDir, 0o755); err != nil {
			return fmt.Errorf("creating cache dir: %w", err)
		}

		client := &http.Client{Timeout: 30 * time.Second}
		updated := 0
		failed := 0

		for _, filename := range dataFiles {
			url := fmt.Sprintf("%s/%s", rawBaseURL, filename)
			fmt.Printf("  Fetching %-30s ", filename)

			resp, err := client.Get(url)
			if err != nil {
				fmt.Println(ui.CrossStyle.Render("✗") + " " + err.Error())
				failed++
				continue
			}

			if resp.StatusCode == 404 {
				fmt.Println(ui.DimStyle.Render("skip"))
				resp.Body.Close()
				continue
			}
			if resp.StatusCode != 200 {
				fmt.Printf(ui.CrossStyle.Render("✗ HTTP %d")+"\n", resp.StatusCode)
				resp.Body.Close()
				failed++
				continue
			}

			body, err := io.ReadAll(resp.Body)
			resp.Body.Close()
			if err != nil {
				fmt.Println(ui.CrossStyle.Render("✗ read error"))
				failed++
				continue
			}

			outPath := filepath.Join(cacheDir, filename)
			if err := os.WriteFile(outPath, body, 0o644); err != nil {
				fmt.Println(ui.CrossStyle.Render("✗ write error"))
				failed++
				continue
			}

			count := strings.Count(string(body), "- name:")
			fmt.Printf(ui.CheckStyle.Render("✓")+" (%d conferences)\n", count)
			updated++
		}

		fmt.Println()
		if updated > 0 {
			fmt.Printf("%s Updated %d data files\n", ui.CheckStyle.Render("✓"), updated)
			fmt.Println(ui.DimStyle.Render(fmt.Sprintf("  Cached at: %s", cacheDir)))
		}
		if failed > 0 {
			fmt.Printf("%s Failed: %d files\n", ui.SoonStyle.Render("⚠"), failed)
		}
		fmt.Println()

		os.MkdirAll(filepath.Dir(cacheFile), 0o755)
		os.WriteFile(cacheFile, []byte(time.Now().Format(time.RFC3339)), 0o644)
		return nil
	},
}

func init() {
	updateCmd.Flags().Bool("force", false, "Force update even if recently updated")
	rootCmd.AddCommand(updateCmd)
}
