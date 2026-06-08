import json
import tempfile
import unittest
from pathlib import Path

from ai_patch_risk_checker.baseline import apply_baseline, load_baseline, render_baseline
from ai_patch_risk_checker.config import DEFAULT_CONFIG
from ai_patch_risk_checker.diff_parser import parse_unified_diff
from ai_patch_risk_checker.rules import analyze_patch


AUTH_DIFF = "diff --git a/src/auth/session.py b/src/auth/session.py\n--- a/src/auth/session.py\n+++ b/src/auth/session.py\n@@ -1 +1 @@\n-old\n+new\n"


class BaselineTests(unittest.TestCase):
    def test_render_baseline_contains_fingerprints(self):
        report = analyze_patch(parse_unified_diff(AUTH_DIFF), DEFAULT_CONFIG)
        data = json.loads(render_baseline(report))
        self.assertEqual(data["schema_version"], 1)
        self.assertTrue(data["findings"][0]["fingerprint"])
        self.assertEqual(data["findings"][0]["code"], "auth_without_tests")

    def test_apply_baseline_suppresses_known_findings(self):
        report = analyze_patch(parse_unified_diff(AUTH_DIFF), DEFAULT_CONFIG)
        baseline = json.loads(render_baseline(report))
        filtered = apply_baseline(report, {entry["fingerprint"] for entry in baseline["findings"]})
        self.assertEqual(filtered.findings, [])
        self.assertEqual(len(filtered.suppressed_findings), 2)
        self.assertEqual(filtered.summary["risk_level"], "none")
        self.assertEqual(filtered.summary["suppressed_finding_count"], 2)

    def test_load_baseline_accepts_object_shape(self):
        report = analyze_patch(parse_unified_diff(AUTH_DIFF), DEFAULT_CONFIG)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.json"
            path.write_text(render_baseline(report), encoding="utf-8")
            fingerprints = load_baseline(path)
        self.assertEqual(len(fingerprints), 2)


if __name__ == "__main__":
    unittest.main()
