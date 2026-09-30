#!/usr/bin/env python3
"""
Convert ccfddl/ccf-deadlines YAML files to cfpctl format.

Downloads all conference YAML files from the ccfddl GitHub repo,
converts them to cfpctl format, and writes merged output files
per category.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

import yaml


# Category mappings: ccfddl sub -> (output filename, fields list)
CATEGORY_MAP = {
    "AI": ("ai.yaml", ["ai"]),
    "CG": ("graphics.yaml", ["vision", "graphics"]),
    "CT": ("theory.yaml", ["theory"]),
    "DB": ("database.yaml", ["database"]),
    "DS": ("systems.yaml", ["systems"]),
    "HI": ("hci.yaml", ["hci"]),
    "MX": ("interdisciplinary.yaml", ["interdisciplinary"]),
    "NW": ("network.yaml", ["network"]),
    "SC": ("security.yaml", ["security"]),
    "SE": ("software.yaml", ["software"]),
}

GITHUB_API_BASE = "https://api.github.com/repos/ccfddl/ccf-deadlines/contents/conference"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/ccfddl/ccf-deadlines/main/conference"


def fetch_json(url):
    """Fetch JSON from a URL."""
    req = Request(url, headers={"User-Agent": "cfpctl-convert/1.0"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_yaml(url):
    """Fetch and parse YAML from a URL."""
    req = Request(url, headers={"User-Agent": "cfpctl-convert/1.0"})
    with urlopen(req, timeout=30) as resp:
        content = resp.read().decode("utf-8")
    return yaml.safe_load(content)


def parse_timezone(tz_str):
    """Convert ccfddl timezone string to ISO 8601 offset suffix.
    
    Examples:
        'UTC-12' -> '-12:00'
        'UTC+8'  -> '+08:00'
        'UTC+5:30' -> '+05:30'
        None     -> '-12:00' (AoE default)
    """
    if not tz_str:
        return "-12:00"
    
    tz_str = tz_str.strip()
    
    # Match patterns like UTC-12, UTC+8, UTC+5:30, UTC-3:30
    m = re.match(r'^UTC([+-])(\d{1,2})(?::(\d{2}))?$', tz_str, re.IGNORECASE)
    if m:
        sign = m.group(1)
        hours = int(m.group(2))
        minutes = int(m.group(3)) if m.group(3) else 0
        return f"{sign}{hours:02d}:{minutes:02d}"
    
    # Fallback: try to handle other formats
    print(f"  WARNING: Unknown timezone format '{tz_str}', defaulting to -12:00")
    return "-12:00"


def convert_datetime(dt_str, tz_suffix):
    """Convert a ccfddl datetime string to ISO 8601 with offset.
    
    Input: '2026-07-28 23:59:59' or '2026-07-28'
    Output: '2026-07-28T23:59:59-12:00' or '2026-07-28T00:00:00-12:00'
    """
    if not dt_str:
        return None
    
    dt_str = str(dt_str).strip()
    
    # Skip TBD/unknown dates
    if dt_str.upper() in ("TBD", "TBA", "UNKNOWN", ""):
        return None
    
    # Already has timezone info? Check for T or +/- at end
    if 'T' in dt_str and ('+' in dt_str[10:] or dt_str.endswith('Z')):
        return dt_str
    
    # Parse date-only or datetime
    if ' ' in dt_str:
        # Has time component
        dt_str_clean = dt_str.replace(' ', 'T')
    else:
        # Date only
        dt_str_clean = dt_str + "T00:00:00"
    
    return f"{dt_str_clean}{tz_suffix}"


def is_past_deadline(deadline_str):
    """Check if a deadline is before the cutoff date."""
    if not deadline_str:
        return True
    
    try:
        # Parse the ISO datetime string
        # Handle various formats
        dl = str(deadline_str).strip()
        # Remove timezone suffix for comparison
        # Try parsing with various formats
        for fmt in [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]:
            try:
                dt = datetime.strptime(dl[:19], "%Y-%m-%dT%H:%M:%S")
                dt = dt.replace(tzinfo=timezone.utc)
                return dt < CUTOFF_DATE
            except ValueError:
                continue
        
        # Try date-only
        dt = datetime.strptime(dl[:10], "%Y-%m-%d")
        dt = dt.replace(tzinfo=timezone.utc)
        return dt < CUTOFF_DATE
    except Exception:
        return False


def convert_conference(data, category_fields):
    """Convert a single ccfddl conference entry to cfpctl format.
    
    Keeps ALL years as separate cycles (history + future).
    Returns a list of cfpctl conference dicts.
    """
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
    
    # Use latest conf for metadata (homepage, location)
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
    
    # Build cycles from ALL years (sorted by year ascending)
    sorted_confs = sorted(
        [c for c in confs if isinstance(c, dict)],
        key=lambda c: int(c.get("year", 0))
    )
    
    cycles = []
    for conf in sorted_confs:
        try:
            year = int(conf.get("year", 0))
        except (ValueError, TypeError):
            continue
        
        tz_suffix = parse_timezone(conf.get("timezone", ""))
        timelines = conf.get("timeline", [])
        if not timelines:
            continue
        
        for tl in timelines:
            if not isinstance(tl, dict):
                continue
            
            deadline_raw = tl.get("deadline")
            abstract_raw = tl.get("abstract_deadline")
            notification_raw = tl.get("notification")
            
            deadline_iso = convert_datetime(deadline_raw, tz_suffix)
            abstract_iso = convert_datetime(abstract_raw, tz_suffix)
            notification_iso = convert_datetime(notification_raw, tz_suffix) if notification_raw else None
            
            if not deadline_iso:
                continue
            
            cycle = {"name": str(year)}
            if abstract_iso:
                cycle["abstract"] = abstract_iso
            cycle["deadline"] = deadline_iso
            if notification_iso:
                cycle["notification"] = notification_iso
            cycles.append(cycle)
    
    if not cycles:
        return []
    
    entry = {
        "name": title,
        "slug": slug,
        "rank": {},
        "fields": list(category_fields),
        "homepage": homepage if homepage else "",
        "location": location,
        "cycles": cycles,
    }
    
    if ccf_rank:
        entry["rank"]["ccf"] = ccf_rank
    if core_rank:
        entry["rank"]["core"] = core_rank
    
    return [entry]


def get_category_files(category):
    """Get list of YAML files for a category from GitHub API."""
    url = f"{GITHUB_API_BASE}/{category}"
    try:
        items = fetch_json(url)
        files = []
        for item in items:
            name = item.get("name", "")
            if name.endswith(".yml") or name.endswith(".yaml"):
                files.append(name)
        return files
    except HTTPError as e:
        print(f"  ERROR: Failed to list {category}: HTTP {e.code}")
        return []
    except URLError as e:
        print(f"  ERROR: Failed to list {category}: {e.reason}")
        return []
    except Exception as e:
        print(f"  ERROR: Failed to list {category}: {e}")
        return []


def download_and_convert(category, filename, category_fields):
    """Download a single YAML file and convert it."""
    # Remove extension for URL construction
    base_name = filename.rsplit(".", 1)[0]
    url = f"{GITHUB_RAW_BASE}/{category}/{filename}"
    
    try:
        data = fetch_yaml(url)
    except HTTPError as e:
        print(f"  SKIP {filename}: HTTP {e.code}")
        return []
    except URLError as e:
        print(f"  SKIP {filename}: {e.reason}")
        return []
    except Exception as e:
        print(f"  SKIP {filename}: {e}")
        return []
    
    if data is None:
        return []
    
    # ccfddl files contain a list of conference entries
    if isinstance(data, list):
        results = []
        for entry in data:
            results.extend(convert_conference(entry, category_fields))
        return results
    elif isinstance(data, dict):
        return convert_conference(data, category_fields)
    else:
        return []


def main():
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(output_dir, exist_ok=True)
    
    total_stats = {}
    
    for category, (output_file, fields) in CATEGORY_MAP.items():
        print(f"\n{'='*60}")
        print(f"Processing category: {category} -> {output_file}")
        print(f"{'='*60}")
        
        # Get file listing
        print(f"  Fetching directory listing for {category}...")
        files = get_category_files(category)
        print(f"  Found {len(files)} YAML files")
        
        if not files:
            print(f"  No files found for {category}, skipping")
            total_stats[category] = 0
            continue
        
        all_conferences = []
        
        for filename in sorted(files):
            print(f"  Processing {filename}...", end=" ")
            converted = download_and_convert(category, filename, fields)
            if converted:
                all_conferences.extend(converted)
                print(f"OK ({len(converted)} conf(s))")
            else:
                print("skipped")
        
        # Deduplicate by slug (keep first occurrence)
        seen_slugs = set()
        unique_conferences = []
        for conf in all_conferences:
            slug = conf["slug"]
            if slug not in seen_slugs:
                seen_slugs.add(slug)
                unique_conferences.append(conf)
        
        # Sort by name
        unique_conferences.sort(key=lambda c: c["name"].lower())
        
        # Write output
        output_path = os.path.join(output_dir, output_file)
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(
                unique_conferences,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                width=120,
            )
        
        count = len(unique_conferences)
        total_stats[category] = count
        print(f"  Wrote {count} conferences to {output_path}")
    
    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    total = 0
    for category, count in total_stats.items():
        output_file = CATEGORY_MAP[category][0]
        print(f"  {category:4s} -> {output_file:30s}: {count:3d} conferences")
        total += count
    print(f"  {'':4s}    {'TOTAL':30s}: {total:3d} conferences")


if __name__ == "__main__":
    main()
