package calendar

import (
	"fmt"
	"strings"
	"time"

	"github.com/cfpctl/cfpctl/internal/model"
)

// Event represents a single calendar event for ICS generation.
type Event struct {
	UID         string
	Summary     string
	Description string
	DTStart     time.Time
	DTEnd       time.Time
	URL         string
	AlarmBefore []time.Duration
}

// GenerateICS produces an iCalendar (RFC 5545) document from a list of events.
func GenerateICS(events []Event, calName string) string {
	var b strings.Builder
	b.WriteString("BEGIN:VCALENDAR\r\n")
	b.WriteString("VERSION:2.0\r\n")
	b.WriteString("PRODID:-//cfpctl//Conference Deadlines//EN\r\n")
	b.WriteString(fmt.Sprintf("X-WR-CALNAME:%s\r\n", escapeICS(calName)))
	b.WriteString("CALSCALE:GREGORIAN\r\n")
	b.WriteString("METHOD:PUBLISH\r\n")
	for _, e := range events {
		writeEvent(&b, e)
	}
	b.WriteString("END:VCALENDAR\r\n")
	return b.String()
}

func writeEvent(b *strings.Builder, e Event) {
	b.WriteString("BEGIN:VEVENT\r\n")
	b.WriteString(fmt.Sprintf("UID:%s\r\n", e.UID))
	b.WriteString(fmt.Sprintf("DTSTAMP:%s\r\n", formatICSDateTime(time.Now().UTC())))
	b.WriteString(fmt.Sprintf("DTSTART:%s\r\n", formatICSDateTime(e.DTStart.UTC())))
	b.WriteString(fmt.Sprintf("DTEND:%s\r\n", formatICSDateTime(e.DTEnd.UTC())))
	b.WriteString(fmt.Sprintf("SUMMARY:%s\r\n", escapeICS(e.Summary)))
	if e.Description != "" {
		b.WriteString(fmt.Sprintf("DESCRIPTION:%s\r\n", escapeICS(e.Description)))
	}
	if e.URL != "" {
		b.WriteString(fmt.Sprintf("URL:%s\r\n", e.URL))
	}
	for _, alarm := range e.AlarmBefore {
		writeAlarm(b, alarm)
	}
	b.WriteString("END:VEVENT\r\n")
}

func writeAlarm(b *strings.Builder, before time.Duration) {
	b.WriteString("BEGIN:VALARM\r\n")
	b.WriteString("ACTION:DISPLAY\r\n")
	b.WriteString("DESCRIPTION:Deadline reminder\r\n")
	b.WriteString(fmt.Sprintf("TRIGGER:%s\r\n", formatICSDuration(before)))
	b.WriteString("END:VALARM\r\n")
}

func formatICSDateTime(t time.Time) string {
	return t.Format("20060102T150405Z")
}

func formatICSDuration(d time.Duration) string {
	if d > 0 {
		d = -d
	}
	totalHours := int(-d.Hours())
	days := totalHours / 24
	hours := totalHours % 24
	if days > 0 && hours == 0 {
		return fmt.Sprintf("-P%dD", days)
	}
	if days > 0 {
		return fmt.Sprintf("-P%dDT%dH", days, hours)
	}
	return fmt.Sprintf("-PT%dH", hours)
}

func escapeICS(s string) string {
	s = strings.ReplaceAll(s, `\`, `\\`)
	s = strings.ReplaceAll(s, `;`, `\;`)
	s = strings.ReplaceAll(s, `,`, `\,`)
	s = strings.ReplaceAll(s, "\n", `\n`)
	return s
}

// ConferenceToEvents converts a conference's future deadlines into calendar events.
func ConferenceToEvents(c *model.Conference, now time.Time, alarms []time.Duration) []Event {
	var events []Event
	fds := c.AllFutureDeadlines(now)

	for _, fd := range fds {
		cycleLabel := fd.CycleName
		if cycleLabel == "" {
			cycleLabel = "Submission"
		}
		trackLabel := fd.TrackName
		fullLabel := cycleLabel
		if trackLabel != "" {
			fullLabel = fmt.Sprintf("%s [%s]", cycleLabel, trackLabel)
		}

		// Abstract deadline
		if fd.Track.Abstract != nil {
			events = append(events, Event{
				UID:         fmt.Sprintf("%s-%s-abstract@cfpctl", c.Slug, sanitizeUID(fullLabel)),
				Summary:     fmt.Sprintf("📝 %s %s — Abstract Deadline", c.Name, fullLabel),
				Description: fmt.Sprintf("Abstract submission deadline for %s %s.\nHomepage: %s", c.Name, fullLabel, c.Homepage),
				DTStart:     *fd.Track.Abstract,
				DTEnd:       fd.Track.Abstract.Add(1 * time.Hour),
				URL:         c.Homepage,
				AlarmBefore: alarms,
			})
		}

		// Full paper deadline
		events = append(events, Event{
			UID:         fmt.Sprintf("%s-%s-deadline@cfpctl", c.Slug, sanitizeUID(fullLabel)),
			Summary:     fmt.Sprintf("🚨 %s %s — Paper Deadline", c.Name, fullLabel),
			Description: fmt.Sprintf("Full paper submission deadline for %s %s.\nHomepage: %s", c.Name, fullLabel, c.Homepage),
			DTStart:     fd.Track.Deadline,
			DTEnd:       fd.Track.Deadline.Add(1 * time.Hour),
			URL:         c.Homepage,
			AlarmBefore: alarms,
		})

		// Notification
		if fd.Track.Notification != nil {
			events = append(events, Event{
				UID:         fmt.Sprintf("%s-%s-notification@cfpctl", c.Slug, sanitizeUID(fullLabel)),
				Summary:     fmt.Sprintf("📬 %s %s — Notification", c.Name, fullLabel),
				Description: fmt.Sprintf("Notification date for %s %s.\nHomepage: %s", c.Name, fullLabel, c.Homepage),
				DTStart:     *fd.Track.Notification,
				DTEnd:       fd.Track.Notification.Add(1 * time.Hour),
				URL:         c.Homepage,
			})
		}
	}

	return events
}

func sanitizeUID(s string) string {
	s = strings.ToLower(s)
	s = strings.ReplaceAll(s, " ", "-")
	s = strings.ReplaceAll(s, "/", "-")
	s = strings.ReplaceAll(s, "[", "")
	s = strings.ReplaceAll(s, "]", "")
	if s == "" {
		s = "default"
	}
	return s
}
