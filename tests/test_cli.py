import json
import tempfile
import unittest
from pathlib import Path

from ai_patch_risk_checker.cli import main


class CliTests(unittest.TestCase):
    def test_analyze_writes_json_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diff = root / "patch.diff"
            diff.write_text("diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-old\n+new\n", encoding="utf-8")
            output = root / "report.json"
            exit_code = main(["analyze", "--diff", str(diff), "--format", "json", "--output", str(output)])
            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["summary"]["files_changed"], 1)

    def test_check_returns_nonzero_on_high_risk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diff = root / "patch.diff"
            diff.write_text("diff --git a/src/auth/session.py b/src/auth/session.py\n--- a/src/auth/session.py\n+++ b/src/auth/session.py\n@@ -1 +1 @@\n-old\n+new\n", encoding="utf-8")
            exit_code = main(["check", "--diff", str(diff), "--format", "json"])
            self.assertEqual(exit_code, 1)

    def test_check_returns_zero_when_tests_are_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diff = root / "patch.diff"
            diff.write_text(
                "diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-old\n+new\n"
                "diff --git a/tests/test_app.py b/tests/test_app.py\n--- a/tests/test_app.py\n+++ b/tests/test_app.py\n@@ -1 +1 @@\n-old\n+new\n",
                encoding="utf-8",
            )
            exit_code = main(["check", "--diff", str(diff)])
            self.assertEqual(exit_code, 0)

    def test_init_config_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "config.json"
            exit_code = main(["init-config", "--output", str(output)])
            self.assertEqual(exit_code, 0)
            self.assertIn("large_change_lines", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
