#!/usr/bin/env python3
"""Audit scraper coverage across all conferences."""
import yaml, glob, sys
sys.path.insert(0, '/app')
from scripts.official_adapters import _SITES

total = 0
l1 = l2 = l3 = 0
verified = 0
with_tracks = 0
no_url = 0
l1_slugs = set(_SITES.keys())
l2_hosts = {'iclr.cc','virtual.aistats.org','eccv.ecva.net','neurips.cc','icml.cc',
            'cvpr.thecvf.com','2027.aclweb.org','2026.emnlp.org'}

for f in sorted(glob.glob('/app/data/*.yaml')):
    confs = yaml.safe_load(open(f)) or []
    for c in confs:
        total += 1
        slug = c.get('slug','')
        url = c.get('cfp') or c.get('homepage') or ''
        
        tier = 'L3'
        if slug in l1_slugs:
            tier = 'L1'
            l1 += 1
        elif any(h in url for h in l2_hosts):
            tier = 'L2'
            l2 += 1
        else:
            l3 += 1
        
        if not url or not url.startswith('https://'):
            no_url += 1
        if c.get('verified'):
            verified += 1
        if any('tracks' in cyc for cyc in c.get('cycles',[])):
            with_tracks += 1

print(f"Total conferences: {total}")
print(f"  L1 (dedicated adapter): {l1} ({l1*100//total}%)")
print(f"  L2 (table parser):      {l2} ({l2*100//total}%)")
print(f"  L3 (generic only):      {l3} ({l3*100//total}%)")
print(f"  No valid URL:           {no_url}")
print(f"  Verified:               {verified} ({verified*100//total}%)")
print(f"  Multi-track:            {with_tracks} ({with_tracks*100//total}%)")
print()
print("=== L3 conferences (need adapters or better generic parsing) ===")
for f in sorted(glob.glob('/app/data/*.yaml')):
    confs = yaml.safe_load(open(f)) or []
    for c in confs:
        slug = c.get('slug','')
        url = c.get('cfp') or c.get('homepage') or ''
        if slug in l1_slugs:
            continue
        if any(h in url for h in l2_hosts):
            continue
        ccf = c.get('rank',{}).get('ccf','')
        if ccf == 'A':
            print(f"  CCF-A: {slug:25s} {url[:70]}")
