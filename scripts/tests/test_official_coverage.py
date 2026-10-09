"""Shared parser regressions: coverage must not come from weaker evidence rules."""
import unittest
from scripts.scrape_cfp import collect_conference
from scripts.update_official import merge_result
from scripts.audit_coverage import summarize


class GeneralCoverageTests(unittest.TestCase):
    def test_coverage_uses_observed_results_not_registered_adapters(self):
        report = {'conferences': [
            {'slug': 'a', 'ccf': 'A', 'status': 'ok', 'candidates': [{'field': 'deadline', 'applicable': True}]},
            {'slug': 'b', 'ccf': 'A', 'status': 'review', 'candidates': [], 'reason_codes': ['no_parsed_deadline']},
            {'slug': 'c', 'ccf': 'B', 'status': 'failed', 'candidates': []}]}
        summary = summarize(report, 'A')
        self.assertEqual(summary['total'], 2)
        self.assertEqual(summary['matched_deadline_percent'], 50)
        self.assertEqual(summary['needs_review'][0]['slug'], 'b')
        with self.assertRaises(ValueError):
            summarize({'conferences': []})

    def collect(self, body):
        return collect_conference({'slug':'example','homepage':'https://example.org/2027'},
                                  lambda _: '<title>Example 2027</title>'+body)

    def test_date_first_with_scoped_timezone(self):
        result=self.collect('<p>All deadlines are at 11:59 p.m. AoE.</p>'
                            '<tr><td>September 3rd, 2026</td><td>Paper submission deadline</td></tr>')
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['candidates'][0]['value'],'2026-09-03T23:59:00-12:00')

    def test_nonmain_scope_cannot_supply_main_timezone(self):
        for scope in ('All deadlines for workshops are AoE.', 'All dates for posters are 5 PM UTC.'):
            result=self.collect(f'<p>{scope}</p><p>Paper deadline: June 3, 2027</p>')
            self.assertEqual(result['status'],'review')
            self.assertFalse(any(c['applicable'] for c in result['candidates']))

    def test_unknown_local_timezone_never_inherits_global(self):
        result=self.collect('<p>All deadlines are AoE.</p><p>Paper deadline: June 3, 2027 5 PM EST</p>')
        self.assertEqual(result['status'],'review')

    def test_conflicting_global_zones_without_clocks_are_not_equal(self):
        result=self.collect('<p>All deadlines are UTC.</p><p>All deadlines are UTC+02:00.</p>'
                            '<p>Paper deadline: June 3, 2027 23:59</p>')
        self.assertEqual(result['status'],'review')

    def test_journal_track_and_seasonal_deadlines_not_main(self):
        for heading in ('Journal Track','Fall Deadline','Summer Cycle','Workshop','Industry'):
            result=self.collect(f'<h2>{heading}</h2><p>Paper deadline: June 3, 2027 AoE</p>')
            self.assertEqual(result['status'],'review')
            self.assertFalse(any(c['applicable'] for c in result['candidates']))

    def test_workshop_scope_cannot_leak_to_main_section(self):
        result=self.collect('<h2>Workshop</h2><p>All deadlines are AoE.</p>'
                            '<h2>Main Conference</h2><p>Paper deadline: June 3, 2027</p>')
        self.assertEqual(result['status'],'review')
        self.assertFalse(any(c['applicable'] for c in result['candidates']))

    def test_tentative_and_multicolumn_tbd_dates_remain_review(self):
        for text in ('Paper submission June 3, 2027 23:59 AoE TBD',
                     'Paper deadline: June 3, 2027 AoE (tentative)',
                     'Paper deadline: June 1 → June 3, 2027 AoE'):
            result=self.collect('<p>'+text+'</p>')
            self.assertEqual(result['status'],'review')

    def test_responsive_duplicate_is_not_a_second_round(self):
        block='<p>Paper deadline: June 3, 2027 AoE</p>'
        result=self.collect(block+block)
        self.assertEqual(result['status'],'ok')
        self.assertEqual(len(result['candidates']),1)

    def test_notification_calendar_date_without_inventing_clock(self):
        result=self.collect('<p>Paper deadline: June 3, 2027 AoE</p><p>Author notification: July 3, 2027</p>')
        self.assertEqual(result['status'],'ok')
        notification=next(c for c in result['candidates'] if c['field']=='notification')
        self.assertEqual(notification['value'],'2027-07-03')
        original={'slug':'example','cycles':[{'name':'2027','deadline':'2027-06-03T23:59:59-12:00'}]}
        updated,changes,reasons=merge_result(original,result)
        self.assertEqual(updated['cycles'][0]['notification'],'2027-07-03')
        self.assertFalse(reasons)

    def test_optional_unclear_notification_keeps_independent_deadline(self):
        result=self.collect('<p>Paper deadline: June 3, 2027 AoE</p><p>Author notification: July 3, 2027 5 PM PT</p>')
        self.assertEqual(result['status'],'review')
        self.assertTrue(result['safe_partial'])
        self.assertEqual([c['field'] for c in result['candidates'] if c['applicable']],['deadline'])

    def test_main_cfp_link_wins_over_news_and_special_track(self):
        pages={'https://example.org/2027': '<title>Example 2027</title><a href="/2027/journal-cfp">CFP</a>'
               '<a href="/2027/news/cfp">CFP news</a><a href="/2027/cfp">Call for Papers</a>',
               'https://example.org/2027/cfp':'<title>Example 2027</title><p>Paper deadline: June 3, 2027 AoE</p>'}
        result=collect_conference({'slug':'example','homepage':'https://example.org/2027'},pages.__getitem__)
        self.assertEqual(result['source_url'],'https://example.org/2027/cfp')
        self.assertEqual(result['status'],'ok')

    def test_only_journal_cfp_is_not_followed(self):
        calls=[]
        def fetch(url):
            calls.append(url)
            return '<title>Example 2027</title><a href="/journal-cfp">Journal CFP</a>'
        result=collect_conference({'slug':'example','homepage':'https://example.org/2027'},fetch)
        self.assertEqual(len(calls),1)
        self.assertEqual(result['status'],'review')

    def test_resubmission_is_not_a_second_paper_deadline(self):
        result = self.collect('<p>Paper deadline: June 3, 2027 AoE</p><p>July 3, 2027: Resubmission deadline</p>')
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(len(result['candidates']), 1)

    def test_http_maintained_url_is_only_tried_over_https(self):
        urls = []
        def fetch(url):
            urls.append(url)
            return '<title>Example 2027</title><p>Paper deadline: June 3, 2027 AoE</p>'
        result = collect_conference({'slug': 'example', 'homepage': 'http://example.org/2027'}, fetch)
        self.assertEqual(urls, ['https://example.org/2027'])
        self.assertEqual(result['status'], 'ok')


if __name__=='__main__':unittest.main()
