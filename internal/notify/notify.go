package notify

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"gopkg.in/yaml.v3"
)

// Config holds notification settings.
type Config struct {
	path     string
	Telegram *TelegramConfig `yaml:"telegram,omitempty"`
	Webhook  *WebhookConfig  `yaml:"webhook,omitempty"`
}

// TelegramConfig for Telegram Bot API notifications.
type TelegramConfig struct {
	BotToken string `yaml:"bot_token"`
	ChatID   string `yaml:"chat_id"`
	Enabled  bool   `yaml:"enabled"`
}

// WebhookConfig for generic webhook notifications.
type WebhookConfig struct {
	URL     string            `yaml:"url"`
	Headers map[string]string `yaml:"headers,omitempty"`
	Enabled bool              `yaml:"enabled"`
}

// Message represents a notification message.
type Message struct {
	Title       string    `json:"title"`
	Conference  string    `json:"conference"`
	Event       string    `json:"event"`
	Deadline    time.Time `json:"deadline"`
	DaysLeft    int       `json:"days_left"`
	URL         string    `json:"url,omitempty"`
	CCF         string    `json:"ccf,omitempty"`
}

func configDir() (string, error) {
	dir, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, "cfpctl"), nil
}

// Load reads notification config from disk.
func Load() (*Config, error) {
	dir, err := configDir()
	if err != nil {
		return &Config{}, nil
	}
	cfg := &Config{path: filepath.Join(dir, "notify.yaml")}
	data, err := os.ReadFile(cfg.path)
	if err != nil {
		if os.IsNotExist(err) {
			return cfg, nil
		}
		return cfg, err
	}
	if err := yaml.Unmarshal(data, cfg); err != nil {
		return cfg, err
	}
	return cfg, nil
}

// Save persists notification config to disk.
func (cfg *Config) Save() error {
	dir := filepath.Dir(cfg.path)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	data, err := yaml.Marshal(cfg)
	if err != nil {
		return err
	}
	return os.WriteFile(cfg.path, data, 0o644)
}

// Send dispatches a notification through all enabled channels.
func (cfg *Config) Send(msg Message) []error {
	var errs []error

	if cfg.Telegram != nil && cfg.Telegram.Enabled {
		if err := sendTelegram(cfg.Telegram, msg); err != nil {
			errs = append(errs, fmt.Errorf("telegram: %w", err))
		}
	}

	if cfg.Webhook != nil && cfg.Webhook.Enabled {
		if err := sendWebhook(cfg.Webhook, msg); err != nil {
			errs = append(errs, fmt.Errorf("webhook: %w", err))
		}
	}

	return errs
}

func sendTelegram(tg *TelegramConfig, msg Message) error {
	text := formatTelegramMessage(msg)
	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", tg.BotToken)

	payload := map[string]interface{}{
		"chat_id":    tg.ChatID,
		"text":       text,
		"parse_mode": "HTML",
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	resp, err := http.Post(url, "application/json", bytes.NewReader(body))
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return fmt.Errorf("HTTP %d", resp.StatusCode)
	}
	return nil
}

func formatTelegramMessage(msg Message) string {
	emoji := "📅"
	if msg.DaysLeft <= 7 {
		emoji = "🚨"
	} else if msg.DaysLeft <= 30 {
		emoji = "⏰"
	}

	text := fmt.Sprintf("%s <b>%s</b>\n", emoji, msg.Title)
	text += fmt.Sprintf("📋 %s — %s\n", msg.Conference, msg.Event)
	text += fmt.Sprintf("📆 Deadline: %s (%d days)\n", msg.Deadline.Format("2006-01-02"), msg.DaysLeft)
	if msg.CCF != "" {
		text += fmt.Sprintf("🏷 CCF: %s\n", msg.CCF)
	}
	if msg.URL != "" {
		text += fmt.Sprintf("🔗 <a href=\"%s\">Conference Page</a>\n", msg.URL)
	}
	return text
}

func sendWebhook(wh *WebhookConfig, msg Message) error {
	body, err := json.Marshal(msg)
	if err != nil {
		return err
	}

	req, err := http.NewRequest("POST", wh.URL, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	for k, v := range wh.Headers {
		req.Header.Set(k, v)
	}

	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return fmt.Errorf("HTTP %d", resp.StatusCode)
	}
	return nil
}
