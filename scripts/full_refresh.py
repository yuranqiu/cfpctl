#!/usr/bin/env python3
"""Refresh existing cfpctl-data from official websites (same options as update_official)."""

if __package__:
    from .update_official import main
else:
    from update_official import main

if __name__ == "__main__":
    raise SystemExit(main())
