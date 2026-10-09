"""Adapter for conf.researchr.org /dates/ pages.

Parses the unified When|Track|What table that all researchr.org conferences share.
Matches rows only to the explicitly identified edition and exact named tracks.
"""
import re

try:
    from .official_dates import parse_date, parse_timestamp
except ImportError:
    from official_dates import parse_date, parse_timestamp


class _TableParser:
    """Read only a table explicitly headed When / Track / What."""
    def __init__(self):
        self.rows, self.found_dates_table = [], False

    def feed(self, html):
        if __package__:
            from .official_tables import Tree, Node
        else:
            from official_tables import Tree, Node
        tree = Tree()
        tree.feed(html)
        for table in tree.root.walk():
            if table.tag != 'table':
                continue
            rows = []
            for row in table.walk():
                if row.tag == 'tr':
                    cells = [' '.join(c.text().split()) for c in row.children
                             if isinstance(c, Node) and c.tag in ('td', 'th')]
                    if len(cells) == 3:
                        rows.append(tuple(cells))
            if rows and [c.casefold() for c in rows[0]] == ['when', 'track', 'what']:
                self.found_dates_table = True
                self.rows.extend(rows[1:])


# Map researchr track names to cfpctl field types
_FIELD_KEYWORDS = {
    'abstract': [r'abstract\s+(?:submission|registration|deadline)', r'paper\s+titles?\s+and\s+abstracts'],
    'deadline': [r'(?:paper\s+)?submission\s*(?:deadline)?$', r'submissions?\s+deadline',
                 r'paper\s+deadline', r'full\s+paper', r'submission\s+due',
                 r'submission\s+of\s+(?:solution\s+)?papers'],
    'notification': [r'notification', r'acceptance'],
}


def _classify_event(what_text):
    """Classify a 'What' column text into abstract/deadline/notification or None."""
    text = what_text.strip().lower()
    if re.search(r'early|reject|rebuttal|author.response|review.release|revision|final acceptance', text):
        return None
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
    """Resolve a dates table only within its explicitly identified edition."""
    from urllib.parse import urlparse
    if __package__:
        from .official_tables import Tree
        from .official_identity import title_years
    else:
        from official_tables import Tree
        from official_identity import title_years
    host = urlparse(url).hostname or ''
    domains = ('researchr.org', 'sigplan.org', 'splashcon.org', 'msrconf.org', 'formalise.org')
    if not any(host == d or host.endswith('.' + d) for d in domains):
        return None
    parser = _TableParser()
    parser.feed(html)
    if not parser.found_dates_table:
        return None
    tree = Tree()
    tree.feed(html)
    headings = [(n.tag, ' '.join(n.text().split())) for n in tree.root.walk() if n.tag in ('title', 'h1')]
    years = title_years(headings, conference)
    if len(years) != 1:
        return {'candidates': [], 'review_reasons': ['researchr page must identify one conference edition']}
    year = int(next(iter(years)))
    cycles = [c for c in conference.get('cycles', []) if str(c.get('name')) == str(year) or c.get('year') == year]
    scopes = [' '.join(n.text().split()) for n in tree.root.walk() if n.tag == 'p'
              and re.search(r'all (?:deadlines|dates|times) are', n.text(), re.I)
              and not re.search(r'workshop|poster|artifact', n.text(), re.I)]
    policy = scopes[0] if len(set(scopes)) == 1 else ''
    candidates, reasons, seen = [], [], set()
    for when, track, event in parser.rows:
        field = _classify_event(event)
        if not field or re.search(r'workshop|poster|tutorial|doctoral|artifact|challenge|competition|demonstration', track, re.I):
            continue
        date = parse_date(when)
        if not date:
            continue
        matches = [(c, t) for c in cycles for t in c.get('tracks', [])
                   if t['name'].strip().casefold() == track.strip().casefold()]
        main_track = re.fullmatch(r'(?:' + re.escape(conference.get('slug', '')) + r'\s+)?(?:research(?: papers?)?(?: track)?|technical papers(?: track)?|main conference|papers)', track.strip(), re.I)
        if not matches and len(cycles) == 1 and not cycles[0].get('tracks') and main_track:
            matches = [(cycles[0], None)]
        if len(matches) != 1:
            reasons.append('Track "' + track + '" not uniquely matched within conference edition')
            continue
        cycle, target = matches[0]
        evidence = f'{when} | {track} | {event}'
        value = date if field == 'notification' and not re.search(r'\d{1,2}:\d{2}', when) else parse_timestamp(when, date)
        if not value and policy and not re.search(r'UTC|GMT|AoE|\b[A-Z]{2,4}T\b', when):
            value = parse_timestamp(when + ' ' + policy, date)
            evidence += ' [' + policy + ']'
        reason = None
        if int(date[:4]) not in (year-1, year):
            reason = 'date falls outside explicit conference edition'
        elif re.search(r'tentative|TBD|deleted content', when + event, re.I):
            reason = 'researchr date is tentative or revised'
        elif not value:
            reason = 'No explicit timezone in researchr dates table'
        key = (cycle['name'], target['name'] if target else None, field, value, date)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(dict(year=year, cycle_name=cycle['name'], track_name=target['name'] if target else None,
                               field=field, date=date, value=value, evidence=evidence,
                               applicable=reason is None, reason=reason))
    keys = [(c['cycle_name'], c['track_name'], c['field']) for c in candidates]
    if len(keys) != len(set(keys)):
        reasons.append('conflicting researchr dates for one edition/track/field')
    return {'candidates': candidates, 'review_reasons': list(dict.fromkeys(reasons))} if candidates or reasons else None
