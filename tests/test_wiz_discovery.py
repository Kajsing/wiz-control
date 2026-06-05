import logging
import unittest
from unittest import mock

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

    def test_broadcast_addresses_fall_back_when_ip_command_is_missing(self):
        with mock.patch("wiz_discovery.shutil.which", return_value=None):
            addresses = WizDiscovery(broadcast_address="192.168.1.255")._get_broadcast_addresses()

        self.assertEqual(addresses, ["192.168.1.255", "255.255.255.255"])


if __name__ == "__main__":
    unittest.main()
