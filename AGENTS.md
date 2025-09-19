# Repository Guidelines

## Project Structure & Module Organization
The root module `wiz_gui.py` hosts the Tkinter interface, orchestrating discovery and persistence. Networking logic lives in `wiz_discovery.py`, wrapping UDP broadcast, room grouping, and state polling. `wiz_data.json` is generated at runtime; treat it as cache data and keep fixtures separate. Future helpers belong under `utils/` and GUI assets in `assets/`, referenced from `wiz_gui.py`.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` – set up the local environment; pin dependencies in `requirements.txt`.
- `pip install -r requirements.txt` – install GUI and networking dependencies.
- `python wiz_gui.py` – launch the manager; document new CLI flags in the README if introduced.
- `python -m pytest` or `python -m unittest discover tests` – run automated checks; keep suites sandboxed from live broadcasts by default.

## Coding Style & Naming Conventions
Use 4-space indentation, snake_case functions, and UpperCamelCase classes. Keep constants uppercased (`BROADCAST_ADDRESS`) near related logic. Add type hints when touching network helpers and align docstrings with the current tone. GUI strings are Danish—extend that translation consistently or gate alternates with a toggle.

## Testing Guidelines
Prioritize unit coverage of `wiz_discovery.py`, mocking sockets to avoid traffic. Place live-bulb integration tests in `tests/integration/` and guard them with `WIZ_LIVE_TEST=1 python -m pytest`. Name files `test_<module>.py`; store fixtures in `tests/fixtures/`. Add log assertions or state checks so regressions surface before manual QA.

## Commit & Pull Request Guidelines
History favors concise messages (`o1-mini readme generated`, `version 1`); continue with single-line imperatives or scoped prefixes (`gui:`). Each pull request should state motivation, summarize impact, list verification steps, and attach GUI screenshots or recordings. Link issues and flag networking assumptions or firewall needs.

## Network & Configuration Notes
Default broadcast settings (`192.168.87.255:38899`) match a typical WiZ subnet; override via constructor args when testing elsewhere and note changes in PRs. Never commit personal addresses or credentials. Add new configs under `config/` and extend `.gitignore` for developer-specific secrets.
