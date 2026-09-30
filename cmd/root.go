package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

var rootCmd = &cobra.Command{
	Use:   "cfpctl",
	Short: "Conference deadlines, without leaving your terminal.",
	Long: `cfpctl - A terminal-first conference deadline tracker for researchers.

Track deadlines, search conferences, manage your watchlist,
and plan your submission strategy — all from the command line.`,
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
