package cmd

import (
	"fmt"

	"github.com/cfpctl/cfpctl/internal/ui"
	"github.com/spf13/cobra"
)

// Register common aliases as hidden subcommands that delegate to the real command.
func init() {
	// up -> upcoming
	upCmd := &cobra.Command{
		Use:    "up",
		Short:  "Alias for 'upcoming'",
		Hidden: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			return upcomingCmd.RunE(cmd, args)
		},
	}
	upCmd.Flags().String("ccf", "", "Filter by CCF rank")
	upCmd.Flags().String("field", "", "Filter by field")
	upCmd.Flags().String("within", "", "Time window")
	rootCmd.AddCommand(upCmd)

	// tl -> timeline
	tlCmd := &cobra.Command{
		Use:    "tl",
		Short:  "Alias for 'timeline'",
		Hidden: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			return timelineCmd.RunE(cmd, args)
		},
	}
	tlCmd.Flags().String("ccf", "", "Filter by CCF rank")
	tlCmd.Flags().String("field", "", "Filter by field")
	tlCmd.Flags().String("within", "", "Time window")
	rootCmd.AddCommand(tlCmd)

	// s -> search
	sCmd := &cobra.Command{
		Use:    "s <keyword>",
		Short:  "Alias for 'search'",
		Hidden: true,
		Args:   cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return searchCmd.RunE(cmd, args)
		},
	}
	rootCmd.AddCommand(sCmd)

	// w -> watch
	wCmd := &cobra.Command{
		Use:    "w <conference>",
		Short:  "Alias for 'watch'",
		Hidden: true,
		Args:   cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return watchCmd.RunE(cmd, args)
		},
	}
	rootCmd.AddCommand(wCmd)

	// Shell completion help command
	completionHelpCmd := &cobra.Command{
		Use:   "completion-help",
		Short: "Show shell completion setup instructions",
		Run: func(cmd *cobra.Command, args []string) {
			fmt.Println()
			fmt.Println(ui.TitleStyle.Render("🐚 Shell Completion Setup"))
			fmt.Println()
			fmt.Println(ui.HeaderStyle.Render("Bash:"))
			fmt.Println("  cfpctl completion bash > /etc/bash_completion.d/cfpctl")
			fmt.Println("  # or add to ~/.bashrc:")
			fmt.Println("  source <(cfpctl completion bash)")
			fmt.Println()
			fmt.Println(ui.HeaderStyle.Render("Zsh:"))
			fmt.Println("  cfpctl completion zsh > \"${fpath[1]}/_cfpctl\"")
			fmt.Println("  # or add to ~/.zshrc:")
			fmt.Println("  source <(cfpctl completion zsh)")
			fmt.Println()
			fmt.Println(ui.HeaderStyle.Render("Fish:"))
			fmt.Println("  cfpctl completion fish > ~/.config/fish/completions/cfpctl.fish")
			fmt.Println("  # or:")
			fmt.Println("  cfpctl completion fish | source")
			fmt.Println()
			fmt.Println(ui.HeaderStyle.Render("PowerShell:"))
			fmt.Println("  cfpctl completion powershell | Out-String | Invoke-Expression")
			fmt.Println("  # To persist, add to your profile:")
			fmt.Println("  cfpctl completion powershell >> $PROFILE")
			fmt.Println()
			fmt.Println(ui.DimStyle.Render("Aliases: up=upcoming, tl=timeline, s=search, w=watch, wl=watchlist"))
			fmt.Println()
		},
	}
	rootCmd.AddCommand(completionHelpCmd)
}
