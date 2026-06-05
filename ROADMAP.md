# WiZ Control Companion Roadmap

This file tracks ideas for the Windows-focused companion experience. The GUI remains the setup surface, the CLI remains the automation API, and the companion should become the everyday quick-control layer.

## Near-Term CLI Improvements

- Add a CLI status command for saved devices.
  - Example: `py wiz_cli.py status device "Stue 1"`
  - Include current power state, online/offline result, and basic metadata.
- Consider status commands for rooms and groups.
  - Room/group output should summarize how many lights are on, off, offline, or unknown.
- Add machine-readable CLI output.
  - Example: `--json` for scripts, launchers, and future companion integrations.
- Keep CLI commands stable enough to behave like a local project API.

## Windows Companion App

- Build a small Windows tray companion as a separate entrypoint, likely `wiz_tray.py`.
- Show saved groups, rooms, and favorite shortcuts from a tray menu.
- Add quick actions:
  - All Off
  - Group On/Off
  - Room On/Off
  - Favorite scene or shortcut
- Use the existing data store and discovery/control code instead of duplicating logic.
- Keep the full GUI as the setup and editing surface.

## Windows Integration Ideas

- Generate Windows shortcuts for saved actions.
  - Useful for Start menu, desktop, and user-pinned taskbar workflows.
- Support optional auto-start with Windows for the tray companion.
- Add Windows notifications for success, failure, and unreachable lights.
- Explore global hotkeys for common actions.
  - Example: a hotkey for All Off.
- Consider a small always-on-top floating control panel for favorite groups.

## Widgets And Taskbar Research

- Treat real Windows 11 Widgets as a later option, not the first implementation.
- A true Windows Widget likely requires packaging as a supported widget provider.
- Direct custom controls inside the Windows taskbar are limited, so tray, shortcuts, and pinned apps are more practical first.
- Revisit a packaged app only after the CLI and tray companion are stable.

## UX Ideas

- Add favorites so the companion does not show every room and device all the time.
- Add a compact "command palette" window for keyboard-driven control.
- Show last-used actions near the top of the companion menu.
- Add a simple health view:
  - Online lights
  - Offline lights
  - Last discovery time
  - Last command result

## Open Questions

- Should favorites be stored as a new top-level section in `wiz_data.json`?
- Should the tray companion call `wiz_cli.py`, or should it import the shared Python modules directly?
- Should status polling be passive/on-demand, or should the companion keep a small live cache?
- Should Windows shortcut generation live in the GUI, the CLI, or both?
