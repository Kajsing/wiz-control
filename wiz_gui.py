import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import tkinter.font as tkfont
import copy
import threading
import json
import queue
import time

from wiz_discovery import WizDiscovery
from wiz_store import (
    DATA_FILE,
    build_device_record,
    load_data as load_store_data,
    normalize_data,
    save_data as save_store_data,
)

BACKGROUND_COLOR = "#f3f4f6"
SURFACE_COLOR = "#ffffff"
ACCENT_COLOR = "#6366f1"
ACCENT_HOVER_COLOR = "#4f46e5"
SECONDARY_COLOR = "#e5e7eb"
DANGER_COLOR = "#f87171"
DANGER_HOVER_COLOR = "#ef4444"
TEXT_COLOR = "#111827"
MUTED_TEXT_COLOR = "#6b7280"
BORDER_COLOR = "#d1d5db"
LOG_BACKGROUND_COLOR = "#111827"
PRESET_BUTTON_COLOR = "#dbeafe"

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


def load_data():
    try:
        return load_store_data(DATA_FILE)
    except json.JSONDecodeError:
        messagebox.showerror("Error", "Data file is corrupted. Loading empty data.")
        return normalize_data(None)


def save_data(data):
    save_store_data(data, DATA_FILE)


class WizGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WiZ Device Manager")
        self.geometry("800x600")
        self.resizable(True, True)
        self._main_thread = threading.current_thread()
        self._state_lock = threading.RLock()
        self._refresh_lock = threading.Lock()
        self._worker_lock = threading.Lock()
        self._worker_threads = set()
        self._ui_queue = queue.Queue()
        self._closing = False
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self._configure_style()

        self.discovery = WizDiscovery()
        self.data = load_data()
        self.active_ips = set()
        self.device_status_cache = {ip: None for ip in self.data["devices"]}
        self._refresh_scheduled = False

        self.create_widgets()
        self.refresh_control_frame()
        self.after(50, self._process_ui_queue)
        self.stop_event = self.update_status_periodically()

    def _configure_style(self):
        self.configure(bg=BACKGROUND_COLOR)
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=10)

        text_font = tkfont.nametofont("TkTextFont")
        text_font.configure(family="Segoe UI", size=10)

        fixed_font = tkfont.nametofont("TkFixedFont")
        fixed_font.configure(family="Consolas", size=10)

        self.heading_font = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        self.subheading_font = tkfont.Font(family="Segoe UI", size=11)
        self.room_title_font = tkfont.Font(family="Segoe UI", size=12, weight="bold")

        # Base styles
        self.style.configure("TFrame", background=BACKGROUND_COLOR)
        self.style.configure("App.TFrame", background=BACKGROUND_COLOR)
        self.style.configure("Toolbar.TFrame", background=BACKGROUND_COLOR)
        self.style.configure("CardContainer.TFrame", background=SURFACE_COLOR)
        self.style.configure("CardHeader.TFrame", background=SURFACE_COLOR)
        self.style.configure("CardBody.TFrame", background=SURFACE_COLOR)
        self.style.configure("Section.TFrame", background=SURFACE_COLOR)
        self.style.configure("SectionHeader.TFrame", background=SURFACE_COLOR)
        self.style.configure("SectionBody.TFrame", background=SURFACE_COLOR)
        self.style.configure("Log.TFrame", background=LOG_BACKGROUND_COLOR)

        self.style.configure("Heading.TLabel", background=BACKGROUND_COLOR, foreground=TEXT_COLOR, font=self.heading_font)
        self.style.configure("Subheading.TLabel", background=BACKGROUND_COLOR, foreground=MUTED_TEXT_COLOR, font=self.subheading_font)
        self.style.configure("CardTitle.TLabel", background=SURFACE_COLOR, foreground=TEXT_COLOR, font=self.room_title_font)
        self.style.configure("Card.TLabel", background=SURFACE_COLOR, foreground=TEXT_COLOR)
        self.style.configure("CardMuted.TLabel", background=SURFACE_COLOR, foreground=MUTED_TEXT_COLOR)
        self.style.configure("Muted.TLabel", background=BACKGROUND_COLOR, foreground=MUTED_TEXT_COLOR)
        self.style.configure("Badge.TLabel", background=ACCENT_COLOR, foreground="white", padding=(8, 2))

        self.style.configure("Divider.TSeparator", background=BORDER_COLOR)

        # Buttons
        self.style.configure("Primary.TButton", background=ACCENT_COLOR, foreground="white", padding=(12, 6), borderwidth=0, focusthickness=0)
        self.style.map("Primary.TButton", background=[("active", ACCENT_HOVER_COLOR), ("disabled", "#a5b4fc")], foreground=[("disabled", "#e0e7ff")])

        self.style.configure("Secondary.TButton", background=SECONDARY_COLOR, foreground=TEXT_COLOR, padding=(10, 5), borderwidth=0)
        self.style.map("Secondary.TButton", background=[("active", "#d1d5db"), ("disabled", SECONDARY_COLOR)])

        self.style.configure("Ghost.TButton", background=BACKGROUND_COLOR, foreground=TEXT_COLOR, padding=(10, 5), borderwidth=0)
        self.style.map("Ghost.TButton", background=[("active", SECONDARY_COLOR)])

        self.style.configure("Danger.TButton", background=DANGER_COLOR, foreground="white", padding=(10, 5), borderwidth=0)
        self.style.map("Danger.TButton", background=[("active", DANGER_HOVER_COLOR)])

        self.style.configure("Preset.TButton", background=PRESET_BUTTON_COLOR, foreground=ACCENT_COLOR, padding=(8, 3), borderwidth=0)
        self.style.map("Preset.TButton", background=[("active", "#bfdbfe")])

        self.style.configure("Toggle.TButton", background=SURFACE_COLOR, foreground=ACCENT_COLOR, padding=(0, 0), borderwidth=0)
        self.style.map("Toggle.TButton", foreground=[("active", ACCENT_HOVER_COLOR)])

        # Form controls
        self.style.configure("App.TEntry", fieldbackground=SURFACE_COLOR, foreground=TEXT_COLOR, padding=(6, 4))
        self.style.configure(
            "Title.TEntry",
            fieldbackground=SURFACE_COLOR,
            foreground=TEXT_COLOR,
            font=self.room_title_font,
            padding=(8, 6),
        )
        self.style.configure(
            "App.TCombobox",
            fieldbackground=SURFACE_COLOR,
            background=SURFACE_COLOR,
            foreground=TEXT_COLOR,
            padding=6,
            arrowsize=14,
        )
        self.style.map(
            "App.TCombobox",
            fieldbackground=[("readonly", SURFACE_COLOR)],
            foreground=[("readonly", TEXT_COLOR)],
        )

        self.style.configure("Vertical.TScrollbar", background=BACKGROUND_COLOR, troughcolor=BACKGROUND_COLOR, bordercolor=BACKGROUND_COLOR)

    def create_widgets(self):
        self.main_container = ttk.Frame(self, style="App.TFrame", padding=(20, 10, 20, 20))
        self.main_container.pack(fill="both", expand=True)

        header_frame = ttk.Frame(self.main_container, style="Toolbar.TFrame")
        header_frame.pack(fill="x")
        header_frame.columnconfigure(0, weight=1)

        heading_label = ttk.Label(header_frame, text="WiZ Device Manager", style="Heading.TLabel")
        heading_label.grid(row=0, column=0, sticky="w")

        subheading_label = ttk.Label(
            header_frame,
            text="Click Discover Devices to scan your WiZ network and fine-tune each light.",
            style="Subheading.TLabel",
        )
        subheading_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        action_frame = ttk.Frame(header_frame, style="Toolbar.TFrame")
        action_frame.grid(row=0, column=1, rowspan=2, sticky="e")

        discover_button = ttk.Button(
            action_frame,
            text="Discover Devices",
            style="Primary.TButton",
            command=self.on_discover_click,
        )
        discover_button.pack(side="left", padx=(0, 10))
        discover_button.configure(takefocus=False)

        self.log_toggle = ttk.Button(action_frame, text="Show Logs", style="Ghost.TButton", command=self.toggle_logs)
        self.log_toggle.pack(side="left")

        ttk.Separator(self.main_container, style="Divider.TSeparator").pack(fill="x", pady=(16, 16))

        self.output_container = ttk.Frame(self.main_container, style="Log.TFrame", padding=12)
        self.output_box = scrolledtext.ScrolledText(self.output_container, width=80, height=8, state="disabled")
        self.output_box.pack(fill='both', expand=True)
        self.output_box.configure(
            bg=LOG_BACKGROUND_COLOR,
            fg="#e5e7eb",
            insertbackground="#e5e7eb",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=("Consolas", 10),
        )
        self.output_visible = False

        self.control_container = ttk.Frame(self.main_container, style="App.TFrame")
        self.control_container.pack(fill="both", expand=True)

        self.control_canvas = tk.Canvas(self.control_container, borderwidth=0, highlightthickness=0, bg=BACKGROUND_COLOR)
        self.control_scrollbar = ttk.Scrollbar(self.control_container, orient="vertical", command=self.control_canvas.yview)

        self.control_canvas.pack(side="left", fill="both", expand=True)
        self.control_scrollbar.pack(side="right", fill="y")

        self.control_frame = ttk.Frame(self.control_canvas, style="App.TFrame")
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

    def _run_on_ui_thread(self, callback, *args, **kwargs):
        if self._closing:
            return
        self._ui_queue.put((callback, args, kwargs))

    def _process_ui_queue(self):
        while True:
            try:
                callback, args, kwargs = self._ui_queue.get_nowait()
            except queue.Empty:
                break

            if self._closing:
                continue

            try:
                callback(*args, **kwargs)
            except tk.TclError:
                if not self._closing:
                    raise

        if not self._closing:
            self.after(50, self._process_ui_queue)

    def _append_log_message(self, message):
        if self._closing or not hasattr(self, "output_box") or not self.output_box.winfo_exists():
            return
        self.output_box.config(state="normal")
        self.output_box.insert(tk.END, f"{message}\n")
        self.output_box.see(tk.END)
        self.output_box.config(state="disabled")

    def log(self, message):
        self._run_on_ui_thread(self._append_log_message, message)

    def _show_error(self, title, message):
        if self._closing or not self.winfo_exists():
            return
        messagebox.showerror(title, message)

    def _snapshot_data(self):
        with self._state_lock:
            return copy.deepcopy(self.data)

    def _save_data(self):
        try:
            save_data(self._snapshot_data())
            return True
        except Exception as exc:
            self.log(f"Could not save data: {exc}")
            self._run_on_ui_thread(self._show_error, "Error", f"Could not save data: {exc}")
            return False

    def _start_worker(self, target, name):
        def runner():
            try:
                target()
            finally:
                with self._worker_lock:
                    self._worker_threads.discard(threading.current_thread())

        worker = threading.Thread(target=runner, name=name, daemon=True)
        with self._worker_lock:
            self._worker_threads.add(worker)
        worker.start()

    def on_toggle_room(self, room_id, devices, state):
        def toggle():
            refresh_needed = False
            for device in devices:
                ip = device["ip"]
                try:
                    response = self.discovery.send_command(ip, "setState", {"state": state})
                    if response:
                        self.log(f"Device {ip} {'turned on' if state else 'turned off'}.")
                        with self._state_lock:
                            self.device_status_cache[ip] = state
                            self.active_ips.add(ip)
                        refresh_needed = True
                    else:
                        self.log(f"Could not update device {ip}.")
                except Exception as e:
                    self.log(f"Error while controlling device {ip}: {e}")

            if refresh_needed:
                self.schedule_refresh()

        self._start_worker(toggle, "toggle-room")

    def on_toggle_device(self, ip, state):
        def toggle():
            try:
                response = self.discovery.send_command(ip, "setState", {"state": state})
                if response:
                    self.log(f"Device {ip} {'turned on' if state else 'turned off'}.")
                    with self._state_lock:
                        self.device_status_cache[ip] = state
                        self.active_ips.add(ip)
                    self.schedule_refresh()
                else:
                    self.log(f"Could not update device {ip}.")
                time.sleep(0.2)  # Give the device time to update
            except Exception as e:
                self.log(f"Error while controlling device {ip}: {e}")

        self._start_worker(toggle, "toggle-device")

    def on_remove_device(self, ip):
        removed = False
        with self._state_lock:
            if ip in self.data["devices"]:
                del self.data["devices"][ip]
                self.active_ips.discard(ip)
                self.device_status_cache.pop(ip, None)
                removed = True

        if removed:
            self._save_data()
            self.log(f"Device {ip} removed.")
            self.schedule_refresh()

    def on_discover_click(self):
        self._start_worker(self.discover_devices, "discover-devices")

    def schedule_refresh(self):
        if self._closing:
            return

        with self._refresh_lock:
            if self._refresh_scheduled:
                return
            self._refresh_scheduled = True

        self._run_on_ui_thread(self._perform_refresh)

    def _perform_refresh(self):
        with self._refresh_lock:
            self._refresh_scheduled = False

        if self._closing:
            return
        self.refresh_control_frame()

    def _get_device_preferences(self, ip):
        with self._state_lock:
            record = self.data["devices"].setdefault(ip, {})
            preferences = record.get("preferences")
            if not isinstance(preferences, dict):
                preferences = {}
                record["preferences"] = preferences
            return preferences

    def _store_device_preferences(self, ip, **updates):
        sanitized = {key: value for key, value in updates.items() if value is not None}
        if not sanitized:
            return

        with self._state_lock:
            preferences = self._get_device_preferences(ip)
            preferences.update(sanitized)

        self._save_data()

    def _get_room_settings(self, room_id):
        with self._state_lock:
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
            self.output_container.pack(fill='both', expand=False, pady=(0, 16), before=self.control_container)
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
        container = ttk.Frame(parent, style="Section.TFrame")
        header = ttk.Frame(container, style="SectionHeader.TFrame")
        header.pack(fill="x")
        body = ttk.Frame(container, style="SectionBody.TFrame", padding=(4, 0, 4, 0))

        def show():
            body.pack(fill="x", pady=(8, 0))
            toggle_btn.config(text=f"Hide {title}")

        def hide():
            body.pack_forget()
            toggle_btn.config(text=f"Show {title}")

        def toggle():
            if body.winfo_ismapped():
                hide()
            else:
                show()

        toggle_btn = ttk.Button(header, text="", style="Toggle.TButton", command=toggle)
        toggle_btn.pack(side="left")

        if collapsed:
            hide()
        else:
            show()

        return container, body

    def _build_device_record(self, ip, info):
        with self._state_lock:
            existing = self.data["devices"].get(ip, {})
        return build_device_record(ip, info, existing)

    def _build_view_snapshot(self, include_offline=True):
        with self._state_lock:
            grouped = {}
            active_ips = set(self.active_ips)
            device_status_cache = dict(self.device_status_cache)
            room_names = dict(self.data.get("rooms", {}))
            room_settings = {
                room_id: dict(settings) if isinstance(settings, dict) else {}
                for room_id, settings in self.data.get("room_settings", {}).items()
            }

            for ip, record in self.data["devices"].items():
                if not include_offline and ip not in active_ips:
                    continue
                room_id = record.get("roomId", "Unknown")
                grouped.setdefault(room_id, []).append(copy.deepcopy(record))

        for device_list in grouped.values():
            device_list.sort(key=lambda entry: entry.get("moduleName", ""))

        rooms = dict(sorted(grouped.items(), key=lambda item: item[0]))
        return rooms, active_ips, device_status_cache, room_names, room_settings

    def discover_devices(self):
        self.log("Starting device discovery...")
        try:
            discovered = self.discovery.discover_wiz_devices()
            found_ips = [ip for ip, _ in discovered]
            with self._state_lock:
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
                rooms, _, _, room_names, _ = self._build_view_snapshot(include_offline=False)
                for room_id, devices_in_room in rooms.items():
                    room_name = room_names.get(room_id, f"Room {room_id}")
                    self.log(f"  {room_name} (ID: {room_id})")
            else:
                self.log("No WiZ devices found.")

            if updated:
                self._save_data()
            self.schedule_refresh()
        except Exception as e:
            self.log(f"Error during discovery: {e}")

    def refresh_control_frame(self):
        for widget in self.control_frame.winfo_children():
            widget.destroy()

        rooms, active_ips, device_status_cache, room_names, room_settings_map = self._build_view_snapshot(include_offline=True)

        if not rooms:
            empty_label = ttk.Label(self.control_frame, text="No rooms registered yet.", style="Muted.TLabel")
            empty_label.pack(pady=20)
            return

        for room_index, (room_id, devices_in_room) in enumerate(rooms.items()):
            room_name = room_names.get(room_id, f"Room {room_id}")
            room_settings = room_settings_map.get(room_id, {})
            device_ips = tuple(device["ip"] for device in devices_in_room)

            card = tk.Frame(
                self.control_frame,
                bg=SURFACE_COLOR,
                bd=0,
                highlightbackground=BORDER_COLOR,
                highlightcolor=BORDER_COLOR,
                highlightthickness=1,
            )
            card.pack(fill="x", pady=12, padx=4)

            room_frame = ttk.Frame(card, style="CardContainer.TFrame", padding=16)
            room_frame.pack(fill="both", expand=True)
            room_frame.columnconfigure(0, weight=1)

            header_frame = ttk.Frame(room_frame, style="CardHeader.TFrame")
            header_frame.grid(row=0, column=0, sticky="ew")
            header_frame.columnconfigure(0, weight=1)

            name_var = tk.StringVar(value=room_name)
            name_container = ttk.Frame(header_frame, style="CardHeader.TFrame")
            name_container.grid(row=0, column=0, sticky="w")

            name_entry = ttk.Entry(name_container, textvariable=name_var, width=28, style="Title.TEntry")
            name_entry.pack(side="left")

            room_badge = ttk.Label(name_container, text=f"ID {room_id}", style="Badge.TLabel")
            room_badge.pack(side="left", padx=(12, 0))

            save_btn = ttk.Button(
                header_frame,
                text="Save Name",
                style="Ghost.TButton",
                command=lambda rid=room_id, var=name_var: self.on_save_room_name(rid, var),
            )
            save_btn.grid(row=0, column=1, sticky="e")

            scene_frame = ttk.Frame(room_frame, style="CardHeader.TFrame")
            scene_frame.grid(row=1, column=0, sticky="ew", pady=(12, 8))
            scene_frame.columnconfigure(0, weight=1)

            initial_scene_choice = self._format_scene_choice(room_settings.get("sceneId"))
            scene_var = tk.StringVar(value=initial_scene_choice)

            scene_controls = ttk.Frame(scene_frame, style="CardHeader.TFrame")
            scene_controls.grid(row=0, column=0, sticky="w")

            ttk.Label(scene_controls, text="Scene", style="CardMuted.TLabel").pack(side="left")

            scene_combo = ttk.Combobox(
                scene_controls,
                values=SCENE_CHOICES,
                textvariable=scene_var,
                width=24,
                state="readonly",
                style="App.TCombobox",
            )
            scene_combo.pack(side="left", padx=(8, 10))

            speed_value = room_settings.get("sceneSpeed", 100)
            try:
                speed_value = int(speed_value)
            except (TypeError, ValueError):
                speed_value = 100
            speed_value = max(20, min(200, speed_value))
            speed_var = tk.IntVar(value=speed_value)

            ttk.Label(scene_controls, text="Speed", style="CardMuted.TLabel").pack(side="left")
            speed_spin = tk.Spinbox(scene_controls, from_=20, to=200, textvariable=speed_var, width=4)
            speed_spin.pack(side="left", padx=(6, 10))
            speed_spin.configure(
                background=SURFACE_COLOR,
                foreground=TEXT_COLOR,
                relief="flat",
                highlightthickness=1,
                highlightbackground=BORDER_COLOR,
                highlightcolor=ACCENT_COLOR,
                insertbackground=TEXT_COLOR,
            )

            apply_scene_btn = ttk.Button(
                scene_controls,
                text="Apply Scene",
                style="Secondary.TButton",
                command=lambda rid=room_id, ips=device_ips, svar=scene_var, spd_var=speed_var: self.on_apply_room_scene(rid, ips, svar, spd_var),
            )
            apply_scene_btn.pack(side="left")

            room_actions = ttk.Frame(scene_frame, style="CardHeader.TFrame")
            room_actions.grid(row=0, column=1, sticky="e")

            turn_on_btn = ttk.Button(
                room_actions,
                text="Turn All On",
                style="Ghost.TButton",
                command=lambda rid=room_id, d=devices_in_room: self.on_toggle_room(rid, d, True),
            )
            turn_on_btn.pack(side="left", padx=(0, 6))

            turn_off_btn = ttk.Button(
                room_actions,
                text="Turn All Off",
                style="Ghost.TButton",
                command=lambda rid=room_id, d=devices_in_room: self.on_toggle_room(rid, d, False),
            )
            turn_off_btn.pack(side="left")

            room_shortcut_var = tk.StringVar(value=room_name)
            room_shortcut_frame = ttk.Frame(scene_frame, style="CardHeader.TFrame")
            room_shortcut_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
            ttk.Label(room_shortcut_frame, text="Shortcut", style="CardMuted.TLabel").pack(side="left")
            ttk.Entry(room_shortcut_frame, textvariable=room_shortcut_var, width=24, style="App.TEntry").pack(side="left", padx=(8, 6))
            ttk.Button(
                room_shortcut_frame,
                text="Save On",
                style="Ghost.TButton",
                command=lambda var=room_shortcut_var, rid=room_id: self.on_save_state_shortcut(var, "room", rid, True),
            ).pack(side="left", padx=(0, 4))
            ttk.Button(
                room_shortcut_frame,
                text="Save Off",
                style="Ghost.TButton",
                command=lambda var=room_shortcut_var, rid=room_id: self.on_save_state_shortcut(var, "room", rid, False),
            ).pack(side="left")

            for device_index, device in enumerate(devices_in_room):
                row_offset = 2 + device_index * 2
                ip = device["ip"]
                module_name = device.get("moduleName", f"Device {ip}")
                state = device_status_cache.get(ip)

                if ip not in active_ips:
                    state_text = "Offline"
                    state_color = "#9ca3af"
                elif state is None:
                    state_text = "Unknown"
                    state_color = "#f59e0b"
                else:
                    state_text = "On" if state else "Off"
                    state_color = "#10b981" if state else "#ef4444"

                preferences = device.get("preferences", {})
                if not isinstance(preferences, dict):
                    preferences = {}

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

                device_frame = ttk.Frame(room_frame, style="CardBody.TFrame", padding=(0, 8))
                device_frame.grid(row=row_offset, column=0, sticky="ew")
                device_frame.columnconfigure(1, weight=1)

                name_label = ttk.Label(device_frame, text=f"{module_name} ({ip})", style="Card.TLabel")
                name_label.grid(row=0, column=0, sticky="w")

                status_label = ttk.Label(
                    device_frame,
                    text=f"Status: {state_text}",
                    style="Card.TLabel",
                    foreground=state_color,
                )
                status_label.grid(row=0, column=1, sticky="w", padx=10)

                on_button = ttk.Button(device_frame, text="Turn On", style="Primary.TButton", command=lambda i=ip: self.on_toggle_device(i, True))
                on_button.grid(row=0, column=2, padx=5)

                off_button = ttk.Button(device_frame, text="Turn Off", style="Secondary.TButton", command=lambda i=ip: self.on_toggle_device(i, False))
                off_button.grid(row=0, column=3, padx=5)

                remove_button = ttk.Button(device_frame, text="Remove", style="Danger.TButton", command=lambda i=ip: self.on_remove_device(i))
                remove_button.grid(row=0, column=4, padx=5)

                device_shortcut_var = tk.StringVar(value=module_name)
                device_shortcut_frame = ttk.Frame(device_frame, style="CardBody.TFrame")
                device_shortcut_frame.grid(row=1, column=0, columnspan=5, sticky="w", pady=(8, 0))
                ttk.Label(device_shortcut_frame, text="Shortcut", style="CardMuted.TLabel").pack(side="left")
                ttk.Entry(device_shortcut_frame, textvariable=device_shortcut_var, width=24, style="App.TEntry").pack(side="left", padx=(8, 6))
                ttk.Button(
                    device_shortcut_frame,
                    text="Save On",
                    style="Ghost.TButton",
                    command=lambda var=device_shortcut_var, target_ip=ip: self.on_save_state_shortcut(var, "device", target_ip, True),
                ).pack(side="left", padx=(0, 4))
                ttk.Button(
                    device_shortcut_frame,
                    text="Save Off",
                    style="Ghost.TButton",
                    command=lambda var=device_shortcut_var, target_ip=ip: self.on_save_state_shortcut(var, "device", target_ip, False),
                ).pack(side="left")

                color_container, color_frame = self._create_collapsible_section(device_frame, "Color Controls", collapsed=True)
                color_container.grid(row=2, column=0, columnspan=5, sticky="we", pady=(8, 0))
                color_frame.columnconfigure(1, weight=1)

                brightness_var = tk.IntVar(value=brightness_value)
                brightness_label_var = tk.StringVar(value=f"{brightness_value}%")

                ttk.Label(color_frame, text="Brightness", style="CardMuted.TLabel").grid(row=0, column=0, sticky="w")
                ttk.Scale(
                    color_frame,
                    from_=BRIGHTNESS_MIN,
                    to=BRIGHTNESS_MAX,
                    variable=brightness_var,
                    command=lambda value, lbl=brightness_label_var: self._update_scale_label(lbl, value, "%"),
                ).grid(row=0, column=1, sticky="we", padx=(8, 10))
                ttk.Label(color_frame, textvariable=brightness_label_var, style="CardMuted.TLabel", width=6).grid(row=0, column=2, sticky="w")

                temperature_var = tk.IntVar(value=temperature_value)
                temperature_label_var = tk.StringVar(value=f"{temperature_value}K")

                ttk.Label(color_frame, text="Temperature", style="CardMuted.TLabel").grid(row=1, column=0, sticky="w")
                ttk.Scale(
                    color_frame,
                    from_=TEMPERATURE_MIN,
                    to=TEMPERATURE_MAX,
                    variable=temperature_var,
                    command=lambda value, lbl=temperature_label_var: self._update_scale_label(lbl, value, "K"),
                ).grid(row=1, column=1, sticky="we", padx=(8, 10))
                ttk.Label(color_frame, textvariable=temperature_label_var, style="CardMuted.TLabel", width=8).grid(row=1, column=2, sticky="w")

                apply_white_btn = ttk.Button(
                    color_frame,
                    text="Apply White",
                    style="Primary.TButton",
                    command=lambda i=ip, b_var=brightness_var, t_var=temperature_var: self.on_apply_white(i, b_var, t_var),
                )
                apply_white_btn.grid(row=1, column=3, padx=5, sticky="e")

                red_var = tk.IntVar(value=red_value)
                green_var = tk.IntVar(value=green_value)
                blue_var = tk.IntVar(value=blue_value)

                red_label_var = tk.StringVar(value=str(red_value))
                green_label_var = tk.StringVar(value=str(green_value))
                blue_label_var = tk.StringVar(value=str(blue_value))

                ttk.Label(color_frame, text="Red", style="CardMuted.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))
                ttk.Scale(
                    color_frame,
                    from_=0,
                    to=255,
                    variable=red_var,
                    command=lambda value, lbl=red_label_var: self._update_scale_label(lbl, value),
                ).grid(row=2, column=1, sticky="we", padx=(8, 10))
                ttk.Label(color_frame, textvariable=red_label_var, style="CardMuted.TLabel", width=4).grid(row=2, column=2, sticky="w")

                ttk.Label(color_frame, text="Green", style="CardMuted.TLabel").grid(row=3, column=0, sticky="w")
                ttk.Scale(
                    color_frame,
                    from_=0,
                    to=255,
                    variable=green_var,
                    command=lambda value, lbl=green_label_var: self._update_scale_label(lbl, value),
                ).grid(row=3, column=1, sticky="we", padx=(8, 10))
                ttk.Label(color_frame, textvariable=green_label_var, style="CardMuted.TLabel", width=4).grid(row=3, column=2, sticky="w")

                ttk.Label(color_frame, text="Blue", style="CardMuted.TLabel").grid(row=4, column=0, sticky="w")
                ttk.Scale(
                    color_frame,
                    from_=0,
                    to=255,
                    variable=blue_var,
                    command=lambda value, lbl=blue_label_var: self._update_scale_label(lbl, value),
                ).grid(row=4, column=1, sticky="we", padx=(8, 10))
                ttk.Label(color_frame, textvariable=blue_label_var, style="CardMuted.TLabel", width=4).grid(row=4, column=2, sticky="w")

                apply_color_btn = ttk.Button(
                    color_frame,
                    text="Apply Color",
                    style="Primary.TButton",
                    command=lambda i=ip, b_var=brightness_var, r_var=red_var, g_var=green_var, bl_var=blue_var: self.on_apply_color(i, b_var, r_var, g_var, bl_var),
                )
                apply_color_btn.grid(row=2, column=3, rowspan=3, padx=5, sticky="nsw")

                preset_frame = ttk.Frame(color_frame, style="SectionBody.TFrame")
                preset_frame.grid(row=5, column=0, columnspan=4, sticky="w", pady=(6, 0))

                for preset in COLOR_PRESETS:
                    ttk.Button(
                        preset_frame,
                        text=preset["label"],
                        style="Preset.TButton",
                        command=lambda p=preset, i=ip, b_var=brightness_var, t_var=temperature_var, r_var=red_var, g_var=green_var, bl_var=blue_var, b_lbl=brightness_label_var, t_lbl=temperature_label_var, r_lbl=red_label_var, g_lbl=green_label_var, bl_lbl=blue_label_var: self.on_apply_preset(i, p, b_var, t_var, r_var, g_var, bl_var, b_lbl, t_lbl, r_lbl, g_lbl, bl_lbl),
                    ).pack(side="left", padx=4, pady=(0, 4))

                if device_index < len(devices_in_room) - 1:
                    ttk.Separator(room_frame, style="Divider.TSeparator").grid(row=row_offset + 1, column=0, sticky="ew", pady=(4, 0))

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
                    with self._state_lock:
                        self.device_status_cache[ip] = True
                        self.active_ips.add(ip)
                    self._store_device_preferences(ip, dimming=brightness, temperature=temperature)
                    self.schedule_refresh()
                else:
                    self.log(f"Could not apply white settings to {ip}.")
            except Exception as exc:
                self.log(f"Error applying white settings to {ip}: {exc}")

        self._start_worker(apply, "apply-white")

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
                    with self._state_lock:
                        self.device_status_cache[ip] = True
                        self.active_ips.add(ip)
                    self._store_device_preferences(ip, dimming=brightness, r=red, g=green, b=blue)
                    self.schedule_refresh()
                else:
                    self.log(f"Could not apply color to {ip}.")
            except Exception as exc:
                self.log(f"Error applying color to {ip}: {exc}")

        self._start_worker(apply, "apply-color")

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
                        with self._state_lock:
                            self.device_status_cache[ip] = True
                            self.active_ips.add(ip)
                    else:
                        self.log(f"Device {ip} did not accept scene {scene_id}.")
                except Exception as exc:
                    self.log(f"Error applying scene {scene_id} to {ip}: {exc}")

            if success:
                with self._state_lock:
                    settings = self._get_room_settings(room_id)
                    settings["sceneId"] = scene_id
                    if speed_value is not None:
                        settings["sceneSpeed"] = speed_value
                self._save_data()
                scene_name = SCENE_MAP.get(scene_id, "Scene")
                self.log(f"Applied scene {scene_id} ({scene_name}) to room {room_id}.")
                self.schedule_refresh()
            else:
                self.log(f"Failed to apply scene {scene_id} to room {room_id}.")

        self._start_worker(apply, "apply-room-scene")

    def update_status_periodically(self):
        stop_event = threading.Event()

        def update():
            while not stop_event.is_set():
                state_changed = False
                with self._state_lock:
                    device_ips = list(self.data["devices"].keys())

                for ip in device_ips:
                    if stop_event.is_set():
                        break
                    try:
                        state = self.discovery.get_device_state(ip)
                        with self._state_lock:
                            previous_state = self.device_status_cache.get(ip)

                        if state is None:
                            with self._state_lock:
                                was_online = ip in self.active_ips
                                self.active_ips.discard(ip)
                                if previous_state is not None:
                                    self.device_status_cache[ip] = None
                            if was_online:
                                self.log(f"Device {ip} became unreachable.")
                                state_changed = True
                            if previous_state is not None:
                                state_changed = True
                        else:
                            with self._state_lock:
                                if ip not in self.active_ips:
                                    self.active_ips.add(ip)
                                    state_changed = True
                                if previous_state != state:
                                    self.device_status_cache[ip] = state
                                else:
                                    self.device_status_cache[ip] = state
                            if previous_state != state:
                                self.log(f"Updated status for {ip}: {'On' if state else 'Off'}")
                                state_changed = True
                    except Exception as e:
                        self.log(f"Error while updating status for {ip}: {e}")

                if state_changed:
                    self.schedule_refresh()

                if stop_event.wait(5):
                    break

        self._start_worker(update, "status-poller")
        return stop_event

    def on_save_state_shortcut(self, name_var, target_type, target, state):
        shortcut_name = (name_var.get() or "").strip()
        if not shortcut_name:
            messagebox.showwarning("Invalid Shortcut", "Please enter a shortcut name.")
            return

        state_label = "On" if state else "Off"
        if not shortcut_name.casefold().endswith((" on", " off")):
            shortcut_name = f"{shortcut_name} {state_label}"

        shortcut = {
            "label": shortcut_name,
            "target_type": target_type,
            "target": str(target),
            "action": "state",
            "state": bool(state),
        }

        with self._state_lock:
            self.data.setdefault("shortcuts", {})[shortcut_name] = shortcut

        self._save_data()
        command = f'python wiz_cli.py shortcut "{shortcut_name}"'
        self.log(f"Shortcut '{shortcut_name}' saved. Use: {command}")

    def on_save_room_name(self, room_id, name_var):
        new_name = (name_var.get() or "").strip()
        if not new_name:
            messagebox.showwarning("Invalid Name", "Please enter a valid room name.")
            return

        with self._state_lock:
            self.data["rooms"][room_id] = new_name
        self._save_data()
        self.log(f"Room {room_id} renamed to {new_name}.")
        self.schedule_refresh()

    def on_close(self):
        self._closing = True
        self.stop_event.set()
        self.destroy()

    def run(self):
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.mainloop()


if __name__ == "__main__":
    app = WizGUI()
    app.run()
