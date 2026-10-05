#!/usr/bin/env python3
"""Historical one-time bootstrap from an already downloaded ccfddl snapshot.

This tool performs no network access. Daily maintenance uses update_official.py
and the existing cfpctl-data repository, never this bootstrap importer.
"""

import argparse
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sys
import tempfile
from zoneinfo import ZoneInfo

import yaml

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
REPO_ROOT = Path(__file__).resolve().parents[1]
# Keep existing public identifiers for different conferences sharing a title.
# ifip-sec is a historical identifier for the DS/SEC entry in this repository.
SLUG_ALIASES = {("SC", "fse"): "fse-crypto", ("DS", "sec"): "ifip-sec"}
UNKNOWN_DATES = {"", "TBD", "TBA", "UNKNOWN", "NONE"}


def parse_timezone(value):
    """Resolve offsets and PT using the deadline's actual daylight-saving date."""
    value = str(value or "AoE").strip()
    if value.upper() == "AOE":
        return timezone(timedelta(hours=-12))
    if value.upper() in {"UTC", "GMT", "Z"}:
        return timezone.utc
    if value.upper() == "PT":
        return ZoneInfo("America/Los_Angeles")
    match = re.fullmatch(r"(?:UTC)?([+-])(\d{1,2})(?::(\d{2}))?", value, re.I)
    if match:
        sign, hours, minutes = match.groups()
        hours, minutes = int(hours), int(minutes or 0)
        if hours > 23 or minutes > 59:
            raise ValueError(f"Invalid timezone: {value!r}")
        offset = timedelta(hours=hours, minutes=minutes)
        return timezone(offset if sign == "+" else -offset)
    raise ValueError(f"Unknown timezone: {value!r}")


def convert_datetime(value, tz):
    """Normalize valid dates without appending a second offset or time component."""
    if value is None or str(value).strip().upper() in UNKNOWN_DATES:
        return None
    parsed = datetime.fromisoformat(str(value).strip())
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=parse_timezone(tz) if isinstance(tz, str) else tz)
    return parsed.isoformat(timespec="seconds")


def convert_conference(data, category_fields, category=None):
    if not isinstance(data, dict):
        raise ValueError("Conference entry must be a mapping")
    rank = data.get("rank") or {}
    if not isinstance(rank, dict):
        raise ValueError("rank must be a mapping")
    if rank.get("ccf") not in {"A", "B", "C"}:
        return []
    title = str(data.get("title") or "").strip()
    if not title:
        raise ValueError("Ranked conference has no title")
    slug = title.lower().replace(" ", "-")
    slug = SLUG_ALIASES.get((category, slug), slug)
    editions = data.get("confs") or []
    if not isinstance(editions, list) or any(not isinstance(c, dict) for c in editions):
        raise ValueError(f"{title}: confs must be a list of mappings")
    if not editions:
        return []
    # Bad years are source errors, not a reason to publish a partial conference.
    editions = sorted(editions, key=lambda c: int(c["year"]))
    cycles = []
    for edition in editions:
        year = int(edition["year"])
        timelines = edition.get("timeline") or []
        if not isinstance(timelines, list):
            raise ValueError(f"{title} {year}: timeline must be a list")
        for timeline in timelines:
            if not isinstance(timeline, dict):
                raise ValueError(f"{title} {year}: timeline entry must be a mapping")
            tz = parse_timezone(edition.get("timezone"))
            deadline = convert_datetime(timeline.get("deadline"), tz)
            if not deadline:
                continue
            cycle = {"name": str(year)}
            abstract = convert_datetime(timeline.get("abstract_deadline"), tz)
            if abstract:
                cycle["abstract"] = abstract
            cycle["deadline"] = deadline
            notification = convert_datetime(timeline.get("notification"), tz)
            if notification:
                cycle["notification"] = notification
            if cycle not in cycles:
                cycles.append(cycle)
    if not cycles:
        return []
    latest = editions[-1]
    return [{
        "name": title, "slug": slug,
        "rank": {k: rank[k] for k in ("ccf", "core") if rank.get(k)},
        "fields": list(category_fields),
        "homepage": latest.get("link") or "",
        "location": latest.get("place") or "TBD",
        "cycles": cycles,
    }]


def deadline_dates(cycles):
    dates = []
    for cycle in cycles:
        for track in cycle.get("tracks") or [cycle]:
            if track.get("deadline"):
                dates.append(datetime.fromisoformat(str(track["deadline"])).date())
    return dates


def merge_cycles(existing, incoming, verified=False):
    """Replace ordinary year groups; retain manual groups and absent history.

For named manual rounds with no explicit edition year, upstream editions sharing
a submission calendar year are left to the curated records. The deliberately
conservative boundary also covers rescheduled deadlines. An explicit year name
allows precise edition matching; separate historical/future years can sync.
"""
    protected = [c for c in existing if verified or c.get("tracks")]
    protected_names = {str(c.get("name", "")) for c in protected}
    unnamed_dates = deadline_dates([
        c for c in protected if not re.fullmatch(r"\d{4}", str(c.get("name", "")))
    ])
    protected_submission_years = {d.year for d in unnamed_dates}
    groups = defaultdict(list)
    for cycle in incoming:
        groups[str(cycle.get("name", ""))].append(cycle)
    replace = {}
    for name, cycles in groups.items():
        if name in protected_names:
            continue
        dates = deadline_dates(cycles)
        if protected_submission_years.intersection(d.year for d in dates):
            continue
        replace[name] = cycles
    result = [deepcopy(c) for c in existing if str(c.get("name", "")) not in replace]
    for cycles in replace.values():
        result.extend(deepcopy(cycles))
    # Stable ordering for multi-round years; don't collapse identical year names.
    return sorted(result, key=lambda c: (str(c.get("name", "")), min(deadline_dates([c]), default=datetime.min.date())))


def merge_conference(existing, incoming):
    if existing is None:
        return deepcopy(incoming)
    merged = deepcopy(existing)
    for key in ("homepage", "location"):
        value = incoming.get(key)
        if value and value != "TBD" and not existing.get("verified"):
            merged[key] = deepcopy(value)
    if not existing.get("verified"):
        merged.setdefault("rank", {}).update({k: v for k, v in incoming.get("rank", {}).items() if v})
    merged["fields"] = list(dict.fromkeys(existing.get("fields", []) + incoming["fields"]))
    merged["cycles"] = merge_cycles(existing["cycles"], incoming["cycles"], existing.get("verified", False))
    return merged


def load_list(path):
    with path.open(encoding="utf-8") as stream:
        entries = yaml.safe_load(stream)
    if not isinstance(entries, list) or any(not isinstance(c, dict) for c in entries):
        raise ValueError(f"{path}: expected a list of conference mappings")
    return entries


def validate_data(outputs):
    """Fail before publishing malformed, empty, or duplicate data."""
    seen = {}
    for filename, conferences in outputs.items():
        if not conferences:
            raise ValueError(f"{filename}: empty category")
        for conference in conferences:
            slug = conference.get("slug")
            if not isinstance(slug, str) or not slug or slug != slug.lower():
                raise ValueError(f"{filename}: invalid slug {slug!r}")
            if slug in seen:
                raise ValueError(f"Duplicate slug {slug!r} in {seen[slug]} and {filename}")
            seen[slug] = filename
            for key in ("name", "fields", "homepage", "cycles"):
                if not conference.get(key):
                    raise ValueError(f"{slug}: missing {key}")
            if conference.get("rank", {}).get("ccf", "") not in {"", "A", "B", "C"}:
                raise ValueError(f"{slug}: invalid CCF rank")
            for cycle in conference["cycles"]:
                tracks = cycle.get("tracks") or [cycle]
                for track in tracks:
                    if not track.get("deadline"):
                        raise ValueError(f"{slug}: cycle/track missing deadline")
                    for field in ("abstract", "deadline", "notification"):
                        if track.get(field) and not convert_datetime(track[field], timezone(timedelta(hours=-12))):
                            raise ValueError(f"{slug}: invalid {field}")


def refresh(source_dir, output_dir):
    source_dir, output_dir = Path(source_dir), Path(output_dir)
    # Preserve curated/local-only entries, and index globally to retain file placement.
    existing = {}
    locations = {}
    for category, (filename, _) in CATEGORY_MAP.items():
        path = output_dir / filename
        existing[filename] = load_list(path) if path.exists() else []
        for conference in existing[filename]:
            slug = conference["slug"]
            if slug in locations:
                raise ValueError(f"Duplicate existing slug {slug!r}")
            locations[slug] = filename
    merged = {name: {c["slug"]: c for c in entries} for name, entries in existing.items()}
    upstream_slugs = set()
    for category, (filename, fields) in CATEGORY_MAP.items():
        files = sorted(p for p in (source_dir / category).glob("*") if p.suffix in {".yaml", ".yml"})
        if not files:
            raise ValueError(f"Missing or empty upstream category: {category}")
        count = 0
        for path in files:
            try:
                entries = load_list(path)
                if not entries:
                    raise ValueError("empty upstream file")
                for entry in entries:
                    for conference in convert_conference(entry, fields, category):
                        slug = conference["slug"]
                        if slug in upstream_slugs:
                            raise ValueError(f"Duplicate upstream slug {slug!r}; add an explicit category alias")
                        upstream_slugs.add(slug)
                        destination = locations.get(slug, filename)
                        merged[destination][slug] = merge_conference(merged[destination].get(slug), conference)
                        count += 1
            except (ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
                raise ValueError(f"{path}: {exc}") from exc
        if not count:
            raise ValueError(f"No usable conferences in upstream category: {category}")
        print(f"{category}: {len(files)} source files, {count} conferences")
    outputs = {name: sorted(entries.values(), key=lambda c: c["name"].lower()) for name, entries in merged.items()}
    # Include other YAML files in global validation, e.g. a leftover scraped.yaml.
    extras = {p.name: load_list(p) for p in output_dir.glob("*.yaml") if p.name not in outputs}
    validate_data({**outputs, **extras})
    output_dir.mkdir(parents=True, exist_ok=True)
    # Serialize all files before replacing any; unchanged YAML keeps its formatting.
    pending = {name: yaml.safe_dump(entries, allow_unicode=True, sort_keys=False, width=120)
               for name, entries in outputs.items() if entries != existing[name]}
    with tempfile.TemporaryDirectory(prefix=".cfpctl-", dir=output_dir) as staging:
        for name, content in pending.items():
            (Path(staging) / name).write_text(content, encoding="utf-8")
        for name in pending:
            (Path(staging) / name).replace(output_dir / name)
    print(f"Updated {len(pending)} files; {sum(map(len, outputs.values()))} conferences retained")
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True,
                        help="Previously downloaded conference/ snapshot; historical bootstrap only")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="Explicit bootstrap destination; never used by daily updates")
    args = parser.parse_args(argv)
    try:
        refresh(args.source_dir, args.output_dir)
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        print(f"Update failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
