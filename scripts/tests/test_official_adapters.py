import unittest
from pathlib import Path
from scripts.official_adapters import extract_adapter, _SITES

FIXTURES = Path(__file__).parent / 'fixtures' / 'official_adapters'


def conference(slug):
    names = _SITES[slug][2]
    cycles = []
    for name in names:
        c = {'name': '2027' if slug in {'osdi', 'eurosys'} else name.rstrip(':').replace(' deadline', ' Cycle')}
        if slug in {'ndss', 'asplos'}:
            tracks = ['Technical Papers'] if slug == 'ndss' else ['Full Paper (Architecture)', 'Full Paper (Systems)', 'Full Paper (PL)']
            c['tracks'] = [{'name': t} for t in tracks]
        cycles.append(c)
    # For conferences with empty headings lists, add a default cycle
    if not cycles:
        cycles = [{'name': '2027'}]
    return {'slug': slug, 'cycles': cycles}


def extract(slug, html=None, conf=None):
    host, path, _ = _SITES[slug]
    return extract_adapter(html if html is not None else (FIXTURES / f'{slug}.html').read_text(), 'https://' + host + path + '/', conf or conference(slug))


class OfficialAdapterTests(unittest.TestCase):
    def test_asplos_named_tracks(self):
        result = extract('asplos')['candidates']
        self.assertEqual(len(result), 12)
        self.assertTrue(all(c['applicable'] for c in result))
        self.assertEqual(result[0]['value'], '2026-04-15T23:59:59-12:00')
        self.assertEqual({c['cycle_name'] for c in result}, {'April Cycle', 'September Cycle'})

    def test_asplos_missing_aoe_rejected(self):
        html = (FIXTURES / 'asplos.html').read_text().replace('All dates are expressed as AoE (Anywhere on Earth).', '')
        self.assertTrue(all(not c['applicable'] for c in extract('asplos', html)['candidates'] if c['field'] == 'deadline'))

    def test_ndss_scoped_cycles(self):
        result = extract('ndss')['candidates']
        self.assertEqual(len(result), 4)
        deadline = [c for c in result if c['field'] == 'deadline']
        self.assertEqual([c['date'] for c in deadline], ['2026-05-06', '2026-08-19'])
        self.assertTrue(all(c['applicable'] for c in deadline))
        self.assertFalse(next(c for c in result if 'tentative' in c['evidence'])['applicable'])

    def test_ndss_unknown_track_rejected(self):
        conf = conference('ndss')
        for cycle in conf['cycles']:
            cycle['tracks'] = [{'name': 'Workshop'}]
        self.assertTrue(all(not c['applicable'] for c in extract('ndss', conf=conf)['candidates']))

    def test_nsdi_explicit_edt(self):
        result = extract('nsdi')['candidates']
        self.assertEqual(len(result), 6)
        self.assertEqual(result[0]['value'], '2026-04-16T23:59:00-04:00')
        self.assertTrue(all(c['applicable'] for c in result))

    def test_nsdi_legacy_duplicate_year_is_not_round_identity(self):
        conf = {'slug': 'nsdi', 'cycles': [{'name': '2027'}, {'name': '2027'}]}
        self.assertTrue(all(not c['applicable'] for c in extract('nsdi', conf=conf)['candidates']))

    def test_osdi_equivalent_clocks(self):
        result = extract('osdi')['candidates']
        self.assertEqual(len(result), 3)
        self.assertTrue(all(c['applicable'] for c in result))
        self.assertEqual(result[0]['value'], '2026-12-01T22:59:00+00:00')

    def test_osdi_disagreeing_clocks_rejected(self):
        html = (FIXTURES / 'osdi.html').read_text().replace('10:59 pm UTC', '11:59 pm UTC')
        self.assertTrue(all(not c['applicable'] for c in extract('osdi', html)['candidates'] if c['field'] != 'notification'))

    def test_wrong_edition_and_host_are_not_supported(self):
        for slug, (host, path, _) in _SITES.items():
            # Wrong host should always return None
            self.assertIsNone(extract_adapter('', 'https://example.org'+path, conference(slug)))
            # Wrong edition: only test if path contains a year to replace
            if '27' in path or '2027' in path:
                self.assertIsNone(extract_adapter('', 'https://'+host+path.replace('27', '28'), conference(slug)))

    def test_empty_layout_reports_review(self):
        for slug in _SITES:
            result = extract(slug, '<p>Updated website</p>')
            self.assertFalse(result['candidates'])
            self.assertTrue(result['review_reasons'])

    def test_wrong_identity_at_old_url_is_rejected(self):
        for slug in _SITES:
            with self.subTest(slug=slug):
                # Every registered site must reject a different edition, even
                # sites that only use the generic fallback and have no snapshot.
                html = (f'<title>{slug} 2028</title>'
                        '<p>Paper submission deadline: June 3, 2027 AoE</p>')
                result = extract(slug, html)
                self.assertFalse(result['candidates'])
                self.assertIn('title or h1', result['review_reasons'][0])

    def test_wrong_identity_in_saved_pages_is_rejected(self):
        for fixture in sorted(FIXTURES.glob('*.html')):
            with self.subTest(slug=fixture.stem):
                html = fixture.read_text(encoding='utf-8')
                html = html.replace('2027', '2028').replace('2026', '2028').replace('&#039;27', '&#039;28')
                result = extract(fixture.stem, html)
                self.assertFalse(result['candidates'])
                self.assertIn('title or h1', result['review_reasons'][0])

    def test_deleted_date_remains_review_only(self):
        html = (FIXTURES / 'asplos.html').read_text().replace('April 15, 2026', '<del>April 14, 2026</del> April 15, 2026')
        result = extract('asplos', html)
        rows = [c for c in result['candidates'] if c['cycle_name'] == 'April Cycle' and c['field'] == 'deadline']
        self.assertTrue(all(not c['applicable'] for c in rows))
        self.assertTrue(all('[deleted content]' in c['evidence'] for c in rows))
        self.assertTrue(result['review_reasons'])

    def test_missing_second_round_blocks_whole_schedule(self):
        html = (FIXTURES / 'ndss.html').read_text().replace('Fall Cycle', 'Retired Round')
        result = extract('ndss', html)
        self.assertTrue(any('Fall Cycle' in reason for reason in result['review_reasons']))

    def test_duplicate_deadlines_block_whole_schedule(self):
        html = (FIXTURES / 'asplos.html').read_text().replace('<li>Full paper submission — April 15, 2026</li>', '<li>Full paper submission — April 15, 2026</li><li>Full paper submission — April 16, 2026</li>')
        result = extract('asplos', html)
        self.assertTrue(any('exactly one deadline' in reason for reason in result['review_reasons']))

    def test_missing_abstract_blocks_whole_schedule(self):
        html = (FIXTURES / 'osdi.html').read_text().replace('Abstract registrations due:', 'Registration opens:')
        result = extract('osdi', html)
        self.assertTrue(any('exactly one abstract' in reason for reason in result['review_reasons']))
