import json
import unittest

from ai_patch_risk_checker.config import DEFAULT_CONFIG, default_config_json, load_config
from ai_patch_risk_checker.diff_parser import parse_unified_diff
from ai_patch_risk_checker.report import render_csv, render_json, render_markdown
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

    def test_render_csv_has_header(self):
        csv = render_csv(self.report)
        self.assertTrue(csv.startswith("severity,code,message"))

    def test_default_config_json_is_loadable(self):
        data = json.loads(default_config_json())
        self.assertIn("categories", data)


if __name__ == "__main__":
    unittest.main()
