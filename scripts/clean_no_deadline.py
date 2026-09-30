#!/usr/bin/env python3
"""Remove cycles without a deadline field, and conferences with no valid cycles."""
import yaml, os, glob

for f in sorted(glob.glob("/app/data/*.yaml")):
    with open(f) as fh:
        data = yaml.safe_load(fh)
    if not data:
        continue
    cleaned = []
    for conf in data:
        valid_cycles = [c for c in conf.get("cycles", []) if c.get("deadline")]
        if valid_cycles:
            conf["cycles"] = valid_cycles
            cleaned.append(conf)
    removed = len(data) - len(cleaned)
    if removed > 0:
        with open(f, "w") as fh:
            yaml.dump(cleaned, fh, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)
        print(f"{os.path.basename(f)}: removed {removed} entries without deadline, {len(cleaned)} remaining")
    else:
        print(f"{os.path.basename(f)}: OK ({len(cleaned)})")
