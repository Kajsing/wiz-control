import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import json
import os
import time

from wiz_discovery import WizDiscovery  # Import the WizDiscovery class


# File for persisting data
DATA_FILE = "wiz_data.json"

BRIGHTNESS_MIN = 10
BRIGHTNESS_MAX = 100
TEMPERATURE_MIN = 2200
TEMPERATURE_MAX = 6500
DEFAULT_TEMPERATURE = 3000
DEFAULT_DIMMING = 100

SCENE_OPTIONS = [
    (1, "Ocean"),
    (2, "Romance"),
    (3, "Sunset"),
    (4, "Party"),
    (5, "Fireplace"),
    (6, "Cozy"),
    (7, "Forest"),
    (8, "Pastel"),
    (9, "Wake Up"),
    (10, "Bedtime"),
    (11, "Warm White"),
    (12, "Daylight"),
    (13, "Cool White"),
    (14, "Night Light"),
    (15, "Focus"),
    (16, "Relax"),
    (17, "True Colors"),
    (18, "TV Time"),
    (19, "Plant Growth"),
    (20, "Spring"),
    (21, "Summer"),
    (22, "Fall"),
    (23, "Deep Dive"),
    (24, "Jungle"),
    (25, "Mojito"),
    (26, "Club"),
    (27, "Christmas"),
    (28, "Halloween"),
    (29, "Candlelight"),
    (30, "Golden Hour"),
    (31, "Pulse"),
    (32, "Steampunk"),
]

SCENE_MAP = {scene_id: label for scene_id, label in SCENE_OPTIONS}
SCENE_CHOICES = [f"{scene_id:02d} - {label}" for scene_id, label in SCENE_OPTIONS]

COLOR_PRESETS = [
    {"label": "Warm Relax", "temperature": 2700, "dimming": 80},
    {"label": "Cool Daylight", "temperature": 5000, "dimming": 90},
    {"label": "Sky Blue", "r": 0, "g": 120, "b": 255, "dimming": 100},
]


def _extract_preferences(payload):
    if isinstance(payload, dict):
        preferences = payload.get("preferences")
        if isinstance(preferences, dict):
            return preferences
    return {}


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
    data.setdefault("room_settings", {})
    raw_devices = data.get("devices", {})
    data["devices"] = _normalize_device_records(raw_devices)
    for record in data["devices"].values():
        if not isinstance(record.get("preferences"), dict):
            record["preferences"] = {}
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

        self.log_toggle = ttk.Button(top_frame, text="Show Logs", command=self.toggle_logs)
        self.log_toggle.pack(side='right')

        # Scrolled log box
        self.output_container = ttk.Frame(self)
        self.output_box = scrolledtext.ScrolledText(self.output_container, width=80, height=10, state="disabled")
        self.output_box.pack(fill='both', expand=True)
        self.output_visible = False

        # Control frame for device controls
        self.control_container = ttk.Frame(self)
        self.control_container.pack(fill="both", expand=True, padx=10, pady=5)

        self.control_canvas = tk.Canvas(self.control_container, borderwidth=0, highlightthickness=0)
        self.control_scrollbar = ttk.Scrollbar(self.control_container, orient="vertical", command=self.control_canvas.yview)

        self.control_canvas.pack(side="left", fill="both", expand=True)
        self.control_scrollbar.pack(side="right", fill="y")

        self.control_frame = ttk.Frame(self.control_canvas)
        self._control_frame_id = self.control_canvas.create_window((0, 0), window=self.control_frame, anchor="nw")
        self.control_canvas.configure(yscrollcommand=self.control_scrollbar.set)

        self.control_frame.bind(
            "<Configure>",
            lambda event: self.control_canvas.configure(scrollregion=self.control_canvas.bbox("all")),
        )
        self.control_canvas.bind(
            "<Configure>",
            lambda event: self.control_canvas.itemconfigure(self._control_frame_id, width=event.width),
        )

        self.control_frame.bind("<Enter>", self._bind_canvas_scroll)
        self.control_frame.bind("<Leave>", self._unbind_canvas_scroll)

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

    def _get_device_preferences(self, ip):
        record = self.data["devices"].setdefault(ip, {})
        preferences = record.get("preferences")
        if not isinstance(preferences, dict):
            preferences = {}
            record["preferences"] = preferences
        return preferences

    def _store_device_preferences(self, ip, **updates):
        preferences = self._get_device_preferences(ip)
        sanitized = {key: value for key, value in updates.items() if value is not None}
        if not sanitized:
            return
        preferences.update(sanitized)
        save_data(self.data)

    def _get_room_settings(self, room_id):
        room_settings = self.data.setdefault("room_settings", {})
        settings = room_settings.get(room_id)
        if not isinstance(settings, dict):
            settings = {}
            room_settings[room_id] = settings
        return settings

    def _format_scene_choice(self, scene_id):
        if scene_id in SCENE_MAP:
            return f"{scene_id:02d} - {SCENE_MAP[scene_id]}"
        return ""

    def _parse_scene_selection(self, value):
        if not value:
            return None
        try:
            scene_text = value.split("-", 1)[0].strip()
            return int(scene_text)
        except (ValueError, AttributeError):
            return None

    def _update_scale_label(self, label_var, value, suffix=""):
        label_var.set(f"{int(float(value))}{suffix}")

    def toggle_logs(self):
        if self.output_visible:
            self.output_container.pack_forget()
            self.output_visible = False
            self.log_toggle.config(text="Show Logs")
        else:
            self.output_container.pack(fill='both', expand=False, padx=10, pady=10)
            self.output_visible = True
            self.log_toggle.config(text="Hide Logs")

    def _bind_canvas_scroll(self, _event):
        self.control_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_canvas_scroll(self, _event):
        self.control_canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        if event.delta == 0:
            return
        self.control_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _create_collapsible_section(self, parent, title, collapsed=True):
        container = ttk.Frame(parent)
        header = ttk.Frame(container)
        header.pack(fill="x")
        body = ttk.Frame(container)

        def show():
            body.pack(fill="x", pady=(4, 0))
            toggle_btn.config(text=f"Hide {title}")

        def hide():
            body.pack_forget()
            toggle_btn.config(text=f"Show {title}")

        def toggle():
            if body.winfo_ismapped():
                hide()
            else:
                show()

        toggle_btn = ttk.Button(header, text="", command=toggle)
        toggle_btn.pack(side="left")

        if collapsed:
            hide()
        else:
            show()

        return container, body

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
            "preferences": existing.get("preferences", {}),
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
        for widget in self.control_frame.winfo_children():
            widget.destroy()

        rooms = self._group_devices_by_room(include_offline=True)

        for room_id, devices_in_room in rooms.items():
            room_name = self.data["rooms"].get(room_id, f"Room {room_id}")
            room_settings = self._get_room_settings(room_id)
            device_ips = tuple(device["ip"] for device in devices_in_room)

            room_frame = ttk.LabelFrame(self.control_frame, text=f"{room_name} (ID: {room_id})")
            room_frame.pack(fill="x", padx=5, pady=5)

            header_frame = ttk.Frame(room_frame)
            header_frame.pack(fill="x", pady=5)

            name_var = tk.StringVar(value=room_name)
            name_entry = ttk.Entry(header_frame, textvariable=name_var, width=25)
            name_entry.pack(side="left", padx=5)

            save_btn = ttk.Button(
                header_frame,
                text="Save Name",
                command=lambda rid=room_id, var=name_var: self.on_save_room_name(rid, var),
            )
            save_btn.pack(side="left", padx=5)

            turn_on_btn = ttk.Button(
                header_frame,
                text="Turn All On",
                command=lambda rid=room_id, d=devices_in_room: self.on_toggle_room(rid, d, True),
            )
            turn_on_btn.pack(side="left", padx=5)

            turn_off_btn = ttk.Button(
                header_frame,
                text="Turn All Off",
                command=lambda rid=room_id, d=devices_in_room: self.on_toggle_room(rid, d, False),
            )
            turn_off_btn.pack(side="left", padx=5)

            scene_label = ttk.Label(header_frame, text="Scene:")
            scene_label.pack(side="left", padx=(15, 0))

            initial_scene_choice = self._format_scene_choice(room_settings.get("sceneId"))
            scene_var = tk.StringVar(value=initial_scene_choice)

            scene_combo = ttk.Combobox(
                header_frame,
                values=SCENE_CHOICES,
                textvariable=scene_var,
                width=20,
                state="readonly",
            )
            scene_combo.pack(side="left", padx=5)

            speed_value = room_settings.get("sceneSpeed", 100)
            try:
                speed_value = int(speed_value)
            except (TypeError, ValueError):
                speed_value = 100
            speed_value = max(20, min(200, speed_value))
            speed_var = tk.IntVar(value=speed_value)

            speed_label = ttk.Label(header_frame, text="Speed")
            speed_label.pack(side="left", padx=(10, 0))

            speed_spin = tk.Spinbox(header_frame, from_=20, to=200, textvariable=speed_var, width=5)
            speed_spin.pack(side="left", padx=5)

            apply_scene_btn = ttk.Button(
                header_frame,
                text="Apply Scene",
                command=lambda rid=room_id, ips=device_ips, svar=scene_var, spd_var=speed_var: self.on_apply_room_scene(rid, ips, svar, spd_var),
            )
            apply_scene_btn.pack(side="left", padx=5)

            for device in devices_in_room:
                ip = device["ip"]
                module_name = device.get("moduleName", f"Device {ip}")
                state = self.device_status_cache.get(ip)

                if ip not in self.active_ips:
                    state_text = "Offline"
                    state_color = "gray"
                elif state is None:
                    state_text = "Unknown"
                    state_color = "orange"
                else:
                    state_text = "On" if state else "Off"
                    state_color = "green" if state else "red"

                preferences = self._get_device_preferences(ip)

                brightness_pref = preferences.get("dimming", DEFAULT_DIMMING)
                temperature_pref = preferences.get("temperature", DEFAULT_TEMPERATURE)
                red_pref = preferences.get("r", 0)
                green_pref = preferences.get("g", 0)
                blue_pref = preferences.get("b", 0)

                try:
                    brightness_value = int(float(brightness_pref))
                except (TypeError, ValueError):
                    brightness_value = DEFAULT_DIMMING
                brightness_value = max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, brightness_value))

                try:
                    temperature_value = int(float(temperature_pref))
                except (TypeError, ValueError):
                    temperature_value = DEFAULT_TEMPERATURE
                temperature_value = max(TEMPERATURE_MIN, min(TEMPERATURE_MAX, temperature_value))

                try:
                    red_value = max(0, min(255, int(float(red_pref))))
                except (TypeError, ValueError):
                    red_value = 0
                try:
                    green_value = max(0, min(255, int(float(green_pref))))
                except (TypeError, ValueError):
                    green_value = 0
                try:
                    blue_value = max(0, min(255, int(float(blue_pref))))
                except (TypeError, ValueError):
                    blue_value = 0

                device_frame = ttk.Frame(room_frame)
                device_frame.pack(fill="x", pady=4, padx=10)
                device_frame.columnconfigure(1, weight=1)

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

                color_container, color_frame = self._create_collapsible_section(
                    device_frame, "Color Controls", collapsed=True
                )
                color_container.grid(row=1, column=0, columnspan=5, sticky="we", pady=(4, 0))
                color_frame.columnconfigure(1, weight=1)

                brightness_var = tk.IntVar(value=brightness_value)
                brightness_label_var = tk.StringVar(value=f"{brightness_value}%")

                ttk.Label(color_frame, text="Brightness").grid(row=0, column=0, sticky="w")
                ttk.Scale(
                    color_frame,
                    from_=BRIGHTNESS_MIN,
                    to=BRIGHTNESS_MAX,
                    variable=brightness_var,
                    command=lambda value, lbl=brightness_label_var: self._update_scale_label(lbl, value, "%"),
                ).grid(row=0, column=1, sticky="we", padx=(5, 10))
                ttk.Label(color_frame, textvariable=brightness_label_var, width=6).grid(row=0, column=2, sticky="w")

                temperature_var = tk.IntVar(value=temperature_value)
                temperature_label_var = tk.StringVar(value=f"{temperature_value}K")

                ttk.Label(color_frame, text="Temperature").grid(row=1, column=0, sticky="w")
                ttk.Scale(
                    color_frame,
                    from_=TEMPERATURE_MIN,
                    to=TEMPERATURE_MAX,
                    variable=temperature_var,
                    command=lambda value, lbl=temperature_label_var: self._update_scale_label(lbl, value, "K"),
                ).grid(row=1, column=1, sticky="we", padx=(5, 10))
                ttk.Label(color_frame, textvariable=temperature_label_var, width=8).grid(row=1, column=2, sticky="w")

                apply_white_btn = ttk.Button(
                    color_frame,
                    text="Apply White",
                    command=lambda i=ip, b_var=brightness_var, t_var=temperature_var: self.on_apply_white(i, b_var, t_var),
                )
                apply_white_btn.grid(row=1, column=3, padx=5, sticky="e")

                red_var = tk.IntVar(value=red_value)
                green_var = tk.IntVar(value=green_value)
                blue_var = tk.IntVar(value=blue_value)

                red_label_var = tk.StringVar(value=str(red_value))
                green_label_var = tk.StringVar(value=str(green_value))
                blue_label_var = tk.StringVar(value=str(blue_value))

                ttk.Label(color_frame, text="Red").grid(row=2, column=0, sticky="w", pady=(6, 0))
                ttk.Scale(
                    color_frame,
                    from_=0,
                    to=255,
                    variable=red_var,
                    command=lambda value, lbl=red_label_var: self._update_scale_label(lbl, value),
                ).grid(row=2, column=1, sticky="we", padx=(5, 10))
                ttk.Label(color_frame, textvariable=red_label_var, width=4).grid(row=2, column=2, sticky="w")

                ttk.Label(color_frame, text="Green").grid(row=3, column=0, sticky="w")
                ttk.Scale(
                    color_frame,
                    from_=0,
                    to=255,
                    variable=green_var,
                    command=lambda value, lbl=green_label_var: self._update_scale_label(lbl, value),
                ).grid(row=3, column=1, sticky="we", padx=(5, 10))
                ttk.Label(color_frame, textvariable=green_label_var, width=4).grid(row=3, column=2, sticky="w")

                ttk.Label(color_frame, text="Blue").grid(row=4, column=0, sticky="w")
                ttk.Scale(
                    color_frame,
                    from_=0,
                    to=255,
                    variable=blue_var,
                    command=lambda value, lbl=blue_label_var: self._update_scale_label(lbl, value),
                ).grid(row=4, column=1, sticky="we", padx=(5, 10))
                ttk.Label(color_frame, textvariable=blue_label_var, width=4).grid(row=4, column=2, sticky="w")

                apply_color_btn = ttk.Button(
                    color_frame,
                    text="Apply Color",
                    command=lambda i=ip, b_var=brightness_var, r_var=red_var, g_var=green_var, bl_var=blue_var: self.on_apply_color(i, b_var, r_var, g_var, bl_var),
                )
                apply_color_btn.grid(row=2, column=3, rowspan=3, padx=5, sticky="nsw")

                preset_frame = ttk.Frame(color_frame)
                preset_frame.grid(row=5, column=0, columnspan=4, sticky="w", pady=(4, 0))

                for preset in COLOR_PRESETS:
                    ttk.Button(
                        preset_frame,
                        text=preset["label"],
                        command=lambda p=preset, i=ip, b_var=brightness_var, t_var=temperature_var, r_var=red_var, g_var=green_var, bl_var=blue_var, b_lbl=brightness_label_var, t_lbl=temperature_label_var, r_lbl=red_label_var, g_lbl=green_label_var, bl_lbl=blue_label_var: self.on_apply_preset(i, p, b_var, t_var, r_var, g_var, bl_var, b_lbl, t_lbl, r_lbl, g_lbl, bl_lbl),
                    ).pack(side="left", padx=2)

        if not rooms:
            empty_label = ttk.Label(self.control_frame, text="No rooms registered yet.")
            empty_label.pack(pady=10)

    def on_apply_white(self, ip, brightness_var, temperature_var):
        try:
            brightness = int(float(brightness_var.get()))
        except (TypeError, ValueError):
            brightness = DEFAULT_DIMMING
        brightness = max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, brightness))

        try:
            temperature = int(float(temperature_var.get()))
        except (TypeError, ValueError):
            temperature = DEFAULT_TEMPERATURE
        temperature = max(TEMPERATURE_MIN, min(TEMPERATURE_MAX, temperature))

        def apply():
            try:
                response = self.discovery.set_color_temperature(ip, temperature, dimming=brightness, turn_on=True)
                if response:
                    self.log(f"Applied white settings to {ip} (brightness {brightness}%, {temperature}K).")
                    self.device_status_cache[ip] = True
                    self.active_ips.add(ip)
                    self._store_device_preferences(ip, dimming=brightness, temperature=temperature)
                    self.schedule_refresh()
                else:
                    self.log(f"Could not apply white settings to {ip}.")
            except Exception as exc:
                self.log(f"Error applying white settings to {ip}: {exc}")

        threading.Thread(target=apply, daemon=True).start()

    def on_apply_color(self, ip, brightness_var, red_var, green_var, blue_var):
        try:
            brightness = int(float(brightness_var.get()))
        except (TypeError, ValueError):
            brightness = DEFAULT_DIMMING
        brightness = max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, brightness))

        def to_channel(var):
            try:
                return max(0, min(255, int(float(var.get()))))
            except (TypeError, ValueError):
                return 0

        red = to_channel(red_var)
        green = to_channel(green_var)
        blue = to_channel(blue_var)

        def apply():
            try:
                response = self.discovery.set_color(
                    ip,
                    r=red,
                    g=green,
                    b=blue,
                    dimming=brightness,
                    turn_on=True,
                )
                if response:
                    self.log(f"Applied color to {ip} (R{red} G{green} B{blue}, brightness {brightness}%).")
                    self.device_status_cache[ip] = True
                    self.active_ips.add(ip)
                    self._store_device_preferences(ip, dimming=brightness, r=red, g=green, b=blue)
                    self.schedule_refresh()
                else:
                    self.log(f"Could not apply color to {ip}.")
            except Exception as exc:
                self.log(f"Error applying color to {ip}: {exc}")

        threading.Thread(target=apply, daemon=True).start()

    def on_apply_preset(
        self,
        ip,
        preset,
        brightness_var,
        temperature_var,
        red_var,
        green_var,
        blue_var,
        brightness_label,
        temperature_label,
        red_label,
        green_label,
        blue_label,
    ):
        dimming = preset.get("dimming")
        if dimming is not None:
            brightness_var.set(dimming)
            self._update_scale_label(brightness_label, dimming, "%")

        if "temperature" in preset:
            temperature = preset["temperature"]
            temperature_var.set(temperature)
            self._update_scale_label(temperature_label, temperature, "K")
            self.on_apply_white(ip, brightness_var, temperature_var)
            return

        red = preset.get("r", 0)
        green = preset.get("g", 0)
        blue = preset.get("b", 0)

        red_var.set(red)
        green_var.set(green)
        blue_var.set(blue)

        self._update_scale_label(red_label, red)
        self._update_scale_label(green_label, green)
        self._update_scale_label(blue_label, blue)

        self.on_apply_color(ip, brightness_var, red_var, green_var, blue_var)

    def on_apply_room_scene(self, room_id, device_ips, scene_var, speed_var):
        scene_id = self._parse_scene_selection(scene_var.get())
        if scene_id is None:
            messagebox.showwarning("Scene Required", "Select a scene before applying.")
            return

        try:
            speed_value = int(float(speed_var.get()))
        except (TypeError, ValueError):
            speed_value = None

        if speed_value is not None:
            speed_value = max(20, min(200, speed_value))

        def apply():
            success = False
            for ip in device_ips:
                try:
                    response = self.discovery.set_scene(ip, scene_id=scene_id, speed=speed_value, turn_on=True)
                    if response:
                        success = True
                        self.device_status_cache[ip] = True
                        self.active_ips.add(ip)
                    else:
                        self.log(f"Device {ip} did not accept scene {scene_id}.")
                except Exception as exc:
                    self.log(f"Error applying scene {scene_id} to {ip}: {exc}")

            if success:
                settings = self._get_room_settings(room_id)
                settings["sceneId"] = scene_id
                if speed_value is not None:
                    settings["sceneSpeed"] = speed_value
                save_data(self.data)
                scene_name = SCENE_MAP.get(scene_id, "Scene")
                self.log(f"Applied scene {scene_id} ({scene_name}) to room {room_id}.")
                self.schedule_refresh()
            else:
                self.log(f"Failed to apply scene {scene_id} to room {room_id}.")

        threading.Thread(target=apply, daemon=True).start()

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

    def on_save_room_name(self, room_id, name_var):
        new_name = (name_var.get() or "").strip()
        if not new_name:
            messagebox.showwarning("Invalid Name", "Please enter a valid room name.")
            return

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
