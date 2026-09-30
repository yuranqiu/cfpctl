package cmd

import (
	"fmt"

	"github.com/cfpctl/cfpctl/internal/notify"
	"github.com/cfpctl/cfpctl/internal/ui"
	"github.com/spf13/cobra"
)

var notifyCmd = &cobra.Command{
	Use:   "notify",
	Short: "Manage notification channels (Telegram, Webhook)",
	Long: `Configure and test notification channels for deadline reminders.

Supported channels:
  - Telegram: Bot API notifications
  - Webhook:  Generic HTTP POST (Slack, Discord, custom)

Examples:
  cfpctl notify setup telegram --token <BOT_TOKEN> --chat-id <CHAT_ID>
  cfpctl notify setup webhook --url https://hooks.slack.com/...
  cfpctl notify test
  cfpctl notify status`,
}

var notifySetupCmd = &cobra.Command{
	Use:   "setup <channel>",
	Short: "Configure a notification channel",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		channel := args[0]
		cfg, err := notify.Load()
		if err != nil {
			return fmt.Errorf("loading config: %w", err)
		}

		switch channel {
		case "telegram":
			token, _ := cmd.Flags().GetString("token")
			chatID, _ := cmd.Flags().GetString("chat-id")
			if token == "" || chatID == "" {
				return fmt.Errorf("--token and --chat-id are required")
			}
			cfg.Telegram = &notify.TelegramConfig{
				BotToken: token,
				ChatID:   chatID,
				Enabled:  true,
			}
			fmt.Printf("%s Telegram configured (chat: %s)\n", ui.CheckStyle.Render("✓"), chatID)

		case "webhook":
			url, _ := cmd.Flags().GetString("url")
			if url == "" {
				return fmt.Errorf("--url is required")
			}
			cfg.Webhook = &notify.WebhookConfig{
				URL:     url,
				Enabled: true,
			}
			fmt.Printf("%s Webhook configured: %s\n", ui.CheckStyle.Render("✓"), url)

		default:
			return fmt.Errorf("unknown channel: %s (supported: telegram, webhook)", channel)
		}

		if err := cfg.Save(); err != nil {
			return fmt.Errorf("saving config: %w", err)
		}
		return nil
	},
}

var notifyTestCmd = &cobra.Command{
	Use:   "test",
	Short: "Send a test notification",
	RunE: func(cmd *cobra.Command, args []string) error {
		cfg, err := notify.Load()
		if err != nil {
			return fmt.Errorf("loading config: %w", err)
		}

		msg := notify.Message{
			Title:      "🔔 cfpctl Test Notification",
			Conference: "Test Conference",
			Event:      "Paper Submission",
			DaysLeft:   7,
			CCF:        "A",
		}

		errs := cfg.Send(msg)
		if len(errs) == 0 {
			fmt.Println(ui.CheckStyle.Render("✓") + " Test notification sent successfully!")
		} else {
			for _, e := range errs {
				fmt.Printf("%s %v\n", ui.CrossStyle.Render("✗"), e)
			}
		}
		return nil
	},
}

var notifyStatusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show notification configuration status",
	RunE: func(cmd *cobra.Command, args []string) error {
		cfg, err := notify.Load()
		if err != nil {
			return fmt.Errorf("loading config: %w", err)
		}

		fmt.Println()
		fmt.Println(ui.TitleStyle.Render("🔔 Notification Status"))
		fmt.Println()

		if cfg.Telegram != nil && cfg.Telegram.Enabled {
			fmt.Printf("  %s Telegram: %s (chat: %s)\n",
				ui.CheckStyle.Render("✓"), "enabled", cfg.Telegram.ChatID)
		} else {
			fmt.Printf("  %s Telegram: not configured\n", ui.DimStyle.Render("○"))
		}

		if cfg.Webhook != nil && cfg.Webhook.Enabled {
			fmt.Printf("  %s Webhook:  %s (%s)\n",
				ui.CheckStyle.Render("✓"), "enabled", cfg.Webhook.URL)
		} else {
			fmt.Printf("  %s Webhook:  not configured\n", ui.DimStyle.Render("○"))
		}

		fmt.Println()
		fmt.Println(ui.DimStyle.Render("  Setup: cfpctl notify setup telegram --token <TOKEN> --chat-id <ID>"))
		fmt.Println(ui.DimStyle.Render("  Setup: cfpctl notify setup webhook --url <URL>"))
		fmt.Println(ui.DimStyle.Render("  Test:  cfpctl notify test"))
		fmt.Println()
		return nil
	},
}

func init() {
	notifySetupCmd.Flags().String("token", "", "Telegram bot token")
	notifySetupCmd.Flags().String("chat-id", "", "Telegram chat ID")
	notifySetupCmd.Flags().String("url", "", "Webhook URL")

	notifyCmd.AddCommand(notifySetupCmd)
	notifyCmd.AddCommand(notifyTestCmd)
	notifyCmd.AddCommand(notifyStatusCmd)
	rootCmd.AddCommand(notifyCmd)
}
