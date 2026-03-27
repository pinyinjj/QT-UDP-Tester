# Project Memory

## Project Overview
- **Type**: Desktop Application (UDP Testing Tool)
- **Stack**: Python, PyQt5, QFluentWidgets, SQLite
- **Platform**: Windows (.exe), Linux (.deb)

## Key Files
- `udp_tool_gui.py` - Main application entry point
- `.venv/` - Python virtual environment
- `requirements.txt` - Python dependencies
- `.github/workflows/build.yml` - CI/CD workflow
- `GEMINI.md` - Project changelog/memory

## Data Storage
- Config: `~/.commstool/config.json`
- Database: `~/.commstool/protocols.db`

## Build/Release Process
- Push to `build-release` branch triggers GitHub Actions
- Workflow auto-increments version from latest tag (patch+1)
- Creates git tag and GitHub Release automatically
- Fixed: Corrected release action input from `tag` to `tag_name` and fixed `VERSION_NUMBER` formatting.
- Artifacts: `QT-UDP-Tester-{version}-Windows.exe`, `QT-UDP-Tester-{version}-Linux.deb`
