#!/usr/bin/env python3
"""Compatibility entry point: use an actual official report, optionally --ccf A."""
if __package__:
    from .audit_coverage import main
else:
    from audit_coverage import main

if __name__ == '__main__':
    raise SystemExit(main())
