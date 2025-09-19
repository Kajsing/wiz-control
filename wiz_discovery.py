# File: wiz_discovery.py
import socket
import json
import logging
from typing import List, Tuple, Dict, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BROADCAST_ADDRESS = "192.168.87.255"
BROADCAST_PORT = 38899
BUFFER_SIZE = 1024

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
