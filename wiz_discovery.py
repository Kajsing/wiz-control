# File: wiz_discovery.py
import socket
import json
import logging
from typing import List, Tuple, Dict, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BROADCAST_ADDRESS = "192.168.87.255"
BROADCAST_PORT = 38899
BUFFER_SIZE = 1024

PILOT_ALLOWED_FIELDS = {
    "state",
    "sceneId",
    "speed",
    "dimming",
    "temperature",
    "ratio",
    "r",
    "g",
    "b",
    "cw",
    "ww",
}

PILOT_RANGES = {
    "r": (0, 255),
    "g": (0, 255),
    "b": (0, 255),
    "cw": (0, 255),
    "ww": (0, 255),
    "dimming": (10, 100),
    "temperature": (1000, 10000),
    "sceneId": (1, 32),
    "speed": (20, 200),
    "ratio": (0, 100),
}

class WizDiscovery:
    def __init__(self, broadcast_address: str = BROADCAST_ADDRESS, broadcast_port: int = BROADCAST_PORT):
        self.broadcast_address = broadcast_address
        self.broadcast_port = broadcast_port

    def discover_wiz_devices(self, timeout: int = 5) -> List[Tuple[str, Dict]]:
        """
        Broadcast a discovery request to WiZ devices and listen for replies.

        :param timeout: How long (in seconds) to wait for responses.
        :return: List of tuples containing IP address and device info.
        """
        devices = []
        message = json.dumps({"method": "getSystemConfig", "params": {}}).encode()

        logging.info("Sending discovery message to %s:%d", self.broadcast_address, self.broadcast_port)

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(timeout)
            try:
                sock.sendto(message, (self.broadcast_address, self.broadcast_port))
                logging.info("Broadcast sent, waiting for responses...")
                while True:
                    try:
                        data, addr = sock.recvfrom(BUFFER_SIZE)
                        device_info = json.loads(data.decode())
                        devices.append((addr[0], device_info))
                        logging.info("Received response from %s: %s", addr[0], device_info)
                    except socket.timeout:
                        logging.info("Discovery finished after timeout.")
                        break
                    except json.JSONDecodeError as e:
                        logging.warning("Received invalid JSON from %s: %s", addr[0], e)
            except Exception as e:
                logging.error("Error during discovery: %s", e)

        return devices

    def send_command(self, ip: str, method: str, params: Dict, timeout: int = 2) -> Optional[Dict]:
        """
        Send a command to a WiZ device and await its response.

        :param ip: IP address of the device.
        :param method: Method to invoke on the device.
        :param params: Parameters for the method.
        :param timeout: How long (in seconds) to wait for a response.
        :return: Response payload, or None when no reply is received.
        """
        message = json.dumps({"method": method, "params": params}).encode()
        logging.info("Sending command to %s: %s", ip, message)

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            try:
                sock.sendto(message, (ip, self.broadcast_port))
                data, _ = sock.recvfrom(BUFFER_SIZE)
                response = json.loads(data.decode())
                logging.info("Received response from %s: %s", ip, response)
                return response
            except socket.timeout:
                logging.warning("Device at %s did not respond before the timeout.", ip)
                return None
            except json.JSONDecodeError as e:
                logging.warning("Received invalid JSON from %s: %s", ip, e)
                return None
            except Exception as e:
                logging.error("Error sending command to %s: %s", ip, e)
                return None

    def _clamp_value(self, field: str, value: Any) -> Optional[int]:
        range_limits = PILOT_RANGES.get(field)
        if range_limits is None:
            return None

        try:
            numeric_value = int(value)
        except (TypeError, ValueError):
            logging.warning("Invalid value for %s: %s", field, value)
            return None

        min_value, max_value = range_limits
        return max(min_value, min(max_value, numeric_value))

    def _sanitize_pilot_payload(self, **kwargs: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        for key, value in kwargs.items():
            if key not in PILOT_ALLOWED_FIELDS:
                logging.debug("Ignoring unsupported pilot field %s", key)
                continue

            if value is None:
                continue

            if key == "state":
                if isinstance(value, bool):
                    payload[key] = value
                else:
                    logging.warning("State must be a boolean, got %s", value)
                continue

            clamped = self._clamp_value(key, value)
            if clamped is not None:
                if clamped != value:
                    logging.debug("Clamped %s from %s to %s", key, value, clamped)
                payload[key] = clamped

        return payload

    def set_pilot(self, ip: str, timeout: int = 2, **kwargs: Any) -> Optional[Dict]:
        """Send a pilot payload to control brightness, color, temperature, or scenes."""
        payload = self._sanitize_pilot_payload(**kwargs)
        if not payload:
            logging.warning("Pilot payload empty for %s", ip)
            return None
        return self.send_command(ip, "setPilot", payload, timeout=timeout)

    def set_scene(self, ip: str, scene_id: int, speed: Optional[int] = None, turn_on: bool = True, timeout: int = 2) -> Optional[Dict]:
        payload = {"sceneId": scene_id, "state": turn_on}
        if speed is not None:
            payload["speed"] = speed
        return self.set_pilot(ip, timeout=timeout, **payload)

    def set_color_temperature(self, ip: str, temperature: int, dimming: Optional[int] = None, turn_on: bool = True, timeout: int = 2) -> Optional[Dict]:
        payload = {"temperature": temperature, "state": turn_on}
        if dimming is not None:
            payload["dimming"] = dimming
        return self.set_pilot(ip, timeout=timeout, **payload)

    def set_color(
        self,
        ip: str,
        *,
        r: Optional[int] = None,
        g: Optional[int] = None,
        b: Optional[int] = None,
        cw: Optional[int] = None,
        ww: Optional[int] = None,
        dimming: Optional[int] = None,
        turn_on: bool = True,
        timeout: int = 2,
    ) -> Optional[Dict]:
        payload = {
            "r": r,
            "g": g,
            "b": b,
            "cw": cw,
            "ww": ww,
            "dimming": dimming,
            "state": turn_on,
        }
        return self.set_pilot(ip, timeout=timeout, **payload)

    def sort_devices_by_room(self, devices: List[Tuple[str, Dict]]) -> Dict[str, List[Dict]]:
        """
        Group devices by their reported room identifier.

        :param devices: List of tuples with IP address and device info.
        :return: Dictionary keyed by room id with lists of device dictionaries.
        """
        rooms = {}
        for ip, info in devices:
            room_id = str(info.get('result', {}).get('roomId', 'Unknown'))
            module_name = info.get('result', {}).get('moduleName', 'Unknown')
            if room_id not in rooms:
                rooms[room_id] = []
            rooms[room_id].append({
                "ip": ip,
                "moduleName": module_name,
                "info": info
            })
        logging.info("Grouped devices by room: %s", list(rooms.keys()))
        return rooms

    def get_device_state(self, ip: str) -> Optional[bool]:
        """
        Retrieve the on/off state for a WiZ device.

        :param ip: IP address of the device.
        :return: True when on, False when off, None when unknown.
        """
        response = self.send_command(ip, "getPilot", {})
        if response and "result" in response:
            state = response["result"].get("state")
            logging.info("Device %s state: %s", ip, state)
            return state
        logging.warning("Could not determine state for %s", ip)
        return None
