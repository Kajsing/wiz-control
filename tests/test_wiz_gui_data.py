import unittest

from wiz_gui import _coerce_device_record, _normalize_device_records


class WizGuiDataTests(unittest.TestCase):
    def test_coerce_device_record_keeps_existing_record_shape(self):
        record = _coerce_device_record(
            "192.168.1.20",
            {
                "moduleName": "Desk Lamp",
                "roomId": 2,
                "info": {"result": {"state": True}},
                "preferences": {"dimming": 75},
            },
        )

        self.assertEqual(
            record,
            {
                "ip": "192.168.1.20",
                "moduleName": "Desk Lamp",
                "roomId": "2",
                "info": {"result": {"state": True}},
                "preferences": {"dimming": 75},
            },
        )

    def test_coerce_device_record_supports_raw_discovery_payload(self):
        record = _coerce_device_record(
            "192.168.1.21",
            {"result": {"moduleName": "Floor Lamp", "roomId": 4}},
        )

        self.assertEqual(record["moduleName"], "Floor Lamp")
        self.assertEqual(record["roomId"], "4")
        self.assertEqual(record["info"], {"result": {"moduleName": "Floor Lamp", "roomId": 4}})
        self.assertEqual(record["preferences"], {})

    def test_normalize_device_records_skips_invalid_payloads(self):
        normalized = _normalize_device_records(
            {
                "192.168.1.22": {"result": {"moduleName": "Valid Lamp"}},
                "192.168.1.23": "invalid",
            }
        )

        self.assertEqual(list(normalized), ["192.168.1.22"])


if __name__ == "__main__":
    unittest.main()
