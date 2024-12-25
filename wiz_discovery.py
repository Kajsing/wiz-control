# Fil: wiz_discovery.py
import socket
import json
import logging
from typing import List, Tuple, Dict, Optional

# Konfigurer logging
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
        Sender en discovery-forespørgsel til WiZ-enheder og lytter efter svar.
        
        :param timeout: Hvor lang tid (i sekunder) der skal ventes på svar.
        :return: Liste af tuples indeholdende IP-adresse og enhedsinfo.
        """
        devices = []
        message = json.dumps({"method": "getSystemConfig", "params": {}}).encode()

        logging.info("Sender discovery-besked til %s:%d", self.broadcast_address, self.broadcast_port)

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(timeout)
            try:
                sock.sendto(message, (self.broadcast_address, self.broadcast_port))
                logging.info("Broadcast sendt, venter på svar...")
                while True:
                    try:
                        data, addr = sock.recvfrom(BUFFER_SIZE)
                        device_info = json.loads(data.decode())
                        devices.append((addr[0], device_info))
                        logging.info("Modtaget svar fra %s: %s", addr[0], device_info)
                    except socket.timeout:
                        logging.info("Opdagelse færdig efter timeout.")
                        break
                    except json.JSONDecodeError as e:
                        logging.warning("Modtog ugyldig JSON fra %s: %s", addr[0], e)
            except Exception as e:
                logging.error("Fejl under opdagelse: %s", e)

        return devices

    def send_command(self, ip: str, method: str, params: Dict, timeout: int = 2) -> Optional[Dict]:
        """
        Sender en kommando til en WiZ-enhed og venter på svar.
        
        :param ip: IP-adressen til enheden.
        :param method: Metoden der skal kaldes.
        :param params: Parametre for metoden.
        :param timeout: Hvor lang tid (i sekunder) der skal ventes på svar.
        :return: Respons fra enheden, eller None hvis der ikke blev modtaget svar.
        """
        message = json.dumps({"method": method, "params": params}).encode()
        logging.info("Sender kommando til %s: %s", ip, message)

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            try:
                sock.sendto(message, (ip, self.broadcast_port))
                data, _ = sock.recvfrom(BUFFER_SIZE)
                response = json.loads(data.decode())
                logging.info("Modtog respons fra %s: %s", ip, response)
                return response
            except socket.timeout:
                logging.warning("Enheden ved %s svarede ikke inden for timeout.", ip)
                return None
            except json.JSONDecodeError as e:
                logging.warning("Modtog ugyldig JSON fra %s: %s", ip, e)
                return None
            except Exception as e:
                logging.error("Fejl ved sending af kommando til %s: %s", ip, e)
                return None

    def sort_devices_by_room(self, devices: List[Tuple[str, Dict]]) -> Dict[str, List[Dict]]:
        """
        Sorterer enhederne efter rum.
        
        :param devices: Liste af tuples med IP-adresse og enhedsinfo.
        :return: Dictionary med rum-id som nøgler og lister af enheder som værdier.
        """
        rooms = {}
        for ip, info in devices:
            room_id = str(info.get('result', {}).get('roomId', 'Ukendt'))
            module_name = info.get('result', {}).get('moduleName', 'Ukendt')
            if room_id not in rooms:
                rooms[room_id] = []
            rooms[room_id].append({
                "ip": ip,
                "moduleName": module_name,
                "info": info
            })
        logging.info("Sorterede enheder efter rum: %s", list(rooms.keys()))
        return rooms

    def get_device_state(self, ip: str) -> Optional[bool]:
        """
        Henter tilstanden (tændt/slukket) for en WiZ-enhed.
        
        :param ip: IP-adressen til enheden.
        :return: True hvis tændt, False hvis slukket, None hvis ukendt.
        """
        response = self.send_command(ip, "getPilot", {})
        if response and "result" in response:
            state = response["result"].get("state")
            logging.info("Enhed %s tilstand: %s", ip, state)
            return state
        logging.warning("Kunne ikke hente tilstand for %s", ip)
        return None
