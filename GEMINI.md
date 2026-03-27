## Project Memories
A modern UDP tool with Fluent UI, supporting broadcast sending (Hz) and high-precision receiving.

### Commit Update: 2026-03-26 15:45:00
- **Author**: Gemini CLI
- **Changes**: 
    - Implemented persistent configuration (`config.json`) for font sizes and filters.
    - Upgraded log view to a structured `TableWidget` with column formatting.
    - Added JSON format toggle (pretty-print/compact) for Message Payload.
    - Optimized UI layout: combined receiver settings into a single row, fixed button text truncation.
    - Enhanced error handling for UDP port binding failures.
    - Fixed dependencies in `requirements.txt`.
### Commit Update: 2026-03-26 11:03:21
- **Commit**: c979405
- **Author**: Zed Liu
- **Message**: feat: enhance UDP tool with persistent config, TableWidget logs, and JSON formatting

### Commit Update: 2026-03-26 16:24:31
- **Commit**: 6915bbd
- **Author**: Zed Liu
- **Message**: feat: upgrade protocol library with SQLite, multi-field editing, and layout fixes

### Commit Update: 2026-03-26 16:35:32
- **Commit**: a3430ac
- **Author**: Zed Liu
- **Message**: ci: add GitHub Actions workflow for Windows EXE and Linux DEB packaging

### Commit Update: 2026-03-26 17:00:00
- **Author**: Claude Opus 4.6
- **Changes**:
    - Update build workflow: trigger on `build-release` branch only
    - Auto-increment version from latest tag (patch+1)
    - Auto-create git tag and GitHub Release after successful builds
    - Include version number in artifact filenames

### Commit Update: 2026-03-26 17:18:34
- **Commit**: 70a2a39
- **Author**: Zed Liu
- **Message**: feat: update build workflow for automatic releases

