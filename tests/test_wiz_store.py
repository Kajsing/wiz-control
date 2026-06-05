import unittest
from pathlib import Path

from wiz_store import DATA_FILE, build_device_record, normalize_data


class WizStoreTests(unittest.TestCase):
    def test_default_data_file_lives_next_to_project_modules(self):
        self.assertEqual(Path(DATA_FILE).name, "wiz_data.json")
        self.assertEqual(Path(DATA_FILE).parent, Path(__file__).resolve().parent.parent)

    def test_normalize_data_adds_shortcuts_container(self):
        data = normalize_data({"rooms": {}, "devices": {}})

        self.assertEqual(data["shortcuts"], {})
        self.assertEqual(data["groups"], {})

    def test_build_device_record_preserves_existing_preferences(self):
        record = build_device_record(
            "192.168.1.10",
            {"result": {"moduleName": "Desk Lamp", "roomId": 2}},
            {"preferences": {"dimming": 40}},
        )

        self.assertEqual(record["moduleName"], "Desk Lamp")
        self.assertEqual(record["roomId"], "2")
        self.assertEqual(record["preferences"], {"dimming": 40})

    def test_normalize_data_keeps_valid_state_shortcuts(self):
        data = normalize_data(
            {
                "shortcuts": {
                    "desk-on": {
                        "label": "Desk On",
                        "target_type": "device",
                        "target": "192.168.1.10",
                        "action": "state",
                        "state": True,
                    }
                }
            }
        )

        self.assertEqual(
            data["shortcuts"]["desk-on"],
            {
                "label": "Desk On",
                "target_type": "device",
                "target": "192.168.1.10",
                "action": "state",
                "state": True,
            },
        )

    def test_normalize_data_drops_invalid_shortcuts(self):
        data = normalize_data(
            {
                "shortcuts": {
                    "bad-action": {
                        "target_type": "device",
                        "target": "192.168.1.10",
                        "action": "color",
                        "state": True,
                    },
                    "bad-state": {
                        "target_type": "room",
                        "target": "1",
                        "action": "state",
                        "state": "on",
                    },
                }
            }
        )

        self.assertEqual(data["shortcuts"], {})

    def test_normalize_data_keeps_valid_groups(self):
        data = normalize_data(
            {
                "groups": {
                    "Group 1": {
                        "label": "Group 1",
                        "rooms": ["1"],
                        "devices": ["192.168.1.10"],
                    }
                }
            }
        )

        self.assertEqual(
            data["groups"]["Group 1"],
            {
                "label": "Group 1",
                "rooms": ["1"],
                "devices": ["192.168.1.10"],
            },
        )

    def test_normalize_data_drops_invalid_groups(self):
        data = normalize_data(
            {
                "groups": {
                    "empty": {"label": "Empty", "rooms": [], "devices": []},
                    "bad": {"label": "Bad", "rooms": "1", "devices": None},
                }
            }
        )

        self.assertEqual(data["groups"], {})


if __name__ == "__main__":
    unittest.main()
