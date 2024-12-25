import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog, messagebox
import threading
import json
import os
import time

from wiz_discovery import WizDiscovery  # Importér WizDiscovery-klassen


# Fil til at gemme vedvarende data
DATA_FILE = "wiz_data.json"


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as file:
                return json.load(file)
        except json.JSONDecodeError:
            messagebox.showerror("Fejl", "Datafilen er korrupt. Indlæser tom data.")
    return {"rooms": {}, "devices": {}}


def save_data(data):
    try:
        with open(DATA_FILE, "w") as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        messagebox.showerror("Fejl", f"Kunne ikke gemme data: {e}")


class WizGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WiZ Device Manager")
        self.geometry("800x600")
        self.resizable(True, True)
        self.style = ttk.Style(self)
        self.style.theme_use('clam')  # Kan ændres til 'default', 'classic', etc.

        self.discovery = WizDiscovery()  # Initialiser WizDiscovery-klassen
        self.data = load_data()

        self.create_widgets()
        self.stop_event = self.update_status_periodically()

    def create_widgets(self):
        # Instruktionstekst
        instructions = ttk.Label(self, text="Klik på knappen for at opdage WiZ-enheder på dit lokale netværk.")
        instructions.pack(pady=10)

        # Frame til knapper og log
        top_frame = ttk.Frame(self)
        top_frame.pack(fill='x', padx=10, pady=5)

        # Discover-knap
        discover_button = ttk.Button(top_frame, text="Opdag Enheder", command=self.on_discover_click)
        discover_button.pack(side='left')

        # Log boksen
        self.output_box = scrolledtext.ScrolledText(self, width=80, height=10, state="disabled")
        self.output_box.pack(fill='both', expand=True, padx=10, pady=10)

        # Control frame for enhedsknapper
        self.control_frame = ttk.Frame(self)
        self.control_frame.pack(fill="both", expand=True, padx=10, pady=5)

    def log(self, message):
        self.output_box.config(state="normal")
        self.output_box.insert(tk.END, f"{message}\n")
        self.output_box.see(tk.END)
        self.output_box.config(state="disabled")

    def on_toggle_room(self, room_id, devices, state):
        def toggle():
            for device in devices:
                ip = device["ip"]
                try:
                    response = self.discovery.send_command(ip, "setState", {"state": state})
                    if response:
                        self.log(f"Enhed {ip} {'tændt' if state else 'slukket'}.")
                    else:
                        self.log(f"Kunne ikke opdatere enhed {ip}.")
                except Exception as e:
                    self.log(f"Fejl ved at styre enhed {ip}: {e}")

        threading.Thread(target=toggle).start()

    def on_toggle_device(self, ip, state):
        def toggle():
            try:
                response = self.discovery.send_command(ip, "setState", {"state": state})
                if response:
                    self.log(f"Enhed {ip} {'tændt' if state else 'slukket'}.")
                else:
                    self.log(f"Kunne ikke opdatere enhed {ip}.")
                time.sleep(0.2)  # Giv enheden tid til at opdatere
            except Exception as e:
                self.log(f"Fejl ved at styre enhed {ip}: {e}")

        threading.Thread(target=toggle).start()

    def on_remove_device(self, ip):
        if ip in self.data["devices"]:
            del self.data["devices"][ip]
            save_data(self.data)
            self.log(f"Enhed {ip} fjernet.")
            self.refresh_control_frame()

    def on_discover_click(self):
        threading.Thread(target=self.discover_devices).start()

    def discover_devices(self):
        self.log("Starter enhedsopdagelse...")
        try:
            devices = self.discovery.discover_wiz_devices()
            found_ips = [ip for ip, info in devices]

            # Marker offline enheder
            offline_devices = [ip for ip in self.data["devices"] if ip not in found_ips]

            if devices:
                rooms = self.discovery.sort_devices_by_room(devices)
                # Opdater data med nye enheder
                self.data["devices"] = {ip: info for ip, info in devices}
                self.log(f"WiZ-enheder fundet: {len(devices)}")

                for room_id, devices_in_room in rooms.items():
                    room_name = self.data["rooms"].get(room_id, f"Rum {room_id}")
                    self.log(f"  {room_name} (ID: {room_id})")
                save_data(self.data)
                self.refresh_control_frame()
            else:
                self.log("Ingen WiZ-enheder fundet.")
        except Exception as e:
            self.log(f"Fejl under opdagelse: {e}")

    def refresh_control_frame(self):
        # Rens kontrolrammen
        for widget in self.control_frame.winfo_children():
            widget.destroy()

        try:
            devices = self.discovery.discover_wiz_devices(timeout=2)  # Hurtigere opdagelse til opdatering
            rooms = self.discovery.sort_devices_by_room(devices)
        except Exception as e:
            self.log(f"Fejl under opdatering af kontrolrammen: {e}")
            devices = []
            rooms = {}

        for room_id, devices_in_room in rooms.items():
            room_name = self.data["rooms"].get(room_id, f"Rum {room_id}")
            room_frame = ttk.LabelFrame(self.control_frame, text=room_name)
            room_frame.pack(fill="x", padx=5, pady=5)

            # Header med rumkontroller
            header_frame = ttk.Frame(room_frame)
            header_frame.pack(fill="x", pady=5)

            rename_btn = ttk.Button(header_frame, text="Omdøb rum", command=lambda r=room_id: self.on_rename_room(r))
            rename_btn.pack(side='left', padx=5)

            turn_on_btn = ttk.Button(header_frame, text="Tænd alle", command=lambda d=devices_in_room: self.on_toggle_room(room_id, d, True))
            turn_on_btn.pack(side='left', padx=5)

            turn_off_btn = ttk.Button(header_frame, text="Sluk alle", command=lambda d=devices_in_room: self.on_toggle_room(room_id, d, False))
            turn_off_btn.pack(side='left', padx=5)

            # Vis enheder i rummet
            for device in devices_in_room:
                ip = device["ip"]
                module_name = device.get("moduleName", f"Enhed {ip}")
                try:
                    state = self.discovery.get_device_state(ip)
                    if state is None:
                        state_text = "Ukendt"
                        state_color = "orange"
                    else:
                        state_text = "Tændt" if state else "Slukket"
                        state_color = "green" if state else "red"
                except Exception as e:
                    state_text = "Ukendt"
                    state_color = "orange"
                    self.log(f"Fejl ved hentning af tilstand for {ip}: {e}")

                device_frame = ttk.Frame(room_frame)
                device_frame.pack(fill="x", pady=2, padx=10)

                name_label = ttk.Label(device_frame, text=f"{module_name} ({ip})")
                name_label.grid(row=0, column=0, sticky="w")

                status_label = ttk.Label(device_frame, text=f"Status: {state_text}", foreground=state_color)
                status_label.grid(row=0, column=1, sticky="w", padx=10)

                on_button = ttk.Button(device_frame, text="Tænd", command=lambda i=ip: self.on_toggle_device(i, True))
                on_button.grid(row=0, column=2, padx=5)

                off_button = ttk.Button(device_frame, text="Sluk", command=lambda i=ip: self.on_toggle_device(i, False))
                off_button.grid(row=0, column=3, padx=5)

                remove_button = ttk.Button(device_frame, text="Fjern", command=lambda i=ip: self.on_remove_device(i))
                remove_button.grid(row=0, column=4, padx=5)

        # Vis offline enheder
        offline_devices = [ip for ip in self.data["devices"] if ip not in [d["ip"] for d in devices]]
        if offline_devices:
            offline_frame = ttk.LabelFrame(self.control_frame, text="Offline enheder")
            offline_frame.pack(fill="x", padx=5, pady=5)

            for ip in offline_devices:
                module_name = self.data["devices"].get(ip, {}).get("moduleName", f"Enhed {ip}")
                offline_label = ttk.Label(offline_frame, text=f"{module_name} ({ip}) - Offline", foreground="gray")
                offline_label.pack(anchor='w', pady=2, padx=10)

    def update_status_periodically(self):
        stop_event = threading.Event()

        def update():
            while not stop_event.is_set():
                try:
                    devices = self.discovery.discover_wiz_devices(timeout=2)
                    rooms = self.discovery.sort_devices_by_room(devices)
                    for room_id, devices_in_room in rooms.items():
                        for device in devices_in_room:
                            ip = device["ip"]
                            try:
                                state = self.discovery.get_device_state(ip)
                                # Opdater status_label her, hvis nødvendigt
                                # Dette kræver, at vi har en reference til status_label for hver enhed
                                # For nu kan vi logge status
                                if state is not None:
                                    state_text = "Tændt" if state else "Slukket"
                                    state_color = "green" if state else "red"
                                    self.log(f"Opdateret status for {ip}: {state_text}")
                                else:
                                    self.log(f"Opdateret status for {ip}: Ukendt")
                            except Exception as e:
                                self.log(f"Fejl ved opdatering af status for {ip}: {e}")
                    time.sleep(5)  # Opdater hvert 5. sekund
                except Exception as e:
                    self.log(f"Fejl under statusopdatering: {e}")
                    time.sleep(5)

        threading.Thread(target=update, daemon=True).start()
        return stop_event

    def on_rename_room(self, room_id):
        new_name = simpledialog.askstring("Omdøb rum", f"Indtast nyt navn for rum {room_id}:")
        if new_name:
            self.data["rooms"][room_id] = new_name
            save_data(self.data)
            self.log(f"Rum {room_id} omdøbt til {new_name}.")
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
