#!/usr/bin/env python3
"""Extract official CFP evidence without mutating canonical data.

collect_conference reads maintained official URLs, follows at most one unique
same-host CFP link, and marks only unambiguous, timezone-qualified candidates as
applicable. A dedicated USENIX adapter preserves its explicit two-cycle schedule.

The legacy CLI remains a date-only candidate report for manual investigation:
    python scripts/scrape_cfp.py [conference ...] --output /tmp/cfp-candidates.yaml
    python scripts/scrape_cfp.py --list
"""

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from http.client import HTTPException
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml


if __package__:
    from .official_dates import parse_date, parse_timestamp as _timestamp
    from .official_adapters import extract_adapter
    from .official_tables import extract_table
else:
    from official_dates import parse_date, parse_timestamp as _timestamp
    from official_adapters import extract_adapter
    from official_tables import extract_table


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MAX_PAGE_BYTES = 4 * 1024 * 1024
CFP_CONFIGS = {
    "usenix-security": {
        "name": "USENIX Security",
        "year": 2027,
        "cfp_url": "https://www.usenix.org/conference/usenixsecurity27/call-for-papers",
        "track": "Research",
    },
    "ieee-sp": {
        "name": "IEEE S&P (Oakland)",
        "year": 2027,
        "cfp_url": "https://sp2027.ieee-security.org/cfps.html",
        "track": "Main",
    },
    "ccs": {
        "name": "CCS",
        "year": 2026,
        "cfp_url": "https://www.sigsac.org/ccs/CCS2026/cfp.html",
        "track": "Main",
    },
}


class ScrapeError(ValueError):
    """The page could not supply one unambiguous review candidate."""


def fetch_page(url):
    request = Request(url, headers={"User-Agent": "cfpctl-review-candidates/2.0"})
    try:
        with urlopen(request, timeout=30) as response:
            if response.geturl().split(":", 1)[0] != "https":
                raise ScrapeError("CFP page redirected to a non-HTTPS URL")
            data = response.read(MAX_PAGE_BYTES + 1)
            if len(data) > MAX_PAGE_BYTES:
                raise ScrapeError("CFP page exceeds the 4 MiB limit")
            charset = response.headers.get_content_charset() or "utf-8"
            return data.decode(charset)
    except (HTTPError, URLError, HTTPException, OSError, UnicodeError, LookupError) as error:
        raise ScrapeError(f"could not fetch {url}: {error}") from error


class DeadlineBlocks(HTMLParser):
    """Keep table rows together, but never join text across block boundaries."""

    boundaries = {
        "p", "li", "div", "section", "article", "header", "footer", "main",
        "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "dl", "dt", "dd",
        "table", "tbody", "thead", "tfoot", "br", "hr", "blockquote",
    }
    ignored = {"script", "style", "template", "noscript", "del", "s"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.text = []
        self.row_depth = 0
        self.ignored_tags = []

    def flush(self):
        value = " ".join(" ".join(self.text).split())
        if value:
            self.blocks.append(value)
        self.text = []

    def handle_starttag(self, tag, attrs):
        if self.ignored_tags:
            if tag in self.ignored:
                self.ignored_tags.append(tag)
            return
        if tag in self.ignored:
            # Deleted dates may be replaced nearby; reject the whole block
            # through the marker rather than guessing which revision applies.
            if tag in {"del", "s"}:
                self.text.append("[deleted content]")
            self.ignored_tags.append(tag)
        elif tag == "tr":
            self.flush()
            self.row_depth += 1
        elif not self.row_depth and tag in self.boundaries:
            self.flush()

    def handle_endtag(self, tag):
        if self.ignored_tags:
            if tag == self.ignored_tags[-1]:
                self.ignored_tags.pop()
            return
        if tag == "tr":
            self.flush()
            self.row_depth = max(0, self.row_depth - 1)
        elif not self.row_depth and tag in self.boundaries:
            self.flush()

    def handle_data(self, data):
        if not self.ignored_tags:
            self.text.append(data)


MONTHS = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)
DATE_PATTERN = re.compile(
    rf"\b(?:\d{{4}}-\d{{2}}-\d{{2}}|(?:{MONTHS})\.?\s+\d{{1,2}},?\s+\d{{4}}|"
    rf"\d{{1,2}}\s+(?:{MONTHS})\.?\s+\d{{4}})\b", re.IGNORECASE
)
LABEL_PATTERN = re.compile(
    r"^(?:(?:research|full)\s+)?(?:paper\s+submissions?\s+(?:deadline|due)|"
    r"paper\s+submissions?(?=\s*:)|"
    r"papers?\s+(?:deadline|due)|submission\s+(?:deadline|due))\s*[:–—-]?\s*",
    re.IGNORECASE,
)
DATE_PREFIX = re.compile(
    r"^(?:(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|"
    r"Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?),?\s*)?$", re.IGNORECASE
)
OTHER_DEADLINE = re.compile(
    r"\b(?:abstract|notification|acceptance|camera.ready|artifact|poster|workshop|demo|rebuttal)\b",
    re.IGNORECASE,
)


def parse_deadline(html, year):
    parser = DeadlineBlocks()
    parser.feed(html)
    parser.close()
    parser.flush()
    candidates = []
    for block in parser.blocks:
        label = LABEL_PATTERN.match(block)
        if not label:
            continue
        if OTHER_DEADLINE.search(block) or "[deleted content]" in block:
            raise ScrapeError("ambiguous paper-deadline block contains other deadlines or revisions")
        remainder = block[label.end():]
        matches = list(DATE_PATTERN.finditer(remainder))
        if len(matches) != 1 or not DATE_PREFIX.fullmatch(remainder[:matches[0].start()]):
            raise ScrapeError("paper deadline has no single explicit date in the same block")
        deadline = parse_date(remainder)
        if deadline is None or int(deadline[:4]) not in {year - 1, year}:
            raise ScrapeError(f"paper deadline is invalid or outside configured conference year {year}")
        candidates.append({"deadline_date": deadline, "source_text": block})
    if len(candidates) != 1:
        raise ScrapeError(f"expected one paper-deadline block, found {len(candidates)}; manual review required")
    return candidates[0]


def scrape_conference(slug, config):
    year = config["year"]
    if not isinstance(year, int) or not 2000 <= year <= 2100:
        raise ScrapeError("conference configuration requires an explicit valid year")
    extracted = parse_deadline(fetch_page(config["cfp_url"]), year)
    return {
        "slug": slug,
        "name": config["name"],
        "conference_year": year,
        "source_url": config["cfp_url"],
        "track_name": config["track"],
        **extracted,
    }


def validate_output_path(value):
    path = Path(value).expanduser().absolute()
    resolved = path.resolve()
    for candidate in (path, resolved):
        if candidate == Path("/app/data") or Path("/app/data") in candidate.parents:
            raise ValueError("candidate reports must not use the legacy /app/data directory")
        if candidate == DATA_DIR.resolve() or DATA_DIR.resolve() in candidate.parents:
            raise ValueError("candidate reports must be outside canonical data/")
    if resolved.suffix.lower() not in {".yaml", ".yml", ".json"}:
        raise ValueError("--output must have a .yaml, .yml, or .json extension")
    return resolved


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    contents = (json.dumps(report, ensure_ascii=False, indent=2) + "\n"
                if path.suffix.lower() == ".json"
                else yaml.safe_dump(report, allow_unicode=True, sort_keys=False, width=120))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(contents)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("conferences", nargs="*", help="configured conference slugs (default: all)")
    parser.add_argument("--list", action="store_true", help="list configured conferences without fetching")
    parser.add_argument("--output", help="required candidate report path outside canonical data/")
    args = parser.parse_args(argv)
    if args.list:
        for slug, config in CFP_CONFIGS.items():
            print(f"{slug:20} {config['year']} {config['cfp_url']}")
        return 0
    if not args.output:
        parser.error("--output is required; scraped candidates are never imported automatically")
    try:
        output = validate_output_path(args.output)
    except ValueError as error:
        parser.error(str(error))
    slugs = list(dict.fromkeys(args.conferences or CFP_CONFIGS))
    report = {"schema_version": 1, "status": "ok", "requires_review": True,
              "note": "Date-only candidates; verify conference, round, time and timezone before any manual import.",
              "candidates": [], "failures": []}
    for slug in slugs:
        try:
            if slug not in CFP_CONFIGS:
                raise ScrapeError("unknown conference")
            candidate = scrape_conference(slug, CFP_CONFIGS[slug])
            report["candidates"].append(candidate)
            print(f"{slug}: candidate {candidate['deadline_date']} (review required)")
        except ScrapeError as error:
            report["failures"].append({"slug": slug, "reason": str(error)})
            print(f"{slug}: ERROR: {error}", file=sys.stderr)
    if report["failures"]:
        report["status"] = "partial" if report["candidates"] else "failed"
    try:
        write_report(output, report)
    except OSError as error:
        print(f"ERROR writing candidate report: {error}", file=sys.stderr)
        return 1
    print(f"Wrote review report to {output}")
    return 1 if report["failures"] else 0


class PageMetadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headings = []
        self.links = []
        self.active_heading = None
        self.active_link = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {'title', 'h1', 'h2', 'h3', 'h4'}:
            self.active_heading = [tag, '']
        if tag == 'a':
            self.active_link = [attrs.get('href', ''), '']

    def handle_data(self, data):
        if self.active_heading is not None:
            self.active_heading[1] += data
        if self.active_link is not None:
            self.active_link[1] += data

    def handle_endtag(self, tag):
        if self.active_heading is not None and tag == self.active_heading[0]:
            self.headings.append(tuple(self.active_heading))
            self.active_heading = None
        if tag == 'a' and self.active_link is not None:
            self.links.append(tuple(self.active_link))
            self.active_link = None


def _candidate(year, cycle, track, field, block, aoe=False):
    date = parse_date(block)
    reason = None
    if date is None or '[deleted content]' in block or re.search(r'\b(?:TBD|TBA)\b|\btentative\b(?! non-blank abstract)|→|⇒', block, re.I):
        reason = 'deadline block lacks one unrevised, explicit valid date'
    elif int(date[:4]) not in {year - 1, year}:
        reason = 'date does not belong to the explicit conference edition'
    value = _timestamp(block, date, aoe) if date and reason is None else None
    if (field == 'notification' and date and reason is None and value is None
            and not re.search(r'\d{1,2}:\d{2}|\b(?:AM|PM|UTC|GMT|AoE|PST|PDT|PT|EST|EDT|CET|CEST)\b', block, re.I)):
        value = date  # Official calendar notification day, with no invented clock.
    if value is None and reason is None:
        reason = 'explicit time and unambiguous timezone are required'
    return dict(year=year, cycle_name=cycle, track_name=track, field=field,
                value=value, date=date, evidence=block, applicable=reason is None, reason=reason)


def _extract_official(html, url, conference):
    if isinstance(conference, str):
        conference = {'slug': conference}
    slug = conference.get('slug')
    metadata = PageMetadata()
    metadata.feed(html)
    for adapter in (extract_adapter, extract_table):
        adapted = adapter(html, url, conference)
        if adapted is not None:
            return adapted['candidates'], adapted['review_reasons'], metadata
    blocks = DeadlineBlocks()
    blocks.feed(html)
    blocks.flush()
    titles = ' '.join(text for tag, text in metadata.headings if tag in {'title', 'h1'})
    years = set(re.findall(r'\b20\d{2}\b', titles))
    usenix = slug == 'usenix-security' and re.fullmatch(
        r'https://www\.usenix\.org/conference/usenixsecurity\d{2}/call-for-papers/?', url)
    if usenix:
        edition = re.search(r"USENIX Security\s*['’](\d{2})", titles, re.I)
        if edition:
            years.add('20' + edition.group(1))
    if not years:
        # An edition in the maintained official URL is usable only when the page
        # also identifies that edition in its visible text (not a copyright year).
        from urllib.parse import urlsplit
        url_years = set(re.findall(r'(?<!\d)(20\d{2})(?!\d)', urlsplit(url).netloc + urlsplit(url).path))
        visible = ' '.join(blocks.blocks)
        if len(url_years) == 1:
            y = next(iter(url_years))
            name = re.escape(slug or '').replace(r'\-', r'[ -]?')
            if name and re.search(name + r"\s*['’ -]?" + y, visible, re.I):
                years = url_years
    if len(years) != 1:
        return [], ['page title must identify one explicit conference year'], metadata
    year = int(next(iter(years)))
    if usenix:
        if str(year)[-2:] != re.search(r'usenixsecurity(\d{2})', url).group(1):
            return [], ['page edition disagrees with the official URL'], metadata
        candidates = []
        active = False
        cycle = None
        for block in blocks.blocks:
            if block == 'Important Information (AoE)':
                active = True
                continue
            if not active:
                continue
            if block == 'Requirements':
                break
            if re.fullmatch(r'Cycle [12]', block):
                cycle = block
                continue
            field = None
            if block.startswith('Mandatory registration ') and ' due:' in block:
                field = 'abstract'
            elif block.startswith('Paper submissions due:'):
                field = 'deadline'
            elif block.startswith('Notification to authors:'):
                field = 'notification'
            if field and cycle:
                candidate = _candidate(year, cycle, 'Paper (incl. SoK)', field, block, aoe=True)
                candidate['evidence'] = f'Important Information (AoE) / {cycle}: {block}'
                candidates.append(candidate)
        expected = {(f'Cycle {n}', f) for n in (1, 2) for f in ('abstract', 'deadline', 'notification')}
        if {(c['cycle_name'], c['field']) for c in candidates} != expected or len(candidates) != 6:
            return candidates, ['USENIX schedule structure changed; expected two complete cycles'], metadata
        return candidates, [], metadata
    # Global timezone statements are authoritative only when they explicitly
    # quantify *all* deadlines/times. A timezone in unrelated prose is not used.
    scopes = [block for block in blocks.blocks if len(block) < 350 and
              re.search(r'\ball (?:the )?(?:deadlines|dates|times)\s+(?:are\b|refer to\b)', block, re.I) and
              re.search(r'\bAoE\b|Anywhere on Earth|\b(?:UTC|GMT)\b', block, re.I)]
    first_scope_time = _timestamp(scopes[0], '2026-01-01') if scopes else None
    timezone_scope = scopes[0] if scopes and all(
        t == scopes[0] or (first_scope_time is not None and _timestamp(t, '2026-01-01') == first_scope_time)
        for t in scopes) else ''
    candidates = []
    for block in blocks.blocks:
        field = _deadline_field(block)
        if not field:
            continue
        if len(block) > 600:
            continue
        evidence = block
        # Explicit per-row timezone always takes precedence over a general note.
        if timezone_scope and not re.search(r'\bAoE\b|Anywhere on Earth|\b(?:UTC|GMT|PST|PDT|PT|CET|CEST|EST|EDT|CST|CDT|ET|CT|BST|IST|JST)\b|[+-]\d{2}:\d{2}', block, re.I):
            evidence += ' [' + timezone_scope + ']'
        candidate = _candidate(year, None, None, field, evidence)
        if field == 'deadline' and OTHER_DEADLINE.search(block):
            candidate.update(applicable=False, reason='mixed deadline types in one block')
        candidates.append(candidate)
    # Mirrored responsive date tables often repeat the same facts. Collapse only
    # identical field/value pairs; distinct dates still require round mapping.
    unique = {}
    for candidate in candidates:
        key = (candidate['field'], candidate['value']) if candidate['applicable'] else (candidate['field'], candidate['evidence'])
        unique.setdefault(key, candidate)
    candidates = list(unique.values())
    reasons = []
    if not any(c['field'] == 'deadline' for c in candidates):
        reasons.append('no explicit paper deadline found')
    if len({c['field'] for c in candidates}) != len(candidates):
        reasons.append('multiple deadlines cannot be assigned to rounds safely')
    # Detect multi-round or multi-track structure from headings.
    round_headings = [text for tag, text in metadata.headings if re.search(
        r'\b(?:cycle|round|track)\s+(?:[12]|one|two)\b|(?:summer|winter|spring|fall|first|second)\s+(?:cycle|round|deadline)\b', text, re.I)]
    special_track_headings = [text for tag, text in metadata.headings if re.search(
        r'\b(?:journal|workshop|industry|industrial|poster|demo|short|resource)\s+(?:track|deadlines?|important dates|call for papers)\b', text, re.I) or re.fullmatch(
        r'\s*(?:workshops?|industry|industrial|journal|posters?|demos?|short papers?|doctoral consortium)\s*', text, re.I)]
    multi_round_text = any(re.search(r'\b(?:two|three|four|multiple)\s+(?:submission\s+)?(?:deadlines|rounds|cycles|periods)\b', b, re.I) for b in blocks.blocks)

    if round_headings or multi_round_text:
        # Multi-round page: requires an explicit adapter to safely assign deadlines.
        reasons.append('multiple-round or track-specific page requires an explicit adapter')
    elif special_track_headings:
        # A schedule explicitly scoped to a non-main track cannot be guessed into
        # the ordinary cycle. Navigation links and unrelated workshop headings alone
        # are not proof that the main submission schedule is ambiguous.
        reasons.append('multiple-round or track-specific page requires an explicit adapter')
    return candidates, reasons, metadata


def _deadline_field(block):
    """Recognize both label-first and date-first deadline table/list records."""
    text = ' '.join(block.split())
    paper = r'(?:full\s+)?papers?\s+(?:submissions?(?:\s+(?:deadline|due))?|deadline|due)|submission\s+deadline|submissions?'
    abstract = r'abstracts?(?:\s+(?:submission|registration))?(?:\s+(?:deadline|due))?'
    notification = r'(?:author\s+notification|notification(?:\s+(?:to authors|of acceptance))?)'
    for field, label in [('abstract', abstract), ('deadline', paper), ('notification', notification)]:
        if field == 'notification' and re.search(r'\b(?:early|reject(?:ion)?|desk|phase|rebuttal)\b', text, re.I):
            continue
        if field == 'deadline' and re.search(r'\bregistration\b', text, re.I):
            continue
        if re.match(r'^(?:' + label + r')\s*[:：–—-]?\s+(?:\d|[A-Z])', text, re.I):
            # Exclude narrative sentences such as "paper submissions must...".
            if re.search(r'\b(?:must|should|will|can|are|is|starts?|opens?)\b', text.split(':', 1)[0], re.I):
                continue
            if parse_date(text):
                return field
        if re.search(r'(?:' + label + r')\s*$', text, re.I) and parse_date(text):
            return field
    return None


def _discover_cfp_urls(metadata, url, conference):
    """Score and rank CFP-related links found on a page.

    Returns a sorted list of (score, target_url) tuples, highest score first.
    """
    from urllib.parse import urljoin, urlsplit, urldefrag
    links = {}
    current_years = set(re.findall(r'(?<!\d)20\d{2}(?!\d)', urlsplit(url).netloc + urlsplit(url).path))
    for href, label in metadata.links:
        if not href:
            continue
        target = urldefrag(urljoin(url, href))[0]
        text = re.sub(r'[^a-z0-9]+', ' ', (label + ' ' + href).lower())
        target_years = set(re.findall(r'(?<!\d)20\d{2}(?!\d)', urlsplit(target).netloc + urlsplit(target).path))
        if (urlsplit(target).scheme != 'https' or urlsplit(target).netloc != urlsplit(url).netloc
                or target == url or target.lower().endswith('.pdf')
                or re.search(r'\b(?:journal|workshop|industry|industrial|poster|demo|doctoral|tutorial|short|artifact|sponsor)\b', text)
                or (len(current_years) == 1 and target_years and current_years != target_years)):
            continue
        score = 0
        if re.search(r'\bcfp\b|\bcfpapers\b|call[ -]?for[ -]?papers|callforpapers|calls?/papers', label + ' ' + href, re.I):
            score = 2
            if re.search(r'\b(?:news|announcements?)\b', href, re.I):
                score = 1
        elif re.fullmatch(r'\s*(?:important )?(?:dates|dates and deadlines)\s*', label, re.I):
            score = 1
        elif re.search(r'\bsubmission\b|\bdeadlines?\b|\bimportant.dates?\b', label + ' ' + href, re.I):
            score = 1
        if score:
            links[target] = max(score, links.get(target, 0))
    return sorted(links.items(), key=lambda x: (-x[1], x[0]))


def _try_common_cfp_patterns(fetcher, url, conference):
    """Try well-known CFP URL patterns when link discovery fails.

    Returns (html, resolved_url) or (None, None). Never raises.
    """
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    slug = conference.get('slug', '')
    # Extract year from URL or conference cycles
    years = set(re.findall(r'(?<!\d)(20\d{2})(?!\d)', parsed.path))
    for cycle in conference.get('cycles', []):
        name = str(cycle.get('name', ''))
        y = re.match(r'(\d{4})', name)
        if y:
            years.add(y.group(1))
    if not years:
        return None, None
    latest_year = max(years)
    short_year = latest_year[-2:]

    # Common CFP URL patterns by host family
    patterns = []
    host = parsed.netloc.lower()

    # USENIX pattern
    if 'usenix.org' in host:
        conf_slug = slug.replace('-', '')
        patterns.append(f"{base}/conference/{conf_slug}{short_year}/call-for-papers")
        patterns.append(f"{base}/conference/{conf_slug}{latest_year}/call-for-papers")

    # ACM conference pattern (e.g., sigcomm, chi)
    if 'acm.org' in host or 'sig' in slug:
        patterns.append(f"{url.rstrip('/')}/cfp")
        patterns.append(f"{url.rstrip('/')}/call-for-papers")
        patterns.append(f"{url.rstrip('/')}/dates")

    # IEEE pattern
    if 'ieee' in host:
        patterns.append(f"{url.rstrip('/')}/cfps.html")
        patterns.append(f"{url.rstrip('/')}/call-for-papers")

    # Generic patterns
    stripped = url.rstrip('/')
    patterns.extend([
        f"{stripped}/cfp",
        f"{stripped}/call-for-papers",
        f"{stripped}/dates",
        f"{stripped}/important-dates",
        f"{stripped}/submission",
        f"{stripped}/deadlines",
    ])

    for candidate_url in patterns:
        if candidate_url == url:
            continue
        try:
            html = fetcher(candidate_url)
            # Quick sanity check: does the page contain deadline-like content?
            if re.search(r'(?:deadline|submission|due|notification)', html, re.I):
                return html, candidate_url
        except (ScrapeError, OSError):
            continue
    return None, None


def collect_conference(conference, fetcher=None):
    """Collect evidence from maintained official URLs; never mutate conference data.

    At most three HTTPS pages are requested (initial + one link follow + one
    pattern probe). Any ambiguity makes every candidate review-only, so a
    partially understood schedule cannot overwrite valid data.
    """
    from urllib.parse import urljoin, urlsplit, urldefrag
    fetcher = fetcher or fetch_page
    url = conference.get('cfp') or conference.get('homepage') or ''
    result = dict(slug=conference.get('slug'), source_url=url, status='review',
                  candidates=[], review_reasons=[], failure=None)
    if not isinstance(url, str) or urlsplit(url).scheme != 'https' or not urlsplit(url).hostname:
        result['review_reasons'] = ['maintained HTTPS official URL is required']
        return result
    try:
        html = fetcher(url)
        candidates, reasons, metadata = _extract_official(html, url, conference)
        if reasons or not any(c['field'] == 'deadline' and c['applicable'] for c in candidates):
            ranked_links = _discover_cfp_urls(metadata, url, conference)
            best = [target for target, score in ranked_links if score == ranked_links[0][1]] if ranked_links else []
            if len(best) == 1:
                url = best[0]
                result['source_url'] = url
                candidates, reasons, metadata = _extract_official(fetcher(url), url, conference)
            elif len(best) > 1:
                reasons.append('multiple official CFP links require review')
            # If link discovery failed AND no explicit cfp URL was configured,
            # try common URL patterns as last resort (at most one extra fetch).
            # Only probe when we have NO applicable deadline candidates at all;
            # structural reasons (e.g., multi-track page) mean the page was
            # understood and should not trigger blind URL guessing.
            if (not any(c['field'] == 'deadline' and c['applicable'] for c in candidates)
                    and not best and not conference.get('cfp')
                    and not reasons):
                pattern_html, pattern_url = _try_common_cfp_patterns(fetcher, url, conference)
                if pattern_html is not None:
                    url = pattern_url
                    result['source_url'] = url
                    candidates, reasons, metadata = _extract_official(pattern_html, url, conference)
        structural_reasons = list(reasons)
        reasons.extend(c['reason'] for c in candidates if c['reason'])
        # An optional notification with no time must not invalidate a separately
        # evidenced paper deadline. Round/edition ambiguity always blocks all.
        safe_partial = (not structural_reasons and any(c['field'] == 'deadline' and c['applicable'] for c in candidates)
                        and all(c['applicable'] or c['field'] == 'notification' for c in candidates))
        if reasons and not safe_partial:
            for candidate in candidates:
                candidate['applicable'] = False
                candidate['reason'] = candidate['reason'] or '; '.join(dict.fromkeys(reasons))
        result.update(candidates=candidates, review_reasons=list(dict.fromkeys(reasons)),
                      safe_partial=bool(reasons and safe_partial),
                      status='review' if reasons or not candidates else 'ok')
    except (ScrapeError, OSError, ValueError) as error:
        result.update(status='failed', failure=str(error))
    return result


if __name__ == "__main__":
    sys.exit(main())
