import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import wiz_cli


class FakeDiscovery:
    def __init__(self):
        self.commands = []

    def send_command(self, ip, method, params, timeout=2):
        self.commands.append((ip, method, params, timeout))
        return {"result": {"success": True}}


class WizCliTests(unittest.TestCase):
    def write_data(self, payload):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        data_file = Path(temp_dir.name) / "wiz_data.json"
        data_file.write_text(json.dumps(payload))
        return data_file

    def run_cli(self, argv, discovery=None):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return wiz_cli.main(argv, discovery=discovery)

    def test_device_command_targets_saved_ip(self):
        data_file = self.write_data(
            {
                "devices": {
                    "192.168.1.10": {
                        "moduleName": "Desk Lamp",
                        "roomId": "1",
                        "info": {},
                    }
                }
            }
        )
        discovery = FakeDiscovery()

        exit_code = self.run_cli(
            ["--data-file", str(data_file), "device", "192.168.1.10", "off"],
            discovery=discovery,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            discovery.commands,
            [("192.168.1.10", "setState", {"state": False}, 2)],
        )

    def test_room_command_targets_all_devices_in_room(self):
        data_file = self.write_data(
            {
                "rooms": {"1": "Office"},
                "devices": {
                    "192.168.1.10": {"moduleName": "Desk Lamp", "roomId": "1", "info": {}},
                    "192.168.1.11": {"moduleName": "Shelf Lamp", "roomId": "1", "info": {}},
                    "192.168.1.12": {"moduleName": "Hall Lamp", "roomId": "2", "info": {}},
                },
            }
        )
        discovery = FakeDiscovery()

        exit_code = self.run_cli(
            ["--data-file", str(data_file), "room", "Office", "on"],
            discovery=discovery,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            discovery.commands,
            [
                ("192.168.1.10", "setState", {"state": True}, 2),
                ("192.168.1.11", "setState", {"state": True}, 2),
            ],
        )

    def test_shortcut_command_uses_saved_action(self):
        data_file = self.write_data(
            {
                "devices": {
                    "192.168.1.10": {"moduleName": "Desk Lamp", "roomId": "1", "info": {}}
                },
                "shortcuts": {
                    "desk-off": {
                        "label": "Desk Off",
                        "target_type": "device",
                        "target": "192.168.1.10",
                        "action": "state",
                        "state": False,
                    }
                },
            }
        )
        discovery = FakeDiscovery()

        exit_code = self.run_cli(
            ["--data-file", str(data_file), "shortcut", "Desk Off"],
            discovery=discovery,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            discovery.commands,
            [("192.168.1.10", "setState", {"state": False}, 2)],
        )

    def test_list_shortcuts_prints_saved_shortcuts(self):
        data_file = self.write_data(
            {
                "shortcuts": {
                    "office-on": {
                        "label": "Office On",
                        "target_type": "room",
                        "target": "1",
                        "action": "state",
                        "state": True,
                    }
                }
            }
        )

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = wiz_cli.main(["--data-file", str(data_file), "list", "shortcuts"])

        self.assertEqual(exit_code, 0)
        self.assertIn("office-on\troom:1\ton", output.getvalue())


if __name__ == "__main__":
    unittest.main()
