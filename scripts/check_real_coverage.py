#!/usr/bin/env python3
"""Check real adapter coverage by testing each CCF-A conference through collect_conference."""
import yaml, glob, sys
sys.path.insert(0, '/app')
from scripts.scrape_cfp import collect_conference

# Build list of CCF-A conferences
ccf_a = []
for f in sorted(glob.glob('/app/data/*.yaml')):
    confs = yaml.safe_load(open(f)) or []
    for c in confs:
        if c.get('rank', {}).get('ccf') == 'A':
            ccf_a.append(c)

print(f"Testing {len(ccf_a)} CCF-A conferences...\n")

covered = []  # Would get applicable candidates from adapter/table
generic = []  # Falls through to L3 generic
no_url = []   # No valid URL
failed = []   # Fetch failed

for c in ccf_a:
    slug = c.get('slug', '')
    url = c.get('cfp') or c.get('homepage') or ''
    
    if not url or not url.startswith('https://'):
        no_url.append(slug)
        continue
    
    # Test with a mock fetcher that returns empty HTML (to test adapter matching without network)
    def mock_fetch(u):
        return '<title>Test</title>'
    
    try:
        result = collect_conference(c, fetcher=mock_fetch)
        # If the adapter matched (even with empty HTML), it means the URL pattern is recognized
        has_adapter = False
        
        # Check if any adapter claimed this URL
        from scripts.official_adapters import extract_adapter, _SITES
        from scripts.official_tables import extract_table
        from scripts.researchr_adapter import extract_researchr
        
        html = '<title>Test</title>'
        if extract_adapter(html, url, c) is not None:
            has_adapter = True
        elif extract_table(html, url, c) is not None:
            has_adapter = True
        elif extract_researchr(html, url, c) is not None:
            has_adapter = True
        
        if has_adapter:
            covered.append(slug)
        else:
            generic.append(slug)
    except Exception as e:
        failed.append((slug, str(e)[:60]))

print(f"=== ADAPTER COVERED ({len(covered)}/{len(ccf_a)}) ===")
for s in sorted(covered):
    print(f"  ✓ {s}")

print(f"\n=== L3 GENERIC ONLY ({len(generic)}/{len(ccf_a)}) ===")
for s in sorted(generic):
    print(f"  ~ {s}")

print(f"\n=== NO VALID URL ({len(no_url)}) ===")
for s in sorted(no_url):
    print(f"  ? {s}")

print(f"\n=== FAILED ({len(failed)}) ===")
for s, e in sorted(failed):
    print(f"  ✗ {s}: {e}")

pct = len(covered) * 100 // len(ccf_a) if ccf_a else 0
print(f"\nCoverage: {len(covered)}/{len(ccf_a)} ({pct}%) CCF-A conferences have dedicated adapters")
