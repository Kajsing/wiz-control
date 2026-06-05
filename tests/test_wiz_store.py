import unittest

from wiz_store import normalize_data


class WizStoreTests(unittest.TestCase):
    def test_normalize_data_adds_shortcuts_container(self):
        data = normalize_data({"rooms": {}, "devices": {}})

        self.assertEqual(data["shortcuts"], {})

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


if __name__ == "__main__":
    unittest.main()
