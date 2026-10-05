"""Edition-specific official CFP adapters; round identity is never inferred from dates."""
import re
from html.parser import HTMLParser
from urllib.parse import urlparse
from datetime import datetime
from collections import Counter

try:
    from .official_dates import parse_date, parse_timestamp
except ImportError:
    from official_dates import parse_date, parse_timestamp


class _Blocks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self.stack, self.hidden = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'del', 's'}:
            self.hidden += 1
            if tag in {'del', 's'} and self.stack:
                self.stack[-1][1].append(' [deleted content] ')
        if tag in {'title', 'p', 'li', 'h1', 'h2', 'h3', 'h4'}:
            self.stack.append((tag, []))

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'del', 's'}:
            self.hidden = max(0, self.hidden - 1)
        if self.stack and self.stack[-1][0] == tag:
            kind, parts = self.stack.pop()
            self.blocks.append((kind, ' '.join(''.join(parts).split())))

    def handle_data(self, data):
        if self.stack and not self.hidden:
            self.stack[-1][1].append(data)


_SITES = {
    'asplos': ('www.asplos-conference.org', '/asplos2027/cfp', ['April Cycle', 'September Cycle']),
    'ndss': ('www.ndss-symposium.org', '/ndss2027/submissions/call-for-papers', ['Summer Cycle', 'Fall Cycle']),
    'nsdi': ('www.usenix.org', '/conference/nsdi27/call-for-papers', ['Spring deadline:', 'Fall deadline:']),
    'osdi': ('www.usenix.org', '/conference/osdi27/call-for-papers', ['Important Dates']),
}
_TRACKS = {'asplos': {'Full Paper (Architecture)', 'Full Paper (Systems)', 'Full Paper (PL)'},
           'ndss': {'Technical Papers'}}


def _timestamp(text, date, policy):
    # USENIX prints two equivalent clocks. Both must agree before selecting UTC.
    dual = re.search(r'(\d{1,2}:\d{2}\s*[ap]m)\s+EST\s*\((\d{1,2}:\d{2}\s*[ap]m)\s+UTC\)', text, re.I)
    if dual:
        local = parse_timestamp(dual[1] + ' UTC-05:00', date)
        utc = parse_timestamp(dual[2] + ' UTC', date)
        return utc if local and utc and datetime.fromisoformat(local) == datetime.fromisoformat(utc) else None
    text = re.sub(r'\bUS EDT\b', 'UTC-04:00', text)
    return parse_timestamp(text + (' ' + policy if policy else ''), date)


def extract_adapter(html, url, conference):
    """Return candidates for inspected editions, or None for unsupported pages."""
    slug = conference.get('slug')
    if slug not in _SITES:
        return None
    host, path, headings = _SITES[slug]
    parsed = urlparse(url)
    if parsed.hostname != host or parsed.path.rstrip('/') != path:
        return None
    parser = _Blocks()
    parser.feed(html)
    candidates, reasons = [], []
    identity = ' '.join(text for tag, text in parser.blocks if tag in {'title', 'h1'})
    edition_pattern = rf"\b{slug}(?:\s+Symposium)?\s+(?:2027|['’]27)\b"
    identity_years = set(re.findall(r'\b20\d{2}\b', identity))
    identity_short_years = set(re.findall(rf"\b{slug}\s+['’](\d{{2}})\b", identity, re.I))
    if not re.search(edition_pattern, identity, re.I) or identity_years - {'2027'} or identity_short_years - {'27'}:
        return {'candidates': [], 'review_reasons': ['Official title or h1 does not unambiguously identify the expected 2027 edition']}
    section_counts, field_counts = Counter(), Counter()
    policy = ''
    for _, text in parser.blocks:
        if slug == 'asplos' and 'All dates are expressed as AoE (Anywhere on Earth).' in text:
            policy = 'AoE'
        if slug == 'ndss' and text == 'All deadlines are 11:59 PM AoE (UTC-12).':
            policy = '11:59 PM AoE (UTC-12)'
    section = None
    for tag, text in parser.blocks:
        if text in headings:
            section = text
            section_counts[section] += 1
            continue
        if tag.startswith('h'):
            section = None
        if not section or tag != 'li':
            continue
        field = None
        if re.match(r'(Full paper submission|Complete paper submissions due|Paper titles and abstracts due|Abstract registrations due)', text, re.I):
            field = 'abstract' if re.search('abstract', text, re.I) else 'deadline'
        elif slug == 'ndss' and re.search(r': Paper submission deadline$', text):
            field = 'deadline'
        elif re.match(r'Notification(?: to authors)?\s*[—:]', text) or (slug == 'ndss' and re.search(r': Author notification$', text)):
            field = 'notification'
        if not field:
            continue
        field_counts[(section, field)] += 1
        date = parse_date(text)
        if not date:
            reasons.append(f'{section}: ambiguous or missing explicit date: {text}')
            continue
        cycle_name = '2027' if slug == 'osdi' else section.rstrip(':').replace(' deadline', ' Cycle')
        cycles = [c for c in conference.get('cycles', []) if c.get('name') == cycle_name]
        tracks = [None]
        reason = ''
        if '[deleted content]' in text:
            reason = 'Official record contains deleted content; replacement needs review'
            reasons.append(f'{section}: deleted content in {field} record')
        if len(cycles) != 1:
            reason = 'Official round does not uniquely match an existing named cycle'
        elif cycles[0].get('tracks'):
            tracks = [t.get('name') for t in cycles[0]['tracks'] if t.get('name') in _TRACKS.get(slug, set())]
            if not tracks:
                tracks, reason = [None], 'No supported existing track matches the official schedule'
        value = date if field == 'notification' else _timestamp(text, date, policy)
        if not value:
            reason = reason or 'No unambiguous explicit time and timezone'
        if 'tentative' in text.lower():
            reason = 'Official date is tentative'
        for track in tracks:
            candidates.append({'year': 2027, 'cycle_name': cycle_name, 'track_name': track,
                               'field': field, 'date': date, 'value': value,
                               'evidence': f'{section}: {text}' + (f' [{policy}]' if policy else ''),
                               'applicable': not reason, 'reason': reason})
    expected_fields = ['abstract', 'deadline'] if slug in {'nsdi', 'osdi'} else ['deadline']
    for heading in headings:
        if section_counts[heading] != 1:
            reasons.append(f'{heading}: expected exactly one official schedule section')
        for field in expected_fields:
            if field_counts[(heading, field)] != 1:
                reasons.append(f'{heading}: expected exactly one {field} record')
        if field_counts[(heading, 'notification')] > 1:
            reasons.append(f'{heading}: duplicate notification records')
    if not candidates:
        reasons.append('Supported official page has no recognizable schedule; check for layout changes')
    return {'candidates': candidates, 'review_reasons': reasons}
