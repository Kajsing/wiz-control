# WiZ Smart Bulb Manager


## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Clone the Repository](#clone-the-repository)
  - [Set Up a Virtual Environment (Optional but Recommended)](#set-up-a-virtual-environment-optional-but-recommended)
  - [Install Dependencies](#install-dependencies)
- [Usage](#usage)
  - [Running the Application](#running-the-application)
  - [Command Line Control](#command-line-control)
  - [Using the Application](#using-the-application)
- [Configuration](#configuration)
  - [Data File](#data-file)
- [Architecture Notes](#architecture-notes)
- [Contributing](#contributing)
- [Contact](#contact)

## Introduction

WiZ Smart Bulb Manager is a Python-based graphical user interface (GUI) application that allows you to discover, control, and manage your WiZ smart bulbs on your local network. With this tool, you can easily turn your lights on or off, organize devices by rooms, rename rooms, remove devices, and monitor the status of each bulb in real-time.

## Features

- **Device Discovery**: Automatically discover WiZ smart bulbs on your local network.
- **Room Management**: Organize devices by rooms and rename rooms as needed.
- **Device Control**: Turn individual devices on or off or control all devices within a room simultaneously.
- **Advanced Color & Brightness**: Adjust brightness, color temperature, and RGB values, or use quick presets stored per bulb.
- **Room Scenes**: Apply any of the 32 built-in WiZ scenes to an entire room and fine-tune the playback speed.
- **Remove Devices**: Easily remove devices from the manager.
- **Real-time Logging**: Monitor actions and device statuses in real-time, with a toggle to hide the log when you need more screen space.
- **Offline Device Detection**: Identify and display devices that are offline.
- **Persistent Data**: Save device, room, and per-light preference data for future sessions.

## Installation

### Prerequisites

- **Python 3.10+** with Tkinter support. Most desktop Python installers ship with Tkinter, but some Linux distributions split it into a separate package (see below).
- **Broadcast access** on your local network. The discovery protocol uses UDP broadcasts on port `38899`.

### Clone the Repository

```bash
git clone https://github.com/Kajsing/wiz-control.git
cd wiz-control
```

### Set Up a Virtual Environment (Optional but Recommended)

Creating a virtual environment helps manage dependencies and keep your project isolated.

```bash
py -m venv .venv
```

Activate the virtual environment:

- **On Windows:**

  ```bash
  .venv\Scripts\activate
  ```

- **On macOS and Linux:**

  ```bash
  source .venv/bin/activate
  ```

### Install Dependencies

Install optional Windows companion dependencies with:

```bash
pip install -r requirements.txt
```

**Tkinter note:** If `tkinter` is missing when you launch the app, install the platform package:

- **Debian/Ubuntu:** `sudo apt-get install python3-tk`
- **Fedora:** `sudo dnf install python3-tkinter`
- **Windows/macOS:** bundled with the official Python installers.

## Usage

### Running the Application

To start the WiZ Smart Bulb Manager, navigate to the project directory and run:

```bash
py wiz_gui.py
```

### Command Line Control

Use `wiz_cli.py` to control devices already discovered and saved by the GUI:

```bash
py wiz_cli.py list devices
py wiz_cli.py list rooms
py wiz_cli.py list shortcuts
py wiz_cli.py list groups
py wiz_cli.py list favorites
py wiz_cli.py discover
py wiz_cli.py discover --timeout 15
py wiz_cli.py status device "Desk Lamp"
py wiz_cli.py --json status room "Living Room"
py wiz_cli.py device "192.168.87.10" on
py wiz_cli.py room "Living Room" off
py wiz_cli.py save-group "Group 1" --room "Living Room" --device "Desk Lamp"
py wiz_cli.py group "Group 1" on
py wiz_cli.py delete-group "Group 1"
py wiz_cli.py save-favorite "Movie Off" group "Movie Lights" off
py wiz_cli.py favorite "Movie Off"
py wiz_cli.py export-shortcut favorite "Movie Off" --output-dir "$env:USERPROFILE\Desktop"
py wiz_cli.py shortcut "Desk Lamp On"
```

`discover` listens for up to 10 seconds by default and prints progress while it
waits for bulb responses. Use `--timeout` after `discover` to choose a different
listen window.

Shortcuts are saved from the GUI beside each room and device. Enter a base name,
then select **Save On** or **Save Off**; the app stores names such as
`Desk Lamp On` and `Desk Lamp Off`. The CLI and GUI read the same
`wiz_data.json` file, so either entry point can discover bulbs for the other.

Groups combine whole rooms and individual devices. A group can turn on every
light in one room plus a single lamp from another room, and duplicate devices
are only controlled once.

Favorites are curated quick actions intended for the Windows companion and
shortcut exports. They can target a device, room, or group and store an on/off
state. Use `--json` before the command when another tool needs machine-readable
output.

For a Windows taskbar shortcut, set the shortcut target to a command like:

```powershell
py "C:\project\wiz-control\wiz_cli.py" shortcut "Desk Lamp On"
```

Or generate a `.lnk` file from a saved favorite or shortcut:

```powershell
py wiz_cli.py export-shortcut favorite "Movie Off" --output-dir "$env:USERPROFILE\Desktop"
```

### Windows Companion

Run the tray companion after installing `requirements.txt`:

```bash
py wiz_tray.py
```

The companion shows quick menu actions for **All Off**, favorites, groups, and
rooms. The full GUI remains the setup surface for discovery and editing.

### Using the Application

1. **Discover Devices**: Click **Discover Devices** in the GUI, or run `py wiz_cli.py discover`, to broadcast a `getSystemConfig` request and catalog reachable bulbs.
2. **View Devices**: The control panel groups devices by reported room ID and shows the last known power state.
3. **Control Devices**:
   - **Individual Control**: Use **Turn On/Turn Off** next to each entry to toggle that bulb.
   - **Room Control**: Use **Turn All On/Turn All Off** in the room header to broadcast a state change to every bulb in the group.
4. **Edit Rooms**: Replace the text in the room header, click **Save Name**, and the label will persist between sessions.
5. **Adjust Light Output**:
   - Click **Show Color Controls** on a device to reveal brightness, color temperature, and RGB sliders.
   - Use **Apply White** for tunable-white devices or **Apply Color** for RGB output. Preset buttons auto-fill the sliders and send the command.
6. **Apply Room Scenes**: Select a scene from the dropdown in the room header, optionally adjust the speed, and click **Apply Scene** to broadcast the preset to every light in that room.
7. **Build Groups**: Use the **Groups** panel to combine whole rooms and individual devices for CLI control.
8. **Save CLI Shortcuts**: Enter a base shortcut name beside a room or device, then select **Save On** or **Save Off**.
9. **Remove Devices**: Select **Remove** to clear an IP from the cache until the next discovery run.
10. **Monitor Logs**: Click **Show Logs** / **Hide Logs** in the toolbar to toggle the status console (handy on smaller displays).

## Configuration

### Data File

The application writes a `wiz_data.json` file alongside the scripts to remember room labels, device metadata, and the raw discovery payloads (`info`). A typical structure looks like:

```json
{
  "rooms": {
    "1": "Living Room",
    "2": "Bedroom"
  },
  "devices": {
    "192.168.87.10": {
      "ip": "192.168.87.10",
      "moduleName": "Ceiling Lamp",
      "roomId": "1",
      "info": { "result": { "moduleName": "Ceiling Lamp", "roomId": 1, "state": true } },
      "preferences": {
        "dimming": 75,
        "temperature": 3200,
        "r": 0,
        "g": 0,
        "b": 0
      }
    }
  },
  "room_settings": {
    "1": {
      "sceneId": 5,
      "sceneSpeed": 120
    }
  },
  "shortcuts": {
    "Desk Lamp On": {
      "label": "Desk Lamp On",
      "target_type": "device",
      "target": "192.168.87.10",
      "action": "state",
      "state": true
    }
  },
  "groups": {
    "Group 1": {
      "label": "Group 1",
      "rooms": ["1"],
      "devices": ["192.168.87.10"]
    }
  },
  "favorites": {
    "Movie Off": {
      "label": "Movie Off",
      "target_type": "group",
      "target": "Group 1",
      "action": "state",
      "state": false
    }
  }
}
```

You can safely delete this file to reset the cache. The application will regenerate it on the next launch (room names, preferred light levels, and scene choices will revert to defaults).

## Architecture Notes

- **GUI (`wiz_gui.py`)** manages Tkinter widgets, cached discovery data, and background polling threads. Device state changes update an in-memory cache before triggering lightweight UI refreshes.
- **Discovery (`wiz_discovery.py`)** encapsulates UDP broadcast discovery, per-device command calls, and room grouping helpers. Network access is deliberately serialized in the status poller to avoid saturating the WiZ protocol.
- **CLI (`wiz_cli.py`)** exposes saved devices, rooms, groups, favorites, status reads, JSON output, and Windows shortcut exports for scripts and shell aliases.
- **Companion (`wiz_tray.py`)** provides an optional Windows tray menu for daily quick actions.
- **Windows Shortcuts (`wiz_windows_shortcuts.py`)** creates `.lnk` files that call back into the CLI.
- **Data Store (`wiz_store.py`)** centralizes `wiz_data.json` loading, normalization, and atomic writes for both GUI and CLI entry points.
- **Contributor Guide**: See [`AGENTS.md`](AGENTS.md) for coding standards, testing guidance, and pull-request expectations tailored to this project.

## Contributing

Contributions are welcome! To contribute to WiZ Smart Bulb Manager:

1. **Fork the Repository**

2. **Create a Feature Branch**

   ```bash
   git checkout -b feature/YourFeature
   ```

3. **Commit Your Changes**

   ```bash
   git commit -m "Add a new feature"
   ```

4. **Push to the Branch**

   ```bash
   git push origin feature/YourFeature
   ```

5. **Open a Pull Request**

Please ensure your code follows the existing style and includes appropriate documentation. Consult [`AGENTS.md`](AGENTS.md) for detailed contributor guidelines.

## Contact

For questions or support, open an issue on the GitHub repository.
