"""Guard the daily job's data ownership and failure handling boundaries."""
from pathlib import Path
import unittest

import yaml


class DailyWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (Path(__file__).resolve().parents[2] /
                    ".github/workflows/daily-update.yml").read_text()
        cls.workflow = yaml.safe_load(cls.text)
        cls.steps = cls.workflow["jobs"]["update-data"]["steps"]

    def test_only_maintained_data_repository_is_checked_out_as_upstream(self):
        checkouts = [s["with"] for s in self.steps
                     if s.get("uses", "").startswith("actions/checkout@")]
        self.assertEqual(len(checkouts), 2)
        self.assertEqual(checkouts[1]["repository"], "yuranqiu/cfpctl-data")
        self.assertEqual(checkouts[1]["ref"], "main")
        self.assertTrue(all(s["persist-credentials"] is False for s in checkouts))
        self.assertNotIn("ccfddl", self.text.lower())
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})

    def test_pull_request_targets_same_data_checkout_with_explicit_token(self):
        checkout = next(s["with"] for s in self.steps
                        if s.get("with", {}).get("repository") == "yuranqiu/cfpctl-data")
        pr = next(s["with"] for s in self.steps
                  if s.get("uses", "").startswith("peter-evans/create-pull-request@"))
        self.assertEqual(pr["path"], checkout["path"])
        self.assertEqual(pr["token"], checkout["token"])
        self.assertEqual(pr["token"], "${{ secrets.CFPCTL_DATA_TOKEN }}")
        self.assertEqual(pr["base"], "main")
        self.assertEqual(pr["branch"], "auto/official-update")
        self.assertEqual(set(pr["add-paths"].split()), {
            "ai.yaml", "database.yaml", "graphics.yaml", "hci.yaml",
            "interdisciplinary.yaml", "network.yaml", "security.yaml",
            "software.yaml", "systems.yaml", "theory.yaml",
        })
        self.assertTrue(pr["body-path"].startswith("${{ runner.temp }}/"))
        self.assertNotIn("labels", pr)
        guard = next(s for s in self.steps if s.get("env", {}).get("DATA_TOKEN"))
        self.assertIn('if [ -z "$DATA_TOKEN" ]', guard["run"])
        self.assertIn("exit 1", guard["run"])

    def test_update_and_validation_failures_block_publication_but_keep_reports(self):
        update_index = next(i for i, s in enumerate(self.steps)
                            if "scripts/update_official.py" in s.get("run", ""))
        validate_index = next(i for i, s in enumerate(self.steps)
                              if "validate --data-dir" in s.get("run", ""))
        pr_index = next(i for i, s in enumerate(self.steps)
                        if s.get("uses", "").startswith("peter-evans/create-pull-request@"))
        update = self.steps[update_index]
        self.assertIn("--data-dir .upstream/cfpctl-data", update["run"])
        self.assertIn("--apply", update["run"])
        self.assertLess(update_index, validate_index)
        self.assertLess(validate_index, pr_index)
        for step in self.steps[:pr_index + 1]:
            self.assertNotIn("continue-on-error", step)
            self.assertNotIn("|| true", step.get("run", ""))
            self.assertNotEqual(step.get("if"), "always()")
        reports = [s for s in self.steps if s.get("uses", "").startswith("actions/upload-artifact@")]
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["if"], "always()")
        self.assertIn("official-report.json", reports[0]["with"]["path"])
        self.assertIn("official-report.md", reports[0]["with"]["path"])


if __name__ == "__main__":
    unittest.main()
