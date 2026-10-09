#!/usr/bin/env python3
"""Refresh an existing cfpctl-data checkout using conference websites only.

Dry run by default. --apply changes only unambiguously matched deadline fields.
Uncertain dates, unavailable sites and unsupported rounds retain existing data.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen

import yaml

if __package__:
    from .scrape_cfp import collect_conference, ScrapeError
else:
    from scrape_cfp import collect_conference, ScrapeError

FILES = ('ai.yaml', 'graphics.yaml', 'theory.yaml', 'database.yaml', 'systems.yaml',
         'hci.yaml', 'interdisciplinary.yaml', 'network.yaml', 'security.yaml', 'software.yaml')


class PartialApplyError(OSError):
    """An output failure whose rollback could not fully restore the original files."""
    def __init__(self, files):
        self.files = files
        super().__init__('write and rollback failed; inspect these files: ' + ', '.join(files))


def apply_files(directory, pending, before):
    with tempfile.TemporaryDirectory(prefix='.official-', dir=directory) as staging:
        for name, content in pending.items():
            (Path(staging) / name).write_text(content, encoding='utf-8')
        replaced = []
        try:
            for name in pending:
                (Path(staging) / name).replace(directory / name)
                replaced.append(name)
        except OSError:
            unrestored = []
            for name in reversed(replaced):
                try:
                    (directory / name).write_bytes(before[name])
                except OSError:
                    unrestored.append(name)
            if unrestored:
                raise PartialApplyError(unrestored)
            raise


def load_data(directory):
    output, seen = {}, set()
    for name in FILES:
        entries = yaml.safe_load((directory / name).read_text(encoding='utf-8'))
        if not isinstance(entries, list) or not entries:
            raise ValueError(f'{name}: expected nonempty conference list')
        for conference in entries:
            if not isinstance(conference, dict) or not conference.get('slug') or not conference.get('cycles'):
                raise ValueError(f'{name}: invalid conference')
            if conference['slug'] in seen:
                raise ValueError(f"duplicate slug: {conference['slug']}")
            seen.add(conference['slug'])
        output[name] = entries
    return output


def match_target(conference, candidate):
    """Never identify a round by list position or by its changing deadline."""
    year = candidate.get('year')
    if not isinstance(year, int):
        raise ValueError('missing explicit edition year')
    name = candidate.get('cycle_name')
    cycles = [c for c in conference['cycles'] if str(c.get('name', '')) == (str(name) if name else str(year))]
    if len(cycles) != 1:
        raise ValueError('edition/round does not uniquely match an existing cycle')
    cycle = cycles[0]
    # Named rounds need explicit edition evidence from the existing official URL
    # or a stored year; a parser must not bind next year's Cycle 1 to this year's.
    if str(cycle.get('name', '')) != str(year):
        import re
        urls = ' '.join(str(conference.get(k, '')) for k in ('cfp', 'homepage'))
        years = {int(v) for v in re.findall(r'(?<!\d)(20\d{2})(?!\d)', urls)}
        short = re.findall(r'usenixsecurity(\d{2})(?!\d)', urls)
        years.update(2000 + int(v) for v in short)
        if cycle.get('year') != year and years != {year}:
            raise ValueError('named round has no matching edition evidence in existing data')
    tracks = cycle.get('tracks')
    if tracks:
        track_name = candidate.get('track_name')
        matched = [t for t in tracks if t.get('name') == track_name] if track_name else []
        if len(matched) != 1:
            raise ValueError('track does not uniquely match an existing track')
        return matched[0]
    if candidate.get('track_name'):
        raise ValueError('candidate track cannot be matched to a legacy unnamed track')
    return cycle


def merge_result(conference, result):
    updated = deepcopy(conference)
    changes, reviews, targets = [], [], {}
    # Stage each conference as a unit: inconsistent observations never partially apply.
    for candidate in result.get('candidates', []):
        if not candidate.get('applicable'):
            reviews.append(candidate.get('reason') or 'candidate needs manual review')
            continue
        try:
            field = candidate.get('field')
            if field not in ('deadline', 'abstract', 'notification') or not candidate.get('evidence'):
                raise ValueError('missing field or source evidence')
            value = candidate.get('value')
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None and not (field == 'notification' and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value)):
                raise ValueError('explicit timezone required')
            if parsed.year not in {candidate['year'] - 1, candidate['year']}:
                raise ValueError('date falls outside edition')
            target = match_target(updated, candidate)
            # Bracketed global deadline policies do not establish a clock for
            # an author-notification row. AoE alone is a zone, not a published
            # notification time. Preserve the precision of the source row.
            row_evidence = candidate['evidence'].split(' [', 1)[0]
            explicit_clock = bool(re.search(
                r'\b\d{1,2}:\d{2}|\b\d{1,2}\s*(?:a\.?m\.?|p\.?m\.?)\b|\b(?:noon|midnight)\b',
                row_evidence, re.I))
            if field == 'notification' and not explicit_clock:
                value = parsed.date().isoformat()
                parsed = datetime.fromisoformat(value)
            key = (id(target), field)
            if key in targets and targets[key] != value:
                return deepcopy(conference), [], reviews + ['conflicting official values for the same field']
            if key in targets:
                continue
            targets[key] = value
            old = target.get(field)
            if old == value:
                continue
            # A date-only notification already expresses the same information;
            # avoid daily PR noise from adding a conventional end-of-day time.
            if field == 'notification' and str(old) == parsed.date().isoformat():
                continue
            if old:
                try:
                    old_parsed = datetime.fromisoformat(str(old))
                    if old_parsed == parsed:
                        continue
                    # Keep a curated notification clock when the new evidence
                    # merely repeats its date without publishing a time.
                    if field == 'notification' and not explicit_clock and old_parsed.date() == parsed.date():
                        continue
                    # End-of-minute conventions (:00 versus :59) are not a
                    # deadline change unless the source explicitly gives seconds.
                    # Aware datetime comparison also handles equivalent zones.
                    if (field in ('abstract', 'deadline') and old_parsed.tzinfo is not None
                            and parsed.tzinfo is not None
                            and {old_parsed.second, parsed.second} == {0, 59}
                            and not re.search(r'\b\d{1,2}:\d{2}:\d{2}\b', candidate['evidence'])
                            and old_parsed.replace(second=0, microsecond=0) == parsed.replace(second=0, microsecond=0)):
                        continue
                except ValueError:
                    pass
            target[field] = value
            changes.append({'slug': conference['slug'], 'year': candidate['year'],
                            'cycle': candidate.get('cycle_name'), 'track': candidate.get('track_name'),
                            'field': field, 'old': old, 'new': value,
                            'source_url': result['source_url'], 'evidence': candidate['evidence']})
        except (ValueError, TypeError, KeyError) as exc:
            reviews.append(str(exc))
    # Check chronological consistency only for changed records, without rewriting
    # unrelated historical data or metadata.
    for cycle in updated['cycles']:
        for track in cycle.get('tracks') or [cycle]:
            if not any(id(track) == key[0] for key in targets):
                continue
            try:
                values = {k: datetime.fromisoformat(str(track[k])) for k in ('abstract', 'deadline', 'notification') if track.get(k)}
                if any(v.tzinfo is None for v in values.values()):
                    # Existing date-only notifications cannot resolve time ordering.
                    values = {k: v.date() for k, v in values.items()}
                if ('abstract' in values and values['abstract'] > values['deadline']) or ('notification' in values and values['notification'] < values['deadline']):
                    return deepcopy(conference), [], reviews + ['official changes conflict with abstract/deadline/notification order']
            except (ValueError, TypeError, KeyError):
                return deepcopy(conference), [], reviews + ['cannot verify date ordering for changed record']
    return updated, changes, reviews


def make_fetcher(timeout):
    def fetch(url):
        if not url.startswith(('https://', 'http://')):
            raise ScrapeError('unsupported website URL')
        try:
            request = Request(url, headers={'User-Agent': 'cfpctl-official-updater/1.0'})
            with urlopen(request, timeout=timeout) as response:
                content = response.read(4 * 1024 * 1024 + 1)
                if len(content) > 4 * 1024 * 1024:
                    raise ScrapeError('website exceeds 4 MiB limit')
                return content.decode(response.headers.get_content_charset() or 'utf-8')
        except Exception as exc:
            raise ScrapeError(f'{url}: {exc}') from exc
    return fetch


def refresh(directory, *, collector=collect_conference, workers=4, timeout=20, slugs=None, apply=False):
    data = load_data(directory)
    before = {name: (directory / name).read_bytes() for name in FILES}
    work = [(name, i, c) for name, entries in data.items() for i, c in enumerate(entries)
            if not slugs or c['slug'] in slugs]
    if slugs and set(slugs) - {c['slug'] for _, _, c in work}:
        raise ValueError('unknown conference selection')
    fetcher = make_fetcher(timeout)
    def collect(item):
        name, i, conf = item
        try:
            result = collector(deepcopy(conf), fetcher=fetcher)
        except Exception as exc:
            result = {'slug': conf['slug'], 'source_url': conf.get('cfp') or conf.get('homepage'),
                      'status': 'failed', 'candidates': [], 'failure': str(exc)}
        return name, i, result
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'source': 'official conference websites',
              'applied': False, 'changes': [], 'conferences': [], 'input_sha256': {
                  name: hashlib.sha256(raw).hexdigest() for name, raw in before.items()}}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for name, index, result in pool.map(collect, work):
            if result.get('status') == 'ok' or (result.get('status') == 'review' and result.get('safe_partial')):
                updated, changes, reviews = merge_result(data[name][index], result)
                data[name][index] = updated
                report['changes'].extend(changes)
                result.setdefault('review_reasons', []).extend(reviews)
                if reviews:
                    result['status'] = 'review'
            report['conferences'].append(result)
            print(f"{result['slug']}: {result['status']}", flush=True)
    counts = {status: sum(c['status'] == status for c in report['conferences']) for status in ('ok', 'review', 'failed')}
    report['counts'] = counts
    report['status'] = 'failed' if counts['failed'] == len(work) else 'partial' if counts['failed'] or counts['review'] else 'ok'
    if apply and report['status'] != 'failed':
        # Validate/serialize the full output before touching any source files.
        pending = {name: yaml.safe_dump(entries, allow_unicode=True, sort_keys=False, width=120)
                   for name, entries in data.items() if entries != yaml.safe_load(before[name])}
        if any((directory / name).read_bytes() != raw for name, raw in before.items()):
            raise ValueError('data changed during fetch; refusing to overwrite concurrent edits')
        apply_files(directory, pending, before)
        report['applied'] = True
    return report


def write_reports(report, path, summary):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    def cell(value):
        return str(value or '—').replace('|', '\\|').replace('\n', ' ').replace('<', '&lt;')
    lines = ['# Official conference website update', '',
             f"Status: {report['status']}. Checked: {report.get('counts', {})}. Changes: {len(report.get('changes', []))}.", '',
             'Existing cfpctl-data is the baseline. Only official websites supply changes; uncertain records remain unchanged.', '',
             '| Conference | Cycle / track | Field | Before | After | Source |',
             '|---|---|---|---|---|---|']
    for change in report.get('changes', []):
        lines.append('| ' + ' | '.join(cell(v) for v in (change['slug'], f"{change['cycle'] or change['year']} / {change['track'] or 'main'}", change['field'], change['old'], change['new'], change['source_url'])) + ' |')
    if report.get('changes'):
        lines.extend(['', '## Official evidence', ''])
        for change in report['changes']:
            lines.append(f"- {cell(change['slug'])} ({cell(change['field'])}): {cell(change['evidence'])}")
    lines.extend(['', '## Needs review / fetch failures', ''])
    for item in report.get('conferences', []):
        if item['status'] != 'ok':
            lines.append(f"- {cell(item['slug'])}: {cell(item.get('failure') or '; '.join(item.get('review_reasons', [])) or item['status'])}")
    if report.get('error'):
        lines.append(cell(report['error']))
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--summary', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--workers', type=int, default=4, choices=range(1, 9))
    parser.add_argument('--timeout', type=int, default=20)
    parser.add_argument('--slug', action='append', help='limit to an existing conference; repeatable')
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    if any(p.resolve() == args.data_dir.resolve() or args.data_dir.resolve() in p.resolve().parents for p in (args.report, args.summary)):
        parser.error('reports must be outside the data checkout')
    try:
        report = refresh(args.data_dir, workers=args.workers, timeout=args.timeout, slugs=args.slug, apply=args.apply)
    except PartialApplyError as exc:
        report = {'status': 'failed', 'applied': True, 'partial_apply': True,
                  'files_needing_recovery': exc.files, 'changes': [], 'error': str(exc)}
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
        report = {'status': 'failed', 'applied': False, 'changes': [], 'error': str(exc)}
    write_reports(report, args.report, args.summary)
    return 1 if report['status'] == 'failed' else 0


if __name__ == '__main__':
    sys.exit(main())
