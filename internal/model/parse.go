package model

import (
	"fmt"
	"time"
)

// AoE is the Anywhere on Earth timezone (UTC-12).
var AoE = time.FixedZone("AoE", -12*60*60)

// parseDeadlineTime handles multiple time formats commonly used in CFP data.
// It defaults to AoE (UTC-12) when no timezone is specified.
func parseDeadlineTime(s string) (time.Time, error) {
	formats := []string{
		time.RFC3339,
		"2006-01-02T15:04:05-07:00",
		"2006-01-02T15:04:05Z07:00",
		"2006-01-02T15:04:05",
		"2006-01-02 15:04:05",
		"2006-01-02",
	}

	for _, f := range formats {
		if t, err := time.Parse(f, s); err == nil {
			// If no timezone info was in the format, default to AoE
			if f == "2006-01-02T15:04:05" || f == "2006-01-02 15:04:05" || f == "2006-01-02" {
				t = time.Date(t.Year(), t.Month(), t.Day(), t.Hour(), t.Minute(), t.Second(), 0, AoE)
			}
			return t, nil
		}
	}

	return time.Time{}, fmt.Errorf("unsupported time format: %s", s)
}

// DaysRemaining calculates whole days remaining until deadline from now.
func DaysRemaining(deadline time.Time, now time.Time) int {
	dur := deadline.Sub(now)
	if dur < 0 {
		return 0
	}
	return int(dur.Hours() / 24)
}

// FormatDuration formats a duration as "Xd Yh Zm".
func FormatDuration(d time.Duration) string {
	if d < 0 {
		return "passed"
	}
	days := int(d.Hours() / 24)
	hours := int(d.Hours()) % 24
	minutes := int(d.Minutes()) % 60

	if days > 0 {
		return fmt.Sprintf("%dd %02dh %02dm", days, hours, minutes)
	}
	return fmt.Sprintf("%dh %02dm", hours, minutes)
}
