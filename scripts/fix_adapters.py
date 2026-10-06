#!/usr/bin/env python3
"""Fix official_adapters.py to support new USENIX conferences."""
import re

with open('scripts/official_adapters.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    # Fix the generic edition pattern (around line 80)
    if "edition_pattern = rf" in line and "{slug}" in line and "Symposium" in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent + "slug_pat = slug.replace('-', r'[ -]?')\n")
        new_lines.append(indent + 'edition_pattern = rf"\\b{slug_pat}(?:\\s+(?:Symposium|Conference))?\\s+(?:2027|[\\u2018\\u2019\'"]27)\\b"\n')
        continue
    # Fix identity_short_years pattern
    if "identity_short_years = set(re.findall" in line and "{slug}" in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent + 'identity_short_years = set(re.findall(rf"\\b{slug_pat}\\s+[\\u2018\\u2019\'"](\\d{2})\\b", identity, re.I))\n')
        continue
    new_lines.append(line)

with open('scripts/official_adapters.py', 'w') as f:
    f.writelines(new_lines)

print("Fixed official_adapters.py")
