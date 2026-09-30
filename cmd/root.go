package cmd

import (
	"fmt"
	"os"

	"github.com/cfpctl/cfpctl/internal/tui"
	"github.com/spf13/cobra"
)

var rootCmd = &cobra.Command{
	Use:   "cfpctl",
	Short: "Conference deadlines, without leaving your terminal.",
	Long: `cfpctl - A terminal-first conference deadline tracker for researchers.

Track deadlines, search conferences, manage your watchlist,
and plan your submission strategy — all from the command line.

Run without arguments to launch the interactive TUI.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		// If no subcommand given, launch TUI
		if len(args) == 0 && !cmd.Flags().Changed("help") {
			return tui.Run()
		}
		return nil
	},
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
