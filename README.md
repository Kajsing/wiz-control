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
- [Dependencies](#dependencies)
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

- **Python 3.6 or newer**: Ensure Python is installed on your system. You can download it from [python.org](https://www.python.org/downloads/).

### Clone the Repository

```bash
git clone https://github.com/yourusername/wiz-smart-bulb-manager.git
cd wiz-smart-bulb-manager
```

### Set Up a Virtual Environment (Optional but Recommended)

Creating a virtual environment helps manage dependencies and keep your project isolated.

```bash
python -m venv venv
```

Activate the virtual environment:

- **On Windows:**

  ```bash
  venv\Scripts\activate
  ```

- **On macOS and Linux:**

  ```bash
  source venv/bin/activate
  ```

### Install Dependencies

Install the required Python packages using `pip`:

```bash
pip install -r requirements.txt
```

If you don't have a `requirements.txt` file, you can create one with the following content:

```txt
# requirements.txt
```

**Note:** `tkinter` is usually included with Python on most systems. If it's not installed, follow the instructions below:

- **On Debian/Ubuntu:**

  ```bash
  sudo apt-get install python3-tk
  ```

- **On macOS:**

  `tkinter` is included in the standard Python installation.

- **On Windows:**

  `tkinter` is included in the standard Python installation.

## Usage

### Running the Application

To start the WiZ Smart Bulb Manager, navigate to the project directory and run:

```bash
python wiz_gui.py
```

### Using the Application

1. **Discover Devices**: Click the "Discover Devices" button to scan your local network for WiZ smart bulbs.
2. **View Devices**: Discovered devices will be listed, organized by rooms.
3. **Control Devices**:
   - **Individual Control**: Use the "Turn On" and "Turn Off" buttons next to each device to control them individually.
   - **Room Control**: Use the "Turn All On" and "Turn All Off" buttons in the room header to control all devices within that room simultaneously.
4. **Manage Rooms**:
   - **Rename Room**: Click the "Rename Room" button to assign a custom name to a room.
5. **Remove Devices**: Click the "Remove" button next to a device to remove it from the manager.
6. **Monitor Logs**: The log section displays real-time actions and device statuses.

## Configuration

### Data File

The application uses a `wiz_data.json` file to store persistent data such as room names and device information. This file is automatically created and managed by the application.

- **Location**: The `wiz_data.json` file is located in the same directory as the Python scripts.
- **Structure**:

  ```json
  {
      "rooms": {
          "1": "Living Room",
          "2": "Bedroom"
      },
      "devices": {
          "192.168.87.10": {
              "ip": "192.168.87.10",
              "moduleName": "Bulb A",
              "info": { ... }
          },
          "192.168.87.11": {
              "ip": "192.168.87.11",
              "moduleName": "Bulb B",
              "info": { ... }
          }
      }
  }
  ```

## Dependencies

The application primarily uses Python's standard libraries:

- `tkinter`: For the graphical user interface.
- `socket`: For network communication.
- `json`: For handling JSON data.
- `threading`: For managing background tasks.
- `logging`: For logging actions and errors.

### Optional Dependencies

- **Logging**: Enhanced logging for better debugging and monitoring.

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

Please ensure your code follows the existing style and includes appropriate documentation.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact

For questions or support, open an issue on the GitHub repository or contact [your email](mailto:ckajsing@gmail.com).

