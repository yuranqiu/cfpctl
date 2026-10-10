"""Shared layouts verified against official schedules on 2026-10-10."""
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


def extract_inspected(html, url, conference):
    slug = conference.get('slug')
    hosts = {'asiacrypt': 'asiacrypt.iacr.org', 'pkc': 'pkc.iacr.org', 'tcc': 'tcc.iacr.org',
             'dis': 'dis.acm.org', 'date': 'www.date-conference.com', 'icmr': 'www.icmr2027.org'}
    if slug not in hosts or urlsplit(url).hostname != hosts[slug]:
        return None
    tree = Tree(); tree.feed(html)
    nodes = list(tree.root.walk())
    clean = lambda n: ' '.join(n.text().split())
    years = title_years([(n.tag, clean(n)) for n in nodes if n.tag in ('title', 'h1')], conference)
    if len(years) != 1:
        return None
    year = int(next(iter(years)))
    policies = [clean(n) for n in nodes if (n.tag in ('p', 'figcaption') or n.has_class('customCardFooter')) and len(clean(n)) < 350
                and re.search(r'^(?:Note: )?(?:All deadlines|All dates and deadlines|Deadlines are specified)', clean(n), re.I)
                and re.search(r'AoE|Anywhere on Earth', clean(n), re.I)]
    policy = policies[0] if len(set(policies)) == 1 else ''
    pairs = []
    if slug in ('asiacrypt', 'pkc', 'tcc'):
        previous = None
        for n in nodes:
            if n.tag == 'h6':
                previous = clean(n)
            elif n.tag == 'p' and previous:
                label = clean(n)
                if re.match(r'Submission deadline\b', label, re.I):
                    pairs.append(('deadline', previous + ' ' + label))
                elif re.fullmatch(r'Final notification|Notification of acceptance', label, re.I):
                    pairs.append(('notification', previous + ' ' + label))
                previous = None
            elif re.fullmatch(r'h[1-5]', n.tag):
                previous = None
    else:
        active = slug != 'date'
        labels = {'dis': {'title and abstract': 'abstract', 'paper and pictorial submission': 'deadline', 'acceptance notification': 'notification'},
                  'date': {'abstract': 'abstract', 'final paper': 'deadline', 'notification of acceptance': 'notification'},
                  'icmr': {'regular papers (full & short)': 'deadline', 'notification of acceptance (regular, bni, demo, ds)': 'notification'}}[slug]
        for n in nodes:
            if n.tag != 'tr':
                continue
            cells = [clean(c) for c in n.children if isinstance(c, Node) and c.tag in ('td', 'th')]
            if slug == 'date' and cells and cells[0] in ('Research Papers - D, A, T and E tracks', 'Focus Sessions', 'Embedded Tutorials', 'Workshops', 'Late Breaking Results', 'Multi-Partner Projects', 'Young People Programme'):
                active = cells[0] == 'Research Papers - D, A, T and E tracks'
                continue
            if not active or len(cells) < 2:
                continue
            field = labels.get(cells[0].casefold())
            if field:
                pairs.append((field, ' '.join(cells)))
    if not pairs:
        return None
    candidates, reasons = [], []
    for field, evidence in pairs:
        date = parse_date(evidence)
        row_zone = bool(re.search(r'AoE|Anywhere on Earth|UTC|GMT|PST|PDT', evidence, re.I))
        scoped = evidence if row_zone or not policy else evidence + ' [' + policy + ']'
        value = date if field == 'notification' else parse_timestamp(scoped, date)
        reason = None
        if '[deleted content]' in evidence or re.search(r'TBA|TBD|tentative', evidence, re.I):
            reason = 'schedule contains revised or tentative content'
        elif not date or int(date[:4]) not in (year-1, year):
            reason = 'schedule lacks one valid date for this edition'
        elif not value:
            reason = 'schedule lacks explicit time and timezone'
        candidates.append(dict(year=year, cycle_name=str(year), track_name=None, field=field,
                               date=date, value=value, evidence=scoped, applicable=reason is None, reason=reason))
    if sum(c['field'] == 'deadline' for c in candidates) != 1:
        reasons.append('expected one main submission deadline in inspected layout')
    return dict(candidates=candidates, review_reasons=reasons)
