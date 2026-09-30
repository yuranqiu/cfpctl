package watchlist

import (
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

const fileName = "watchlist.yaml"

// WatchList manages the user's watched conferences.
type WatchList struct {
	path    string
	Entries []Entry `yaml:"entries"`
}

// Entry represents a watched conference.
type Entry struct {
	Slug string `yaml:"slug"`
}

// configDir returns the cfpctl config directory.
func configDir() (string, error) {
	dir, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, "cfpctl"), nil
}

// Load reads the watchlist from disk. Returns an empty list if file doesn't exist.
func Load() (*WatchList, error) {
	dir, err := configDir()
	if err != nil {
		return &WatchList{}, nil
	}

	wl := &WatchList{path: filepath.Join(dir, fileName)}
	data, err := os.ReadFile(wl.path)
	if err != nil {
		if os.IsNotExist(err) {
			return wl, nil
		}
		return wl, err
	}

	if err := yaml.Unmarshal(data, &wl.Entries); err != nil {
		return wl, err
	}
	return wl, nil
}

// Save persists the watchlist to disk.
func (wl *WatchList) Save() error {
	dir := filepath.Dir(wl.path)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}

	data, err := yaml.Marshal(wl.Entries)
	if err != nil {
		return err
	}
	return os.WriteFile(wl.path, data, 0o644)
}

// Add adds a conference slug to the watchlist. No-op if already present.
func (wl *WatchList) Add(slug string) {
	for _, e := range wl.Entries {
		if e.Slug == slug {
			return
		}
	}
	wl.Entries = append(wl.Entries, Entry{Slug: slug})
}

// Remove removes a conference slug from the watchlist.
func (wl *WatchList) Remove(slug string) {
	var filtered []Entry
	for _, e := range wl.Entries {
		if e.Slug != slug {
			filtered = append(filtered, e)
		}
	}
	wl.Entries = filtered
}

// Contains checks if a slug is in the watchlist.
func (wl *WatchList) Contains(slug string) bool {
	for _, e := range wl.Entries {
		if e.Slug == slug {
			return true
		}
	}
	return false
}

// Slugs returns all watched slugs.
func (wl *WatchList) Slugs() []string {
	slugs := make([]string, len(wl.Entries))
	for i, e := range wl.Entries {
		slugs[i] = e.Slug
	}
	return slugs
}
