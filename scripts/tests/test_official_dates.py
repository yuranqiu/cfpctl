import unittest
from scripts.official_dates import parse_date, parse_timestamp


class ExplicitDateTests(unittest.TestCase):
    def test_supported_month_and_iso_forms(self):
        for text in ('September 3rd, 2026', 'Sept. 3, 2026', '3rd Sep 2026',
                     '03 September, 2026', '2026-09-03T23:59:00Z'):
            with self.subTest(text=text):
                self.assertEqual(parse_date(text), '2026-09-03')

    def test_missing_ambiguous_and_invalid_dates(self):
        for text in ('September 3rd', '2026-02-30', 'Feb 29th 2026',
                     'September 3, 2026 or 2026-09-04', 'September 3, 20266'):
            with self.subTest(text=text):
                self.assertIsNone(parse_date(text))


class ExplicitTimeTests(unittest.TestCase):
    def test_offsets_are_not_clocks(self):
        for text, expected in (
            ('23:59 UTC+05:30', '23:59:00+05:30'),
            ('5 PM GMT-4', '17:00:00-04:00'),
            ('11:59 PM UTC + 0530', '23:59:00+05:30'),
            ('23:59:59-12:00', '23:59:59-12:00'),
            ('2026-09-03T23:59:00Z', '23:59:00+00:00'),
            ('12 AM PDT', '00:00:00-07:00'),
            ('12 PM PST', '12:00:00-08:00'),
            ('5 PM UTC', '17:00:00+00:00')):
            with self.subTest(text=text):
                self.assertEqual(parse_timestamp(text, '2026-09-03'), '2026-09-03T' + expected)

    def test_dotted_meridiem(self):
        self.assertEqual(parse_timestamp('11:59 p.m. AoE', '2026-10-12'), '2026-10-12T23:59:00-12:00')
        self.assertEqual(parse_timestamp('12:00 a.m. UTC', '2026-10-12'), '2026-10-12T00:00:00+00:00')

    def test_aoe_clock_and_end_of_day(self):
        self.assertEqual(parse_timestamp('September 3, 2026 AoE', '2026-09-03'), '2026-09-03T23:59:59-12:00')
        self.assertEqual(parse_timestamp('5 PM', '2026-09-03', aoe=True), '2026-09-03T17:00:00-12:00')
        self.assertEqual(parse_timestamp('23:59 Anywhere on Earth', '2026-09-03'), '2026-09-03T23:59:00-12:00')

    def test_refuses_unclear_invalid_and_conflicting_times(self):
        for text in ('23:59', '23:59 PT', 'UTC', '5 PM UTC+15', '5 PM UTC+14:30',
                     '5 PM UTCfoo', '5 PM UTC+5.5', '5 PM EST AoE',
                     '5 PM GMT+05:99', '5 PM UTC+5:3', '5 PM UTC+12345',
                     '23:59 UTC or 22:00 UTC', '5 PM UTC / 6 PM', '24:00 UTC',
                     '12:60 UTC', '13 PM UTC', '5 PM AoE UTC', '12:00:99 UTC'):
            with self.subTest(text=text):
                self.assertIsNone(parse_timestamp(text, '2026-09-03'))
        self.assertIsNone(parse_timestamp('5 PM UTC', '2026-09-03', aoe=True))


if __name__ == '__main__':
    unittest.main()
