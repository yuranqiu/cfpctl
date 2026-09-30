#!/usr/bin/env python3
"""
CFP Page Scraper — Extract track-level deadline information from conference websites.

This script scrapes CFP pages for known conferences and outputs YAML data
in cfpctl format with multi-track support.

Usage:
    python scrape_cfp.py                    # Scrape all configured conferences
    python scrape_cfp.py usenix-security    # Scrape specific conference
    python scrape_cfp.py --list             # List configured conferences
"""

import re
import sys
import yaml
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


# Conference CFP page configurations
# Each entry defines how to extract track deadlines from the conference website
CFP_CONFIGS = {
    "usenix-security": {
        "name": "USENIX Security",
        "cfp_url": "https://www.usenix.org/conferences/usenixsecurity27/call-for-papers",
        "homepage": "https://www.usenix.org/conferences/byname/108",
        "fields": ["security"],
        "rank": {"ccf": "A", "core": "A*"},
        "parser": "usenix",
    },
    "ieee-sp": {
        "name": "IEEE S&P (Oakland)",
        "cfp_url": "https://sp2027.ieee-security.org/cfps.html",
        "homepage": "https://sp.ieee.org",
        "fields": ["security"],
        "rank": {"ccf": "A", "core": "A*"},
        "parser": "ieee_sp",
    },
    "ccs": {
        "name": "CCS",
        "cfp_url": "https://www.sigsac.org/ccs/CCS2026/cfp.html",
        "homepage": "https://www.sigsac.org/ccs",
        "fields": ["security"],
        "rank": {"ccf": "A", "core": "A*"},
        "parser": "generic_table",
    },
}


def fetch_page(url):
    """Fetch a web page and return its text content."""
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; cfpctl-bot/1.0)"
    })
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (URLError, HTTPError) as e:
        print(f"  ERROR fetching {url}: {e}")
        return None


def parse_date(text):
    """Try to extract a date from text and return ISO format string."""
    if not text:
        return None
    text = text.strip()

    patterns = [
        (r'(\d{4}-\d{2}-\d{2})', '%Y-%m-%d'),
        (r'(\w+ \d{1,2},?\s*\d{4})', None),  # "June 3, 2026" or "June 3 2026"
        (r'(\d{1,2}\s+\w+\s+\d{4})', None),  # "3 June 2026"
    ]

    for pattern, fmt in patterns:
        m = re.search(pattern, text)
        if m:
            date_str = m.group(1)
            if fmt:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime('%Y-%m-%dT23:59:59-12:00')
                except ValueError:
                    continue
            else:
                for f in ['%B %d, %Y', '%B %d %Y', '%d %B %Y']:
                    try:
                        dt = datetime.strptime(date_str.replace(',', ''), f)
                        return dt.strftime('%Y-%m-%dT23:59:59-12:00')
                    except ValueError:
                        continue
    return None


def parse_usenix(html, config):
    """Parse USENIX Security CFP page for track deadlines."""
    tracks = []

    # Look for deadline sections - USENIX typically has structured deadlines
    # Pattern: look for "Abstract Deadline", "Paper Submission Deadline" etc.
    deadline_patterns = [
        (r'abstract.*?deadline.*?(\d{4}-\d{2}-\d{2}|\w+ \d+,?\s*\d{4})', 'abstract'),
        (r'(?:paper|full).*?(?:submission|deadline).*?(\d{4}-\d{2}-\d{2}|\w+ \d+,?\s*\d{4})', 'deadline'),
        (r'notification.*?(\d{4}-\d{2}-\d{2}|\w+ \d+,?\s*\d{4})', 'notification'),
    ]

    result = {}
    for pattern, key in deadline_patterns:
        m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if m:
            parsed = parse_date(m.group(1))
            if parsed:
                result[key] = parsed

    if result.get('deadline'):
        track = {"name": "Research", "deadline": result['deadline']}
        if result.get('abstract'):
            track['abstract'] = result['abstract']
        if result.get('notification'):
            track['notification'] = result['notification']
        tracks.append(track)

    return tracks


def parse_ieee_sp(html, config):
    """Parse IEEE S&P CFP page."""
    tracks = []
    result = {}

    # IEEE S&P typically lists deadlines in a table or list
    deadline_patterns = [
        (r'(?:abstract|registration).*?(?:deadline|due).*?(\d{4}-\d{2}-\d{2}|\w+ \d+,?\s*\d{4})', 'abstract'),
        (r'(?:full paper|submission|paper).*?(?:deadline|due).*?(\d{4}-\d{2}-\d{2}|\w+ \d+,?\s*\d{4})', 'deadline'),
        (r'(?:notification|acceptance).*?(\d{4}-\d{2}-\d{2}|\w+ \d+,?\s*\d{4})', 'notification'),
    ]

    for pattern, key in deadline_patterns:
        m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if m:
            parsed = parse_date(m.group(1))
            if parsed:
                result[key] = parsed

    if result.get('deadline'):
        track = {"name": "Main", "deadline": result['deadline']}
        if result.get('abstract'):
            track['abstract'] = result['abstract']
        if result.get('notification'):
            track['notification'] = result['notification']
        tracks.append(track)

    return tracks


def parse_generic_table(html, config):
    """Generic parser that looks for deadline tables/lists."""
    tracks = []
    result = {}

    # Generic patterns for any conference
    patterns = [
        (r'abstract\s*(?:deadline|due)[:\s]*(\d{4}-\d{2}-\d{2}|\w+ \d+,?\s*\d{4})', 'abstract'),
        (r'(?:paper\s*)?submission\s*(?:deadline|due)[:\s]*(\d{4}-\d{2}-\d{2}|\w+ \d+,?\s*\d{4})', 'deadline'),
        (r'notification[:\s]*(\d{4}-\d{2}-\d{2}|\w+ \d+,?\s*\d{4})', 'notification'),
    ]

    for pattern, key in patterns:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            parsed = parse_date(m.group(1))
            if parsed:
                result[key] = parsed

    if result.get('deadline'):
        track = {"name": "Main", "deadline": result['deadline']}
        if result.get('abstract'):
            track['abstract'] = result['abstract']
        if result.get('notification'):
            track['notification'] = result['notification']
        tracks.append(track)

    return tracks


PARSERS = {
    "usenix": parse_usenix,
    "ieee_sp": parse_ieee_sp,
    "generic_table": parse_generic_table,
}


def scrape_conference(slug, config):
    """Scrape a single conference and return cfpctl-format data."""
    print(f"\nScraping {config['name']} ({slug})...")
    print(f"  CFP URL: {config['cfp_url']}")

    html = fetch_page(config['cfp_url'])
    if not html:
        print(f"  SKIP: Could not fetch page")
        return None

    parser_name = config.get('parser', 'generic_table')
    parser = PARSERS.get(parser_name, parse_generic_table)

    tracks = parser(html, config)

    if not tracks:
        print(f"  SKIP: No deadlines found")
        return None

    entry = {
        "name": config["name"],
        "slug": slug,
        "rank": config.get("rank", {}),
        "fields": config.get("fields", []),
        "homepage": config.get("homepage", ""),
        "cfp": config["cfp_url"],
        "location": "TBD",
        "cycles": [{
            "name": str(datetime.now().year + 1),
            "tracks": tracks,
        }],
    }

    print(f"  OK: Found {len(tracks)} track(s)")
    for t in tracks:
        print(f"    - {t.get('name', 'Main')}: deadline={t.get('deadline', 'N/A')}")

    return entry


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == '--list':
            print("Configured conferences:")
            for slug, cfg in CFP_CONFIGS.items():
                print(f"  {slug:20s} {cfg['name']:30s} {cfg['cfp_url']}")
            return

        slugs = sys.argv[1:]
    else:
        slugs = list(CFP_CONFIGS.keys())

    results = []
    for slug in slugs:
        if slug not in CFP_CONFIGS:
            print(f"Unknown conference: {slug}")
            continue
        entry = scrape_conference(slug, CFP_CONFIGS[slug])
        if entry:
            results.append(entry)

    if results:
        output_file = "/app/data/scraped.yaml"
        with open(output_file, "w") as f:
            yaml.dump(results, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)
        print(f"\nWrote {len(results)} conferences to {output_file}")
    else:
        print("\nNo conferences scraped successfully.")


if __name__ == "__main__":
    main()
