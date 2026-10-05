import contextlib
from copy import deepcopy
import importlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

from scripts import clean_no_deadline as cleaner
from scripts import clean_tbd


DATE = "2024-01-01T23:59:59-12:00"


class CleanDataTests(unittest.TestCase):
    def test_keeps_track_only_cycles_and_all_valid_history(self):
        data = [{"slug": "example", "cycles": [
            {"name": "2020", "deadline": "2019-12-01T23:59:59-12:00"},
            {"name": "2024", "tracks": [{"name": "Research", "deadline": DATE}]},
            {"name": "2025", "deadline": None},
        ]}]
        before = deepcopy(data)
        cleaned = cleaner.clean_data(data)
        self.assertEqual(len(cleaned[0]["cycles"]), 2)
        self.assertEqual(cleaned[0]["cycles"], data[0]["cycles"][:2])
        self.assertEqual(data, before, "cleaning should not mutate callers' input")

    def test_tbd_cycle_does_not_destroy_usable_track(self):
        data = [{"slug": "example", "cycles": [{"name": "2024", "deadline": "TBD", "tracks": [
            {"name": "Research", "deadline": DATE}, {"name": "Poster", "deadline": "TBA (later)"}
        ]}]}]
        cleaned = cleaner.clean_data(data, placeholders_only=True)
        cycle = cleaned[0]["cycles"][0]
        self.assertNotIn("deadline", cycle)
        self.assertEqual(cycle["tracks"], [{"name": "Research", "deadline": DATE}])

    def test_only_invalid_track_is_removed_and_valid_parent_remains(self):
        data = [{"slug": "example", "cycles": [{"name": "2024", "deadline": DATE, "tracks": [
            {"name": "Poster", "deadline": ""}
        ]}]}]
        cleaned = cleaner.clean_data(data)
        self.assertEqual(cleaned[0]["cycles"], [{"name": "2024", "deadline": DATE}])

    def test_empty_conference_and_placeholder_only_tracks_are_removed(self):
        data = [{"slug": "example", "cycles": [{"name": "2024", "tracks": [
            {"name": "Research", "deadline": " TBD "}
        ]}]}]
        self.assertEqual(cleaner.clean_data(data), [])
        self.assertEqual(cleaner.clean_data(data, placeholders_only=True), [])

    def test_malformed_container_types_fail_instead_of_deleting_data(self):
        for data in ({"slug": "example"}, [None], [{"cycles": None}], [{"cycles": [None]}],
                     [{"cycles": [{"tracks": [None]}]}]):
            with self.subTest(data=data), self.assertRaises(ValueError):
                cleaner.clean_data(data)


class CleanFileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.path = self.directory / "conferences.yaml"

    def test_cycle_only_changes_are_written_and_second_run_is_noop(self):
        data = [{"slug": "example", "cycles": [{"name": "2024", "deadline": DATE}, {"name": "2025"}]}]
        self.path.write_text(yaml.safe_dump(data))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cleaner.clean_directory(self.directory), 1)
            content = self.path.read_bytes()
            modified = self.path.stat().st_mtime_ns
            self.assertEqual(cleaner.clean_directory(self.directory), 0)
        self.assertEqual(len(yaml.safe_load(content)[0]["cycles"]), 1)
        self.assertEqual(content, self.path.read_bytes())
        self.assertEqual(modified, self.path.stat().st_mtime_ns)

    def test_all_inputs_are_checked_before_any_rewrite(self):
        self.path.write_text(yaml.safe_dump([{"slug": "example", "cycles": [{"name": "2024"}]}]))
        original = self.path.read_bytes()
        (self.directory / "z-malformed.yaml").write_text("invalid: mapping\n")
        with self.assertRaises(ValueError):
            cleaner.clean_directory(self.directory)
        self.assertEqual(self.path.read_bytes(), original)

    def test_importing_scripts_has_no_filesystem_side_effect(self):
        with patch("pathlib.Path.open", side_effect=AssertionError("unexpected file access")):
            importlib.reload(cleaner)
            importlib.reload(clean_tbd)

    def test_default_directory_is_repository_relative(self):
        self.assertEqual(cleaner.DEFAULT_DATA_DIR, Path(__file__).resolve().parents[2] / "data")

    def test_tbd_cli_supports_data_dir(self):
        data = [{"slug": "example", "cycles": [{"name": "2024", "deadline": DATE},
                                                  {"name": "2025", "deadline": "TBD"}]}]
        self.path.write_text(yaml.safe_dump(data))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(clean_tbd.main(["--data-dir", str(self.directory)]), 0)
        self.assertEqual(len(yaml.safe_load(self.path.read_text())[0]["cycles"]), 1)

    def test_missing_directory_is_a_failure(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cleaner.main(["--data-dir", str(self.directory / "missing")]), 1)


if __name__ == "__main__":
    unittest.main()
