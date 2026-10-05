import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from official_tables import extract_table

FIXTURES = Path(__file__).parent / 'fixtures' / 'tables'


class TableTests(unittest.TestCase):
    def extract(self, slug, year, host, html=None):
        return extract_table((f'<h1>{slug.upper()} {year}</h1>' + html) if html else (FIXTURES / (slug + '.html')).read_text(),
                             f'https://{host}/Conferences/{year}/CallForPapers', {'slug': slug})

    def test_live_iclr_2027(self):
        result = self.extract('iclr', 2027, 'iclr.cc')
        self.assertEqual([(c['field'], c['value']) for c in result['candidates']], [
            ('abstract', '2026-09-18T23:59:59-12:00'), ('deadline', '2026-09-25T23:59:59-12:00')])
        self.assertTrue(all(c['applicable'] for c in result['candidates']))

    def test_live_aistats_2027(self):
        result = self.extract('aistats', 2027, 'virtual.aistats.org')
        self.assertEqual(result['candidates'][-1]['value'], '2026-10-06T23:59:59-12:00')
        self.assertTrue(all(c['applicable'] for c in result['candidates']))

    def test_live_eccv_2026(self):
        result = self.extract('eccv', 2026, 'eccv.ecva.net')
        self.assertEqual([(c['field'], c['value']) for c in result['candidates']], [
            ('abstract', '2026-02-26T23:00:00+01:00'), ('deadline', '2026-03-05T23:00:00+01:00')])
        self.assertTrue(all(c['applicable'] for c in result['candidates']))

    def row(self, label='Paper Deadline', value="Sep 25 '26 (Anywhere on Earth)"):
        return f'<div class="date-row"><div class="date-title">{label}</div><div class="date-time">{value}</div></div>'

    def test_conflicting_rows_block_all(self):
        result = self.extract('iclr', 2027, 'iclr.cc', self.row() + self.row(value="Sep 26 '26 (Anywhere on Earth)"))
        self.assertTrue(result['review_reasons'])
        self.assertFalse(any(c['applicable'] for c in result['candidates']))

    def test_workshop_label_is_not_main(self):
        result = self.extract('iclr', 2027, 'iclr.cc', self.row('Workshop Paper Deadline'))
        self.assertEqual(result['candidates'], [])

    def test_wrong_host_and_scope_are_unrecognized(self):
        for url in ('https://example.com/Conferences/2027', 'https://iclr.cc/Conferences/2027/Workshops'):
            self.assertIsNone(extract_table(self.row(), url, {'slug': 'iclr'}))

    def test_no_cross_row_pairing(self):
        html = '<div class="date-row"><div class="date-title">Paper Deadline</div></div>' + '<div class="date-row"><div class="date-time">Sep 25 2026 AoE</div></div>'
        result = self.extract('iclr', 2027, 'iclr.cc', html)
        self.assertTrue(result['review_reasons'])

    def test_hidden_countdown_cannot_supply_missing_timezone(self):
        html = self.row(value="Sep 25 '26") + '<script>var paper_deadline="2026/09/26 11:59:59 UTC";</script>'
        result = self.extract('iclr', 2027, 'iclr.cc', html)
        self.assertFalse(result['candidates'][0]['applicable'])

    def test_wrong_year_and_revisions_are_review_only(self):
        for value in ("Sep 25 '24 (Anywhere on Earth)", "<del>Sep 24 '26</del> Sep 25 '26 (Anywhere on Earth)", "Sep 25 '26 (Anywhere on Earth) tentative"):
            result = self.extract('iclr', 2027, 'iclr.cc', self.row(value=value))
            self.assertFalse(result['candidates'][0]['applicable'])

    def test_edition_requires_consistent_title_or_h1(self):
        for heading in ('', '<h1>ICLR 2026</h1>', '<title>2027 Conference</title><h1>ICLR 2026</h1>'):
            result = extract_table(heading + self.row(), 'https://iclr.cc/Conferences/2027', {'slug': 'iclr'})
            self.assertTrue(result['review_reasons'])
            self.assertFalse(any(c['applicable'] for c in result['candidates']))

    def test_abstract_only_is_review(self):
        result = self.extract('iclr', 2027, 'iclr.cc', self.row('Abstract Deadline'))
        self.assertTrue(result['review_reasons'])
        self.assertFalse(result['candidates'][0]['applicable'])

    def test_duplicated_value_container_is_review(self):
        html = self.row().replace('</div></div>', '</div><div class="date-time">Sep 26 2026 AoE</div></div>')
        result = self.extract('iclr', 2027, 'iclr.cc', html)
        self.assertTrue(result['review_reasons'])

    def test_unmatched_eccv_rows(self):
        html = '<table><tr><td>Paper Registration Deadline:<br>Submission Deadline:</td><td>Feb 26, 2026 11:00 PM CET</td></tr></table>'
        result = self.extract('eccv', 2026, 'eccv.ecva.net', html)
        self.assertTrue(result['review_reasons'])
        self.assertEqual(result['candidates'], [])


if __name__ == '__main__':
    unittest.main()
