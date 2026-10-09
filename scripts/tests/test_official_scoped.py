import unittest
from pathlib import Path
import json
from scripts.official_scoped import extract_scoped
from scripts.official_adapters import extract_adapter

FIXTURES = Path(__file__).parent / 'fixtures' / 'scoped'
URLS = json.loads((FIXTURES / 'sources.json').read_text())['urls']


class ScopedTests(unittest.TestCase):
    def extract(self, slug, change=lambda html: html):
        return extract_scoped(change((FIXTURES / (slug + '.html')).read_text(encoding='utf-8')), URLS[slug], {'slug': slug})

    def test_aaai_short_edition_and_main_schedule(self):
        result = self.extract('aaai')
        self.assertFalse(result['review_reasons'])
        self.assertEqual([c['date'] for c in result['candidates']], ['2026-07-21', '2026-07-28', '2026-11-30'])

    def test_web_conference_only_main_table(self):
        result = self.extract('www')
        self.assertFalse(result['review_reasons'])
        self.assertEqual(len(result['candidates']), 3)
        self.assertEqual([c['date'] for c in result['candidates']], ['2026-10-18', '2026-10-25', '2027-01-04'])
        self.assertTrue(all(c['track_name'] is None for c in result['candidates']))

    def test_sigmod_rounds_do_not_include_revision_deadlines(self):
        result = self.extract('sigmod')
        self.assertFalse(result['review_reasons'])
        self.assertEqual(len(result['candidates']), 18)
        self.assertEqual(len({c['cycle_name'] for c in result['candidates']}), 6)
        self.assertEqual([c['date'] for c in result['candidates'] if c['field'] == 'deadline'], ['2026-01-17', '2026-04-17', '2026-07-17', '2026-10-17', '2026-05-30', '2026-12-10'])

    def test_layout_change_and_wrong_edition_block_updates(self):
        self.assertTrue(self.extract('www', lambda h: h.replace('Research &amp; Industry Track Papers', 'Other Papers'))['review_reasons'])
        self.assertTrue(self.extract('aaai', lambda h: h.replace('AAAI-27', 'AAAI-28'))['review_reasons'])
        self.assertTrue(self.extract('sigmod', lambda h: h.replace('Research paper submission round 4', 'Research paper submission round 3'))['review_reasons'])

    def test_eurocrypt_opening_and_early_rejection_are_not_deadlines(self):
        html = '<title>Eurocrypt 2027</title><h6>September 4, 2026</h6><p>Submission server online</p><h6>September 17, 2026</h6><p>Submission deadline at 23:59 anywhere on Earth (AoE)</p><h6>November 30, 2026</h6><p>Early rejection notifications</p><h6>January 18, 2027</h6><p>Final notification</p>'
        result = extract_adapter(html, 'https://eurocrypt.iacr.org/2027/', {'slug': 'eurocrypt'})
        self.assertEqual([c['field'] for c in result['candidates']], ['deadline', 'notification'])
