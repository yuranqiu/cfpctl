import contextlib
from copy import deepcopy
import io
from pathlib import Path
import sys
import tempfile
import unittest

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import convert_ccfddl as convert


def cycle(year, day="06-01"):
    return {"name": str(year), "deadline": f"{year}-{day}T23:59:59-12:00"}


def conference(slug="demo"):
    return {"name": slug.upper(), "slug": slug, "rank": {"ccf": "A"},
            "fields": ["ai"], "homepage": "https://example.org", "cycles": [cycle(2026)]}


def upstream(title="Demo", year=2026):
    return {"title": title, "rank": {"ccf": "A"}, "confs": [
        {"year": year, "link": "https://example.org", "timezone": "AoE",
         "timeline": [{"deadline": f"{year}-06-01 23:59:59"}]}]}


class DateTests(unittest.TestCase):
    def test_formats_offsets_and_unknowns(self):
        for value, expected in [
            ("2026-10-01T23:59:59-07:00", "2026-10-01T23:59:59-07:00"),
            ("2026-10-01T23:59:59", "2026-10-01T23:59:59-12:00"),
            ("2026-10-01 23:59:59+08:00", "2026-10-01T23:59:59+08:00"),
            ("2026-10-01T23:59:59Z", "2026-10-01T23:59:59+00:00"),
            ("2026-10-01", "2026-10-01T00:00:00-12:00"),
            ("TBD", None), (None, None),
        ]:
            with self.subTest(value=value):
                self.assertEqual(convert.convert_datetime(value, "AoE"), expected)

    def test_utc_and_pt_daylight_saving(self):
        self.assertTrue(convert.convert_datetime("2026-06-01", "UTC").endswith("+00:00"))
        self.assertTrue(convert.convert_datetime("2026-06-01", "PT").endswith("-07:00"))
        self.assertTrue(convert.convert_datetime("2026-01-01", "PT").endswith("-08:00"))
        self.assertTrue(convert.convert_datetime("2026-01-01", "UTC+5:30").endswith("+05:30"))
        for tz in ("guess", "UTC+24", "UTC+5:60"):
            with self.assertRaises(ValueError):
                convert.parse_timezone(tz)
        with self.assertRaises(ValueError):
            convert.convert_datetime("2026-02-30", "AoE")

    def test_category_aliases_and_repeated_rounds(self):
        entry = upstream("FSE")
        entry["confs"][0]["timeline"].append({"deadline": "2026-09-01 23:59:59"})
        security = convert.convert_conference(entry, ["security"], "SC")[0]
        self.assertEqual(security["slug"], "fse-crypto")
        self.assertEqual(len(security["cycles"]), 2)
        self.assertEqual(convert.convert_conference(entry, ["software"], "SE")[0]["slug"], "fse")


class MergeTests(unittest.TestCase):
    def test_rank_enrichment_survives_missing_upstream_core(self):
        existing = conference()
        existing["rank"]["core"] = "A*"
        incoming = conference()
        incoming["rank"]["ccf"] = "B"
        self.assertEqual(convert.merge_conference(existing, incoming)["rank"], {"ccf": "B", "core": "A*"})

    def test_curated_metadata_and_tracks_survive_with_new_year(self):
        existing = conference()
        existing.update(accept_rate="25%", verified=True, cfp="https://example.org/cfp",
                        rolling_review={"name": "ARR"}, location="Curated")
        existing["cycles"] = [{"name": "2026", "tracks": [{"name": "Demo", "deadline": cycle(2026)["deadline"]}]}]
        incoming = conference()
        incoming["cycles"] = [cycle(2026, "07-01"), cycle(2027)]
        original = deepcopy(existing)
        merged = convert.merge_conference(existing, incoming)
        for key in ("accept_rate", "verified", "cfp", "rolling_review", "location"):
            self.assertEqual(merged[key], existing[key])
        self.assertEqual(merged["cycles"], existing["cycles"] + [cycle(2027)])
        self.assertEqual(existing, original)

    def test_updated_rounds_replace_year_but_missing_history_survives(self):
        old = [cycle(2024), cycle(2026), cycle(2026, "09-01")]
        new = [cycle(2026, "07-01"), cycle(2026, "10-01"), cycle(2027)]
        self.assertEqual(convert.merge_cycles(old, new), [cycle(2024)] + new)

    def test_named_manual_rounds_do_not_duplicate_upstream_edition(self):
        old = [{"name": "Fall Cycle", "tracks": [{"name": "Research", "deadline": cycle(2026, "09-01")["deadline"]}]}]
        new = [cycle(2025), {"name": "2027", "deadline": cycle(2026, "09-01")["deadline"]}, cycle(2028)]
        merged = convert.merge_cycles(old, new)
        self.assertIn(old[0], merged)
        self.assertNotIn(new[1], merged)
        self.assertIn(new[0], merged)
        self.assertIn(new[2], merged)

    def test_rescheduled_named_round_requires_review(self):
        old = [{"name": "Fall Cycle", "tracks": [{"name": "Research", "deadline": cycle(2026, "09-01")["deadline"]}]}]
        new = [{"name": "2027", "deadline": cycle(2026, "09-08")["deadline"]}]
        self.assertEqual(convert.merge_cycles(old, new), old)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source, self.output = self.root / "conference", self.root / "data"
        self.output.mkdir()
        for category in convert.CATEGORY_MAP:
            path = self.source / category
            path.mkdir(parents=True)
            (path / "demo.yml").write_text(yaml.safe_dump([upstream(category)]))
        (self.output / "ai.yaml").write_text(yaml.safe_dump([conference("local-only")]))

    def refresh(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return convert.refresh(self.source, self.output)

    def bytes(self):
        return {p.name: p.read_bytes() for p in self.output.glob("*.yaml")}

    def test_full_snapshot_preserves_local_only_and_is_idempotent(self):
        self.refresh()
        self.assertEqual(len(self.bytes()), 10)
        slugs = [c["slug"] for c in yaml.safe_load((self.output / "ai.yaml").read_text())]
        self.assertIn("local-only", slugs)
        self.assertIn("ai", slugs)
        before = self.bytes()
        self.refresh()
        self.assertEqual(self.bytes(), before)

    def test_last_category_failure_does_not_write_earlier_categories(self):
        before = self.bytes()
        (self.source / "SE" / "demo.yml").write_text("invalid: [")
        with self.assertRaises(ValueError):
            self.refresh()
        self.assertEqual(self.bytes(), before)

    def test_missing_or_empty_category_aborts(self):
        before = self.bytes()
        (self.source / "SE" / "demo.yml").unlink()
        with self.assertRaises(ValueError):
            self.refresh()
        self.assertEqual(self.bytes(), before)

    def test_duplicate_across_categories_aborts(self):
        before = self.bytes()
        (self.source / "SE" / "demo.yml").write_text(yaml.safe_dump([upstream("AI")]))
        with self.assertRaisesRegex(ValueError, "Duplicate upstream"):
            self.refresh()
        self.assertEqual(self.bytes(), before)

    def test_invalid_date_aborts(self):
        before = self.bytes()
        entry = upstream("SE")
        entry["confs"][0]["timeline"][0]["deadline"] = "2026-02-30 12:00:00"
        (self.source / "SE" / "demo.yml").write_text(yaml.safe_dump([entry]))
        with self.assertRaises(ValueError):
            self.refresh()
        self.assertEqual(self.bytes(), before)


if __name__ == "__main__":
    unittest.main()
