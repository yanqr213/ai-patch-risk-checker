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

    def test_check_writes_sarif_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diff = root / "patch.diff"
            diff.write_text("diff --git a/src/auth/session.py b/src/auth/session.py\n--- a/src/auth/session.py\n+++ b/src/auth/session.py\n@@ -1 +1 @@\n-old\n+new\n", encoding="utf-8")
            output = root / "patch-risk.sarif"
            exit_code = main(["check", "--diff", str(diff), "--format", "sarif", "--output", str(output)])
            self.assertEqual(exit_code, 1)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(data["version"], "2.1.0")
            self.assertEqual(data["runs"][0]["results"][0]["level"], "error")

    def test_analyze_writes_remediation_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diff = root / "patch.diff"
            diff.write_text("diff --git a/src/auth/session.py b/src/auth/session.py\n--- a/src/auth/session.py\n+++ b/src/auth/session.py\n@@ -1 +1 @@\n-old\n+new\n", encoding="utf-8")
            markdown = root / "reports" / "remediation.md"
            json_output = root / "reports" / "remediation.json"

            md_code = main(["analyze", "--diff", str(diff), "--format", "remediation", "--output", str(markdown)])
            json_code = main(["analyze", "--diff", str(diff), "--format", "remediation-json", "--output", str(json_output)])

            self.assertEqual(md_code, 0)
            self.assertEqual(json_code, 0)
            self.assertIn("AI Patch Risk Remediation Plan", markdown.read_text(encoding="utf-8"))
            payload = json.loads(json_output.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "ai-patch-risk-checker.remediation.v1")
            self.assertGreaterEqual(payload["summary"]["task_count"], 1)

    def test_baseline_suppresses_known_check_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diff = root / "patch.diff"
            baseline = root / "baseline.json"
            report = root / "report.json"
            diff.write_text("diff --git a/src/auth/session.py b/src/auth/session.py\n--- a/src/auth/session.py\n+++ b/src/auth/session.py\n@@ -1 +1 @@\n-old\n+new\n", encoding="utf-8")
            self.assertEqual(0, main(["baseline", "--diff", str(diff), "--output", str(baseline)]))
            exit_code = main(["check", "--diff", str(diff), "--baseline", str(baseline), "--format", "json", "--output", str(report)])
            self.assertEqual(exit_code, 0)
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(data["summary"]["finding_count"], 0)
            self.assertEqual(data["summary"]["suppressed_finding_count"], 2)

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
            output = Path(tmp) / "nested" / "config.json"
            exit_code = main(["init-config", "--output", str(output)])
            self.assertEqual(exit_code, 0)
            self.assertIn("large_change_lines", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
