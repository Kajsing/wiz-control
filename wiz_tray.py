import argparse
import logging
import subprocess
import sys
import threading
from pathlib import Path

from wiz_cli import _favorite_devices, _group_devices, _room_devices
from wiz_discovery import WizDiscovery
from wiz_store import DATA_FILE, load_data


PROJECT_DIR = Path(__file__).resolve().parent
GUI_SCRIPT = PROJECT_DIR / "wiz_gui.py"


def _room_label(data, room_id):
    return data.get("rooms", {}).get(room_id, f"Room {room_id}")


def _room_ids(data):
    room_ids = {str(record.get("roomId", "Unknown")) for record in data.get("devices", {}).values()}
    room_ids.update(str(room_id) for room_id in data.get("rooms", {}))
    return sorted(room_ids, key=lambda room_id: _room_label(data, room_id).casefold())


def _room_devices_sorted(data, room_id):
    return sorted(
        _room_devices(data, room_id),
        key=lambda device: device.get("moduleName", f"Device {device['ip']}").casefold(),
    )


def build_companion_actions(data):
    actions = [
        {
            "section": "global",
            "label": "All Off",
            "kind": "all",
            "target": "*",
            "mode": "set",
            "state": False,
        }
    ]

    for name, favorite in sorted(data.get("favorites", {}).items()):
        state_label = "On" if favorite["state"] else "Off"
        actions.append(
            {
                "section": "favorites",
                "label": favorite.get("label", name),
                "kind": "favorite",
                "target": name,
                "mode": "set",
                "state": favorite["state"],
                "description": f"{favorite['target_type']}:{favorite['target']} {state_label}",
            }
        )

    for name in sorted(data.get("groups", {})):
        actions.append(
            {
                "section": "groups",
                "label": name,
                "kind": "group",
                "target": name,
                "mode": "toggle",
            }
        )

    for room_id in _room_ids(data):
        room_name = _room_label(data, room_id)
        actions.append(
            {
                "section": "rooms",
                "label": room_name,
                "kind": "room",
                "target": room_id,
                "mode": "toggle",
            }
        )
        for device in _room_devices_sorted(data, room_id):
            ip = device["ip"]
            actions.append(
                {
                    "section": "devices",
                    "label": device.get("moduleName", f"Device {ip}"),
                    "kind": "device",
                    "target": ip,
                    "room_id": room_id,
                    "mode": "toggle",
                }
            )

    return actions


class CompanionController:
    def __init__(self, data_file=DATA_FILE, discovery=None):
        self.data_file = data_file
        self.discovery = discovery or WizDiscovery()
        self.data = load_data(data_file)

    def reload(self):
        self.data = load_data(self.data_file)

    def devices_for_action(self, action):
        kind = action["kind"]
        if kind == "all":
            return list(self.data.get("devices", {}).values())
        if kind == "favorite":
            favorite = self.data.get("favorites", {})[action["target"]]
            return _favorite_devices(self.data, favorite)
        if kind == "group":
            group = self.data.get("groups", {})[action["target"]]
            return _group_devices(self.data, group)
        if kind == "room":
            return _room_devices(self.data, action["target"])
        if kind == "device":
            return [self.data.get("devices", {})[action["target"]]]
        raise ValueError(f"Unknown companion action kind '{kind}'.")

    def run_action(self, action):
        devices = self.devices_for_action(action)
        if action.get("mode") == "toggle":
            return self.toggle_devices(action, devices)
        return self.set_devices_state(action, devices)

    def set_devices_state(self, action, devices):
        updated = 0
        for device in devices:
            ip = device["ip"]
            response = self.discovery.send_command(ip, "setState", {"state": action["state"]})
            if response:
                updated += 1
            else:
                logging.warning("Could not update %s from tray action '%s'.", ip, action["label"])
        return updated

    def _read_device_state(self, ip):
        get_device_state = getattr(self.discovery, "get_device_state", None)
        if callable(get_device_state):
            return get_device_state(ip)

        response = self.discovery.send_command(ip, "getPilot", {})
        result = response.get("result", {}) if isinstance(response, dict) else {}
        state = result.get("state")
        return state if isinstance(state, bool) else None

    def toggle_devices(self, action, devices):
        updated = 0
        for device in devices:
            ip = device["ip"]
            current_state = self._read_device_state(ip)
            if not isinstance(current_state, bool):
                logging.warning("Could not read %s before tray action '%s'.", ip, action["label"])
                continue

            target_state = not current_state
            response = self.discovery.send_command(ip, "setState", {"state": target_state})
            if response:
                updated += 1
            else:
                logging.warning("Could not toggle %s from tray action '%s'.", ip, action["label"])
        return updated

    def actions(self):
        self.reload()
        return build_companion_actions(self.data)


def _load_tray_dependencies():
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise RuntimeError("Install tray dependencies with: pip install -r requirements.txt") from exc
    return pystray, Image, ImageDraw


def _create_icon_image(image_module, draw_module):
    image = image_module.new("RGB", (64, 64), "#0b1020")
    draw = draw_module.Draw(image)
    draw.ellipse((10, 8, 54, 52), fill="#38bdf8")
    draw.rectangle((26, 46, 38, 58), fill="#e5eefb")
    draw.ellipse((22, 18, 42, 38), fill="#0b1020")
    return image


def _run_in_background(callback):
    threading.Thread(target=callback, daemon=True).start()


def _open_manager():
    subprocess.Popen([sys.executable, str(GUI_SCRIPT)], cwd=str(PROJECT_DIR))


def _build_menu(pystray, controller, icon):
    Menu = pystray.Menu
    MenuItem = pystray.MenuItem

    def run_action(action):
        return lambda _icon=None, _item=None: _run_in_background(lambda: controller.run_action(action))

    def reload_menu(_icon=None, _item=None):
        controller.reload()
        icon.menu = _build_menu(pystray, controller, icon)

    def empty_item(label="No saved items"):
        return MenuItem(label, None, enabled=False)

    def action_items(actions, section):
        items = [
            MenuItem(action["label"], run_action(action))
            for action in actions
            if action["section"] == section
        ]
        return items or [empty_item()]

    def room_items(actions):
        rooms = [action for action in actions if action["section"] == "rooms"]
        devices = [action for action in actions if action["section"] == "devices"]
        if not rooms:
            return [empty_item("No rooms saved")]

        items = []
        for room in rooms:
            room_devices = [
                device
                for device in devices
                if device.get("room_id") == room["target"]
            ]
            submenu_items = [MenuItem("Toggle Room", run_action(room))]
            if room_devices:
                submenu_items.append(Menu.SEPARATOR)
                submenu_items.extend(MenuItem(device["label"], run_action(device)) for device in room_devices)
            else:
                submenu_items.extend([Menu.SEPARATOR, empty_item("No lights in room")])
            items.append(MenuItem(room["label"], Menu(*submenu_items)))
        return items

    actions = controller.actions()
    all_off = next(action for action in actions if action["section"] == "global")

    return Menu(
        MenuItem("Open WiZ Manager", lambda _icon=None, _item=None: _open_manager()),
        MenuItem("Reload Data", reload_menu),
        Menu.SEPARATOR,
        MenuItem("All Off", run_action(all_off)),
        Menu.SEPARATOR,
        MenuItem("Favorites", Menu(*action_items(actions, "favorites"))),
        MenuItem("Groups", Menu(*action_items(actions, "groups"))),
        MenuItem("Rooms", Menu(*room_items(actions))),
        Menu.SEPARATOR,
        MenuItem("Quit", lambda _icon=None, _item=None: icon.stop()),
    )


def run_tray(data_file=DATA_FILE):
    pystray, image_module, draw_module = _load_tray_dependencies()
    controller = CompanionController(data_file=data_file)
    icon = pystray.Icon("wiz-control")
    icon.title = "WiZ Control Companion"
    icon.icon = _create_icon_image(image_module, draw_module)
    icon.menu = _build_menu(pystray, controller, icon)
    icon.run()


def build_parser():
    parser = argparse.ArgumentParser(description="Run the WiZ Control Companion tray app.")
    parser.add_argument("--data-file", default=DATA_FILE, help="Path to wiz_data.json.")
    return parser


def main(argv=None):
    logging.getLogger().setLevel(logging.ERROR)
    args = build_parser().parse_args(argv)
    try:
        run_tray(data_file=args.data_file)
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
