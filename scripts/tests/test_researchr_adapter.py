import unittest
from scripts.researchr_adapter import extract_researchr


class ResearchrTests(unittest.TestCase):
    def test_tooltip_zone_excludes_program_display_zone(self):
        result = self.extract([('<span title="Timezone: AoE (UTC-12h)">12 November 2026</span>', 'PLDI Research Papers', 'Submission deadline'),
                               ('1 December 2026', 'Industry Papers', 'Submission deadline')],
                              '<div>Displayed time zone: UTC+08:00</div>')
        self.assertFalse(result['review_reasons'])
        self.assertEqual(result['candidates'][0]['value'], '2026-11-12T23:59:59-12:00')

    def test_sidebar_dates_are_scoped_to_exact_track_url(self):
        path = '/track/models-2026/models-2026-research-papers'
        html = '<title>MODELS 2026</title><div class="panel"><div class="panel-title">Important Dates AoE (UTC-12h)</div><table class="important-dates-in-sidebar">'
        html += '<tr href="' + path + '"><td>1 May 2026<br>Submission deadline</td></tr>'
        html += '<tr href="/track/models-2026/workshop"><td>2 May 2026<br>Submission deadline</td></tr></table></div>'
        result = extract_researchr(html, 'https://conf.researchr.org' + path,
                                  {'slug': 'models', 'cycles': [{'name': '2026'}]})
        self.assertEqual(len(result['candidates']), 1)
        self.assertEqual(result['candidates'][0]['value'], '2026-05-01T23:59:59-12:00')

    def extract(self, rows, prefix='', cycles=None):
        html = '<title>PLDI 2027</title>' + prefix + '<p>All deadlines are AoE.</p><table><tr><th>When</th><th>Track</th><th>What</th></tr>'
        html += ''.join('<tr>' + ''.join('<td>' + c + '</td>' for c in row) + '</tr>' for row in rows) + '</table>'
        return extract_researchr(html, 'https://pldi27.sigplan.org/dates', {'slug': 'pldi', 'cycles': cycles or [{'name': '2026'}, {'name': '2027'}]})

    def test_deadline_year_does_not_select_previous_edition(self):
        result = self.extract([('12 November 2026', 'PLDI Research Papers', 'Submission deadline'),
                               ('4 March 2027', 'PLDI Research Papers', 'Author notification')])
        self.assertEqual({c['year'] for c in result['candidates']}, {2027})
        self.assertEqual({c['cycle_name'] for c in result['candidates']}, {'2027'})
        self.assertEqual(result['candidates'][0]['value'], '2026-11-12T23:59:59-12:00')
        self.assertFalse(result['review_reasons'])

    def test_feedback_and_final_revision_acceptance_not_initial_notification(self):
        rows = [('4 March 2027', 'PLDI Research Papers', event) for event in ['Author response', 'Review release', 'Final acceptance notification', 'Revision submission']]
        self.assertIsNone(self.extract(rows))

    def test_conflicting_notifications_and_deleted_dates_require_review(self):
        result = self.extract([('4 March 2027', 'PLDI Research Papers', 'Author notification'), ('5 March 2027', 'PLDI Research Papers', 'Author notification'),
                               ('<del>11 November 2026</del>12 November 2026', 'PLDI Research Papers', 'Submission deadline')])
        self.assertTrue(result['review_reasons'])
        self.assertFalse(result['candidates'][-1]['applicable'])

    def test_unrelated_table_and_unknown_track_cannot_match_by_year(self):
        prefix = '<table><tr><td>12 November 2026</td><td>PLDI Research Papers</td><td>Submission deadline</td></tr></table>'
        result = self.extract([('10 November 2026', 'Different Papers', 'Submission deadline')], prefix)
        self.assertEqual(result['candidates'], [])
        self.assertTrue(result['review_reasons'])
