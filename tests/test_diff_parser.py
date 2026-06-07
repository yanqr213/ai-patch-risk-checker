import unittest

from ai_patch_risk_checker.diff_parser import parse_unified_diff


class DiffParserTests(unittest.TestCase):
    def test_parses_modified_file(self):
        diff = "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new\n"
        files = parse_unified_diff(diff)
        self.assertEqual(files[0].path, "app.py")
        self.assertEqual(files[0].additions, 1)
        self.assertEqual(files[0].deletions, 1)

    def test_parses_added_file(self):
        diff = "diff --git a/new.py b/new.py\nnew file mode 100644\n--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n+print('hi')\n"
        files = parse_unified_diff(diff)
        self.assertEqual(files[0].status, "added")

    def test_parses_deleted_file(self):
        diff = "diff --git a/old.py b/old.py\ndeleted file mode 100644\n--- a/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-print('bye')\n"
        files = parse_unified_diff(diff)
        self.assertEqual(files[0].status, "deleted")

    def test_ignores_non_diff_text(self):
        self.assertEqual(parse_unified_diff("notes only\n"), [])


if __name__ == "__main__":
    unittest.main()
