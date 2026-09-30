package validate

import (
	"fmt"
	"io/fs"
	"strings"

	"github.com/cfpctl/cfpctl/data"
	"github.com/cfpctl/cfpctl/internal/model"
	"gopkg.in/yaml.v3"
)

// ValidationError represents a single validation issue.
type ValidationError struct {
	File    string
	Index   int
	Field   string
	Message string
}

func (e ValidationError) Error() string {
	return fmt.Sprintf("%s[%d].%s: %s", e.File, e.Index, e.Field, e.Message)
}

// Result holds the validation outcome.
type Result struct {
	Errors       []ValidationError
	TotalFiles   int
	TotalConfs   int
	SlugsSeen    map[string]string // slug -> file where first seen
}

// ValidateAll validates all embedded YAML data files.
func ValidateAll() *Result {
	result := &Result{
		SlugsSeen: make(map[string]string),
	}

	entries, err := fs.ReadDir(data.FS, ".")
	if err != nil {
		result.Errors = append(result.Errors, ValidationError{
			File:    "(embedded)",
			Field:   "fs",
			Message: fmt.Sprintf("cannot read data dir: %v", err),
		})
		return result
	}

	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".yaml") {
			continue
		}
		result.TotalFiles++
		validateFile(result, entry.Name())
	}

	return result
}

func validateFile(result *Result, filename string) {
	raw, err := fs.ReadFile(data.FS, filename)
	if err != nil {
		result.Errors = append(result.Errors, ValidationError{
			File:    filename,
			Field:   "read",
			Message: fmt.Sprintf("cannot read: %v", err),
		})
		return
	}

	var confs []model.Conference
	if err := yaml.Unmarshal(raw, &confs); err != nil {
		result.Errors = append(result.Errors, ValidationError{
			File:    filename,
			Field:   "yaml",
			Message: fmt.Sprintf("parse error: %v", err),
		})
		return
	}

	for i, c := range confs {
		result.TotalConfs++
		validateConference(result, filename, i, c)
	}
}

func validateConference(result *Result, file string, idx int, c model.Conference) {
	// Required fields
	if c.Name == "" {
		result.Errors = append(result.Errors, ValidationError{
			File: file, Index: idx, Field: "name", Message: "required",
		})
	}
	if c.Slug == "" {
		result.Errors = append(result.Errors, ValidationError{
			File: file, Index: idx, Field: "slug", Message: "required",
		})
	} else {
		// Slug uniqueness
		if prev, ok := result.SlugsSeen[c.Slug]; ok {
			result.Errors = append(result.Errors, ValidationError{
				File: file, Index: idx, Field: "slug",
				Message: fmt.Sprintf("duplicate slug %q (first seen in %s)", c.Slug, prev),
			})
		} else {
			result.SlugsSeen[c.Slug] = file
		}

		// Slug format: lowercase, hyphens only
		if c.Slug != strings.ToLower(c.Slug) {
			result.Errors = append(result.Errors, ValidationError{
				File: file, Index: idx, Field: "slug",
				Message: fmt.Sprintf("must be lowercase, got %q", c.Slug),
			})
		}
	}

	// Fields required
	if len(c.Fields) == 0 {
		result.Errors = append(result.Errors, ValidationError{
			File: file, Index: idx, Field: "fields", Message: "at least one field required",
		})
	}

	// CCF rank validation
	if c.Rank.CCF != "" {
		valid := map[string]bool{"A": true, "B": true, "C": true}
		if !valid[strings.ToUpper(c.Rank.CCF)] {
			result.Errors = append(result.Errors, ValidationError{
				File: file, Index: idx, Field: "rank.ccf",
				Message: fmt.Sprintf("invalid CCF rank %q (must be A/B/C)", c.Rank.CCF),
			})
		}
	}

	// Homepage required
	if c.Homepage == "" {
		result.Errors = append(result.Errors, ValidationError{
			File: file, Index: idx, Field: "homepage", Message: "required",
		})
	}

	// Cycles required
	if len(c.Cycles) == 0 {
		result.Errors = append(result.Errors, ValidationError{
			File: file, Index: idx, Field: "cycles", Message: "at least one cycle required",
		})
	}

	// Validate each cycle
	for ci, cyc := range c.Cycles {
		prefix := fmt.Sprintf("cycles[%d]", ci)

		effectiveTracks := cyc.EffectiveTracks()
		if len(effectiveTracks) == 0 {
			result.Errors = append(result.Errors, ValidationError{
				File: file, Index: idx, Field: prefix, Message: "no deadline found (neither cycle-level nor tracks)",
			})
			continue
		}

		for ti, t := range effectiveTracks {
			tPrefix := prefix
			if len(cyc.Tracks) > 0 {
				tPrefix = fmt.Sprintf("%s.tracks[%d]", prefix, ti)
			}

			if t.Deadline == "" {
				result.Errors = append(result.Errors, ValidationError{
					File: file, Index: idx, Field: tPrefix + ".deadline", Message: "required",
				})
			} else {
				pt, err := model.ParseTrack(t)
				if err != nil {
					result.Errors = append(result.Errors, ValidationError{
						File: file, Index: idx, Field: tPrefix,
						Message: fmt.Sprintf("time parse error: %v", err),
					})
				} else if pt.Deadline.IsZero() {
					result.Errors = append(result.Errors, ValidationError{
						File: file, Index: idx, Field: tPrefix + ".deadline",
						Message: "parsed to zero time",
					})
				}
			}
		}
	}
}

// Summary returns a human-readable summary of the validation result.
func (r *Result) Summary() string {
	var b strings.Builder
	if len(r.Errors) == 0 {
		fmt.Fprintf(&b, "✓ All %d conferences in %d files passed validation.\n", r.TotalConfs, r.TotalFiles)
	} else {
		fmt.Fprintf(&b, "✗ Found %d error(s) across %d files (%d conferences checked):\n\n",
			len(r.Errors), r.TotalFiles, r.TotalConfs)
		for _, e := range r.Errors {
			fmt.Fprintf(&b, "  • %s\n", e.Error())
		}
	}
	return b.String()
}
