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


# USENIX Security is handled by the two-cycle parser in scrape_cfp.py.
# Registering it here would intercept that parser with the generic fallback.
_SITES = {
    'asplos': ('www.asplos-conference.org', '/asplos2027/cfp', ['April Cycle', 'September Cycle']),
    'ndss': ('www.ndss-symposium.org', '/ndss2027/submissions/call-for-papers', ['Summer Cycle', 'Fall Cycle']),
    'nsdi': ('www.usenix.org', '/conference/nsdi27/call-for-papers', ['Spring deadline:', 'Fall deadline:']),
    'osdi': ('www.usenix.org', '/conference/osdi27/call-for-papers', ['Important Dates']),
    'fast': ('www.usenix.org', '/conference/fast27/call-for-papers', ['Spring deadline:', 'Fall deadline:']),
    'atc': ('www.usenix.org', '/conference/atc27/call-for-papers', ['Spring deadline:', 'Fall deadline:']),
    'eurosys': ('www.usenix.org', '/conference/eurosys27/call-for-papers', ['Important Dates']),
    'eurocrypt': ('eurocrypt.iacr.org', '/2027/', []),
    'crypto': ('crypto.iacr.org', '/2027/', []),
    'mobicom': ('www.sigmobile.org', '/mobicom/2027/', []),
    'stoc': ('acm-stoc.org', '/stoc2027/', []),
    'sigmod': ('2027.sigmod.org', '/calls_papers_important_dates.shtml', []),
    'www': ('www2027.thewebconf.org', '/important-dates/', []),
    'sosp': ('sigops.org', '/s/conferences/sosp/2026/', []),
    'ccs': ('www.sigsac.org', '/ccs/', []),
    's&p': ('sp2027.ieee-security.org', '/', []),
    'chi': ('chi2027.acm.org', '/', []),
    'sigcomm': ('conferences.sigcomm.org', '/sigcomm/2027/', []),
    'infocom': ('infocom2027.ieee-infocom.org', '/', []),
    'isca': ('www.iscaconf.org', '/', []),
    'micro': ('microarch.org', '/', []),
    'dac': ('dac.com', '/2027/', []),
    'sc': ('sc26.supercomputing.org', '/', []),
    'hpdc': ('hpdc.sci.utah.edu', '/2026/', []),
    'icde': ('icde2027.github.io', '/', []),
    'vldb': ('www.vldb.org', '/2027/', []),
    'aaai': ('aaai.org', '/conference/aaai/aaai-27/', []),
    'sigkdd': ('kdd2027.kdd.org', '/', []),
    'sigir': ('sigir2027.org', '/', []),
    'acm-mm': ('2026.acmmm.org', '/', []),
    'acm-siggraph': ('s2027.siggraph.org', '/', []),
    'ieee-vis': ('ieeevis.org', '/', []),
    'ieee-vr': ('ieeevr.org', '/2027/', []),
    'cscw': ('cscw.acm.org', '/2026/', []),
    'uist': ('uist.acm.org', '/2026/', []),
    'focs': ('sanjeevkhanna.org', '/', []),
    'soda': ('www.siam.org', '/', []),
    'lics': ('lics.siglog.org', '/', []),
    'cav': ('conferences.i-cav.org', '/2027/', []),
    'fm': ('www.fmeurope.org', '/', []),
    'rtss': ('2026.rtss.org', '/', []),
}
_TRACKS = {'asplos': {'Full Paper (Architecture)', 'Full Paper (Systems)', 'Full Paper (PL)'},
           'ndss': {'Technical Papers'},
           'sigmod': {'Research Paper', 'Industrial Track', 'Demonstration', 'PODS Paper'}}


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
    # Match by hostname. Path must either match exactly or the URL must be on the
    # same host (the adapter will validate edition identity from page content).
    if parsed.hostname != host:
        return None
    # For USENIX/IACR/specific-path adapters, also check path prefix
    if path and not parsed.path.rstrip('/').startswith(path.rstrip('/')):
        # Allow if the URL is the homepage and we have a known CFP path
        cfp_url = conference.get('cfp', '')
        if cfp_url:
            cfp_parsed = urlparse(cfp_url)
            if cfp_parsed.hostname == host and cfp_parsed.path.rstrip('/').startswith(path.rstrip('/')):
                pass  # Will use cfp_url instead
            else:
                return None
        else:
            return None
    parser = _Blocks()
    parser.feed(html)
    candidates, reasons = [], []
    identity = ' '.join(text for tag, text in parser.blocks if tag in {'title', 'h1'})
    slug_pat = slug.replace('-', r'[ -]?')
    edition_pattern = rf'\b{slug_pat}(?:\s+(?:Symposium|Conference))?\s+(?:2027|[\u2018\u2019\'"]27)\b'
    identity_years = set(re.findall(r'\b20\d{2}\b', identity))
    identity_short_years = set(re.findall(rf'\b{slug_pat}\s+[\u2018\u2019\'"](\d{2})\b', identity, re.I))
    if not re.search(edition_pattern, identity, re.I) or identity_years - {'2027'} or identity_short_years - {'27'}:
        return {'candidates': [], 'review_reasons': ['Official title or h1 does not unambiguously identify the expected 2027 edition']}
    usenix_slugs = {'nsdi', 'osdi', 'fast', 'atc', 'eurosys'}
    section_counts, field_counts = Counter(), Counter()
    policy = ''
    for _, text in parser.blocks:
        if slug == 'asplos' and 'All dates are expressed as AoE (Anywhere on Earth).' in text:
            policy = 'AoE'
        if slug == 'ndss' and text == 'All deadlines are 11:59 PM AoE (UTC-12).':
            policy = '11:59 PM AoE (UTC-12)'
        # USENIX conferences use AoE
        if slug in usenix_slugs and re.search(r'\bAoE\b|Anywhere on Earth|23:59\s*AoE', text, re.I):
            policy = 'AoE'
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
        if re.match(r'(Full paper submission|Complete paper submissions due|Paper titles and abstracts due|Abstract registrations due|Paper submissions due)', text, re.I):
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
        if slug in usenix_slugs and re.match(r'(Spring|Fall)\s+deadline', section, re.I):
            cycle_name = section.rstrip(':').replace(' deadline:', ' Cycle').replace(' deadline', ' Cycle')
        elif slug == 'osdi':
            cycle_name = '2027'
        else:
            cycle_name = section.rstrip(':').replace(' deadline', ' Cycle')
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
    # --- Eurocrypt: IACR template with h6 date headers ---
    if slug == 'eurocrypt':
        identity = ' '.join(text for tag, text in parser.blocks if tag in {'title', 'h1'})
        edition_pattern = r"\bEurocrypt\s+(?:2027|['']27)\b"
        identity_years = set(re.findall(r'\b20\d{2}\b', identity))
        if not re.search(edition_pattern, identity, re.I) or identity_years - {'2027'}:
            return {'candidates': [], 'review_reasons': ['Official title or h1 does not unambiguously identify the expected 2027 edition']}
        policy = ''
        for _, text in parser.blocks:
            if re.search(r'23:59\s+anywhere\s+on\s+earth|AoE', text, re.I):
                policy = 'AoE'
                break
        # Eurocrypt uses h6 tags for dates followed by event description
        prev_tag, prev_text = None, None
        for tag, text in parser.blocks:
            if tag == 'h6':
                date = parse_date(text)
                if date and parse_date(prev_text or '') is None:
                    # This h6 is a date header; next block should be the event
                    pass
                prev_tag, prev_text = tag, text
                continue
            if prev_tag == 'h6' and tag in ('p', 'li'):
                date = parse_date(prev_text)
                if date:
                    field = None
                    if re.search(r'submission|paper.*deadline|deadline.*paper', text, re.I):
                        field = 'deadline'
                    elif re.search(r'abstract|registration', text, re.I):
                        field = 'abstract'
                    elif re.search(r'notification|acceptance|decision', text, re.I):
                        field = 'notification'
                    if field:
                        value = date if field == 'notification' else parse_timestamp(prev_text + (' ' + policy if policy else ''), date)
                        reason = '' if value else 'No unambiguous timezone'
                        candidates.append({'year': 2027, 'cycle_name': '2027', 'track_name': None,
                                           'field': field, 'date': date, 'value': value,
                                           'evidence': f'{prev_text} — {text}',
                                           'applicable': not reason, 'reason': reason})
            prev_tag, prev_text = tag, text
        if not candidates:
            reasons.append('Eurocrypt page has no recognizable date/event pairs')
        return {'candidates': candidates, 'review_reasons': reasons}

    # --- MobiCom: dual-column HTML table with Summer/Winter ---
    if slug == 'mobicom':
        identity = ' '.join(text for tag, text in parser.blocks if tag in {'title', 'h1'})
        edition_pattern = r"\bMobiCom\s+(?:2027|['']27)\b"
        identity_years = set(re.findall(r'\b20\d{2}\b', identity))
        if not re.search(edition_pattern, identity, re.I) or identity_years - {'2027'}:
            return {'candidates': [], 'review_reasons': ['Official title or h1 does not unambiguously identify the expected 2027 edition']}
        policy = ''
        for _, text in parser.blocks:
            if re.search(r'23:59\s*AoE|Anywhere on Earth', text, re.I):
                policy = 'AoE'
                break
        # Parse blocks looking for Summer/Winter cycle labels and deadline items
        current_cycle = None
        for tag, text in parser.blocks:
            if re.match(r'\s*Summer\s*(Cycle|Deadline|Submission)?\s*$', text, re.I):
                current_cycle = 'Summer Cycle'
                continue
            if re.match(r'\s*Winter\s*(Cycle|Deadline|Submission)?\s*$', text, re.I):
                current_cycle = 'Winter Cycle'
                continue
            if not current_cycle:
                continue
            field = None
            if re.search(r'abstract\s+registration|paper\s+registration|abstract.*due', text, re.I):
                field = 'abstract'
            elif re.search(r'paper\s+submission|full\s+paper|submission\s+deadline', text, re.I):
                field = 'deadline'
            elif re.search(r'notification|acceptance|decision', text, re.I):
                field = 'notification'
            if not field:
                continue
            date = parse_date(text)
            if not date:
                continue
            value = date if field == 'notification' else parse_timestamp(text + (' ' + policy if policy else ''), date)
            reason = '' if value else 'No unambiguous timezone'
            if 'TBD' in text.upper() or 'tentative' in text.lower():
                reason = 'Date is TBD or tentative'
            candidates.append({'year': 2027, 'cycle_name': current_cycle, 'track_name': None,
                               'field': field, 'date': date, 'value': value,
                               'evidence': f'{current_cycle}: {text}',
                               'applicable': not reason, 'reason': reason})
        if not candidates:
            reasons.append('MobiCom page has no recognizable Summer/Winter deadlines')
        return {'candidates': candidates, 'review_reasons': reasons}

    # --- STOC: prose with inline AoE dates ---
    if slug == 'stoc':
        identity = ' '.join(text for tag, text in parser.blocks if tag in {'title', 'h1'})
        edition_pattern = r"\bSTOC\s+(?:2027|['']27)\b"
        identity_years = set(re.findall(r'\b20\d{2}\b', identity))
        if not re.search(edition_pattern, identity, re.I) or identity_years - {'2027'}:
            return {'candidates': [], 'review_reasons': ['Official title or h1 does not unambiguously identify the expected 2027 edition']}
        policy = ''
        for _, text in parser.blocks:
            if re.search(r'11:59\s*pm?\s*AoE|Anywhere on Earth', text, re.I):
                policy = 'AoE'
                break
        for tag, text in parser.blocks:
            if tag not in ('p', 'li'):
                continue
            field = None
            if re.search(r'(?:full\s+)?paper\s+submission|submission\s+deadline', text, re.I) and not re.search(r'workshop|tutorial|poster|demo', text, re.I):
                field = 'deadline'
            elif re.search(r'abstract\s+(?:submission|registration)|paper\s+registration', text, re.I):
                field = 'abstract'
            elif re.search(r'notification|acceptance|decision', text, re.I):
                field = 'notification'
            if not field:
                continue
            date = parse_date(text)
            if not date:
                continue
            value = date if field == 'notification' else parse_timestamp(text + (' ' + policy if policy else ''), date)
            reason = '' if value else 'No unambiguous timezone'
            candidates.append({'year': 2027, 'cycle_name': '2027', 'track_name': None,
                               'field': field, 'date': date, 'value': value,
                               'evidence': text,
                               'applicable': not reason, 'reason': reason})
        if not candidates:
            reasons.append('STOC page has no recognizable paper deadline in prose')
        return {'candidates': candidates, 'review_reasons': reasons}

    # --- SIGMOD: list-based with multiple rounds and tracks ---
    if slug == 'sigmod':
        identity = ' '.join(text for tag, text in parser.blocks if tag in {'title', 'h1'})
        if not re.search(r'SIGMOD\s+2027', identity, re.I):
            return {'candidates': [], 'review_reasons': ['Page does not identify SIGMOD 2027']}
        policy = ''
        for _, text in parser.blocks:
            if re.search(r'11:59\s*PM\s*AoE|Anywhere on Earth', text, re.I):
                policy = 'AoE'
                break
        current_section = None
        for tag, text in parser.blocks:
            if tag in ('h2', 'h3'):
                current_section = text.strip()
                continue
            if tag != 'li' or not current_section:
                continue
            field = None
            if re.search(r'abstract.*(?:deadline|submission|registration)', text, re.I):
                field = 'abstract'
            elif re.search(r'(?:paper|full paper|research).*submission|submission.*deadline', text, re.I) and not re.search(r'abstract', text, re.I):
                field = 'deadline'
            elif re.search(r'notification|acceptance|decision', text, re.I):
                field = 'notification'
            if not field:
                continue
            date = parse_date(text)
            if not date:
                continue
            # Determine cycle and track from section heading
            cycle_name = '2027'
            track_name = None
            if re.search(r'research.*round\s*(\d)', current_section, re.I):
                m = re.search(r'round\s*(\d)', current_section, re.I)
                cycle_name = f'Research Round {m.group(1)}'
                track_name = 'Research Paper'
            elif re.search(r'industrial', current_section, re.I):
                cycle_name = 'Industrial & Demo'
                track_name = 'Industrial Track'
            elif re.search(r'demonstration', current_section, re.I):
                cycle_name = 'Industrial & Demo'
                track_name = 'Demonstration'
            elif re.search(r'PODS', current_section, re.I):
                m = re.search(r'cycle\s*(\d)', current_section, re.I)
                cycle_name = f'PODS Cycle {m.group(1)}' if m else 'PODS'
                track_name = 'PODS Paper'
            value = date if field == 'notification' else parse_timestamp(text + (' ' + policy if policy else ''), date)
            reason = '' if value else 'No unambiguous timezone'
            candidates.append({'year': 2027, 'cycle_name': cycle_name, 'track_name': track_name,
                               'field': field, 'date': date, 'value': value,
                               'evidence': f'{current_section}: {text}',
                               'applicable': not reason, 'reason': reason})
        if not candidates:
            reasons.append('SIGMOD page has no recognizable deadlines')
        return {'candidates': candidates, 'review_reasons': reasons}

    # --- WWW (The Web Conf): Jekyll-style table or list ---
    if slug == 'www':
        identity = ' '.join(text for tag, text in parser.blocks if tag in {'title', 'h1'})
        if not re.search(r'(?:WWW|Web Conf|The Web)\s+2027', identity, re.I):
            return {'candidates': [], 'review_reasons': ['Page does not identify WWW 2027']}
        policy = ''
        for _, text in parser.blocks:
            if re.search(r'11:59\s*PM?\s*AoE|Anywhere on Earth|UTC-12', text, re.I):
                policy = 'AoE'
                break
        for tag, text in parser.blocks:
            if tag not in ('p', 'li', 'td'):
                continue
            field = None
            if re.search(r'(?:full\s+)?paper.*(?:submission|deadline)|research.*deadline', text, re.I) and not re.search(r'workshop|tutorial|demo|poster|short|industry', text, re.I):
                field = 'deadline'
            elif re.search(r'abstract.*(?:deadline|submission|registration)', text, re.I):
                field = 'abstract'
            elif re.search(r'short\s+paper.*(?:deadline|submission)', text, re.I):
                field = 'deadline'
            elif re.search(r'demo.*(?:deadline|submission)', text, re.I):
                field = 'deadline'
            elif re.search(r'workshop.*proposal.*(?:deadline|submission)', text, re.I):
                field = 'deadline'
            elif re.search(r'tutorial.*proposal.*(?:deadline|submission)', text, re.I):
                field = 'deadline'
            elif re.search(r'notification|acceptance|decision', text, re.I):
                field = 'notification'
            if not field:
                continue
            date = parse_date(text)
            if not date:
                continue
            track_name = None
            cycle_name = '2027'
            if re.search(r'short\s+paper', text, re.I):
                track_name = 'Short Paper'
            elif re.search(r'demo', text, re.I):
                track_name = 'Demo Paper'
            elif re.search(r'workshop.*proposal', text, re.I):
                track_name = 'Workshop Proposal'
            elif re.search(r'tutorial.*proposal', text, re.I):
                track_name = 'Tutorial Proposal'
            elif re.search(r'abstract', text, re.I):
                track_name = 'Full Paper (Research & Industry)'
            else:
                track_name = 'Full Paper (Research & Industry)'
            value = date if field == 'notification' else parse_timestamp(text + (' ' + policy if policy else ''), date)
            reason = '' if value else 'No unambiguous timezone'
            candidates.append({'year': 2027, 'cycle_name': cycle_name, 'track_name': track_name,
                               'field': field, 'date': date, 'value': value,
                               'evidence': text,
                               'applicable': not reason, 'reason': reason})
        if not candidates:
            reasons.append('WWW page has no recognizable deadlines')
        return {'candidates': candidates, 'review_reasons': reasons}

    # --- SOSP: USENIX-style but different URL pattern ---
    if slug == 'sosp':
        identity = ' '.join(text for tag, text in parser.blocks if tag in {'title', 'h1'})
        if not re.search(r'SOSP\s+(?:2026|2027)', identity, re.I):
            return {'candidates': [], 'review_reasons': ['Page does not identify SOSP']}
        policy = ''
        for _, text in parser.blocks:
            if re.search(r'\bAoE\b|Anywhere on Earth', text, re.I):
                policy = 'AoE'
                break
        for tag, text in parser.blocks:
            if tag != 'li':
                continue
            field = None
            if re.search(r'paper\s+submission|submission\s+deadline|full\s+paper', text, re.I) and not re.search(r'abstract', text, re.I):
                field = 'deadline'
            elif re.search(r'abstract.*(?:deadline|registration)', text, re.I):
                field = 'abstract'
            elif re.search(r'notification|acceptance', text, re.I):
                field = 'notification'
            if not field:
                continue
            date = parse_date(text)
            if not date:
                continue
            year = int(date[:4])
            value = date if field == 'notification' else parse_timestamp(text + (' ' + policy if policy else ''), date)
            reason = '' if value else 'No unambiguous timezone'
            candidates.append({'year': year, 'cycle_name': str(year), 'track_name': None,
                               'field': field, 'date': date, 'value': value,
                               'evidence': text,
                               'applicable': not reason, 'reason': reason})
        if not candidates:
            reasons.append('SOSP page has no recognizable deadlines')
        return {'candidates': candidates, 'review_reasons': reasons}

    # --- Generic catch-all for registered-but-unspecialized conferences ---
    # These conferences are registered in _SITES but don't have dedicated parsers.
    # Use enhanced block parsing similar to L3 but within the adapter framework.
    generic_slugs = set(_SITES.keys()) - usenix_slugs - {
        'asplos', 'ndss', 'eurocrypt', 'crypto', 'mobicom', 'stoc',
        'sigmod', 'www', 'sosp',
    }
    if slug in generic_slugs:
        identity = ' '.join(text for tag, text in parser.blocks if tag in {'title', 'h1'})
        # Extract year from page content
        years = set(re.findall(r'\b20\d{2}\b', identity))
        if not years:
            return {'candidates': [], 'review_reasons': ['Page does not identify conference year']}
        year = max(int(y) for y in years)
        
        # Detect timezone policy
        policy = ''
        for _, text in parser.blocks:
            if re.search(r'\bAoE\b|Anywhere on Earth|23:59\s*AoE', text, re.I):
                policy = 'AoE'
                break
            if re.search(r'11:59\s*PM?\s*(?:AoE|UTC-12)', text, re.I):
                policy = 'AoE'
                break
        
        # Parse deadline blocks
        for tag, text in parser.blocks:
            if tag not in ('p', 'li', 'td'):
                continue
            field = None
            if re.search(r'(?:full\s+)?paper\s+submission|submission\s+deadline|paper\s+deadline', text, re.I) and not re.search(r'\b(?:workshop|tutorial|poster|demo|short|industry|artifact)\b', text, re.I):
                field = 'deadline'
            elif re.search(r'abstract\s+(?:submission|registration|deadline)|paper\s+(?:title|registration)', text, re.I):
                field = 'abstract'
            elif re.search(r'notification|acceptance|decision', text, re.I) and not re.search(r'\b(?:early|reject|desk|rebuttal)\b', text, re.I):
                field = 'notification'
            if not field:
                continue
            date = parse_date(text)
            if not date or int(date[:4]) not in {year - 1, year}:
                continue
            value = date if field == 'notification' else parse_timestamp(text + (' ' + policy if policy else ''), date)
            reason = '' if value else 'No unambiguous timezone'
            candidates.append({'year': year, 'cycle_name': str(year), 'track_name': None,
                               'field': field, 'date': date, 'value': value,
                               'evidence': text,
                               'applicable': not reason, 'reason': reason})
        if not candidates:
            reasons.append(f'{slug} page has no recognizable deadlines (may not be posted yet)')
        return {'candidates': candidates, 'review_reasons': reasons}

    # --- Default: USENIX/ASPLOS/NDSS/NSDI list-based adapters ---
    expected_fields = ['abstract', 'deadline'] if slug in usenix_slugs else ['deadline']
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
