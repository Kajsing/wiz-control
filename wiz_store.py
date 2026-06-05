import json
import os
import tempfile
import threading


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(PROJECT_DIR, "wiz_data.json")
DATA_FILE_LOCK = threading.Lock()


def _extract_preferences(payload):
    if isinstance(payload, dict):
        preferences = payload.get("preferences")
        if isinstance(preferences, dict):
            return preferences
    return {}


def _coerce_device_record(ip, payload):
    if not isinstance(payload, dict):
        return None

    preferences = _extract_preferences(payload)

    if {"moduleName", "roomId", "info"}.issubset(payload.keys()):
        room_id = payload.get("roomId", "Unknown")
        info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
        return {
            "ip": ip,
            "moduleName": payload.get("moduleName") or f"Device {ip}",
            "roomId": str(room_id) if room_id is not None else "Unknown",
            "info": info,
            "preferences": preferences,
        }

    info = payload.get("info") if isinstance(payload.get("info"), dict) else payload
    if not isinstance(info, dict):
        info = {}
    result = info.get("result", {}) if isinstance(info, dict) else {}
    module_name = (
        payload.get("moduleName")
        or result.get("moduleName")
        or f"Device {ip}"
    )
    room_id = payload.get("roomId") or result.get("roomId")
    room_id_str = "Unknown" if room_id is None else str(room_id)

    return {
        "ip": ip,
        "moduleName": module_name,
        "roomId": room_id_str,
        "info": info,
        "preferences": preferences,
    }


def _normalize_device_records(raw_devices):
    normalized = {}
    if not isinstance(raw_devices, dict):
        return normalized

    for ip, payload in raw_devices.items():
        record = _coerce_device_record(ip, payload)
        if record:
            normalized[ip] = record
    return normalized


def build_device_record(ip, info, existing=None):
    existing = existing if isinstance(existing, dict) else {}
    raw_info = info if isinstance(info, dict) else existing.get("info", {})
    if not isinstance(raw_info, dict):
        raw_info = {}

    result = raw_info.get("result", {}) if isinstance(raw_info, dict) else {}
    module_name = (
        result.get("moduleName")
        or existing.get("moduleName")
        or f"Device {ip}"
    )
    room_id = result.get("roomId")
    if room_id is None:
        room_id = existing.get("roomId", "Unknown")

    room_id_str = "Unknown" if room_id is None else str(room_id)
    preferences = existing.get("preferences", {})
    if not isinstance(preferences, dict):
        preferences = {}

    return {
        "ip": ip,
        "moduleName": module_name,
        "roomId": room_id_str,
        "info": raw_info,
        "preferences": preferences,
    }


def _normalize_shortcuts(raw_shortcuts):
    normalized = {}
    if not isinstance(raw_shortcuts, dict):
        return normalized

    for name, shortcut in raw_shortcuts.items():
        if not isinstance(shortcut, dict):
            continue

        normalized_name = str(name).strip()
        target_type = shortcut.get("target_type")
        target = shortcut.get("target")
        action = shortcut.get("action")

        if not normalized_name or target_type not in {"device", "room"}:
            continue
        if not target or action != "state":
            continue
        if not isinstance(shortcut.get("state"), bool):
            continue

        normalized[normalized_name] = {
            "label": str(shortcut.get("label") or normalized_name).strip() or normalized_name,
            "target_type": target_type,
            "target": str(target),
            "action": "state",
            "state": shortcut["state"],
        }

    return normalized


def _normalize_groups(raw_groups):
    normalized = {}
    if not isinstance(raw_groups, dict):
        return normalized

    for name, group in raw_groups.items():
        if not isinstance(group, dict):
            continue

        normalized_name = str(name).strip()
        raw_rooms = group.get("rooms", [])
        raw_devices = group.get("devices", [])
        rooms = [str(room).strip() for room in raw_rooms if str(room).strip()] if isinstance(raw_rooms, list) else []
        devices = [str(device).strip() for device in raw_devices if str(device).strip()] if isinstance(raw_devices, list) else []

        if not normalized_name or not rooms and not devices:
            continue

        normalized[normalized_name] = {
            "label": str(group.get("label") or normalized_name).strip() or normalized_name,
            "rooms": rooms,
            "devices": devices,
        }

    return normalized


def _empty_data():
    return {
        "rooms": {},
        "devices": {},
        "room_settings": {},
        "shortcuts": {},
        "groups": {},
    }


def normalize_data(data):
    if not isinstance(data, dict):
        data = _empty_data()

    data.setdefault("rooms", {})
    data.setdefault("room_settings", {})
    data["devices"] = _normalize_device_records(data.get("devices", {}))
    data["shortcuts"] = _normalize_shortcuts(data.get("shortcuts", {}))
    data["groups"] = _normalize_groups(data.get("groups", {}))

    for record in data["devices"].values():
        if not isinstance(record.get("preferences"), dict):
            record["preferences"] = {}

    return data


def load_data(data_file=DATA_FILE):
    if os.path.exists(data_file):
        with open(data_file, "r") as file:
            data = json.load(file)
    else:
        data = None

    return normalize_data(data)


def save_data(data, data_file=DATA_FILE):
    directory = os.path.dirname(os.path.abspath(data_file)) or "."
    temp_path = None

    with DATA_FILE_LOCK:
        try:
            fd, temp_path = tempfile.mkstemp(prefix="wiz_data_", suffix=".json", dir=directory)
            with os.fdopen(fd, "w") as file:
                json.dump(normalize_data(data), file, indent=4)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, data_file)
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
