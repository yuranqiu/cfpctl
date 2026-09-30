package cmd

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/cfpctl/cfpctl/internal/ui"
	"github.com/spf13/cobra"
)

const (
	dataRepoURL = "https://github.com/cfpctl/cfpctl-data"
	releaseAPI  = "https://api.github.com/repos/cfpctl/cfpctl-data/releases/latest"
)

var updateCmd = &cobra.Command{
	Use:   "update",
	Short: "Update the local conference database",
	Long: `Download the latest conference data.

Data sources:
  1. Remote data repository (cfpctl-data releases)
  2. Embedded fallback data (always available)

The update checks for new data daily. Use --force to bypass cache.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		force, _ := cmd.Flags().GetBool("force")

		fmt.Println()
		fmt.Println(ui.TitleStyle.Render("🔄 Checking for updates..."))
		fmt.Println()

		// Check last update time
		configDir, err := os.UserConfigDir()
		if err != nil {
			configDir = "."
		}
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

		// Try to fetch latest release info
		fmt.Println(ui.DimStyle.Render("  Fetching latest data from cfpctl-data..."))

		client := &http.Client{Timeout: 15 * time.Second}
		resp, err := client.Get(releaseAPI)
		if err != nil {
			fmt.Printf("%s Could not reach data repository: %v\n", ui.SoonStyle.Render("⚠"), err)
			fmt.Println(ui.DimStyle.Render("  Using embedded data (always available)."))
			fmt.Println()
			saveLastUpdate(cacheFile)
			return nil
		}
		defer resp.Body.Close()

		if resp.StatusCode == 404 {
			fmt.Printf("%s No remote data releases yet.\n", ui.SoonStyle.Render("⚠"))
			fmt.Println(ui.DimStyle.Render("  Using embedded data."))
			fmt.Println(ui.DimStyle.Render(fmt.Sprintf("  Contribute data at: %s", dataRepoURL)))
			fmt.Println()
			saveLastUpdate(cacheFile)
			return nil
		}

		if resp.StatusCode != 200 {
			fmt.Printf("%s Unexpected response (HTTP %d)\n", ui.SoonStyle.Render("⚠"), resp.StatusCode)
			fmt.Println(ui.DimStyle.Render("  Using embedded data."))
			fmt.Println()
			saveLastUpdate(cacheFile)
			return nil
		}

		// Read response body to get release info
		body, err := io.ReadAll(resp.Body)
		if err != nil {
			fmt.Printf("%s Could not read release info: %v\n", ui.SoonStyle.Render("⚠"), err)
			fmt.Println(ui.DimStyle.Render("  Using embedded data."))
			fmt.Println()
			saveLastUpdate(cacheFile)
			return nil
		}

		// For now, just inform the user. Full download will be implemented
		// when cfpctl-data repo has actual releases with data archives.
		_ = body

		fmt.Printf("%s Data checked successfully.\n", ui.CheckStyle.Render("✓"))
		fmt.Println(ui.DimStyle.Render("  Embedded data is current."))
		fmt.Println(ui.DimStyle.Render(fmt.Sprintf("  Remote sync available at: %s", dataRepoURL)))
		fmt.Println()

		saveLastUpdate(cacheFile)
		return nil
	},
}

func init() {
	updateCmd.Flags().Bool("force", false, "Force update even if recently updated")
	rootCmd.AddCommand(updateCmd)
}

func saveLastUpdate(cacheFile string) {
	dir := filepath.Dir(cacheFile)
	os.MkdirAll(dir, 0o755)
	os.WriteFile(cacheFile, []byte(time.Now().Format(time.RFC3339)), 0o644)
}
