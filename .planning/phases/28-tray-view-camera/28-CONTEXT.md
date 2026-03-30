# Phase 28: Tray View Camera - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a "View Camera" menu item to the system tray that stops detection, spawns a camera preview subprocess via `--view-camera`, and resumes detection when the camera window closes.

</domain>

<decisions>
## Implementation Decisions

### Camera Subprocess Lifecycle
- Use `subprocess.Popen` with `sys.executable + ['-m', 'gesture_keys', '--view-camera']` (or exe path when frozen)
- Stop pipeline and release camera before spawning subprocess (avoids "camera in use" errors)
- Use `subprocess.Popen.wait()` in a background thread to detect camera window closed, then restart detection
- Disable "View Camera" menu item while camera window is open (prevents double-click; aligns with TRAY-03)

### Stuck Key Prevention
- Rely on `pipeline.stop()` for key release in both tray and camera modes (existing v2.0 stuck-key prevention)
- Camera mode's `finally` block in `run_camera_mode` already calls `pipeline.stop()` which handles cleanup

### Frozen Exe Compatibility
- Use `sys.executable + ['--view-camera']` for spawning — PyInstaller sets `sys.executable` to the exe path
- Use `CREATE_NO_WINDOW` flag on Windows subprocess to suppress console window (camera window is OpenCV, not console)
- Forward `args.config` path to camera subprocess so it uses the same config file

### Claude's Discretion
- Thread management details for camera process monitoring
- Menu state update mechanism (pystray menu refresh approach)
- Error handling for subprocess spawn failures

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tray.py`: `TrayApp` with `_build_menu()`, `_detection_loop()`, `_active` threading.Event, `_shutdown` threading.Event
- `__main__.py`: `run_camera_mode(args)` — camera subprocess entry point (added in Phase 27)
- `__main__.py`: `parse_args()` with `--view-camera` flag (hidden, added in Phase 27)
- `pipeline.py`: `Pipeline.stop()` with stuck-key prevention

### Established Patterns
- `threading.Event` for active/shutdown state control
- Detection loop uses outer (state check) + inner (processing) loop pattern
- `pipeline.stop()` in `finally` block for cleanup
- `pystray.MenuItem` with lambda for dynamic text/checked state
- `os.startfile()` for opening files (Edit Config pattern)

### Integration Points
- `_build_menu()` — add "View Camera" item between "Edit Config" and "Quit"
- `_detection_loop()` — needs to be stoppable/restartable for camera handoff
- `--view-camera` flag in `parse_args()` routes to `run_camera_mode()`
- `sys.executable` resolves correctly for both Python and frozen exe

</code_context>

<specifics>
## Specific Ideas

No specific requirements — standard approaches accepted for all areas.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
