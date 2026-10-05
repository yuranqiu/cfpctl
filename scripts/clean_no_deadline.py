#!/usr/bin/env python3
"""Remove empty deadline records while preserving valid tracks and historical cycles."""

import argparse
from copy import deepcopy
import os
from pathlib import Path
import re
import sys
import tempfile

import yaml


DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PLACEHOLDER = re.compile(r"^(?:TBD|TBA|UNKNOWN)(?:\b|$)", re.IGNORECASE)


def is_placeholder(value):
    return isinstance(value, str) and bool(PLACEHOLDER.match(value.strip()))


def has_deadline(value):
    return value is not None and bool(str(value).strip()) and not is_placeholder(value)


def clean_data(data, *, placeholders_only=False):
    """Return a cleaned copy, validating container types before removing anything.

    No comparison with today's date occurs: historical deadlines are retained.
    In placeholder mode, missing deadlines are left for the missing-deadline
    cleaner. A usable track always keeps its parent cycle alive.
    """
    if data is None:
        return None
    if not isinstance(data, list):
        raise ValueError("expected a YAML list of conferences")
    cleaned = []
    for index, original in enumerate(data):
        if not isinstance(original, dict):
            raise ValueError(f"conference {index}: expected a mapping")
        conference = deepcopy(original)
        cycles = conference.get("cycles", [])
        if not isinstance(cycles, list):
            raise ValueError(f"conference {index}: cycles must be a list")
        valid_cycles = []
        for cycle_index, cycle in enumerate(cycles):
            if not isinstance(cycle, dict):
                raise ValueError(f"conference {index}, cycle {cycle_index}: expected a mapping")
            tracks = cycle.get("tracks", [])
            if not isinstance(tracks, list) or any(not isinstance(track, dict) for track in tracks):
                raise ValueError(f"conference {index}, cycle {cycle_index}: tracks must be a list of mappings")
            valid_tracks = [track for track in tracks if (
                not is_placeholder(track.get("deadline")) if placeholders_only
                else has_deadline(track.get("deadline"))
            )]
            if "tracks" in cycle:
                if valid_tracks:
                    cycle["tracks"] = valid_tracks
                else:
                    cycle.pop("tracks")
            deadline = cycle.get("deadline")
            usable_track = any(has_deadline(track.get("deadline")) for track in valid_tracks)
            if placeholders_only:
                if is_placeholder(deadline):
                    if not usable_track:
                        continue
                    cycle.pop("deadline")
                if tracks and not valid_tracks and not has_deadline(deadline):
                    continue
            else:
                if not has_deadline(deadline) and not usable_track:
                    continue
                if not has_deadline(deadline):
                    cycle.pop("deadline", None)
            valid_cycles.append(cycle)
        if valid_cycles:
            conference["cycles"] = valid_cycles
            cleaned.append(conference)
    return cleaned


def clean_directory(data_dir, *, placeholders_only=False):
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise ValueError(f"data directory does not exist: {data_dir}")
    files = sorted({*data_dir.glob("*.yaml"), *data_dir.glob("*.yml")})
    if not files:
        raise ValueError(f"no YAML data files in {data_dir}")
    changes = []
    # Validate every input before writing any file, so malformed input is not
    # silently discarded and a shape error cannot cause a partial cleanup.
    for path in files:
        with path.open(encoding="utf-8") as stream:
            original = yaml.safe_load(stream)
        cleaned = clean_data(original, placeholders_only=placeholders_only)
        if cleaned != original:
            changes.append((path, cleaned))
    for path, cleaned in changes:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                yaml.safe_dump(cleaned, stream, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)
            os.chmod(temporary, path.stat().st_mode & 0o777)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        print(f"{path.name}: cleaned deadline records; retained {len(cleaned)} conferences")
    print(f"Checked {len(files)} files; changed {len(changes)}")
    return len(changes)


def main(argv=None, *, placeholders_only=False):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                        help="YAML directory (default: repository data/, independent of working directory)")
    args = parser.parse_args(argv)
    try:
        clean_directory(args.data_dir, placeholders_only=placeholders_only)
    except (ValueError, OSError, yaml.YAMLError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
