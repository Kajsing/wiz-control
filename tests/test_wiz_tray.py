import json
import tempfile
import unittest
from pathlib import Path

from wiz_tray import CompanionController, build_companion_actions


class FakeDiscovery:
    def __init__(self):
        self.commands = []

    def send_command(self, ip, method, params, timeout=2):
        self.commands.append((ip, method, params, timeout))
        return {"result": {"success": True}}


class WizTrayTests(unittest.TestCase):
    def write_data(self, payload):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        data_file = Path(temp_dir.name) / "wiz_data.json"
        data_file.write_text(json.dumps(payload))
        return data_file

    def test_build_companion_actions_includes_global_favorites_groups_and_rooms(self):
        actions = build_companion_actions(
            {
                "rooms": {"1": "Office"},
                "devices": {
                    "192.168.1.10": {"ip": "192.168.1.10", "moduleName": "Desk", "roomId": "1"}
                },
                "groups": {"Work": {"label": "Work", "rooms": ["1"], "devices": []}},
                "favorites": {
                    "Work Off": {
                        "label": "Work Off",
                        "target_type": "group",
                        "target": "Work",
                        "action": "state",
                        "state": False,
                    }
                },
            }
        )

        labels = [action["label"] for action in actions]
        self.assertIn("All Off", labels)
        self.assertIn("Work Off", labels)
        self.assertIn("Work On", labels)
        self.assertIn("Office On", labels)

    def test_controller_runs_favorite_action(self):
        data_file = self.write_data(
            {
                "devices": {
                    "192.168.1.10": {
                        "ip": "192.168.1.10",
                        "moduleName": "Desk Lamp",
                        "roomId": "1",
                        "info": {},
                    }
                },
                "groups": {"Work": {"label": "Work", "rooms": ["1"], "devices": []}},
                "favorites": {
                    "Work Off": {
                        "label": "Work Off",
                        "target_type": "group",
                        "target": "Work",
                        "action": "state",
                        "state": False,
                    }
                },
            }
        )
        discovery = FakeDiscovery()
        controller = CompanionController(data_file=str(data_file), discovery=discovery)
        action = {
            "section": "favorites",
            "label": "Work Off",
            "kind": "favorite",
            "target": "Work Off",
            "state": False,
        }

        updated = controller.run_action(action)

        self.assertEqual(updated, 1)
        self.assertEqual(
            discovery.commands,
            [("192.168.1.10", "setState", {"state": False}, 2)],
        )


if __name__ == "__main__":
    unittest.main()
