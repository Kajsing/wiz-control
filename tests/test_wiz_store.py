import unittest
from pathlib import Path

from wiz_store import (
    DATA_FILE,
    build_device_record,
    build_favorite_record,
    build_group_record,
    describe_group,
    normalize_data,
    rename_generic_room_devices,
)


class WizStoreTests(unittest.TestCase):
    def test_default_data_file_lives_next_to_project_modules(self):
        self.assertEqual(Path(DATA_FILE).name, "wiz_data.json")
        self.assertEqual(Path(DATA_FILE).parent, Path(__file__).resolve().parent.parent)

    def test_normalize_data_adds_shortcuts_container(self):
        data = normalize_data({"rooms": {}, "devices": {}})

        self.assertEqual(data["shortcuts"], {})
        self.assertEqual(data["groups"], {})
        self.assertEqual(data["favorites"], {})

    def test_build_device_record_preserves_existing_preferences(self):
        record = build_device_record(
            "192.168.1.10",
            {"result": {"moduleName": "Desk Lamp", "roomId": 2}},
            {"preferences": {"dimming": 40}},
        )

        self.assertEqual(record["moduleName"], "Desk Lamp")
        self.assertEqual(record["roomId"], "2")
        self.assertEqual(record["preferences"], {"dimming": 40})

    def test_build_device_record_preserves_existing_custom_name(self):
        record = build_device_record(
            "192.168.1.10",
            {"result": {"moduleName": "ESP01_SHRGB1C", "roomId": 2}},
            {"moduleName": "Living Room 1", "preferences": {"dimming": 40}},
        )

        self.assertEqual(record["moduleName"], "Living Room 1")
        self.assertEqual(record["roomId"], "2")
        self.assertEqual(record["preferences"], {"dimming": 40})

    def test_build_device_record_uses_discovered_name_when_existing_is_generic(self):
        record = build_device_record(
            "192.168.1.10",
            {"result": {"moduleName": "Desk Lamp", "roomId": 2}},
            {"moduleName": "Device 192.168.1.10"},
        )

        self.assertEqual(record["moduleName"], "Desk Lamp")

    def test_build_group_record_requires_a_name_and_target(self):
        with self.assertRaises(ValueError):
            build_group_record("", ["1"], [])
        with self.assertRaises(ValueError):
            build_group_record("Group 1", [], [])

    def test_build_group_record_normalizes_rooms_and_devices(self):
        self.assertEqual(
            build_group_record(" Group 1 ", [" 1 "], [" 192.168.1.10 "]),
            {
                "label": "Group 1",
                "rooms": ["1"],
                "devices": ["192.168.1.10"],
            },
        )

    def test_build_favorite_record_normalizes_state_action(self):
        self.assertEqual(
            build_favorite_record(" All Off ", "group", " Evening ", False),
            {
                "label": "All Off",
                "target_type": "group",
                "target": "Evening",
                "action": "state",
                "state": False,
            },
        )

    def test_build_favorite_record_supports_toggle_action(self):
        self.assertEqual(
            build_favorite_record(" Evening Toggle ", "group", " Evening ", action="toggle"),
            {
                "label": "Evening Toggle",
                "target_type": "group",
                "target": "Evening",
                "action": "toggle",
            },
        )

    def test_build_favorite_record_requires_valid_fields(self):
        with self.assertRaises(ValueError):
            build_favorite_record("", "group", "Evening", False)
        with self.assertRaises(ValueError):
            build_favorite_record("Evening", "scene", "Evening", False)
        with self.assertRaises(ValueError):
            build_favorite_record("Evening", "group", "", False)
        with self.assertRaises(ValueError):
            build_favorite_record("Evening", "group", "Evening", "off")
        with self.assertRaises(ValueError):
            build_favorite_record("Evening", "group", "Evening", action="scene")

    def test_describe_group_uses_room_and_device_labels(self):
        description = describe_group(
            {"rooms": ["1"], "devices": ["192.168.1.10"]},
            room_names={"1": "Office"},
            devices={"192.168.1.10": {"moduleName": "Desk Lamp"}},
        )

        self.assertEqual(description, "Rooms: Office | Devices: Desk Lamp")

    def test_rename_generic_room_devices_only_renames_generic_names(self):
        data = {
            "devices": {
                "192.168.1.10": {"moduleName": "Device 192.168.1.10", "roomId": "1"},
                "192.168.1.11": {"moduleName": "Ceiling Lamp", "roomId": "1"},
                "192.168.1.12": {"moduleName": "Unknown", "roomId": "1"},
                "192.168.1.13": {"moduleName": "Device 192.168.1.13", "roomId": "2"},
            }
        }

        renamed = rename_generic_room_devices(data, "1", "Living Room")

        self.assertEqual(renamed, 2)
        self.assertEqual(data["devices"]["192.168.1.10"]["moduleName"], "Living Room 1")
        self.assertEqual(data["devices"]["192.168.1.11"]["moduleName"], "Ceiling Lamp")
        self.assertEqual(data["devices"]["192.168.1.12"]["moduleName"], "Living Room 2")
        self.assertEqual(data["devices"]["192.168.1.13"]["moduleName"], "Device 192.168.1.13")

    def test_rename_generic_room_devices_renames_default_discovered_names(self):
        data = {
            "devices": {
                "192.168.1.10": {
                    "moduleName": "ESP01_SHRGB1C",
                    "roomId": "1",
                    "info": {"result": {"moduleName": "ESP01_SHRGB1C"}},
                },
                "192.168.1.11": {
                    "moduleName": "Custom Lamp",
                    "roomId": "1",
                    "info": {"result": {"moduleName": "ESP01_SHRGB1C"}},
                },
            }
        }

        renamed = rename_generic_room_devices(data, "1", "Stue")

        self.assertEqual(renamed, 1)
        self.assertEqual(data["devices"]["192.168.1.10"]["moduleName"], "Stue 1")
        self.assertEqual(data["devices"]["192.168.1.11"]["moduleName"], "Custom Lamp")

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

    def test_normalize_data_keeps_valid_favorites(self):
        data = normalize_data(
            {
                "favorites": {
                    "evening-off": {
                        "label": "Evening Off",
                        "target_type": "group",
                        "target": "Evening",
                        "action": "state",
                        "state": False,
                    }
                }
            }
        )

        self.assertEqual(
            data["favorites"]["evening-off"],
            {
                "label": "Evening Off",
                "target_type": "group",
                "target": "Evening",
                "action": "state",
                "state": False,
            },
        )

    def test_normalize_data_keeps_toggle_favorites(self):
        data = normalize_data(
            {
                "favorites": {
                    "evening-toggle": {
                        "label": "Evening Toggle",
                        "target_type": "group",
                        "target": "Evening",
                        "action": "toggle",
                    }
                }
            }
        )

        self.assertEqual(
            data["favorites"]["evening-toggle"],
            {
                "label": "Evening Toggle",
                "target_type": "group",
                "target": "Evening",
                "action": "toggle",
            },
        )

    def test_normalize_data_drops_invalid_favorites(self):
        data = normalize_data(
            {
                "favorites": {
                    "bad-target": {
                        "target_type": "scene",
                        "target": "Evening",
                        "action": "state",
                        "state": False,
                    },
                    "bad-state": {
                        "target_type": "group",
                        "target": "Evening",
                        "action": "state",
                        "state": "off",
                    },
                }
            }
        )

        self.assertEqual(data["favorites"], {})


if __name__ == "__main__":
    unittest.main()
