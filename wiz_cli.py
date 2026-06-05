import argparse
import json
import logging
import sys
import threading
import time

from wiz_discovery import WizDiscovery
from wiz_store import DATA_FILE, build_device_record, build_favorite_record, build_group_record, load_data, save_data


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


def _resolve_favorite(data, name):
    favorites = data.get("favorites", {})
    if name in favorites:
        return name, favorites[name]

    matches = [
        (favorite_name, favorite)
        for favorite_name, favorite in favorites.items()
        if _casefold(favorite_name) == _casefold(name)
        or _casefold(favorite.get("label", "")) == _casefold(name)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"Favorite '{name}' matches more than one saved favorite.")
    raise ValueError(f"Unknown favorite '{name}'.")


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


def _print_json(payload):
    print(json.dumps(payload, indent=2, sort_keys=True))


def _list_devices(data):
    return [
        {
            "ip": ip,
            "name": record.get("moduleName", f"Device {ip}"),
            "room_id": str(record.get("roomId", "Unknown")),
        }
        for ip, record in sorted(data.get("devices", {}).items())
    ]


def _list_rooms(data):
    room_ids = {str(record.get("roomId", "Unknown")) for record in data.get("devices", {}).values()}
    room_ids.update(str(room_id) for room_id in data.get("rooms", {}))
    return [
        {
            "id": room_id,
            "name": _room_label(data, room_id),
            "devices": len(_room_devices(data, room_id)),
        }
        for room_id in sorted(room_ids)
    ]


def _list_shortcuts(data):
    return [
        {
            "name": name,
            "label": shortcut.get("label", name),
            "target_type": shortcut["target_type"],
            "target": shortcut["target"],
            "state": shortcut["state"],
        }
        for name, shortcut in sorted(data.get("shortcuts", {}).items())
    ]


def _list_groups(data):
    return [
        {
            "name": name,
            "label": group.get("label", name),
            "rooms": group.get("rooms", []),
            "devices": group.get("devices", []),
        }
        for name, group in sorted(data.get("groups", {}).items())
    ]


def _list_favorites(data):
    return [
        {
            "name": name,
            "label": favorite.get("label", name),
            "target_type": favorite["target_type"],
            "target": favorite["target"],
            "state": favorite["state"],
        }
        for name, favorite in sorted(data.get("favorites", {}).items())
    ]


def _send_state(discovery, devices, state, timeout, json_output=False):
    if not devices:
        raise ValueError("No devices matched the command.")

    failures = []
    results = []
    for device in devices:
        ip = device["ip"]
        response = discovery.send_command(ip, "setState", {"state": state}, timeout=timeout)
        if response:
            results.append({"ip": ip, "ok": True, "state": "on" if state else "off"})
            if not json_output:
                print(f"{ip}: {'on' if state else 'off'}")
        else:
            failures.append(ip)
            results.append({"ip": ip, "ok": False, "state": "on" if state else "off"})
            if not json_output:
                print(f"{ip}: failed", file=sys.stderr)

    if json_output:
        _print_json(
            {
                "ok": not failures,
                "action": "state",
                "state": "on" if state else "off",
                "devices": results,
            }
        )

    return 0 if not failures else 1


def _read_device_status(discovery, device, timeout):
    ip = device["ip"]
    response = discovery.send_command(ip, "getPilot", {}, timeout=timeout)
    result = response.get("result", {}) if isinstance(response, dict) else {}
    state = result.get("state")

    if response is None:
        status = "offline"
    elif state is True:
        status = "on"
    elif state is False:
        status = "off"
    else:
        status = "unknown"

    return {
        "ip": ip,
        "name": device.get("moduleName", f"Device {ip}"),
        "room_id": str(device.get("roomId", "Unknown")),
        "online": response is not None,
        "state": state if isinstance(state, bool) else None,
        "status": status,
    }


def _print_status(statuses, data):
    for status in statuses:
        room_label = _room_label(data, status["room_id"])
        print(
            f"{status['ip']}\t{status['name']}\t"
            f"room={room_label}\tstatus={status['status']}"
        )


def _status_summary(statuses):
    counts = {"on": 0, "off": 0, "offline": 0, "unknown": 0}
    for status in statuses:
        counts[status["status"]] += 1
    return counts


def _print_status_summary(statuses):
    counts = _status_summary(statuses)
    print(
        "summary\t"
        f"on={counts['on']}\t"
        f"off={counts['off']}\t"
        f"offline={counts['offline']}\t"
        f"unknown={counts['unknown']}"
    )


def _run_status(data, discovery, kind, target, timeout, json_output=False):
    if kind == "device":
        devices = [_resolve_device(data, target)]
    elif kind == "room":
        room_id = _resolve_room_id(data, target)
        devices = _room_devices(data, room_id)
    else:
        _, group = _resolve_group(data, target)
        devices = _group_devices(data, group)

    if not devices:
        raise ValueError("No devices matched the status command.")

    statuses = [_read_device_status(discovery, device, timeout) for device in devices]
    ok = all(status["online"] for status in statuses)
    if json_output:
        _print_json(
            {
                "ok": ok,
                "kind": kind,
                "target": target,
                "devices": statuses,
                "summary": _status_summary(statuses),
            }
        )
    else:
        _print_status(statuses, data)
        if len(statuses) > 1:
            _print_status_summary(statuses)
    return 0 if ok else 1


def _print_devices(data):
    for device in _list_devices(data):
        print(f"{device['ip']}\t{device['name']}\troom={device['room_id']}")


def _print_rooms(data):
    for room in _list_rooms(data):
        print(f"{room['id']}\t{room['name']}\tdevices={room['devices']}")


def _print_shortcuts(data):
    for shortcut in _list_shortcuts(data):
        state = "on" if shortcut["state"] else "off"
        print(f"{shortcut['name']}\t{shortcut['target_type']}:{shortcut['target']}\t{state}")


def _print_groups(data):
    for group in _list_groups(data):
        rooms = ",".join(group["rooms"]) or "-"
        devices = ",".join(group["devices"]) or "-"
        print(f"{group['name']}\trooms={rooms}\tdevices={devices}")


def _print_favorites(data):
    for favorite in _list_favorites(data):
        state = "on" if favorite["state"] else "off"
        print(f"{favorite['name']}\t{favorite['target_type']}:{favorite['target']}\t{state}")


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


def _run_discover(data, data_file, discovery, timeout, json_output=False):
    discovered = _discover_with_progress(discovery, timeout)
    if not discovered:
        if json_output:
            _print_json({"ok": False, "devices": []})
        else:
            print("No WiZ devices found.")
        return 1

    _save_discovered_devices(data, discovered)
    save_data(data, data_file)

    if json_output:
        _print_json(
            {
                "ok": True,
                "devices": _list_devices(data),
                "rooms": _list_rooms(data),
            }
        )
    else:
        print(f"Found and saved {len(discovered)} WiZ device(s).")
        _print_devices(data)
        print()
        print("Rooms:")
        _print_rooms(data)
    return 0


def _run_save_group(data, data_file, name, rooms, devices, json_output=False):
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

    if json_output:
        _print_json({"ok": True, "group": data["groups"][group_name]})
    else:
        print(f"Saved group '{group_name}'.")
        print(f"rooms={','.join(room_ids) or '-'}")
        print(f"devices={','.join(device_ips) or '-'}")
    return 0


def _run_delete_group(data, data_file, name, json_output=False):
    group_name, _ = _resolve_group(data, name)
    del data["groups"][group_name]
    save_data(data, data_file)
    if json_output:
        _print_json({"ok": True, "deleted": group_name})
    else:
        print(f"Deleted group '{group_name}'.")
    return 0


def _resolve_favorite_target(data, target_type, target):
    if target_type == "device":
        return _resolve_device(data, target)["ip"]
    if target_type == "room":
        return _resolve_room_id(data, target)
    if target_type == "group":
        group_name, _ = _resolve_group(data, target)
        return group_name
    raise ValueError("Favorite target type must be device, room, or group.")


def _favorite_devices(data, favorite):
    target_type = favorite["target_type"]
    target = favorite["target"]
    if target_type == "device":
        return [_resolve_device(data, target)]
    if target_type == "room":
        return _room_devices(data, target)
    _, group = _resolve_group(data, target)
    return _group_devices(data, group)


def _run_save_favorite(data, data_file, name, target_type, target, state, json_output=False):
    resolved_target = _resolve_favorite_target(data, target_type, target)
    favorite = build_favorite_record(name, target_type, resolved_target, state == "on")
    favorite_name = favorite["label"]
    data.setdefault("favorites", {})[favorite_name] = favorite
    save_data(data, data_file)

    if json_output:
        _print_json({"ok": True, "favorite": favorite})
    else:
        print(f"Saved favorite '{favorite_name}'.")
        print(f"target={favorite['target_type']}:{favorite['target']}")
        print(f"state={'on' if favorite['state'] else 'off'}")
    return 0


def _run_delete_favorite(data, data_file, name, json_output=False):
    favorite_name, _ = _resolve_favorite(data, name)
    del data["favorites"][favorite_name]
    save_data(data, data_file)
    if json_output:
        _print_json({"ok": True, "deleted": favorite_name})
    else:
        print(f"Deleted favorite '{favorite_name}'.")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Control saved WiZ devices from the command line.")
    parser.add_argument("--data-file", default=DATA_FILE, help="Path to wiz_data.json.")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Print machine-readable JSON output.")
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

    list_parser = subparsers.add_parser("list", help="List saved devices, rooms, shortcuts, groups, or favorites.")
    list_parser.add_argument("kind", choices=("devices", "rooms", "shortcuts", "groups", "favorites"))

    device_parser = subparsers.add_parser("device", help="Turn one saved device on or off.")
    device_parser.add_argument("target", help="Device IP address or unique module name.")
    device_parser.add_argument("state", choices=("on", "off"))

    room_parser = subparsers.add_parser("room", help="Turn a saved room on or off.")
    room_parser.add_argument("target", help="Room ID or unique saved room name.")
    room_parser.add_argument("state", choices=("on", "off"))

    group_parser = subparsers.add_parser("group", help="Turn a saved group on or off.")
    group_parser.add_argument("target", help="Saved group name.")
    group_parser.add_argument("state", choices=("on", "off"))

    status_parser = subparsers.add_parser("status", help="Read current status for a saved device, room, or group.")
    status_parser.add_argument("kind", choices=("device", "room", "group"))
    status_parser.add_argument("target", help="Device, room, or group name/identifier.")

    save_group_parser = subparsers.add_parser("save-group", help="Create or replace a group of rooms and devices.")
    save_group_parser.add_argument("name", help="Group name.")
    save_group_parser.add_argument("--room", action="append", default=[], help="Room ID or unique room name. Can be repeated.")
    save_group_parser.add_argument("--device", action="append", default=[], help="Device IP or unique module name. Can be repeated.")

    delete_group_parser = subparsers.add_parser("delete-group", help="Delete a saved group.")
    delete_group_parser.add_argument("name", help="Group name.")

    save_favorite_parser = subparsers.add_parser("save-favorite", help="Create or replace a favorite quick action.")
    save_favorite_parser.add_argument("name", help="Favorite name.")
    save_favorite_parser.add_argument("target_type", choices=("device", "room", "group"))
    save_favorite_parser.add_argument("target", help="Device, room, or group name/identifier.")
    save_favorite_parser.add_argument("state", choices=("on", "off"))

    delete_favorite_parser = subparsers.add_parser("delete-favorite", help="Delete a saved favorite quick action.")
    delete_favorite_parser.add_argument("name", help="Favorite name.")

    favorite_parser = subparsers.add_parser("favorite", help="Run a saved favorite quick action.")
    favorite_parser.add_argument("name", help="Favorite name.")

    shortcut_parser = subparsers.add_parser("shortcut", help="Run a shortcut saved from the GUI.")
    shortcut_parser.add_argument("name", help="Shortcut name.")

    return parser


def run_command(args, discovery=None):
    data = load_data(args.data_file)
    discovery = discovery or WizDiscovery()

    if args.command == "list":
        if args.json_output:
            list_payloads = {
                "devices": _list_devices,
                "rooms": _list_rooms,
                "shortcuts": _list_shortcuts,
                "groups": _list_groups,
                "favorites": _list_favorites,
            }
            _print_json({"ok": True, "kind": args.kind, args.kind: list_payloads[args.kind](data)})
        elif args.kind == "devices":
            _print_devices(data)
        elif args.kind == "rooms":
            _print_rooms(data)
        elif args.kind == "shortcuts":
            _print_shortcuts(data)
        elif args.kind == "favorites":
            _print_favorites(data)
        else:
            _print_groups(data)
        return 0

    if args.command == "discover":
        if args.timeout <= 0:
            raise ValueError("Discovery timeout must be greater than zero.")
        return _run_discover(data, args.data_file, discovery, args.timeout, json_output=args.json_output)

    if args.command == "device":
        device = _resolve_device(data, args.target)
        return _send_state(discovery, [device], args.state == "on", args.command_timeout, json_output=args.json_output)

    if args.command == "room":
        room_id = _resolve_room_id(data, args.target)
        return _send_state(
            discovery,
            _room_devices(data, room_id),
            args.state == "on",
            args.command_timeout,
            json_output=args.json_output,
        )

    if args.command == "group":
        _, group = _resolve_group(data, args.target)
        return _send_state(
            discovery,
            _group_devices(data, group),
            args.state == "on",
            args.command_timeout,
            json_output=args.json_output,
        )

    if args.command == "status":
        return _run_status(data, discovery, args.kind, args.target, args.command_timeout, json_output=args.json_output)

    if args.command == "save-group":
        return _run_save_group(data, args.data_file, args.name, args.room, args.device, json_output=args.json_output)

    if args.command == "delete-group":
        return _run_delete_group(data, args.data_file, args.name, json_output=args.json_output)

    if args.command == "save-favorite":
        return _run_save_favorite(
            data,
            args.data_file,
            args.name,
            args.target_type,
            args.target,
            args.state,
            json_output=args.json_output,
        )

    if args.command == "delete-favorite":
        return _run_delete_favorite(data, args.data_file, args.name, json_output=args.json_output)

    if args.command == "favorite":
        _, favorite = _resolve_favorite(data, args.name)
        return _send_state(
            discovery,
            _favorite_devices(data, favorite),
            favorite["state"],
            args.command_timeout,
            json_output=args.json_output,
        )

    if args.command == "shortcut":
        _, shortcut = _resolve_shortcut(data, args.name)
        if shortcut["target_type"] == "device":
            device = _resolve_device(data, shortcut["target"])
            devices = [device]
        else:
            devices = _room_devices(data, shortcut["target"])
        return _send_state(discovery, devices, shortcut["state"], args.command_timeout, json_output=args.json_output)

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
