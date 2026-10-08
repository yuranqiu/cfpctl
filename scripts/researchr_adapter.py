"""Adapter for conf.researchr.org /dates/ pages.

Parses the unified When|Track|What table that all researchr.org conferences share.
Matches rows to existing conference cycles/tracks by track name fuzzy matching.
"""
import re
from html.parser import HTMLParser

try:
    from .official_dates import parse_date, parse_timestamp
except ImportError:
    from official_dates import parse_date, parse_timestamp


class _TableParser(HTMLParser):
    """Extract rows from the first 3-column table on the page."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.in_table = False
        self.in_row = False
        self.cells = []
        self.cell_text = []
        self.col_count = 0
        self.found_dates_table = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'table' and not self.found_dates_table:
            self.in_table = True
            self.col_count = 0
        elif tag == 'tr' and self.in_table:
            self.in_row = True
            self.cells = []
        elif tag in ('td', 'th') and self.in_row:
            self.cell_text = []
            self.col_count += 1

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.in_row:
            self.cells.append(' '.join(''.join(self.cell_text).split()))
        elif tag == 'tr' and self.in_row:
            self.in_row = False
            if len(self.cells) >= 3:
                self.rows.append(tuple(self.cells[:3]))
                if not self.found_dates_table:
                    # Check if this looks like the dates table header
                    if any('when' in c.lower() or 'track' in c.lower() for c in self.cells):
                        self.found_dates_table = True
        elif tag == 'table' and self.in_table:
            self.in_table = False
            if self.found_dates_table:
                return  # Stop after first dates table

    def handle_data(self, data):
        if self.in_row:
            self.cell_text.append(data)


# Map researchr track names to cfpctl field types
_FIELD_KEYWORDS = {
    'abstract': [r'abstract\s+(?:submission|registration|deadline)', r'paper\s+titles?\s+and\s+abstracts'],
    'deadline': [r'(?:paper\s+)?submission\s*(?:deadline)?$', r'submissions?\s+deadline',
                 r'paper\s+deadline', r'full\s+paper', r'submission\s+due',
                 r'submission\s+of\s+(?:solution\s+)?papers'],
    'notification': [r'notification', r'acceptance', r'author\s+response', r'review\s+release'],
}


def _classify_event(what_text):
    """Classify a 'What' column text into abstract/deadline/notification or None."""
    text = what_text.strip().lower()
    # Skip non-deadline events
    if re.search(r'\b(?:announcement|meeting|tutorial|review\s+tutorial|zoom|members?|committee|camera.ready|artifact\s+submission|revision\s+due|final\s+version)\b', text):
        return None
    for field, patterns in _FIELD_KEYWORDS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.I):
                # Disambiguate: "abstract submission" vs "paper submission"
                if field == 'deadline' and re.search(r'\babstract\b', text):
                    return 'abstract'
                return field
    return None


def extract_researchr(html, url, conference):
    """Parse a conf.researchr.org /dates/ page. Returns candidates or None."""
    slug = conference.get('slug', '')
    from urllib.parse import urlparse
    parsed_url = urlparse(url)

    # Handle conf.researchr.org, *.sigplan.org, *.splashcon.org, and similar
    hostname = parsed_url.hostname or ''
    valid = (hostname == 'conf.researchr.org'
             or 'sigplan.org' in hostname
             or 'splashcon.org' in hostname
             or 'msrconf.org' in hostname
             or 'formalise.org' in hostname)
    if not valid:
        return None

    # Accept /dates/, /track/, /home/, or root pages for researchr-hosted sites
    is_dates_page = bool(re.search(r'/dates/|/track/', parsed_url.path))
    is_home_page = bool(re.search(r'/home/', parsed_url.path))
    is_root = parsed_url.path in ('', '/')
    is_researchr_host = hostname == 'conf.researchr.org'

    if not (is_dates_page or is_home_page or is_root):
        if not ('sigplan.org' in hostname or 'splashcon.org' in hostname or 'msrconf.org' in hostname):
            return None

    parser = _TableParser()
    parser.feed(html)

    if not parser.rows:
        return None

    # Build existing track name set for matching
    existing_tracks = {}
    for cycle in conference.get('cycles', []):
        for track in cycle.get('tracks', []):
            name = track.get('name', '').lower()
            if name:
                existing_tracks[name] = (cycle.get('name'), track.get('name'))

    candidates = []
    review_reasons = []
    seen = set()

    for when_text, track_text, what_text in parser.rows:
        # Skip header row
        if when_text.lower() == 'when' or track_text.lower() == 'track':
            continue

        field = _classify_event(what_text)
        if not field:
            continue

        date = parse_date(when_text)
        if not date:
            continue

        # Extract year from date
        try:
            year = int(date[:4])
        except ValueError:
            continue

        # Try to match track name to existing data
        track_lower = track_text.strip().lower()
        matched_cycle = None
        matched_track = None

        # Direct match
        if track_lower in existing_tracks:
            matched_cycle, matched_track = existing_tracks[track_lower]
        else:
            # Fuzzy match: check if any existing track name is contained in or contains the row track
            for existing_name, (cyc, trk) in existing_tracks.items():
                if existing_name in track_lower or track_lower in existing_name:
                    matched_cycle, matched_track = cyc, trk
                    break

        # Dedup key
        key = (year, matched_cycle, matched_track, field)
        if key in seen:
            continue
        seen.add(key)

        # For notification fields without explicit time, use date-only
        value = None
        if field == 'notification':
            # Check if there's a time component
            if re.search(r'\d{1,2}:\d{2}', when_text):
                value = parse_timestamp(when_text, date)
            else:
                value = date  # Date-only notification
        else:
            # Deadline/abstract: require timezone
            value = parse_timestamp(when_text, date)
            if not value:
                # Researchr dates typically don't include timezone; mark as review
                pass

        reason = None
        if not value:
            reason = 'No explicit timezone in researchr dates table'
        if matched_track is None:
            # Track not found in existing data — still record but mark for review
            reason = reason or f'Track "{track_text}" not matched to existing data'

        candidates.append({
            'year': year,
            'cycle_name': matched_cycle or str(year),
            'track_name': matched_track,
            'field': field,
            'date': date,
            'value': value,
            'evidence': f'{when_text} | {track_text} | {what_text}',
            'applicable': reason is None,
            'reason': reason,
        })

    if not candidates:
        return None

    return {'candidates': candidates, 'review_reasons': review_reasons}
