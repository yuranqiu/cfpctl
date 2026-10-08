#!/usr/bin/env python3
import sys; sys.path.insert(0, '/app')
from scripts.official_adapters import _SITES

# Check which slugs are registered
print("Registered adapter slugs:")
for s in sorted(_SITES.keys()):
    print(f"  {s}: {_SITES[s][0]}{_SITES[s][1]}")

# Check USENIX Security specifically
print("\nusenix-security in _SITES:", 'usenix-security' in _SITES)
print("nsdi in _SITES:", 'nsdi' in _SITES)

# The issue: usenix-security is NOT in _SITES!
# It was handled by the special USENIX code path in scrape_cfp.py, not by official_adapters.py
