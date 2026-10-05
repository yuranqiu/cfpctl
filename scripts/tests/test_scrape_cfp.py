import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

from scripts import scrape_cfp as scraper


class DeadlineExtractionTests(unittest.TestCase):
    def test_accepts_one_labeled_table_row_and_keeps_evidence(self):
        html = "<table><tr><th>Full paper deadline:</th><td>June 3, 2026, 5 PM UTC</td></tr></table>"
        result = scraper.parse_deadline(html, 2027)
        self.assertEqual(result["deadline_date"], "2026-06-03")
        self.assertIn("5 PM UTC", result["source_text"])
        self.assertNotIn("-12:00", result["deadline_date"])

    def test_dates_are_explicit_and_calendar_valid(self):
        for text in ("June 3, 2026", "3 June 2026", "Jun. 3 2026", "2026-06-03"):
            with self.subTest(text=text):
                self.assertEqual(scraper.parse_date(text), "2026-06-03")
        for text in ("June 3", "2026-02-30", "June 3, 2026 or June 5, 2026"):
            with self.subTest(text=text):
                self.assertIsNone(scraper.parse_date(text))

    def test_refuses_to_join_label_and_date_across_paragraphs(self):
        html = "<p>Paper submission deadline:</p><p>Notification: June 3, 2026</p>"
        with self.assertRaises(scraper.ScrapeError):
            scraper.parse_deadline(html, 2027)

    def test_refuses_multiple_rounds(self):
        html = "<h2>Round 1</h2><p>Paper deadline: June 3, 2026</p>" \
               "<h2>Round 2</h2><p>Paper deadline: October 3, 2026</p>"
        with self.assertRaises(scraper.ScrapeError):
            scraper.parse_deadline(html, 2027)

    def test_refuses_revised_or_multiple_dates_in_row(self):
        for text in ("June 3, 2026; October 3, 2026", "<del>June 3, 2026</del>June 5, 2026"):
            with self.subTest(text=text), self.assertRaises(scraper.ScrapeError):
                scraper.parse_deadline(f"<p>Paper deadline: {text}</p>", 2027)

    def test_rejects_mixed_deadline_types(self):
        html = "<p>Paper deadline: June 3, 2026 (abstract and notification dates to follow)</p>"
        with self.assertRaises(scraper.ScrapeError):
            scraper.parse_deadline(html, 2027)

    def test_ignores_scripts_and_unrelated_labels(self):
        html = "<script>Paper deadline: June 3, 2026</script>" \
               "<p>Abstract deadline: June 3, 2026</p><p>Notification: July 3, 2026</p>"
        with self.assertRaises(scraper.ScrapeError):
            scraper.parse_deadline(html, 2027)

    def test_paper_submission_prose_is_not_a_deadline_label(self):
        html = "<p>Paper deadline: June 3, 2026</p><p>Paper submissions can include 13 pages</p>"
        self.assertEqual(scraper.parse_deadline(html, 2027)["deadline_date"], "2026-06-03")

    def test_rejects_year_outside_configured_conference(self):
        with self.assertRaises(scraper.ScrapeError):
            scraper.parse_deadline("<p>Paper deadline: June 3, 2028</p>", 2027)

    def test_conference_year_is_configuration_not_wall_clock(self):
        with patch.object(scraper, "fetch_page", return_value="<p>Paper deadline: June 3, 2026</p>"):
            candidate = scraper.scrape_conference("ccs", scraper.CFP_CONFIGS["ccs"])
        self.assertEqual(candidate["conference_year"], 2026)
        self.assertNotIn("cycles", candidate)


class CandidateOutputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "candidates.yaml"

    def test_output_required_before_network_access(self):
        with patch.object(scraper, "fetch_page") as fetch, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                scraper.main([])
        self.assertEqual(raised.exception.code, 2)
        fetch.assert_not_called()

    def test_canonical_and_legacy_app_paths_are_rejected(self):
        for path in (scraper.DATA_DIR / "scraped.yaml", Path("/app/data/scraped.yaml")):
            with self.subTest(path=path), self.assertRaises(ValueError):
                scraper.validate_output_path(path)
        link = Path(self.temporary.name) / "canonical"
        link.symlink_to(scraper.DATA_DIR, target_is_directory=True)
        with self.assertRaises(ValueError):
            scraper.validate_output_path(link / "scraped.yaml")
        self.assertEqual(scraper.validate_output_path("/app/output/candidates.yaml"),
                         Path("/app/output/candidates.yaml"))

    def test_success_writes_review_report_only(self):
        with patch.object(scraper, "fetch_page", return_value="<p>Paper deadline: June 3, 2026</p>"), \
                contextlib.redirect_stdout(io.StringIO()):
            code = scraper.main(["ccs", "--output", str(self.output)])
        self.assertEqual(code, 0)
        report = yaml.safe_load(self.output.read_text())
        self.assertTrue(report["requires_review"])
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["candidates"][0]["conference_year"], 2026)

    def test_fetch_failure_is_reported_and_nonzero(self):
        with patch.object(scraper, "fetch_page", side_effect=scraper.ScrapeError("network timeout")), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = scraper.main(["ccs", "--output", str(self.output)])
        self.assertEqual(code, 1)
        report = yaml.safe_load(self.output.read_text())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["candidates"], [])
        self.assertIn("network timeout", report["failures"][0]["reason"])

    def test_unknown_conference_and_partial_failures_remain_visible(self):
        with patch.object(scraper, "fetch_page", return_value="<p>Paper deadline: June 3, 2026</p>"), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = scraper.main(["ccs", "typo", "--output", str(self.output)])
        self.assertEqual(code, 1)
        report = yaml.safe_load(self.output.read_text())
        self.assertEqual(report["status"], "partial")
        self.assertEqual(len(report["candidates"]), 1)
        self.assertEqual(report["failures"][0]["slug"], "typo")


class OfficialCollectorTests(unittest.TestCase):
    def collect(self, html, slug='example'):
        return scraper.collect_conference({'slug': slug, 'homepage': 'https://example.org/2027'}, lambda url: html)

    def test_generic_explicit_utc_and_aoe(self):
        for suffix, expected in [('5 PM UTC', '17:00:00+00:00'), ('23:30 UTC', '23:30:00+00:00'), ('AoE', '23:59:59-12:00'), ('12:00 AoE', '12:00:00-12:00'), ('5 PM AoE', '17:00:00-12:00'), ('23:59 UTC+02:00', '23:59:00+02:00'), ('5 PM GMT-4', '17:00:00-04:00'), ('5 PM PST', '17:00:00-08:00')]:
            with self.subTest(suffix=suffix):
                result = self.collect(f'<h1>Example 2027</h1><p>Paper deadline: June 3, 2027 {suffix}</p>')
                self.assertEqual(result['status'], 'ok')
                self.assertEqual(result['candidates'][0]['value'], '2027-06-03T' + expected)
                self.assertIsNone(result['candidates'][0]['cycle_name'])

    def test_ambiguous_time_year_and_round_stay_review_only(self):
        pages = [
            '<h1>Example</h1><p>Paper deadline: June 3, 2027 AoE</p>',
            '<h1>Example 2027</h1><p>Paper deadline: June 3, 2027</p>',
            '<h1>Example 2027</h1><p>Paper deadline:</p><p>June 3, 2027 AoE</p>',
            '<h1>Example 2027</h1><p>Paper deadline: June 3, 2027 AoE</p><p>Paper deadline: July 3, 2027 AoE</p>',
            '<h1>Example 2027</h1><h2>Cycle 1</h2><p>Paper deadline: June 3, 2027 AoE</p>',
            '<h1>Example 2027</h1><p>Paper deadline: <del>June 1, 2027</del> June 3, 2027 AoE</p>',
        ]
        for html in pages:
            with self.subTest(html=html):
                result = self.collect(html)
                self.assertEqual(result['status'], 'review')
                self.assertFalse(any(c['applicable'] for c in result['candidates']))

    def test_real_usenix_html_has_two_explicit_cycles(self):
        html = (Path(__file__).parent / 'fixtures/usenix-security-2027.html').read_text()
        conference = {'slug': 'usenix-security', 'homepage': 'https://www.usenix.org/conference/usenixsecurity27/call-for-papers'}
        result = scraper.collect_conference(conference, lambda url: html)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(len(result['candidates']), 6)
        self.assertIn('Important Information (AoE) / Cycle 1', result['candidates'][0]['evidence'])
        self.assertEqual(result['candidates'][1]['value'], '2026-08-25T23:59:59-12:00')
        self.assertEqual(result['candidates'][4]['cycle_name'], 'Cycle 2')
        self.assertEqual(result['candidates'][4]['value'], '2027-01-26T23:59:59-12:00')
        self.assertEqual(result['candidates'][4]['track_name'], 'Paper (incl. SoK)')
        changed = scraper.collect_conference(conference, lambda url: html.replace('Important Information (AoE)', 'Important Information'))
        self.assertEqual(changed['status'], 'review')

    def test_follows_only_one_unique_same_host_cfp(self):
        pages = {'https://example.org/2027': '<h1>Example 2027</h1><a href="/cfp">Call for Papers</a><a href="https://other.org/cfp">CFP</a>',
                 'https://example.org/cfp': '<h1>Example 2027</h1><p>Paper deadline: June 3, 2027 AoE</p>'}
        calls = []
        def fetch(url):
            calls.append(url)
            return pages[url]
        result = scraper.collect_conference({'slug': 'example', 'homepage': 'https://example.org/2027'}, fetch)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['source_url'], 'https://example.org/cfp')
        self.assertEqual(len(calls), 2)

    def test_fetch_failure_preserves_failure_reason(self):
        def fetch(url):
            raise scraper.ScrapeError('HTTP 503')
        result = scraper.collect_conference({'slug': 'example', 'homepage': 'https://example.org'}, fetch)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('503', result['failure'])


if __name__ == "__main__":
    unittest.main()
