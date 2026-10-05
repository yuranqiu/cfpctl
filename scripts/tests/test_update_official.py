from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import update_official as updater


def conf(slug='example'):
    return {'slug': slug, 'name': 'Example', 'homepage': 'https://example.org/2027',
            'verified': True, 'accept_rate': '25%', 'rolling_review': {'name': 'ARR'},
            'cycles': [{'name': '2026', 'deadline': '2026-06-01T23:59:59-12:00'},
                       {'name': '2027', 'deadline': '2026-09-01T23:59:59-12:00'}]}


def observation(slug='example', **overrides):
    candidate = {'year': 2027, 'cycle_name': '2027', 'track_name': None, 'field': 'deadline',
                 'value': '2026-09-08T23:59:59-12:00', 'evidence': 'Paper deadline: September 8, 2026 AoE',
                 'applicable': True}
    candidate.update(overrides)
    return {'slug': slug, 'source_url': 'https://example.org/2027/cfp', 'status': 'ok',
            'candidates': [candidate], 'review_reasons': []}


class MergeTests(unittest.TestCase):
    def test_verified_date_changes_without_losing_curated_data(self):
        original = conf()
        updated, changes, review = updater.merge_result(original, observation())
        self.assertEqual(updated['cycles'][-1]['deadline'], '2026-09-08T23:59:59-12:00')
        self.assertEqual(updated['cycles'][0], original['cycles'][0])
        for field in ['verified', 'accept_rate', 'rolling_review', 'homepage']:
            self.assertEqual(updated[field], original[field])
        self.assertEqual(len(changes), 1)
        self.assertFalse(review)
        self.assertEqual(original, conf())

    def test_ambiguous_year_round_or_track_never_overwrites(self):
        for overrides in [{'cycle_name': 'Unknown'}, {'track_name': 'Research'}, {'year': 2028, 'cycle_name': '2028'},
                          {'applicable': False}, {'value': '2026-09-08'}, {'evidence': ''}]:
            with self.subTest(overrides=overrides):
                updated, changes, review = updater.merge_result(conf(), observation(**overrides))
                self.assertEqual(updated, conf())
                self.assertFalse(changes)
                self.assertTrue(review)

    def test_duplicate_years_not_matched_by_position(self):
        original = conf()
        original['cycles'].append(deepcopy(original['cycles'][-1]))
        updated, changes, reviews = updater.merge_result(original, observation())
        self.assertEqual(updated, original)
        self.assertFalse(changes)
        self.assertTrue(reviews)

    def test_conflicting_observations_revert_conference(self):
        result = observation()
        result['candidates'].append(observation(value='2026-09-10T23:59:59-12:00')['candidates'][0])
        updated, changes, reviews = updater.merge_result(conf(), result)
        self.assertEqual(updated, conf())
        self.assertFalse(changes)
        self.assertTrue(reviews)

    def test_named_round_requires_existing_edition_evidence(self):
        original = conf()
        original['cycles'] = [{'name': 'Cycle 1', 'tracks': [{'name': 'Paper', 'deadline': '2026-08-25T23:59:59-12:00'}]}]
        result = observation(cycle_name='Cycle 1', track_name='Paper')
        updated, changes, _ = updater.merge_result(original, result)
        self.assertEqual(len(changes), 1)
        original['homepage'] = 'https://example.org/2026'
        updated, changes, reviews = updater.merge_result(original, result)
        self.assertEqual(updated, original)
        self.assertFalse(changes)
        self.assertTrue(reviews)

    def test_date_order_conflict_reverts(self):
        original = conf()
        original['cycles'][-1]['notification'] = '2026-09-05'
        updated, changes, reviews = updater.merge_result(original, observation())
        self.assertEqual(updated, original)
        self.assertFalse(changes)
        self.assertTrue(reviews)

    def test_notification_date_only_does_not_create_formatting_change(self):
        original = conf()
        original['cycles'][-1]['notification'] = '2026-10-01'
        updated, changes, reviews = updater.merge_result(original, observation(field='notification', value='2026-10-01T23:59:59-12:00'))
        self.assertEqual(updated, original)
        self.assertFalse(changes)
        self.assertFalse(reviews)


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for filename in updater.FILES:
            (self.root / filename).write_text(yaml.safe_dump([conf(filename[:-5])]))

    def snapshot(self):
        return {p.name: p.read_bytes() for p in self.root.glob('*.yaml')}

    def collect(self, conference, fetcher):
        return observation(conference['slug'])

    def test_dry_run_preserves_bytes_apply_is_idempotent(self):
        before = self.snapshot()
        report = updater.refresh(self.root, collector=self.collect)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(report['changes']), 10)
        updater.refresh(self.root, collector=self.collect, apply=True)
        after = self.snapshot()
        self.assertNotEqual(after, before)
        report = updater.refresh(self.root, collector=self.collect, apply=True)
        self.assertFalse(report['changes'])
        self.assertEqual(self.snapshot(), after)

    def test_total_failure_does_not_touch_data(self):
        before = self.snapshot()
        def fail(conf, fetcher):
            raise OSError('offline')
        report = updater.refresh(self.root, collector=fail, apply=True)
        self.assertEqual(report['status'], 'failed')
        self.assertFalse(report['applied'])
        self.assertEqual(self.snapshot(), before)

    def test_partial_failure_keeps_failed_conference(self):
        before = (self.root / 'ai.yaml').read_bytes()
        def partial(conf, fetcher):
            if conf['slug'] == 'ai':
                raise OSError('offline')
            return self.collect(conf, fetcher)
        report = updater.refresh(self.root, collector=partial, apply=True)
        self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['counts']['failed'], 1)
        self.assertEqual((self.root / 'ai.yaml').read_bytes(), before)
        self.assertEqual(len(report['changes']), 9)

    def test_missing_category_fails_before_fetch(self):
        (self.root / 'ai.yaml').unlink()
        with self.assertRaises(OSError):
            updater.refresh(self.root, collector=lambda *a, **k: self.fail('unexpected fetch'))

    def test_second_file_write_failure_rolls_back_first(self):
        before = self.snapshot()
        real_replace = Path.replace
        calls = []
        def failing_replace(source, target):
            calls.append(str(target))
            if len(calls) == 2:
                raise OSError('simulated disk error')
            return real_replace(source, target)
        with patch.object(Path, 'replace', failing_replace), self.assertRaises(OSError):
            updater.refresh(self.root, collector=self.collect, apply=True)
        self.assertEqual(self.snapshot(), before)

    def test_review_candidates_do_not_apply(self):
        before = self.snapshot()
        def review(conf, fetcher):
            result = observation(conf['slug'])
            result['status'] = 'review'
            return result
        report = updater.refresh(self.root, collector=review, apply=True)
        self.assertEqual(report['status'], 'partial')
        self.assertFalse(report['changes'])
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
