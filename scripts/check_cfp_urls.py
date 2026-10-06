#!/usr/bin/env python3
"""Check which CCF-A conference CFP URLs are live and have dates."""
import yaml, glob, re
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

ccf_a_slugs = set()
for f in sorted(glob.glob('/app/data/*.yaml')):
    confs = yaml.safe_load(open(f)) or []
    for c in confs:
        if c.get('rank', {}).get('ccf') == 'A':
            ccf_a_slugs.add(c['slug'])

print(f"Checking {len(ccf_a_slugs)} CCF-A conferences...\n")

results = {'live': [], 'no_dates': [], 'dead': [], 'no_url': []}

for f in sorted(glob.glob('/app/data/*.yaml')):
    confs = yaml.safe_load(open(f)) or []
    for c in confs:
        slug = c.get('slug', '')
        if slug not in ccf_a_slugs:
            continue
        url = c.get('cfp') or c.get('homepage') or ''
        if not url or not url.startswith('http'):
            results['no_url'].append(slug)
            continue
        try:
            req = Request(url, headers={'User-Agent': 'cfpctl-check/1.0'})
            with urlopen(req, timeout=15) as resp:
                html = resp.read(500000).decode('utf-8', errors='replace')
                has_deadline = bool(re.search(r'(?:deadline|submission|due|important.date)', html, re.I))
                has_date = bool(re.search(r'\b20(?:26|27)\b', html))
                if has_deadline and has_date:
                    results['live'].append((slug, url))
                else:
                    results['no_dates'].append((slug, url))
        except Exception as e:
            results['dead'].append((slug, str(e)[:80]))

print(f"=== LIVE with dates ({len(results['live'])}) ===")
for slug, url in sorted(results['live']):
    print(f"  ✓ {slug:25s} {url[:70]}")

print(f"\n=== NO DATES ({len(results['no_dates'])}) ===")
for slug, url in sorted(results['no_dates']):
    print(f"  ~ {slug:25s} {url[:70]}")

print(f"\n=== DEAD/ERROR ({len(results['dead'])}) ===")
for slug, err in sorted(results['dead']):
    print(f"  ✗ {slug:25s} {err}")

print(f"\n=== NO URL ({len(results['no_url'])}) ===")
for slug in sorted(results['no_url']):
    print(f"  ? {slug}")
