import argparse
import json
import logging
import sys

from wiz_discovery import WizDiscovery
from wiz_store import DATA_FILE, load_data


def _casefold(value):
    return str(value).casefold()


def _room_label(data, room_id):
    return data.get("rooms", {}).get(room_id, f"Room {room_id}")


def _resolve_device(data, target):
    devices = data.get("devices", {})
    if target in devices:
        return devices[target]

    matches = [
        record
        for record in devices.values()
        if _casefold(record.get("moduleName", "")) == _casefold(target)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"Device name '{target}' matches more than one device; use the IP address.")
    raise ValueError(f"Unknown device '{target}'.")


def _resolve_room_id(data, target):
    room_ids = {str(room_id) for room_id in data.get("rooms", {})}
    room_ids.update(str(record.get("roomId", "Unknown")) for record in data.get("devices", {}).values())

    if str(target) in room_ids:
        return str(target)

    matches = [
        room_id
        for room_id in room_ids
        if _casefold(_room_label(data, room_id)) == _casefold(target)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"Room name '{target}' matches more than one room; use the room ID.")
    raise ValueError(f"Unknown room '{target}'.")


def _room_devices(data, room_id):
    return [
        record
        for record in data.get("devices", {}).values()
        if str(record.get("roomId", "Unknown")) == str(room_id)
    ]


def _resolve_shortcut(data, name):
    shortcuts = data.get("shortcuts", {})
    if name in shortcuts:
        return name, shortcuts[name]

    matches = [
        (shortcut_name, shortcut)
        for shortcut_name, shortcut in shortcuts.items()
        if _casefold(shortcut_name) == _casefold(name)
        or _casefold(shortcut.get("label", "")) == _casefold(name)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"Shortcut '{name}' matches more than one saved shortcut.")
    raise ValueError(f"Unknown shortcut '{name}'.")


def _send_state(discovery, devices, state, timeout):
    if not devices:
        raise ValueError("No devices matched the command.")

    failures = []
    for device in devices:
        ip = device["ip"]
        response = discovery.send_command(ip, "setState", {"state": state}, timeout=timeout)
        if response:
            print(f"{ip}: {'on' if state else 'off'}")
        else:
            failures.append(ip)
            print(f"{ip}: failed", file=sys.stderr)

    return 0 if not failures else 1


def _print_devices(data):
    for ip, record in sorted(data.get("devices", {}).items()):
        print(f"{ip}\t{record.get('moduleName', f'Device {ip}')}\troom={record.get('roomId', 'Unknown')}")


def _print_rooms(data):
    room_ids = {str(record.get("roomId", "Unknown")) for record in data.get("devices", {}).values()}
    room_ids.update(str(room_id) for room_id in data.get("rooms", {}))
    for room_id in sorted(room_ids):
        devices = _room_devices(data, room_id)
        print(f"{room_id}\t{_room_label(data, room_id)}\tdevices={len(devices)}")


def _print_shortcuts(data):
    for name, shortcut in sorted(data.get("shortcuts", {}).items()):
        target_type = shortcut["target_type"]
        target = shortcut["target"]
        state = "on" if shortcut["state"] else "off"
        print(f"{name}\t{target_type}:{target}\t{state}")


def build_parser():
    parser = argparse.ArgumentParser(description="Control saved WiZ devices from the command line.")
    parser.add_argument("--data-file", default=DATA_FILE, help="Path to wiz_data.json.")
    parser.add_argument("--timeout", type=int, default=2, help="Per-device UDP timeout in seconds.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List saved devices, rooms, or shortcuts.")
    list_parser.add_argument("kind", choices=("devices", "rooms", "shortcuts"))

    device_parser = subparsers.add_parser("device", help="Turn one saved device on or off.")
    device_parser.add_argument("target", help="Device IP address or unique module name.")
    device_parser.add_argument("state", choices=("on", "off"))

    room_parser = subparsers.add_parser("room", help="Turn a saved room on or off.")
    room_parser.add_argument("target", help="Room ID or unique saved room name.")
    room_parser.add_argument("state", choices=("on", "off"))

    shortcut_parser = subparsers.add_parser("shortcut", help="Run a shortcut saved from the GUI.")
    shortcut_parser.add_argument("name", help="Shortcut name.")

    return parser


def run_command(args, discovery=None):
    data = load_data(args.data_file)
    discovery = discovery or WizDiscovery()

    if args.command == "list":
        if args.kind == "devices":
            _print_devices(data)
        elif args.kind == "rooms":
            _print_rooms(data)
        else:
            _print_shortcuts(data)
        return 0

    if args.command == "device":
        device = _resolve_device(data, args.target)
        return _send_state(discovery, [device], args.state == "on", args.timeout)

    if args.command == "room":
        room_id = _resolve_room_id(data, args.target)
        return _send_state(discovery, _room_devices(data, room_id), args.state == "on", args.timeout)

    if args.command == "shortcut":
        _, shortcut = _resolve_shortcut(data, args.name)
        if shortcut["target_type"] == "device":
            device = _resolve_device(data, shortcut["target"])
            devices = [device]
        else:
            devices = _room_devices(data, shortcut["target"])
        return _send_state(discovery, devices, shortcut["state"], args.timeout)

    raise ValueError(f"Unknown command '{args.command}'.")


def main(argv=None, discovery=None):
    logging.getLogger().setLevel(logging.WARNING)
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run_command(args, discovery=discovery)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
