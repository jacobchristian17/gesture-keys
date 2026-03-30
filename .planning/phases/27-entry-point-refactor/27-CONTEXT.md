# Phase 27: Entry Point Refactor - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Refactor `__main__.py` so `python -m gesture_keys` shows camera preview with INFO logging by default (no flags needed), frozen exe enters tray mode silently, and a clean `main()` routes between three modes: dev-camera, tray-headless, and camera-subprocess.

</domain>

<decisions>
## Implementation Decisions

### Default Mode Routing
- `python -m gesture_keys` (no flags) opens camera preview with INFO-level console logging
- Frozen exe (`getattr(sys, 'frozen', False)`) enters tray mode automatically
- `--preview` flag kept as deprecated no-op with printed warning (removal is ENTRY-03, future scope)
- `--tray` flag added for forcing tray mode from Python without freezing (useful for development/testing)

### Mode Function Structure
- Single `main()` with if/elif on frozen state + flags, calling `run_dev_mode()`, `run_tray_mode()`, or `run_camera_mode()`
- Rename `run_preview_mode` → `run_dev_mode` to match new semantics (always camera + logging)
- `run_camera_mode` is same as `run_dev_mode` but skips the startup banner (it's a subprocess of tray)
- `--view-camera` flag uses `help=argparse.SUPPRESS` — internal for Phase 28 tray subprocess usage

### Logging & Banner Behavior
- Dev mode always shows startup banner via `print_banner()`
- Camera mode (tray subprocess) shows INFO-level console logging — user opened camera to see activity
- `--debug` upgrades console from INFO to DEBUG level (same as current behavior)

### Claude's Discretion
- Internal implementation details of mode routing logic
- Test structure and organization

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `__main__.py`: `parse_args()`, `run_tray_mode()`, `run_preview_mode()`, `print_banner()`, `hide_console_window()`
- `logging_setup.py`: `setup_logging(console, debug)` — already parameterized from Phase 26
- `Pipeline` class for gesture processing loop
- `preview.py`: `draw_hand_landmarks()`, `render_preview()` for camera overlay

### Established Patterns
- `getattr(sys, 'frozen', False)` for PyInstaller detection (used in `__main__.py` and `detector.py`)
- Config path resolution relative to exe directory when frozen
- Camera loop with `cv2.waitKey(1)` and window property check for close detection
- Function-attribute `_was_moving` for motion state tracking in preview loop

### Integration Points
- `main()` is the entry point called by `__main__` block and by PyInstaller exe
- `TrayApp` imported lazily in `run_tray_mode()` (avoids pystray import in dev mode)
- Phase 28 will use `--view-camera` to spawn camera subprocess from tray

</code_context>

<specifics>
## Specific Ideas

No specific requirements — standard approaches accepted for all areas.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
