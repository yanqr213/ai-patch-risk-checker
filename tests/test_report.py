import json
import unittest

from ai_patch_risk_checker.baseline import apply_baseline, render_baseline
from ai_patch_risk_checker.config import DEFAULT_CONFIG, default_config_json, load_config
from ai_patch_risk_checker.diff_parser import parse_unified_diff
from ai_patch_risk_checker.report import render_csv, render_json, render_markdown, render_sarif
from ai_patch_risk_checker.rules import analyze_patch


class ReportTests(unittest.TestCase):
    def setUp(self):
        diff = "diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-old\n+new\n"
        self.report = analyze_patch(parse_unified_diff(diff), DEFAULT_CONFIG)

    def test_render_json(self):
        data = json.loads(render_json(self.report))
        self.assertEqual(data["summary"]["files_changed"], 1)

    def test_render_markdown_contains_sections(self):
        markdown = render_markdown(self.report)
        self.assertIn("AI Patch Risk Report", markdown)
        self.assertIn("Changed Files", markdown)
        self.assertIn("Fingerprint", markdown)

    def test_render_csv_has_header(self):
        csv = render_csv(self.report)
        self.assertTrue(csv.startswith("status,severity,code,fingerprint,message"))

    def test_render_csv_includes_suppressed_rows(self):
        baseline = json.loads(render_baseline(self.report))
        filtered = apply_baseline(self.report, {entry["fingerprint"] for entry in baseline["findings"]})
        csv = render_csv(filtered)
        self.assertIn("suppressed,medium,code_without_tests", csv)

    def test_render_sarif_has_code_scanning_shape(self):
        sarif = json.loads(render_sarif(self.report))
        run = sarif["runs"][0]
        self.assertEqual(sarif["version"], "2.1.0")
        self.assertEqual(run["tool"]["driver"]["name"], "ai-patch-risk-checker")
        self.assertEqual(run["results"][0]["ruleId"], "code_without_tests")
        self.assertIn("aiPatchRisk/v1", run["results"][0]["partialFingerprints"])
        self.assertEqual(run["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"], "src/app.py")

    def test_default_config_json_is_loadable(self):
        data = json.loads(default_config_json())
        self.assertIn("categories", data)


if __name__ == "__main__":
    unittest.main()
