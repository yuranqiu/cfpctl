import unittest

from scripts.official_dates import parse_timestamp
from scripts.official_inspected import extract_inspected
from scripts.official_sources import repaired_source
from scripts.scrape_cfp import collect_conference


class InspectedSchedulesTests(unittest.TestCase):
    def test_iacr_final_notification_and_explicit_dotted_clock(self):
        html = '''<title>ASIACRYPT 2026</title>
        <h6>May 21, 2026</h6><p>Submission deadline (11.59pm AoE)</p>
        <h6>July 1, 2026</h6><p>First round notification</p>
        <h6>August 14, 2026</h6><p>Final notification</p>'''
        result = extract_inspected(html, 'https://asiacrypt.iacr.org/2026/', {'slug': 'asiacrypt'})
        self.assertEqual([c['value'] for c in result['candidates']],
                         ['2026-05-21T23:59:00-12:00', '2026-08-14'])

    def test_missing_timezone_is_not_inferred_from_existing_data(self):
        html = '<title>TCC 2026</title><h6>May 1, 2026</h6><p>Submission deadline</p>'
        result = extract_inspected(html, 'https://tcc.iacr.org/2026/', {'slug': 'tcc'})
        self.assertFalse(result['candidates'][0]['applicable'])

    def test_dis_table_caption_and_compact_edition_title(self):
        html = '''<title>Call for papers – DIS2027</title><figure><table>
        <tr><td>Paper and Pictorial Submission</td><td>18 January 2027</td></tr>
        <tr><td>Acceptance Notification</td><td>19 March 2027</td></tr>
        </table><figcaption>Deadlines are specified as Anywhere on Earth time</figcaption></figure>'''
        result = extract_inspected(html, 'https://dis.acm.org/2027/call-for-papers/', {'slug': 'dis'})
        self.assertEqual(result['candidates'][0]['value'], '2027-01-18T23:59:59-12:00')
        self.assertEqual(result['candidates'][1]['value'], '2027-03-19')

    def test_date_research_scope_excludes_workshops(self):
        html = '''<title>DATE 2027</title><table>
        <tr><td>Research Papers - D, A, T and E tracks</td><td></td></tr>
        <tr><td>Final paper</td><td>20 September 2026 AoE</td></tr>
        <tr><td>Workshops</td><td></td></tr>
        <tr><td>Final paper</td><td>20 October 2026 AoE</td></tr></table>'''
        result = extract_inspected(html, 'https://www.date-conference.com/call-for-papers', {'slug': 'date'})
        self.assertEqual(len(result['candidates']), 1)
        self.assertEqual(result['candidates'][0]['date'], '2026-09-20')

    def test_wrong_conference_identity_is_rejected(self):
        self.assertIsNone(extract_inspected('<title>Crypto 2027</title>',
                                           'https://pkc.iacr.org/2027/', {'slug': 'pkc'}))

    def test_repaired_links_are_exact_and_followed_as_https(self):
        self.assertEqual(repaired_source('cscwd', 'http://2027.cscwd.org')[0],
                         'https://cscwd2027.dailyeliteevents.com.au/')
        self.assertIsNone(repaired_source('icws', 'https://services.conferences.computer.org/2027/icws-2027/'))
        requested = []
        def fetch(url):
            requested.append(url)
            if len(requested) == 1:
                return '<title>Inscrypt 2026</title><a href="/call-for-papers">Call for papers</a>'
            return '<title>Inscrypt 2026</title><p>Paper submission deadline: May 1, 2026 AoE</p>'
        collect_conference({'slug': 'inscrypt', 'homepage': 'https://inscrypt2026.comp.polyu.edu.hk',
                            'cycles': [{'name': '2026'}]}, fetch)
        self.assertEqual(requested[-1], 'https://inscrypt2026.comp.polyu.edu.hk/call-for-papers/')

    def test_researchr_zone_suffix_does_not_accept_conflicting_zones(self):
        self.assertEqual(parse_timestamp('May 1, 2026 AoE (UTC-12h)', '2026-05-01'), '2026-05-01T23:59:59-12:00')
        self.assertIsNone(parse_timestamp('May 1, 2026 AoE (UTC+08h)', '2026-05-01'))
