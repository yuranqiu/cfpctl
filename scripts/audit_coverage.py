#!/usr/bin/env python3
"""Summarize observed updater results, never infer coverage from adapter registration."""
import argparse
from collections import Counter
import json
from pathlib import Path


def summarize(report, ccf=None):
    rows = [c for c in report.get('conferences', []) if not ccf or c.get('ccf') == ccf]
    if not rows:
        raise ValueError('report has no matching conference results')
    slugs = [r['slug'] for r in rows]
    if len(slugs) != len(set(slugs)):
        raise ValueError('report contains duplicate conference results')
    counts = dict(Counter(r['status'] for r in rows))
    accepted = [r['slug'] for r in rows if r['status'] == 'ok' and any(c.get('applicable') and c.get('field') == 'deadline' for c in r.get('candidates', []))]
    return dict(checked_at=report.get('checked_at'), offline=report.get('offline', False),
                total=len(rows), counts=counts, matched_deadline_conferences=accepted,
                matched_deadline_percent=round(100 * len(accepted) / len(rows), 1),
                reason_counts=dict(Counter(code for r in rows for code in set(r.get('reason_codes', [])))),
                needs_review=[dict(slug=r['slug'], ccf=r.get('ccf'), source_url=r.get('source_url'),
                                   status=r['status'], reasons=r.get('review_reasons', []), failure=r.get('failure'))
                              for r in rows if r['status'] != 'ok'],
                scope='Coverage describes matched fields in this run, not every edition or track. Unparsed dates are not necessarily unpublished.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path, help='official-report.json from update_official.py')
    parser.add_argument('--ccf', choices=['A', 'B', 'C'], help='optional rank filter')
    args = parser.parse_args(argv)
    try:
        result = summarize(json.loads(args.report.read_text(encoding='utf-8')), args.ccf)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
