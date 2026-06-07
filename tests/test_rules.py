import unittest

from ai_patch_risk_checker.config import DEFAULT_CONFIG
from ai_patch_risk_checker.diff_parser import parse_unified_diff
from ai_patch_risk_checker.rules import analyze_patch, is_test_path, max_severity, severity_at_least
from ai_patch_risk_checker.models import Finding


def report_for(diff):
    return analyze_patch(parse_unified_diff(diff), DEFAULT_CONFIG)


class RuleTests(unittest.TestCase):
    def test_auth_change_without_tests_is_high(self):
        diff = "diff --git a/src/auth/session.py b/src/auth/session.py\n--- a/src/auth/session.py\n+++ b/src/auth/session.py\n@@ -1 +1 @@\n-old\n+new\n"
        report = report_for(diff)
        self.assertIn("auth_without_tests", [finding.code for finding in report.findings])
        self.assertEqual(report.summary["risk_level"], "high")

    def test_code_change_without_tests_is_medium(self):
        diff = "diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-old\n+new\n"
        report = report_for(diff)
        self.assertIn("code_without_tests", [finding.code for finding in report.findings])

    def test_code_change_with_tests_avoids_missing_test_finding(self):
        diff = (
            "diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-old\n+new\n"
            "diff --git a/tests/test_app.py b/tests/test_app.py\n--- a/tests/test_app.py\n+++ b/tests/test_app.py\n@@ -1 +1 @@\n-old\n+new\n"
        )
        report = report_for(diff)
        self.assertNotIn("code_without_tests", [finding.code for finding in report.findings])

    def test_dependency_change_without_tests_is_high(self):
        diff = "diff --git a/pyproject.toml b/pyproject.toml\n--- a/pyproject.toml\n+++ b/pyproject.toml\n@@ -1 +1 @@\n-old\n+new\n"
        report = report_for(diff)
        self.assertIn("dependencies_without_tests", [finding.code for finding in report.findings])

    def test_ci_change_without_tests_is_high(self):
        diff = "diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n--- a/.github/workflows/ci.yml\n+++ b/.github/workflows/ci.yml\n@@ -1 +1 @@\n-old\n+new\n"
        report = report_for(diff)
        self.assertIn("ci_without_tests", [finding.code for finding in report.findings])

    def test_secret_like_addition_is_critical(self):
        fake = "github_" + "pat_" + ("A" * 44)
        diff = f"diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+TOKEN={fake}\n"
        report = report_for(diff)
        self.assertEqual(report.summary["risk_level"], "critical")
        self.assertIn("secret_like_addition", [finding.code for finding in report.findings])

    def test_large_patch_finding(self):
        added = "".join(f"+line {index}\n" for index in range(650))
        diff = f"diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -0,0 +1,650 @@\n{added}"
        report = report_for(diff)
        self.assertIn("large_patch", [finding.code for finding in report.findings])

    def test_large_deletion_finding(self):
        deleted = "".join(f"-line {index}\n" for index in range(220))
        diff = f"diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1,220 +0,0 @@\n{deleted}"
        report = report_for(diff)
        self.assertIn("large_deletion", [finding.code for finding in report.findings])

    def test_generated_file_finding(self):
        diff = "diff --git a/package-lock.json b/package-lock.json\n--- a/package-lock.json\n+++ b/package-lock.json\n@@ -1 +1 @@\n-old\n+new\n"
        report = report_for(diff)
        self.assertIn("generated_or_lockfile_changed", [finding.code for finding in report.findings])

    def test_is_test_path(self):
        self.assertTrue(is_test_path("tests/test_app.py"))
        self.assertTrue(is_test_path("src/app.test.ts"))
        self.assertFalse(is_test_path("src/app.py"))

    def test_severity_helpers(self):
        self.assertTrue(severity_at_least("critical", "high"))
        self.assertEqual(max_severity([Finding("a", "low", "x"), Finding("b", "high", "x")]), "high")


if __name__ == "__main__":
    unittest.main()
