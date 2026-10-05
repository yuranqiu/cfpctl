#!/usr/bin/env python3
"""Remove TBD/TBA/UNKNOWN deadline placeholders without losing usable tracks."""

import sys

if __package__:
    from .clean_no_deadline import clean_data, clean_directory, main as clean_main
else:
    from clean_no_deadline import clean_data, clean_directory, main as clean_main


def main(argv=None):
    return clean_main(argv, placeholders_only=True)


if __name__ == "__main__":
    sys.exit(main())
