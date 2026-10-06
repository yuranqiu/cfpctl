#!/usr/bin/env python3
"""Create minimal fixture files for new adapters."""
import os

fixtures_dir = 'scripts/tests/fixtures/official_adapters'

# Read NSDI fixture as template
with open(os.path.join(fixtures_dir, 'nsdi.html')) as f:
    nsdi_html = f.read()

for slug, title in [('fast', 'FAST'), ('atc', 'ATC'), ('eurosys', 'EuroSys'), ('crypto', 'CRYPTO')]:
    html = nsdi_html.replace('NSDI', title).replace('nsdi', slug)
    path = os.path.join(fixtures_dir, f'{slug}.html')
    with open(path, 'w') as f:
        f.write(html)
    print(f'Created {path}')
