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
  - [Using the Application](#using-the-application)
- [Configuration](#configuration)
  - [Data File](#data-file)
- [Architecture Notes](#architecture-notes)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Introduction

WiZ Smart Bulb Manager is a Python-based graphical user interface (GUI) application that allows you to discover, control, and manage your WiZ smart bulbs on your local network. With this tool, you can easily turn your lights on or off, organize devices by rooms, rename rooms, remove devices, and monitor the status of each bulb in real-time.

## Features

- **Device Discovery**: Automatically discover WiZ smart bulbs on your local network.
- **Room Management**: Organize devices by rooms and rename rooms as needed.
- **Device Control**: Turn individual devices on or off or control all devices within a room simultaneously.
- **Remove Devices**: Easily remove devices from the manager.
- **Real-time Logging**: Monitor actions and device statuses in real-time.
- **Offline Device Detection**: Identify and display devices that are offline.
- **Persistent Data**: Save device and room configurations for future sessions.

## Installation

### Prerequisites

- **Python 3.10+** with Tkinter support. Most desktop Python installers ship with Tkinter, but some Linux distributions split it into a separate package (see below).
- **Broadcast access** on your local network. The discovery protocol uses UDP broadcasts on port `38899`.

### Clone the Repository

```bash
git clone https://github.com/Kajsing/wiz-control.git
cd wiz-smart-bulb-manager
```

### Set Up a Virtual Environment (Optional but Recommended)

Creating a virtual environment helps manage dependencies and keep your project isolated.

```bash
python3 -m venv .venv
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

This project currently relies only on the Python standard library. If you maintain shared tooling for linting or testing, pin it in `requirements-dev.txt`.

**Tkinter note:** If `tkinter` is missing when you launch the app, install the platform package:

- **Debian/Ubuntu:** `sudo apt-get install python3-tk`
- **Fedora:** `sudo dnf install python3-tkinter`
- **Windows/macOS:** bundled with the official Python installers.

## Usage

### Running the Application

To start the WiZ Smart Bulb Manager, navigate to the project directory and run:

```bash
python3 wiz_gui.py
```

### Using the Application

1. **Discover Devices**: Click **Discover Devices** to broadcast a `getSystemConfig` request and catalog reachable bulbs.
2. **View Devices**: The control panel groups devices by reported room ID and shows the last known power state.
3. **Control Devices**:
   - **Individual Control**: Use **Turn On/Turn Off** next to each entry to toggle that bulb.
   - **Room Control**: Use **Turn All On/Turn All Off** in the room header to broadcast a state change to every bulb in the group.
4. **Manage Rooms**: Use **Rename Room** to assign a friendly name that is cached locally.
5. **Remove Devices**: Select **Remove** to clear an IP from the cache until the next discovery run.
6. **Monitor Logs**: The log area records discovery updates, command responses, and connectivity changes for quick troubleshooting.

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
      "info": { "result": { "moduleName": "Ceiling Lamp", "roomId": 1, "state": true } }
    }
  }
}
```

You can safely delete this file to reset the cache—the application will regenerate it on the next launch.

## Architecture Notes

- **GUI (`wiz_gui.py`)** manages Tkinter widgets, cached discovery data, and background polling threads. Device state changes update an in-memory cache before triggering lightweight UI refreshes.
- **Discovery (`wiz_discovery.py`)** encapsulates UDP broadcast discovery, per-device command calls, and room grouping helpers. Network access is deliberately serialized in the status poller to avoid saturating the WiZ protocol.
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

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact

For questions or support, open an issue on the GitHub repository or contact [your email](mailto:ckajsing@gmail.com).
