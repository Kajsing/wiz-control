import logging
import unittest

from wiz_discovery import WizDiscovery


class WizDiscoveryPayloadTests(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.discovery = WizDiscovery()

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_sanitize_pilot_payload_filters_unsupported_fields(self):
        payload = self.discovery._sanitize_pilot_payload(
            state=True,
            dimming=80,
            unsupported="ignored",
        )

        self.assertEqual(payload, {"state": True, "dimming": 80})

    def test_sanitize_pilot_payload_clamps_numeric_values(self):
        payload = self.discovery._sanitize_pilot_payload(
            dimming=5,
            r=999,
            temperature=20000,
            sceneId=-1,
        )

        self.assertEqual(
            payload,
            {
                "dimming": 10,
                "r": 255,
                "temperature": 10000,
                "sceneId": 1,
            },
        )

    def test_sanitize_pilot_payload_rejects_non_boolean_state(self):
        payload = self.discovery._sanitize_pilot_payload(state="on", dimming=50)

        self.assertEqual(payload, {"dimming": 50})


if __name__ == "__main__":
    unittest.main()
