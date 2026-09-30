package remind

import (
	"os"
	"path/filepath"
	"time"

	"gopkg.in/yaml.v3"
)

const fileName = "reminders.yaml"

// Config holds all reminder configurations.
type Config struct {
	path    string
	Entries []Entry `yaml:"entries"`
}

// Entry represents a reminder configuration for a conference.
type Entry struct {
	Slug   string   `yaml:"slug"`
	Before []string `yaml:"before"` // e.g., ["30d", "14d", "7d", "1d"]
}

func configDir() (string, error) {
	dir, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, "cfpctl"), nil
}

// Load reads the reminder config from disk.
func Load() (*Config, error) {
	dir, err := configDir()
	if err != nil {
		return &Config{}, nil
	}

	cfg := &Config{path: filepath.Join(dir, fileName)}
	data, err := os.ReadFile(cfg.path)
	if err != nil {
		if os.IsNotExist(err) {
			return cfg, nil
		}
		return cfg, err
	}

	if err := yaml.Unmarshal(data, &cfg.Entries); err != nil {
		return cfg, err
	}
	return cfg, nil
}

// Save persists the reminder config to disk.
func (cfg *Config) Save() error {
	dir := filepath.Dir(cfg.path)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}

	data, err := yaml.Marshal(cfg.Entries)
	if err != nil {
		return err
	}
	return os.WriteFile(cfg.path, data, 0o644)
}

// Set sets or updates reminders for a conference slug.
func (cfg *Config) Set(slug string, before []string) {
	for i, e := range cfg.Entries {
		if e.Slug == slug {
			cfg.Entries[i].Before = before
			return
		}
	}
	cfg.Entries = append(cfg.Entries, Entry{Slug: slug, Before: before})
}

// Remove removes reminders for a conference slug.
func (cfg *Config) Remove(slug string) {
	var filtered []Entry
	for _, e := range cfg.Entries {
		if e.Slug != slug {
			filtered = append(filtered, e)
		}
	}
	cfg.Entries = filtered
}

// Get returns the reminder intervals for a slug, or nil if not configured.
func (cfg *Config) Get(slug string) []string {
	for _, e := range cfg.Entries {
		if e.Slug == slug {
			return e.Before
		}
	}
	return nil
}

// ParseBefore parses a list of duration strings into time.Duration values.
// Each string should be like "30d", "14d", "7d", "1d".
func ParseBefore(before []string) []time.Duration {
	var durations []time.Duration
	for _, s := range before {
		if len(s) < 2 {
			continue
		}
		n := 0
		for _, ch := range s[:len(s)-1] {
			if ch >= '0' && ch <= '9' {
				n = n*10 + int(ch-'0')
			}
		}
		unit := s[len(s)-1]
		switch unit {
		case 'd', 'D':
			durations = append(durations, time.Duration(n)*24*time.Hour)
		case 'h', 'H':
			durations = append(durations, time.Duration(n)*time.Hour)
		}
	}
	return durations
}
