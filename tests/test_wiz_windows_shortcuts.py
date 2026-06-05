import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wiz_windows_shortcuts import build_cli_shortcut_plan, create_windows_shortcut, sanitize_shortcut_name


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

    def test_create_windows_shortcut_uses_encoded_powershell_for_paths_with_spaces(self):
        plan = {
            "name": "Stue 1 Toggle",
            "path": str(Path(tempfile.gettempdir()) / "Stue 1 Toggle.lnk"),
            "target": r"C:\Program Files\Python\python.exe",
            "arguments": r'"C:\project\wiz-control\wiz_cli.py" "toggle" "device" "Stue 1"',
            "working_dir": r"C:\project\wiz-control",
        }

        with mock.patch("wiz_windows_shortcuts.subprocess.run") as run_mock:
            run_mock.return_value.returncode = 0
            run_mock.return_value.stderr = ""
            run_mock.return_value.stdout = ""
            create_windows_shortcut(plan)

        args = run_mock.call_args.args[0]
        self.assertIn("-EncodedCommand", args)
        self.assertNotIn(plan["path"], args)
        self.assertNotIn(plan["arguments"], args)


if __name__ == "__main__":
    unittest.main()
