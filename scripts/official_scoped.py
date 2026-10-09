"""Inspected schedules whose section identity is essential to interpreting rows."""
import re
from urllib.parse import urlsplit

if __package__:
    from .official_dates import parse_date, parse_timestamp
    from .official_tables import Tree, Node
    from .official_identity import title_years
else:
    from official_dates import parse_date, parse_timestamp
    from official_tables import Tree, Node
    from official_identity import title_years


def text(node):
    return ' '.join(node.text().split())


def extract_scoped(html, url, conference):
    slug = conference.get('slug')
    sites = {'www': ('www2027.thewebconf.org', '/important-dates'),
             'sigmod': ('2027.sigmod.org', '/calls_papers_important_dates.shtml'),
             'aaai': ('aaai.org', '/conference/aaai/aaai-27')}
    parsed = urlsplit(url)
    if slug not in sites or (parsed.hostname, parsed.path.rstrip('/')) != sites[slug]:
        return None
    tree = Tree()
    tree.feed(html)
    nodes = list(tree.root.walk())
    headings = [(n.tag, text(n)) for n in nodes if n.tag in ('title', 'h1')]
    if title_years(headings, conference) != {'2027'}:
        return dict(candidates=[], review_reasons=['page title must identify the expected conference edition'])
    rows, policy, active = [], '', None
    for n in nodes:
        value = text(n)
        if n.tag == 'p' and re.fullmatch(r'All deadlines are 11:59 PM (?:AoE\.|Anywhere on Earth \(AoE\) unless otherwise specified)', value, re.I):
            policy = '11:59 PM AoE'
        if slug == 'aaai':
            if re.fullmatch('h[1-6]', n.tag):
                active = value == 'Main Conference Timetable for Authors'
            if active and n.tag == 'p':
                field = ('abstract' if 'Abstracts due' in value else
                         'deadline' if 'Full papers due' in value else
                         'notification' if 'Notification of final acceptance or rejection' in value else None)
                if field:
                    rows.append(('2027', None, field, value))
        elif slug == 'www':
            if re.fullmatch('h[1-6]', n.tag):
                active = value == 'Research & Industry Track Papers'
            if active and n.tag == 'tr':
                cells = [text(c) for c in n.children if isinstance(c, Node) and c.tag in ('td', 'th')]
                if len(cells) != 2:
                    continue
                field = {'Abstract Submission': 'abstract', 'Paper Submission': 'deadline', 'Notification': 'notification'}.get(cells[0])
                if field:
                    rows.append(('2027', None, field, ' '.join(cells)))
        else:
            # Section labels are strong/i elements inside p, followed by a ul.
            # Walk order preserves the label before its rows even in invalid p/ul HTML.
            if n.tag == 'h2':
                active = None
            if n.tag in ('i', 'strong'):
                research = re.fullmatch(r'Research paper submission round ([1-4])', value, re.I)
                pods = re.fullmatch(r'PODS submission cycle ([12])', value, re.I)
                if research:
                    active = ('Research Round ' + research[1], 'Research Paper')
                elif pods:
                    active = ('PODS Cycle ' + pods[1], 'PODS Paper')
                elif re.search(r'Industrial|Demonstration|Tutorial|Workshop', value, re.I):
                    active = None
            if n.tag == 'li' and active:
                if re.search(r'revised paper|revision submission|final notification|feedback|camera.ready', value, re.I):
                    continue
                field = ('abstract' if re.search(r'Abstract Submission', value, re.I) else
                         'deadline' if re.search(r'(?:Full )?Paper Submission', value, re.I) else
                         'notification' if re.search(r'Initial notification|Notification of accept/reject/revision', value, re.I) else None)
                if field:
                    rows.append((*active, field, value))
    candidates, reasons = [], []
    for cycle, track, field, evidence in rows:
        date = parse_date(evidence)
        value = date if field == 'notification' else parse_timestamp(evidence + ' ' + policy, date)
        reason = None
        if '[deleted content]' in evidence or re.search(r'\bTBD|tentative\b', evidence, re.I):
            reason = 'date contains revised or tentative content'
        elif not date or int(date[:4]) not in (2026, 2027):
            reason = 'date lacks one valid explicit date for this edition'
        elif not value:
            reason = 'date lacks explicit time and timezone'
        candidates.append(dict(year=2027, cycle_name=cycle, track_name=track, field=field,
                               value=value, date=date, evidence=f'{cycle}: {evidence}' + (f' [{policy}]' if policy else ''),
                               applicable=reason is None, reason=reason))
    expected = {(f'Research Round {i}', 'Research Paper') for i in range(1, 5)} | {(f'PODS Cycle {i}', 'PODS Paper') for i in (1, 2)} if slug == 'sigmod' else {('2027', None)}
    for cycle, track in expected:
        for field in ('abstract', 'deadline', 'notification'):
            if sum(c['cycle_name'] == cycle and c['track_name'] == track and c['field'] == field for c in candidates) != 1:
                reasons.append(f'{cycle}: expected one {field} in its official section')
    return dict(candidates=candidates, review_reasons=reasons)
