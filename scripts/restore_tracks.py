#!/usr/bin/env python3
"""Restore multi-track data that was lost during full_refresh merge."""
import yaml, os

DATA_DIR = "/app/data"

# Patches: slug -> {file, cycles_to_replace}
# Only replace the LATEST cycle(s) with track data; keep historical cycles as-is
PATCHES = {
    "chi": {
        "file": "hci.yaml",
        "patch_cycles": [
            {"name": "2027", "tracks": [
                {"name": "Full Papers", "deadline": "2026-09-10T23:59:59-12:00", "notification": "2026-12-17"},
                {"name": "Panels", "deadline": "2026-11-19T23:59:59-12:00", "notification": "2027-01-14"},
                {"name": "Workshops (Organizer)", "deadline": "2026-10-01T23:59:59-12:00", "notification": "2026-11-19"},
                {"name": "Posters", "deadline": "2027-01-21T23:59:59-12:00", "notification": "2027-02-18"},
                {"name": "Interactive Demos", "deadline": "2027-01-21T23:59:59-12:00", "notification": "2027-02-18"},
                {"name": "Student Research Competition", "deadline": "2027-01-21T23:59:59-12:00", "notification": "2027-02-18"},
                {"name": "Digital Experience Competition", "deadline": "2026-12-04T23:59:59-12:00", "notification": "2027-01-31"},
            ]},
        ],
        "extra": {"verified": True, "location": "Pittsburgh, USA"},
    },
    "www": {
        "file": "interdisciplinary.yaml",
        "patch_cycles": [
            {"name": "2027", "tracks": [
                {"name": "Full Paper (Research & Industry)", "abstract": "2026-10-18T23:59:59-12:00", "deadline": "2026-10-25T23:59:59-12:00", "notification": "2027-01-04"},
                {"name": "Short Paper", "abstract": "2026-11-09T23:59:59-12:00", "deadline": "2026-11-16T23:59:59-12:00", "notification": "2027-01-04"},
                {"name": "Demo Paper", "deadline": "2026-11-16T23:59:59-12:00", "notification": "2027-01-04"},
                {"name": "Workshop Proposal", "deadline": "2026-09-28T23:59:59-12:00", "notification": "2026-10-12"},
                {"name": "Tutorial Proposal", "deadline": "2026-10-19T23:59:59-12:00", "notification": "2026-11-02"},
            ]},
        ],
        "extra": {"verified": True},
    },
    "nsdi": {
        "file": "network.yaml",
        "patch_cycles": [
            {"name": "Spring Cycle", "tracks": [
                {"name": "Traditional Research", "abstract": "2026-04-16T23:59:59-04:00", "deadline": "2026-04-23T23:59:59-04:00", "notification": "2026-07-23"},
                {"name": "Frontiers", "abstract": "2026-04-16T23:59:59-04:00", "deadline": "2026-04-23T23:59:59-04:00", "notification": "2026-07-23"},
                {"name": "Operational Systems", "abstract": "2026-04-16T23:59:59-04:00", "deadline": "2026-04-23T23:59:59-04:00", "notification": "2026-07-23"},
            ]},
            {"name": "Fall Cycle", "tracks": [
                {"name": "Traditional Research", "abstract": "2026-09-10T23:59:59-04:00", "deadline": "2026-09-17T23:59:59-04:00", "notification": "2026-12-08"},
                {"name": "Frontiers", "abstract": "2026-09-10T23:59:59-04:00", "deadline": "2026-09-17T23:59:59-04:00", "notification": "2026-12-08"},
                {"name": "Operational Systems", "abstract": "2026-09-10T23:59:59-04:00", "deadline": "2026-09-17T23:59:59-04:00", "notification": "2026-12-08"},
            ]},
        ],
        "extra": {"verified": True, "rank": {"ccf": "A", "core": "A*"}},
    },
    "acl": {
        "file": "ai.yaml",
        "rolling_review": {
            "name": "ACL Rolling Review (ARR)",
            "url": "https://openreview.net/group?id=aclweb.org/ACL/ARR",
            "commitment_windows": ["2026-01-15","2026-02-15","2026-03-15","2026-04-15","2026-05-15","2026-06-15","2026-07-15","2026-08-15","2026-09-15","2026-10-15","2026-11-15","2026-12-15"],
            "note": "Submit via ARR monthly; commit to ACL by Feb 15 for main conference",
        },
        "extra": {"verified": True},
    },
    "emnlp": {
        "file": "ai.yaml",
        "rolling_review": {
            "name": "ACL Rolling Review (ARR)",
            "url": "https://openreview.net/group?id=aclweb.org/ACL/ARR",
            "commitment_windows": ["2026-01-15","2026-02-15","2026-03-15","2026-04-15","2026-05-15","2026-06-15"],
            "note": "Submit via ARR monthly; commit to EMNLP by Jun 15 for main conference",
        },
        "extra": {"verified": True},
    },
    "ubicomp/iswc": {
        "file": "hci.yaml",
        "patch_cycles": [
            {"name": "2026", "tracks": [
                {"name": "ISWC Notes & Briefs", "abstract": "2026-05-17T23:59:59-12:00", "deadline": "2026-05-24T23:59:59-12:00", "notification": "2026-07-01"},
                {"name": "Workshop Proposal", "deadline": "2026-04-30T23:59:59-12:00", "notification": "2026-05-02"},
                {"name": "Tutorial Proposal", "deadline": "2026-05-07T23:59:59-12:00"},
                {"name": "Posters & Demos", "deadline": "2026-06-06T23:59:59-12:00", "notification": "2026-07-20"},
                {"name": "Design Exhibition", "deadline": "2026-06-22T23:59:59-12:00", "notification": "2026-07-24"},
                {"name": "Doctoral Colloquium", "deadline": "2026-06-19T23:59:59-12:00", "notification": "2026-07-15"},
                {"name": "Student Challenge", "deadline": "2026-06-24T23:59:59-12:00", "notification": "2026-07-20"},
            ]},
        ],
        "extra": {"verified": True, "rank": {"ccf": "A", "core": "A*"}},
    },
}


def apply_patch():
    # Group patches by file
    by_file = {}
    for slug, patch in PATCHES.items():
        fname = patch["file"]
        if fname not in by_file:
            by_file[fname] = []
        by_file[fname].append((slug, patch))

    for fname, patches in by_file.items():
        fpath = os.path.join(DATA_DIR, fname)
        with open(fpath) as f:
            confs = yaml.safe_load(f) or []

        for slug, patch in patches:
            for conf in confs:
                if conf["slug"] == slug:
                    # Apply extra fields
                    if "extra" in patch:
                        for k, v in patch["extra"].items():
                            if k == "rank":
                                conf.setdefault("rank", {}).update(v)
                            else:
                                conf[k] = v

                    # Apply rolling_review
                    if "rolling_review" in patch:
                        conf["rolling_review"] = patch["rolling_review"]

                    # Replace latest cycle(s) with track data
                    if "patch_cycles" in patch:
                        patch_names = {c["name"] for c in patch["patch_cycles"]}
                        # Remove existing cycles that match patch names
                        conf["cycles"] = [c for c in conf.get("cycles", []) if c.get("name") not in patch_names]
                        # Add patched cycles
                        conf["cycles"].extend(patch["patch_cycles"])
                        # Sort by year
                        def sort_key(c):
                            try:
                                return int(c.get("name", "0"))
                            except ValueError:
                                return 0
                        conf["cycles"].sort(key=sort_key)

                    print(f"  ✓ Patched {slug} in {fname}")
                    break
            else:
                print(f"  ✗ Slug {slug} not found in {fname}")

        with open(fpath, "w") as f:
            yaml.dump(confs, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)


if __name__ == "__main__":
    apply_patch()
