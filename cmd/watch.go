package cmd

import (
	"fmt"

	"github.com/cfpctl/cfpctl/internal/store"
	"github.com/cfpctl/cfpctl/internal/ui"
	"github.com/cfpctl/cfpctl/internal/watchlist"
	"github.com/spf13/cobra"
)

var watchCmd = &cobra.Command{
	Use:   "watch <conference>",
	Short: "Add a conference to your watchlist",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		s, err := store.New()
		if err != nil {
			return fmt.Errorf("loading data: %w", err)
		}

		conf := s.GetBySlug(args[0])
		if conf == nil {
			return fmt.Errorf("conference not found: %s\nUse 'cfpctl search %s' to find the correct slug", args[0], args[0])
		}

		wl, err := watchlist.Load()
		if err != nil {
			return fmt.Errorf("loading watchlist: %w", err)
		}

		wl.Add(conf.Slug)
		if err := wl.Save(); err != nil {
			return fmt.Errorf("saving watchlist: %w", err)
		}

		fmt.Println()
		fmt.Printf("%s Watching %s (%s)\n", ui.CheckStyle.Render("✓"), ui.HeaderStyle.Render(conf.Name), ui.DimStyle.Render(conf.Slug))
		fmt.Println()
		return nil
	},
}

var unwatchCmd = &cobra.Command{
	Use:   "unwatch <conference>",
	Short: "Remove a conference from your watchlist",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		wl, err := watchlist.Load()
		if err != nil {
			return fmt.Errorf("loading watchlist: %w", err)
		}

		wl.Remove(args[0])
		if err := wl.Save(); err != nil {
			return fmt.Errorf("saving watchlist: %w", err)
		}

		fmt.Println()
		fmt.Printf("%s Unwatched %s\n", ui.CrossStyle.Render("✗"), ui.DimStyle.Render(args[0]))
		fmt.Println()
		return nil
	},
}

func init() {
	rootCmd.AddCommand(watchCmd)
	rootCmd.AddCommand(unwatchCmd)
}
