package store

import (
	"fmt"
	"io/fs"
	"strings"

	"github.com/cfpctl/cfpctl/data"
	"github.com/cfpctl/cfpctl/internal/model"
	"gopkg.in/yaml.v3"
)

// Store manages conference data loading and querying.
type Store struct {
	conferences []model.Conference
	index       map[string]*model.Conference // slug -> conference
}

// New creates a new Store by loading all embedded YAML data files.
func New() (*Store, error) {
	s := &Store{
		index: make(map[string]*model.Conference),
	}

	entries, err := fs.ReadDir(data.FS, ".")
	if err != nil {
		return nil, fmt.Errorf("reading embedded data dir: %w", err)
	}

	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".yaml") {
			continue
		}
		raw, err := fs.ReadFile(data.FS, entry.Name())
		if err != nil {
			return nil, fmt.Errorf("reading %s: %w", entry.Name(), err)
		}
		var confs []model.Conference
		if err := yaml.Unmarshal(raw, &confs); err != nil {
			return nil, fmt.Errorf("parsing %s: %w", entry.Name(), err)
		}
		for i := range confs {
			s.conferences = append(s.conferences, confs[i])
			s.index[confs[i].Slug] = &s.conferences[len(s.conferences)-1]
		}
	}

	return s, nil
}

// All returns all loaded conferences.
func (s *Store) All() []model.Conference {
	return s.conferences
}

// GetBySlug returns a conference by its slug, or nil if not found.
func (s *Store) GetBySlug(slug string) *model.Conference {
	slug = strings.ToLower(strings.TrimSpace(slug))
	if c, ok := s.index[slug]; ok {
		return c
	}
	// Try partial match
	for k, c := range s.index {
		if strings.Contains(k, slug) {
			return c
		}
	}
	return nil
}

// Search returns conferences matching the keyword in name, slug, or fields.
func (s *Store) Search(keyword string) []model.Conference {
	kw := strings.ToLower(strings.TrimSpace(keyword))
	var results []model.Conference
	for _, c := range s.conferences {
		if matchesKeyword(c, kw) {
			results = append(results, c)
		}
	}
	return results
}

func matchesKeyword(c model.Conference, kw string) bool {
	if strings.Contains(strings.ToLower(c.Name), kw) {
		return true
	}
	if strings.Contains(strings.ToLower(c.Slug), kw) {
		return true
	}
	for _, f := range c.Fields {
		if strings.Contains(strings.ToLower(f), kw) {
			return true
		}
	}
	return false
}

// Filter returns conferences matching the given CCF rank and/or field.
func (s *Store) Filter(ccfRank string, fields []string) []model.Conference {
	var results []model.Conference
	for _, c := range s.conferences {
		if ccfRank != "" && !strings.EqualFold(c.Rank.CCF, ccfRank) {
			continue
		}
		if len(fields) > 0 && !matchesAnyField(c.Fields, fields) {
			continue
		}
		results = append(results, c)
	}
	return results
}

func matchesAnyField(confFields, filterFields []string) bool {
	for _, cf := range confFields {
		for _, ff := range filterFields {
			if strings.EqualFold(cf, ff) {
				return true
			}
		}
	}
	return false
}
