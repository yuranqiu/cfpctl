#!/usr/bin/env python3
"""Download remaining categories (HI, NW, MX) using raw GitHub URLs directly, bypassing API."""
import yaml
import os
import re
import json
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

CUTOFF_DATE = datetime(2026, 9, 1, tzinfo=timezone.utc)

# These are the file lists we already fetched via web_fetch earlier
CATEGORY_FILES = {
    "HI": {
        "output": "hci.yaml",
        "fields": ["hci"],
        "files": [
            "assets.yml","chi.yml","collaboratecom.yml","cscw.yml","cscwd.yml",
            "dis.yml","ecscw.yml","gi.yml","group.yml","hicss.yml",
            "icmi.yml","icwsm.yml","idc.yml","interact.yml","iss.yml",
            "iui.yml","mobilehci.yml","percom.yml","ubicomp.yml","uic.yml",
            "uist.yml","whc.yml"
        ]
    },
    "NW": {
        "output": "network.yaml",
        "fields": ["network"],
        "files": [
            "apnet.yml","conext.yml","forte.yml","globecom.yml","hotnets.yml",
            "icc.yml","icccn.yml","icnp.yml","imc.yml","infocom.yml",
            "ipsn.yml","iscc.yml","iwqos.yml","lcn.yml","mmsys.yml",
            "mobicom.yml","mobihoc.yml","mobisys.yml","msn.yml","mswim.yml",
            "networking.yml","nossdav.yml","nsdi.yml","secon.yml","sensys.yml",
            "sigcomm.yml","wasa.yml","wcnc.yml","wicon.yml","wowmom.yml"
        ]
    },
    "MX": {
        "output": "interdisciplinary.yaml",
        "fields": ["interdisciplinary"],
        "files": [
            "aft.yml","apbc.yml","bibm.yml","bigdata.yml","bis.yml",
            "cloud.yml","cogsci.yml","emsoft.yml","icaif.yml","icic.yml",
            "isbra.yml","ismb.yml","miccai.yml","mlsys.yml","recomb.yml",
            "rtss.yml","sai-computing.yml","sigcse.yml","sigspatial.yml","smc.yml",
            "wine.yml","www.yml"
        ]
    }
}

RAW_BASE = "https://raw.githubusercontent.com/ccfddl/ccf-deadlines/main/conference"


def fetch_yaml(url):
    req = Request(url, headers={"User-Agent": "cfpctl-convert/1.0"})
    with urlopen(req, timeout=30) as resp:
        return yaml.safe_load(resp.read().decode("utf-8"))


def parse_timezone(tz_str):
    if not tz_str:
        return "-12:00"
    tz_str = tz_str.strip()
    m = re.match(r'^UTC([+-])(\d{1,2})(?::(\d{2}))?$', tz_str, re.IGNORECASE)
    if m:
        sign, hours, minutes = m.group(1), int(m.group(2)), int(m.group(3) or 0)
        return f"{sign}{hours:02d}:{minutes:02d}"
    return "-12:00"


def convert_datetime(dt_str, tz_suffix):
    if not dt_str:
        return None
    dt_str = str(dt_str).strip()
    if dt_str.upper() in ("TBD", "TBA", "UNKNOWN", ""):
        return None
    if 'T' in dt_str and ('+' in dt_str[10:] or dt_str.endswith('Z')):
        return dt_str
    if ' ' in dt_str:
        dt_str_clean = dt_str.replace(' ', 'T')
    else:
        dt_str_clean = dt_str + "T00:00:00"
    return f"{dt_str_clean}{tz_suffix}"


def is_past(deadline_str):
    if not deadline_str:
        return True
    try:
        dl = str(deadline_str).strip()
        dt = datetime.strptime(dl[:19], "%Y-%m-%dT%H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc)
        return dt < CUTOFF_DATE
    except Exception:
        return False


def convert_conference(data, fields):
    if not isinstance(data, dict):
        return []
    rank_info = data.get("rank", {})
    if not isinstance(rank_info, dict):
        return []
    ccf_rank = rank_info.get("ccf")
    if not ccf_rank or ccf_rank not in ("A", "B", "C"):
        return []
    core_rank = rank_info.get("core")
    title = data.get("title", "").strip()
    if not title:
        return []
    slug = title.lower().replace(" ", "-")
    confs = data.get("confs", [])
    if not confs:
        return []
    latest_conf = None
    latest_year = -1
    for conf in confs:
        if not isinstance(conf, dict):
            continue
        try:
            year = int(conf.get("year", 0))
        except (ValueError, TypeError):
            continue
        if year > latest_year:
            latest_year = year
            latest_conf = conf
    if latest_conf is None:
        return []
    homepage = latest_conf.get("link", "")
    location = latest_conf.get("place", "TBD") or "TBD"
    tz_suffix = parse_timezone(latest_conf.get("timezone", ""))
    timelines = latest_conf.get("timeline", [])
    if not timelines:
        return []
    cycles = []
    for tl in timelines:
        if not isinstance(tl, dict):
            continue
        deadline_iso = convert_datetime(tl.get("deadline"), tz_suffix)
        abstract_iso = convert_datetime(tl.get("abstract_deadline"), tz_suffix)
        notification_iso = convert_datetime(tl.get("notification"), tz_suffix) if tl.get("notification") else None
        if deadline_iso and is_past(deadline_iso):
            continue
        cycle = {"name": str(latest_year)}
        if abstract_iso:
            cycle["abstract"] = abstract_iso
        if deadline_iso:
            cycle["deadline"] = deadline_iso
        if notification_iso:
            cycle["notification"] = notification_iso
        cycles.append(cycle)
    if not cycles:
        return []
    entry = {
        "name": title, "slug": slug,
        "rank": {},
        "fields": list(fields),
        "homepage": homepage or "",
        "location": location,
        "cycles": cycles,
    }
    if ccf_rank:
        entry["rank"]["ccf"] = ccf_rank
    if core_rank:
        entry["rank"]["core"] = core_rank
    return [entry]


def main():
    output_dir = "/app/data"
    total_stats = {}

    for category, info in CATEGORY_FILES.items():
        print(f"\n{'='*60}")
        print(f"Processing {category} -> {info['output']}")
        print(f"{'='*60}")

        files = info["files"]
        if not files:
            # Try to get MX file list from GitHub API
            try:
                url = f"https://api.github.com/repos/ccfddl/ccf-deadlines/contents/conference/{category}"
                req = Request(url, headers={"User-Agent": "cfpctl-convert/1.0"})
                with urlopen(req, timeout=30) as resp:
                    items = json.loads(resp.read().decode("utf-8"))
                files = [i["name"] for i in items if i["name"].endswith((".yml", ".yaml"))]
                print(f"  Discovered {len(files)} files via API")
            except Exception as e:
                print(f"  Could not discover files: {e}")
                total_stats[category] = 0
                continue

        all_confs = []
        for filename in sorted(files):
            url = f"{RAW_BASE}/{category}/{filename}"
            try:
                data = fetch_yaml(url)
            except Exception as e:
                print(f"  SKIP {filename}: {e}")
                continue
            if data is None:
                continue
            results = []
            if isinstance(data, list):
                for entry in data:
                    results.extend(convert_conference(entry, info["fields"]))
            elif isinstance(data, dict):
                results.extend(convert_conference(data, info["fields"]))
            if results:
                all_confs.extend(results)
                print(f"  OK {filename} ({len(results)})")
            else:
                print(f"  skip {filename}")

        # Deduplicate
        seen = set()
        unique = []
        for c in all_confs:
            if c["slug"] not in seen:
                seen.add(c["slug"])
                unique.append(c)
        unique.sort(key=lambda c: c["name"].lower())

        outpath = os.path.join(output_dir, info["output"])
        with open(outpath, "w", encoding="utf-8") as f:
            yaml.dump(unique, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)

        total_stats[category] = len(unique)
        print(f"  Wrote {len(unique)} conferences to {outpath}")

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    total = 0
    for cat, count in total_stats.items():
        print(f"  {cat}: {count} conferences")
        total += count
    print(f"  TOTAL NEW: {total}")


if __name__ == "__main__":
    main()
