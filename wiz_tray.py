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


def build_companion_actions(data):
    actions = [
        {
            "section": "global",
            "label": "All Off",
            "kind": "all",
            "target": "*",
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
                "state": favorite["state"],
                "description": f"{favorite['target_type']}:{favorite['target']} {state_label}",
            }
        )

    for name in sorted(data.get("groups", {})):
        for state in (True, False):
            actions.append(
                {
                    "section": "groups",
                    "label": f"{name} {'On' if state else 'Off'}",
                    "kind": "group",
                    "target": name,
                    "state": state,
                }
            )

    for room_id in _room_ids(data):
        room_name = _room_label(data, room_id)
        for state in (True, False):
            actions.append(
                {
                    "section": "rooms",
                    "label": f"{room_name} {'On' if state else 'Off'}",
                    "kind": "room",
                    "target": room_id,
                    "state": state,
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
        raise ValueError(f"Unknown companion action kind '{kind}'.")

    def run_action(self, action):
        devices = self.devices_for_action(action)
        updated = 0
        for device in devices:
            ip = device["ip"]
            response = self.discovery.send_command(ip, "setState", {"state": action["state"]})
            if response:
                updated += 1
            else:
                logging.warning("Could not update %s from tray action '%s'.", ip, action["label"])
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

    def action_items(section):
        return [
            MenuItem(action["label"], run_action(action))
            for action in controller.actions()
            if action["section"] == section
        ]

    return Menu(
        MenuItem("All Off", run_action(controller.actions()[0])),
        MenuItem("Favorites", Menu(*action_items("favorites"))),
        MenuItem("Groups", Menu(*action_items("groups"))),
        MenuItem("Rooms", Menu(*action_items("rooms"))),
        Menu.SEPARATOR,
        MenuItem("Reload", lambda _icon=None, _item=None: controller.reload()),
        MenuItem("Open Manager", lambda _icon=None, _item=None: _open_manager()),
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
