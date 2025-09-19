import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog, messagebox
import threading
import json
import os
import time

from wiz_discovery import WizDiscovery  # Import the WizDiscovery class


# File for persisting data
DATA_FILE = "wiz_data.json"


def _normalize_device_records(raw_devices):
    normalized = {}
    if not isinstance(raw_devices, dict):
        return normalized

    for ip, payload in raw_devices.items():
        record = _coerce_device_record(ip, payload)
        if record:
            normalized[ip] = record
    return normalized


def _coerce_device_record(ip, payload):
    if not isinstance(payload, dict):
        return None

    if {"moduleName", "roomId", "info"}.issubset(payload.keys()):
        room_id = payload.get("roomId", "Unknown")
        info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
        return {
            "ip": ip,
            "moduleName": payload.get("moduleName") or f"Device {ip}",
            "roomId": str(room_id) if room_id is not None else "Unknown",
            "info": info,
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
    }


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as file:
                data = json.load(file)
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Data file is corrupted. Loading empty data.")
            data = None
    else:
        data = None

    if not isinstance(data, dict):
        data = {"rooms": {}, "devices": {}}

    data.setdefault("rooms", {})
    raw_devices = data.get("devices", {})
    data["devices"] = _normalize_device_records(raw_devices)
    return data


def save_data(data):
    try:
        with open(DATA_FILE, "w") as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        messagebox.showerror("Error", f"Could not save data: {e}")


class WizGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WiZ Device Manager")
        self.geometry("800x600")
        self.resizable(True, True)
        self.style = ttk.Style(self)
        self.style.theme_use('clam')  # Can be changed to 'default', 'classic', etc.

        self.discovery = WizDiscovery()  # Initialize the WizDiscovery class
        self.data = load_data()
        self.active_ips = set()
        self.device_status_cache = {ip: None for ip in self.data["devices"]}
        self._refresh_scheduled = False

        self.create_widgets()
        self.stop_event = self.update_status_periodically()

    def create_widgets(self):
        # Instruction text
        instructions = ttk.Label(self, text="Click the button to discover WiZ devices on your local network.")
        instructions.pack(pady=10)

        # Frame for buttons and log output
        top_frame = ttk.Frame(self)
        top_frame.pack(fill='x', padx=10, pady=5)

        # Discover button
        discover_button = ttk.Button(top_frame, text="Discover Devices", command=self.on_discover_click)
        discover_button.pack(side='left')

        # Scrolled log box
        self.output_box = scrolledtext.ScrolledText(self, width=80, height=10, state="disabled")
        self.output_box.pack(fill='both', expand=True, padx=10, pady=10)

        # Control frame for device controls
        self.control_frame = ttk.Frame(self)
        self.control_frame.pack(fill="both", expand=True, padx=10, pady=5)

    def log(self, message):
        self.output_box.config(state="normal")
        self.output_box.insert(tk.END, f"{message}\n")
        self.output_box.see(tk.END)
        self.output_box.config(state="disabled")

    def on_toggle_room(self, room_id, devices, state):
        def toggle():
            refresh_needed = False
            for device in devices:
                ip = device["ip"]
                try:
                    response = self.discovery.send_command(ip, "setState", {"state": state})
                    if response:
                        self.log(f"Device {ip} {'turned on' if state else 'turned off'}.")
                        self.device_status_cache[ip] = state
                        self.active_ips.add(ip)
                        refresh_needed = True
                    else:
                        self.log(f"Could not update device {ip}.")
                except Exception as e:
                    self.log(f"Error while controlling device {ip}: {e}")

            if refresh_needed:
                self.schedule_refresh()

        threading.Thread(target=toggle, daemon=True).start()

    def on_toggle_device(self, ip, state):
        def toggle():
            try:
                response = self.discovery.send_command(ip, "setState", {"state": state})
                if response:
                    self.log(f"Device {ip} {'turned on' if state else 'turned off'}.")
                    self.device_status_cache[ip] = state
                    self.active_ips.add(ip)
                    self.schedule_refresh()
                else:
                    self.log(f"Could not update device {ip}.")
                time.sleep(0.2)  # Give the device time to update
            except Exception as e:
                self.log(f"Error while controlling device {ip}: {e}")

        threading.Thread(target=toggle, daemon=True).start()

    def on_remove_device(self, ip):
        if ip in self.data["devices"]:
            del self.data["devices"][ip]
            self.active_ips.discard(ip)
            self.device_status_cache.pop(ip, None)
            save_data(self.data)
            self.log(f"Device {ip} removed.")
            self.refresh_control_frame()

    def on_discover_click(self):
        threading.Thread(target=self.discover_devices, daemon=True).start()

    def schedule_refresh(self):
        if getattr(self, "_refresh_scheduled", False):
            return
        self._refresh_scheduled = True
        self.after(0, self._perform_refresh)

    def _perform_refresh(self):
        self._refresh_scheduled = False
        self.refresh_control_frame()

    def _build_device_record(self, ip, info):
        existing = self.data["devices"].get(ip, {})
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

        return {
            "ip": ip,
            "moduleName": module_name,
            "roomId": room_id_str,
            "info": raw_info,
        }

    def _group_devices_by_room(self, include_offline=True):
        grouped = {}
        for ip, record in self.data["devices"].items():
            if not include_offline and ip not in self.active_ips:
                continue
            room_id = record.get("roomId", "Unknown")
            grouped.setdefault(room_id, []).append(record)
        for device_list in grouped.values():
            device_list.sort(key=lambda entry: entry.get("moduleName", ""))
        return dict(sorted(grouped.items(), key=lambda item: item[0]))

    def discover_devices(self):
        self.log("Starting device discovery...")
        try:
            discovered = self.discovery.discover_wiz_devices()
            found_ips = [ip for ip, _ in discovered]
            self.active_ips = set(found_ips)

            updated = False
            for ip, info in discovered:
                record = self._build_device_record(ip, info)
                if self.data["devices"].get(ip) != record:
                    updated = True
                self.data["devices"][ip] = record
                self.device_status_cache.setdefault(ip, None)

            if discovered:
                self.log(f"WiZ devices found: {len(discovered)}")
                rooms = self._group_devices_by_room(include_offline=False)
                for room_id, devices_in_room in rooms.items():
                    room_name = self.data["rooms"].get(room_id, f"Room {room_id}")
                    self.log(f"  {room_name} (ID: {room_id})")
            else:
                self.log("No WiZ devices found.")

            if updated:
                save_data(self.data)
            self.schedule_refresh()
        except Exception as e:
            self.log(f"Error during discovery: {e}")

    def refresh_control_frame(self):
        # Clear the control frame
        for widget in self.control_frame.winfo_children():
            widget.destroy()

        rooms = self._group_devices_by_room(include_offline=False)

        for room_id, devices_in_room in rooms.items():
            room_name = self.data["rooms"].get(room_id, f"Room {room_id}")
            room_frame = ttk.LabelFrame(self.control_frame, text=room_name)
            room_frame.pack(fill="x", padx=5, pady=5)

            # Header with room controls
            header_frame = ttk.Frame(room_frame)
            header_frame.pack(fill="x", pady=5)

            rename_btn = ttk.Button(header_frame, text="Rename Room", command=lambda r=room_id: self.on_rename_room(r))
            rename_btn.pack(side='left', padx=5)

            turn_on_btn = ttk.Button(header_frame, text="Turn All On", command=lambda d=devices_in_room: self.on_toggle_room(room_id, d, True))
            turn_on_btn.pack(side='left', padx=5)

            turn_off_btn = ttk.Button(header_frame, text="Turn All Off", command=lambda d=devices_in_room: self.on_toggle_room(room_id, d, False))
            turn_off_btn.pack(side='left', padx=5)

            # Show devices in the room
            for device in devices_in_room:
                ip = device["ip"]
                module_name = device.get("moduleName", f"Device {ip}")
                state = self.device_status_cache.get(ip)
                if state is None:
                    state_text = "Unknown"
                    state_color = "orange"
                else:
                    state_text = "On" if state else "Off"
                    state_color = "green" if state else "red"

                device_frame = ttk.Frame(room_frame)
                device_frame.pack(fill="x", pady=2, padx=10)

                name_label = ttk.Label(device_frame, text=f"{module_name} ({ip})")
                name_label.grid(row=0, column=0, sticky="w")

                status_label = ttk.Label(device_frame, text=f"Status: {state_text}", foreground=state_color)
                status_label.grid(row=0, column=1, sticky="w", padx=10)

                on_button = ttk.Button(device_frame, text="Turn On", command=lambda i=ip: self.on_toggle_device(i, True))
                on_button.grid(row=0, column=2, padx=5)

                off_button = ttk.Button(device_frame, text="Turn Off", command=lambda i=ip: self.on_toggle_device(i, False))
                off_button.grid(row=0, column=3, padx=5)

                remove_button = ttk.Button(device_frame, text="Remove", command=lambda i=ip: self.on_remove_device(i))
                remove_button.grid(row=0, column=4, padx=5)

        # Show offline devices
        offline_ips = sorted(ip for ip in self.data["devices"] if ip not in self.active_ips)
        if offline_ips:
            offline_frame = ttk.LabelFrame(self.control_frame, text="Offline Devices")
            offline_frame.pack(fill="x", padx=5, pady=5)

            for ip in offline_ips:
                device = self.data["devices"].get(ip, {})
                module_name = device.get("moduleName", f"Device {ip}")
                offline_label = ttk.Label(offline_frame, text=f"{module_name} ({ip}) - Offline", foreground="gray")
                offline_label.pack(anchor='w', pady=2, padx=10)

    def update_status_periodically(self):
        stop_event = threading.Event()

        def update():
            while not stop_event.is_set():
                state_changed = False
                for ip in list(self.data["devices"].keys()):
                    if stop_event.is_set():
                        break
                    try:
                        state = self.discovery.get_device_state(ip)
                        previous_state = self.device_status_cache.get(ip)

                        if state is None:
                            was_online = ip in self.active_ips
                            self.active_ips.discard(ip)
                            if was_online:
                                self.log(f"Device {ip} became unreachable.")
                                state_changed = True
                            if previous_state is not None:
                                state_changed = True
                            self.device_status_cache[ip] = None
                        else:
                            if ip not in self.active_ips:
                                self.active_ips.add(ip)
                                state_changed = True
                            if previous_state != state:
                                self.device_status_cache[ip] = state
                                self.log(f"Updated status for {ip}: {'On' if state else 'Off'}")
                                state_changed = True
                            else:
                                self.device_status_cache[ip] = state
                    except Exception as e:
                        self.log(f"Error while updating status for {ip}: {e}")

                if state_changed:
                    self.schedule_refresh()

                if stop_event.wait(5):
                    break

        threading.Thread(target=update, daemon=True).start()
        return stop_event

    def on_rename_room(self, room_id):
        new_name = simpledialog.askstring("Rename Room", f"Enter a new name for room {room_id}:")
        if new_name:
            self.data["rooms"][room_id] = new_name
            save_data(self.data)
            self.log(f"Room {room_id} renamed to {new_name}.")
            self.refresh_control_frame()

    def on_close(self):
        self.stop_event.set()
        self.destroy()

    def run(self):
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.mainloop()


if __name__ == "__main__":
    app = WizGUI()
    app.run()
