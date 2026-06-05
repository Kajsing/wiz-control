import tempfile
import unittest
from pathlib import Path

from wiz_windows_shortcuts import build_cli_shortcut_plan, sanitize_shortcut_name


class WizWindowsShortcutTests(unittest.TestCase):
    def test_sanitize_shortcut_name_replaces_invalid_windows_characters(self):
        self.assertEqual(sanitize_shortcut_name('Evening: Off / Now'), "Evening- Off - Now")

    def test_sanitize_shortcut_name_rejects_empty_names(self):
        with self.assertRaises(ValueError):
            sanitize_shortcut_name(" ... ")

    def test_build_cli_shortcut_plan_targets_cli_script(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = Path(temp_dir) / "wiz_cli.py"
            plan = build_cli_shortcut_plan(
                "Evening Off",
                ["favorite", "Evening Off"],
                temp_dir,
                python_executable="python.exe",
                script_path=script_path,
            )

        self.assertEqual(plan["name"], "Evening Off")
        self.assertEqual(Path(plan["path"]).name, "Evening Off.lnk")
        self.assertEqual(plan["target"], "python.exe")
        self.assertIn('"favorite"', plan["arguments"])
        self.assertIn('"Evening Off"', plan["arguments"])
        self.assertEqual(Path(plan["working_dir"]), script_path.parent.resolve())


if __name__ == "__main__":
    unittest.main()
