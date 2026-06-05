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
        self.discovered = []
        self.discovery_timeouts = []

    def send_command(self, ip, method, params, timeout=2):
        self.commands.append((ip, method, params, timeout))
        return {"result": {"success": True}}

    def discover_wiz_devices(self, timeout=5):
        self.discovery_timeouts.append(timeout)
        return self.discovered


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

    def test_save_group_resolves_rooms_and_devices(self):
        data_file = self.write_data(
            {
                "rooms": {"1": "Office"},
                "devices": {
                    "192.168.1.10": {"moduleName": "Desk Lamp", "roomId": "1", "info": {}},
                    "192.168.1.12": {"moduleName": "Hall Lamp", "roomId": "2", "info": {}},
                },
            }
        )

        exit_code = self.run_cli(
            [
                "--data-file",
                str(data_file),
                "save-group",
                "Work Lights",
                "--room",
                "Office",
                "--device",
                "Hall Lamp",
            ]
        )

        saved = json.loads(data_file.read_text())
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            saved["groups"]["Work Lights"],
            {
                "label": "Work Lights",
                "rooms": ["1"],
                "devices": ["192.168.1.12"],
            },
        )

    def test_group_command_targets_rooms_and_devices_without_duplicates(self):
        data_file = self.write_data(
            {
                "devices": {
                    "192.168.1.10": {"moduleName": "Desk Lamp", "roomId": "1", "info": {}},
                    "192.168.1.11": {"moduleName": "Shelf Lamp", "roomId": "1", "info": {}},
                    "192.168.1.12": {"moduleName": "Hall Lamp", "roomId": "2", "info": {}},
                },
                "groups": {
                    "Group 1": {
                        "label": "Group 1",
                        "rooms": ["1"],
                        "devices": ["192.168.1.10", "192.168.1.12"],
                    }
                },
            }
        )
        discovery = FakeDiscovery()

        exit_code = self.run_cli(
            ["--data-file", str(data_file), "group", "Group 1", "on"],
            discovery=discovery,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            discovery.commands,
            [
                ("192.168.1.10", "setState", {"state": True}, 2),
                ("192.168.1.11", "setState", {"state": True}, 2),
                ("192.168.1.12", "setState", {"state": True}, 2),
            ],
        )

    def test_list_groups_prints_saved_groups(self):
        data_file = self.write_data(
            {
                "groups": {
                    "Group 1": {
                        "label": "Group 1",
                        "rooms": ["1"],
                        "devices": ["192.168.1.12"],
                    }
                }
            }
        )

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = wiz_cli.main(["--data-file", str(data_file), "list", "groups"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Group 1\trooms=1\tdevices=192.168.1.12", output.getvalue())

    def test_delete_group_removes_saved_group(self):
        data_file = self.write_data(
            {
                "groups": {
                    "Group 1": {
                        "label": "Group 1",
                        "rooms": ["1"],
                        "devices": [],
                    }
                }
            }
        )

        exit_code = self.run_cli(["--data-file", str(data_file), "delete-group", "Group 1"])

        saved = json.loads(data_file.read_text())
        self.assertEqual(exit_code, 0)
        self.assertEqual(saved["groups"], {})

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

    def test_discover_saves_devices_and_uses_default_timeout(self):
        data_file = self.write_data(
            {
                "devices": {
                    "192.168.1.10": {
                        "moduleName": "Old Name",
                        "roomId": "1",
                        "info": {},
                        "preferences": {"dimming": 40},
                    }
                }
            }
        )
        discovery = FakeDiscovery()
        discovery.discovered = [
            (
                "192.168.1.10",
                {"result": {"moduleName": "Desk Lamp", "roomId": 2}},
            ),
            (
                "192.168.1.11",
                {"result": {"moduleName": "Shelf Lamp", "roomId": 2}},
            ),
        ]

        exit_code = self.run_cli(["--data-file", str(data_file), "discover"], discovery=discovery)

        saved = json.loads(data_file.read_text())
        self.assertEqual(exit_code, 0)
        self.assertEqual(discovery.discovery_timeouts, [10])
        self.assertEqual(saved["devices"]["192.168.1.10"]["moduleName"], "Desk Lamp")
        self.assertEqual(saved["devices"]["192.168.1.10"]["roomId"], "2")
        self.assertEqual(saved["devices"]["192.168.1.10"]["preferences"], {"dimming": 40})
        self.assertIn("192.168.1.11", saved["devices"])

    def test_discover_accepts_custom_timeout(self):
        data_file = self.write_data({})
        discovery = FakeDiscovery()
        discovery.discovered = [
            ("192.168.1.10", {"result": {"moduleName": "Desk Lamp", "roomId": 1}})
        ]

        exit_code = self.run_cli(
            ["--data-file", str(data_file), "discover", "--timeout", "3"],
            discovery=discovery,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(discovery.discovery_timeouts, [3])

    def test_discover_rejects_non_positive_timeout(self):
        data_file = self.write_data({})
        discovery = FakeDiscovery()

        exit_code = self.run_cli(
            ["--data-file", str(data_file), "discover", "--timeout", "0"],
            discovery=discovery,
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(discovery.discovery_timeouts, [])


if __name__ == "__main__":
    unittest.main()
