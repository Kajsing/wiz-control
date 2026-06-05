import argparse
import json
import logging
import sys
import threading
import time

from wiz_discovery import WizDiscovery
from wiz_store import DATA_FILE, build_device_record, build_group_record, load_data, save_data


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


def _resolve_group(data, name):
    groups = data.get("groups", {})
    if name in groups:
        return name, groups[name]

    matches = [
        (group_name, group)
        for group_name, group in groups.items()
        if _casefold(group_name) == _casefold(name)
        or _casefold(group.get("label", "")) == _casefold(name)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"Group '{name}' matches more than one saved group.")
    raise ValueError(f"Unknown group '{name}'.")


def _group_devices(data, group):
    devices = []
    seen_ips = set()

    for room_id in group.get("rooms", []):
        for device in _room_devices(data, room_id):
            ip = device["ip"]
            if ip not in seen_ips:
                devices.append(device)
                seen_ips.add(ip)

    for target in group.get("devices", []):
        device = _resolve_device(data, target)
        ip = device["ip"]
        if ip not in seen_ips:
            devices.append(device)
            seen_ips.add(ip)

    return devices


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


def _print_groups(data):
    for name, group in sorted(data.get("groups", {}).items()):
        rooms = ",".join(group.get("rooms", [])) or "-"
        devices = ",".join(group.get("devices", [])) or "-"
        print(f"{name}\trooms={rooms}\tdevices={devices}")


def _print_discovery_progress(stop_event):
    started_at = time.monotonic()
    while not stop_event.wait(1):
        elapsed = int(time.monotonic() - started_at)
        print(f"Still listening... {elapsed}s elapsed", file=sys.stderr, flush=True)


def _discover_with_progress(discovery, timeout):
    print(f"Discovering WiZ devices for up to {timeout}s...", file=sys.stderr, flush=True)
    stop_event = threading.Event()
    progress_thread = threading.Thread(
        target=_print_discovery_progress,
        args=(stop_event,),
        daemon=True,
    )
    progress_thread.start()
    try:
        return discovery.discover_wiz_devices(timeout=timeout)
    finally:
        stop_event.set()
        progress_thread.join(timeout=0.2)
        print("Discovery finished.", file=sys.stderr, flush=True)


def _save_discovered_devices(data, discovered):
    data.setdefault("devices", {})
    for ip, info in discovered:
        existing = data["devices"].get(ip, {})
        data["devices"][ip] = build_device_record(ip, info, existing)


def _run_discover(data, data_file, discovery, timeout):
    discovered = _discover_with_progress(discovery, timeout)
    if not discovered:
        print("No WiZ devices found.")
        return 1

    _save_discovered_devices(data, discovered)
    save_data(data, data_file)

    print(f"Found and saved {len(discovered)} WiZ device(s).")
    _print_devices(data)
    print()
    print("Rooms:")
    _print_rooms(data)
    return 0


def _run_save_group(data, data_file, name, rooms, devices):
    group_name = name.strip()
    if not group_name:
        raise ValueError("Group name cannot be empty.")
    if not rooms and not devices:
        raise ValueError("Add at least one --room or --device target.")

    room_ids = [_resolve_room_id(data, room) for room in rooms]
    device_ips = [_resolve_device(data, device)["ip"] for device in devices]

    data.setdefault("groups", {})[group_name] = {
        **build_group_record(group_name, room_ids, device_ips),
    }
    save_data(data, data_file)

    print(f"Saved group '{group_name}'.")
    print(f"rooms={','.join(room_ids) or '-'}")
    print(f"devices={','.join(device_ips) or '-'}")
    return 0


def _run_delete_group(data, data_file, name):
    group_name, _ = _resolve_group(data, name)
    del data["groups"][group_name]
    save_data(data, data_file)
    print(f"Deleted group '{group_name}'.")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Control saved WiZ devices from the command line.")
    parser.add_argument("--data-file", default=DATA_FILE, help="Path to wiz_data.json.")
    parser.add_argument(
        "--timeout",
        dest="command_timeout",
        metavar="TIMEOUT",
        type=int,
        default=2,
        help="Per-device UDP timeout in seconds for control commands.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover", help="Discover WiZ devices and save them for CLI and GUI use.")
    discover_parser.add_argument("--timeout", type=int, default=10, help="Discovery listen timeout in seconds.")

    list_parser = subparsers.add_parser("list", help="List saved devices, rooms, shortcuts, or groups.")
    list_parser.add_argument("kind", choices=("devices", "rooms", "shortcuts", "groups"))

    device_parser = subparsers.add_parser("device", help="Turn one saved device on or off.")
    device_parser.add_argument("target", help="Device IP address or unique module name.")
    device_parser.add_argument("state", choices=("on", "off"))

    room_parser = subparsers.add_parser("room", help="Turn a saved room on or off.")
    room_parser.add_argument("target", help="Room ID or unique saved room name.")
    room_parser.add_argument("state", choices=("on", "off"))

    group_parser = subparsers.add_parser("group", help="Turn a saved group on or off.")
    group_parser.add_argument("target", help="Saved group name.")
    group_parser.add_argument("state", choices=("on", "off"))

    save_group_parser = subparsers.add_parser("save-group", help="Create or replace a group of rooms and devices.")
    save_group_parser.add_argument("name", help="Group name.")
    save_group_parser.add_argument("--room", action="append", default=[], help="Room ID or unique room name. Can be repeated.")
    save_group_parser.add_argument("--device", action="append", default=[], help="Device IP or unique module name. Can be repeated.")

    delete_group_parser = subparsers.add_parser("delete-group", help="Delete a saved group.")
    delete_group_parser.add_argument("name", help="Group name.")

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
        elif args.kind == "shortcuts":
            _print_shortcuts(data)
        else:
            _print_groups(data)
        return 0

    if args.command == "discover":
        if args.timeout <= 0:
            raise ValueError("Discovery timeout must be greater than zero.")
        return _run_discover(data, args.data_file, discovery, args.timeout)

    if args.command == "device":
        device = _resolve_device(data, args.target)
        return _send_state(discovery, [device], args.state == "on", args.command_timeout)

    if args.command == "room":
        room_id = _resolve_room_id(data, args.target)
        return _send_state(discovery, _room_devices(data, room_id), args.state == "on", args.command_timeout)

    if args.command == "group":
        _, group = _resolve_group(data, args.target)
        return _send_state(discovery, _group_devices(data, group), args.state == "on", args.command_timeout)

    if args.command == "save-group":
        return _run_save_group(data, args.data_file, args.name, args.room, args.device)

    if args.command == "delete-group":
        return _run_delete_group(data, args.data_file, args.name)

    if args.command == "shortcut":
        _, shortcut = _resolve_shortcut(data, args.name)
        if shortcut["target_type"] == "device":
            device = _resolve_device(data, shortcut["target"])
            devices = [device]
        else:
            devices = _room_devices(data, shortcut["target"])
        return _send_state(discovery, devices, shortcut["state"], args.command_timeout)

    raise ValueError(f"Unknown command '{args.command}'.")


def main(argv=None, discovery=None):
    logging.getLogger().setLevel(logging.ERROR)
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run_command(args, discovery=discovery)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
