package model

import "time"

// Conference represents an academic conference with its metadata and submission cycles.
type Conference struct {
	Name     string   `yaml:"name"`
	Slug     string   `yaml:"slug"`
	Rank     Rank     `yaml:"rank"`
	Fields   []string `yaml:"fields"`
	Homepage string   `yaml:"homepage"`
	CFP      string   `yaml:"cfp,omitempty"`
	Location string   `yaml:"location,omitempty"`
	Verified bool     `yaml:"verified,omitempty"` // true = deadline verified against official CFP
	Cycles   []Cycle  `yaml:"cycles"`
}

// Rank holds the ranking information from different evaluation systems.
type Rank struct {
	CCF  string `yaml:"ccf,omitempty"`
	CORE string `yaml:"core,omitempty"`
}

// Track represents a specific submission track within a cycle (e.g., Research, Industry).
type Track struct {
	Name         string `yaml:"name"`
	Abstract     string `yaml:"abstract,omitempty"`
	Deadline     string `yaml:"deadline"`
	Notification string `yaml:"notification,omitempty"`
}

// Cycle represents one submission cycle (e.g., Summer/Winter) for a conference.
// Supports two formats:
//   - Legacy: abstract/deadline/notification directly on the cycle (single implicit track)
//   - Multi-track: tracks field contains a list of Track entries
type Cycle struct {
	Name         string  `yaml:"name,omitempty"`
	Abstract     string  `yaml:"abstract,omitempty"`
	Deadline     string  `yaml:"deadline,omitempty"`
	Notification string  `yaml:"notification,omitempty"`
	Tracks       []Track `yaml:"tracks,omitempty"`
}

// ParsedTrack is a Track with parsed time.Time values.
type ParsedTrack struct {
	Name         string
	Abstract     *time.Time
	Deadline     time.Time
	Notification *time.Time
}

// ParsedCycle is a Cycle with parsed time.Time values.
// For multi-track cycles, Tracks contains the parsed tracks.
// For legacy single-track cycles, Tracks contains one entry derived from the cycle-level fields.
type ParsedCycle struct {
	Name   string
	Tracks []ParsedTrack
}

// EffectiveTracks returns all tracks for this cycle, handling backward compatibility.
// If the cycle has explicit tracks, those are returned.
// Otherwise, the cycle-level abstract/deadline/notification are treated as a single unnamed track.
func (c *Cycle) EffectiveTracks() []Track {
	if len(c.Tracks) > 0 {
		return c.Tracks
	}
	// Legacy format: treat cycle-level fields as a single track
	if c.Deadline == "" {
		return nil
	}
	return []Track{{
		Name:         "", // unnamed = default/main track
		Abstract:     c.Abstract,
		Deadline:     c.Deadline,
		Notification: c.Notification,
	}}
}

// ParseCycle parses a raw Cycle into a ParsedCycle with resolved time values.
func ParseCycle(cyc Cycle) (ParsedCycle, error) {
	pc := ParsedCycle{Name: cyc.Name}

	effectiveTracks := cyc.EffectiveTracks()
	for _, t := range effectiveTracks {
		pt, err := ParseTrack(t)
		if err != nil {
			continue // skip invalid tracks
		}
		pc.Tracks = append(pc.Tracks, pt)
	}

	return pc, nil
}

// ParseTrack parses a raw Track into a ParsedTrack with resolved time values.
func ParseTrack(t Track) (ParsedTrack, error) {
	pt := ParsedTrack{Name: t.Name}

	if t.Abstract != "" {
		at, err := parseDeadlineTime(t.Abstract)
		if err != nil {
			return pt, err
		}
		pt.Abstract = &at
	}

	dt, err := parseDeadlineTime(t.Deadline)
	if err != nil {
		return pt, err
	}
	pt.Deadline = dt

	if t.Notification != "" {
		nt, err := parseDeadlineTime(t.Notification)
		if err != nil {
			return pt, err
		}
		pt.Notification = &nt
	}

	return pt, nil
}

// NextDeadline returns the nearest upcoming deadline across all cycles and tracks.
func (c *Conference) NextDeadline(now time.Time) *ParsedTrack {
	var nearest *ParsedTrack
	for _, cyc := range c.Cycles {
		pc, err := ParseCycle(cyc)
		if err != nil {
			continue
		}
		for i := range pc.Tracks {
			t := &pc.Tracks[i]
			if t.Deadline.Before(now) {
				continue
			}
			if nearest == nil || t.Deadline.Before(nearest.Deadline) {
				nearest = t
			}
		}
	}
	return nearest
}

// AllFutureDeadlines returns all future deadlines across all cycles and tracks, sorted by date.
func (c *Conference) AllFutureDeadlines(now time.Time) []FutureDeadline {
	var result []FutureDeadline
	for _, cyc := range c.Cycles {
		pc, err := ParseCycle(cyc)
		if err != nil {
			continue
		}
		for _, t := range pc.Tracks {
			if t.Deadline.After(now) {
				result = append(result, FutureDeadline{
					CycleName: pc.Name,
					TrackName: t.Name,
					Track:     t,
				})
			}
		}
	}
	sortFutureDeadlines(result)
	return result
}

// FutureDeadline bundles a parsed track with its cycle/track context.
type FutureDeadline struct {
	CycleName string
	TrackName string
	Track     ParsedTrack
}

func sortFutureDeadlines(fds []FutureDeadline) {
	for i := 1; i < len(fds); i++ {
		for j := i; j > 0 && fds[j].Track.Deadline.Before(fds[j-1].Track.Deadline); j-- {
			fds[j], fds[j-1] = fds[j-1], fds[j]
		}
	}
}
