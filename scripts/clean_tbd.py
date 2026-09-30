#!/usr/bin/env python3
"""Remove conferences with TBD deadlines from YAML data files."""
import yaml
import os
import glob

for f in sorted(glob.glob("/app/data/*.yaml")):
    with open(f) as fh:
        data = yaml.safe_load(fh)
    if not data:
        continue
    cleaned = []
    for conf in data:
        valid_cycles = []
        for cyc in conf.get("cycles", []):
            dl = str(cyc.get("deadline", "")).upper()
            if dl.startswith("TBD") or dl.startswith("TBA"):
                continue
            valid_cycles.append(cyc)
        if valid_cycles:
            conf["cycles"] = valid_cycles
            cleaned.append(conf)
    with open(f, "w") as fh:
        yaml.dump(cleaned, fh, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)
    removed = len(data) - len(cleaned)
    if removed > 0:
        print(f"{os.path.basename(f)}: removed {removed} TBD entries, {len(cleaned)} remaining")
    else:
        print(f"{os.path.basename(f)}: OK ({len(cleaned)} conferences)")
