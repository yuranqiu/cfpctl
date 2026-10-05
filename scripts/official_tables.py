"""Scoped DOM adapters for the official virtual-conference date platform.

Only maintained conference hosts and edition-specific main-conference paths are
supported. Dates are paired within one date-row or corresponding table lines;
JavaScript countdown values are never executed or used as hidden evidence.
"""
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

if __package__:
    from .official_dates import parse_date, parse_timestamp
else:
    from official_dates import parse_date, parse_timestamp


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        if self.tag in {'script', 'style', 'template', 'noscript'}:
            return ''
        if self.tag in {'del', 's'}:
            return ' [deleted content] '
        if self.tag == 'br':
            return '\n'
        return ''.join(c if isinstance(c, str) else c.text() for c in self.children)

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def has_class(self, name):
        return name in self.attrs.get('class', '').split()


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _clean(text):
    return ' '.join(text.split())


def extract_table(html, url, conference):
    """Return a candidates/review_reasons result, or None for unrelated pages."""
    hosts = {'iclr': 'iclr.cc', 'aistats': 'virtual.aistats.org', 'eccv': 'eccv.ecva.net'}
    slug = conference.get('slug') if isinstance(conference, dict) else conference
    parsed = urlsplit(url)
    match = re.fullmatch(r'/Conferences/(20\d{2})(?:/(?:Dates|CallForPapers))?/?', parsed.path)
    if slug not in hosts or parsed.hostname != hosts[slug] or parsed.scheme != 'https' or not match:
        return None
    year = int(match[1])
    tree = Tree()
    tree.feed(html)
    pairs, reasons = [], []
    headings = [_clean(n.text()) for n in tree.root.walk() if n.tag in {'title', 'h1'}]
    heading_years = {int(y) for text in headings for y in re.findall(r'\b20\d{2}\b', text)}
    if heading_years != {year}:
        reasons.append('page title/h1 does not establish the URL conference edition')
    for row in tree.root.walk():
        if row.has_class('date-row'):
            labels = [n for n in row.walk() if n.has_class('date-title')]
            values = [n for n in row.walk() if n.has_class('date-time')]
            if len(labels) == len(values) == 1:
                pairs.append((_clean(labels[0].text()), _clean(values[0].text())))
            elif values or any(re.search(r'\b(?:Abstract|Paper|Submission).*Deadline\b', _clean(n.text()), re.I) for n in labels):
                reasons.append('date row has unmatched deadline label and value containers')
        elif slug == 'eccv' and row.tag == 'tr':
            cells = [n for n in row.children if isinstance(n, Node) and n.tag in {'td', 'th'}]
            if len(cells) != 2:
                continue
            # This platform renders parallel lists separated by <br> in two cells.
            def lines(cell):
                # Whitespace from formatting is not a semantic row separator.
                def flatten(node):
                    if node.tag == 'br':
                        return '\x00'
                    if node.tag in {'script', 'style', 'template', 'noscript'}:
                        return ''
                    if node.tag in {'del', 's'}:
                        return ' [deleted content] '
                    return ''.join(c if isinstance(c, str) else flatten(c) for c in node.children)
                return [_clean(v) for v in flatten(cell).split('\x00') if _clean(v)]
            labels, values = lines(cells[0]), lines(cells[1])
            if len(labels) == len(values):
                pairs.extend(zip(labels, values))
            elif any('Submission Deadline' in s for s in labels):
                reasons.append('date table has unmatched label and value lines')
    fields = {
        'Abstract Deadline': 'abstract', 'Abstract Submission Deadline': 'abstract',
        'Paper Deadline': 'deadline', 'Paper Submission Deadline': 'deadline',
        'Full Paper Submission Deadline (including all supplementary material)': 'deadline',
        'Paper Registration Deadline:': 'abstract', 'Submission Deadline:': 'deadline',
    }
    candidates = []
    for label, raw in pairs:
        field = fields.get(label)
        if field is None:
            continue
        # The platform explicitly abbreviates 20xx as 'xx in visible date cards.
        normalized = re.sub(r"\b([A-Za-z]+ \d{1,2}) ['’](\d{2})\b", r'\1 20\2', raw)
        normalized = re.sub(r'\bCET\b', 'UTC+01:00', normalized)
        normalized = re.sub(r'\bCEST\b', 'UTC+02:00', normalized)
        normalized = re.sub(r'\s+or\s*$', '', normalized)
        date = parse_date(normalized)
        value = parse_timestamp(normalized, date) if date else None
        reason = None
        if '[deleted content]' in raw or re.search(r'\b(?:TBD|TBA|tentative)\b|→|⇒', raw, re.I):
            reason = 'date row contains revised or tentative content'
        elif not date or int(date[:4]) not in {year - 1, year}:
            reason = 'date row lacks one valid date for this edition'
        elif value is None:
            reason = 'date row lacks explicit time and unambiguous timezone'
        candidates.append(dict(year=year, cycle_name=str(year), track_name=None,
                               field=field, value=value, date=date,
                               evidence=f'{label} {raw}', applicable=reason is None, reason=reason))
    for field in ('abstract', 'deadline'):
        matches = [c for c in candidates if c['field'] == field]
        if len(matches) > 1:
            reasons.append(f'multiple {field} rows in main conference date table')
    if candidates and not any(c['field'] == 'deadline' and c['applicable'] for c in candidates):
        reasons.append('main conference table lacks an unambiguous full paper deadline')
    if reasons:
        for candidate in candidates:
            candidate.update(applicable=False, reason='; '.join(reasons))
    return dict(candidates=candidates, review_reasons=reasons) if pairs or reasons else None
