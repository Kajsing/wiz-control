import json
import re
import subprocess
import sys
from pathlib import Path


INVALID_SHORTCUT_CHARS = r'[<>:"/\\|?*]'


def sanitize_shortcut_name(name):
    clean_name = re.sub(INVALID_SHORTCUT_CHARS, "-", str(name).strip())
    clean_name = re.sub(r"\s+", " ", clean_name).strip(" .")
    if not clean_name:
        raise ValueError("Shortcut name cannot be empty.")
    return clean_name


def quote_windows_argument(value):
    escaped = str(value).replace('"', '\\"')
    return f'"{escaped}"'


def build_cli_shortcut_plan(name, command, output_dir, python_executable=None, script_path=None):
    clean_name = sanitize_shortcut_name(name)
    output_path = Path(output_dir).expanduser().resolve() / f"{clean_name}.lnk"
    script = Path(script_path or Path(__file__).with_name("wiz_cli.py")).resolve()
    executable = python_executable or sys.executable
    arguments = " ".join([quote_windows_argument(script), *[quote_windows_argument(arg) for arg in command]])

    return {
        "name": clean_name,
        "path": str(output_path),
        "target": executable,
        "arguments": arguments,
        "working_dir": str(script.parent),
    }


def create_windows_shortcut(plan):
    shortcut_path = Path(plan["path"])
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)

    powershell_script = """
$shortcutPath = $args[0]
$targetPath = $args[1]
$arguments = $args[2]
$workingDirectory = $args[3]
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.Arguments = $arguments
$shortcut.WorkingDirectory = $workingDirectory
$shortcut.Save()
"""
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            powershell_script,
            plan["path"],
            plan["target"],
            plan["arguments"],
            plan["working_dir"],
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Unknown shortcut creation error."
        raise RuntimeError(message)

    return plan


def plan_to_json(plan):
    return json.dumps(plan, indent=2, sort_keys=True)
