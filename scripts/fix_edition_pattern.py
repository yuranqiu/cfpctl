#!/usr/bin/env python3
"""Fix the edition pattern syntax error in official_adapters.py."""

with open('scripts/official_adapters.py', 'r') as f:
    content = f.read()

# Replace the broken lines with correct ones
old_line_81 = '    edition_pattern = rf"\\b{slug_pat}(?:\\s+(?:Symposium|Conference))?\\s+(?:2027|[\\u2018\\u2019\'"]27)\\b"'
new_line_81 = "    edition_pattern = rf'\\b{slug_pat}(?:\\s+(?:Symposium|Conference))?\\s+(?:2027|[\\u2018\\u2019\\'\"]27)\\b'"

old_line_83 = '    identity_short_years = set(re.findall(rf"\\b{slug_pat}\\s+[\\u2018\\u2019\'"](\\d{2})\\b", identity, re.I))'
new_line_83 = "    identity_short_years = set(re.findall(rf'\\b{slug_pat}\\s+[\\u2018\\u2019\\'\"](\\d{2})\\b', identity, re.I))"

content = content.replace(old_line_81, new_line_81)
content = content.replace(old_line_83, new_line_83)

with open('scripts/official_adapters.py', 'w') as f:
    f.write(content)

print("Fixed edition patterns")
