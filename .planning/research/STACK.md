# Stack Research

**Domain:** Unified preview/exec mode for Python desktop gesture detection app
**Researched:** 2026-03-30
**Confidence:** HIGH

## Verdict: No New Dependencies

The v3.2 unified preview & exec mode milestone requires **zero new packages**. Every capability needed -- subprocess restart, argparse mode switching, debug log levels, console window management -- is achievable with Python stdlib modules already imported or trivially available. The existing stack (mediapipe, opencv-python, pynput, pystray, Pillow, PyYAML) is unchanged.

**Rationale:** This milestone is a control-flow refactor, not a capability expansion. The codebase already has `--preview`, `--debug`, `logging_setup.py` with `RotatingFileHandler`, `hide_console_window()` via ctypes, and a clean `TrayApp` class. The work is rewiring how these existing pieces connect, not adding new ones.

## Recommended Stack

### Core Technologies

No additions. Existing stack unchanged for v3.2.

| Technology | Version | Purpose | v3.2 Status |
|------------|---------|---------|-------------|
| mediapipe | >=0.10.33 | Hand landmark detection | Unchanged |
| opencv-python | >=4.8.0 | Camera capture, preview window | Unchanged -- `cv2.imshow`/`cv2.destroyAllWindows` already used |
| pynput | >=1.7.6 | Keystroke simulation | Unchanged |
| PyYAML | >=6.0 | Config loading/hot-reload | Unchanged |
| pystray | >=0.19.5 | System tray app with menu | Menu gets new "View Camera" item -- no API additions needed |
| Pillow | >=10.0 | Tray icon rendering | Unchanged |

### Python Stdlib Used for New Features

| Module | Purpose | Why Sufficient |
|--------|---------|----------------|
| `subprocess.Popen` | Tray "View Camera" spawns a new process with camera flag | Already in stdlib. `Popen([sys.executable, ...])` or `Popen([sys.argv[0], ...])` for frozen exe. Non-blocking, returns immediately. No need for `multiprocessing` since we want an independent process that survives tray restart. |
| `sys.executable` / `sys.argv[0]` | Determine correct executable path for re-launch | `sys.argv[0]` works for both `python -m gesture_keys` and frozen PyInstaller exe. `getattr(sys, 'frozen', False)` check already exists in `__main__.py` line 178. |
| `logging.StreamHandler` | Console output for dev mode / --debug | Already used in `run_preview_mode()` line 87-89. Needs to be wired into unified mode. |
| `logging.getLogger().setLevel()` | Toggle DEBUG vs INFO based on --debug flag | Already partially implemented. `setup_logging()` sets root to DEBUG, console handler filters. |
| `argparse` | Mode flags (`--debug`, `--camera`, removing `--preview`) | Already used in `parse_args()`. Just argument changes. |
| `ctypes.windll` | Show/hide console window for tray vs dev mode | Already implemented in `hide_console_window()` at line 41-45. |
| `os.getpid` / `signal` | Optional: clean shutdown of camera subprocess from tray | Stdlib. `Popen.terminate()` is sufficient for the spawned camera process. |

### Supporting Libraries

No new supporting libraries needed.

| Library | Version | Purpose | v3.2 Notes |
|---------|---------|---------|------------|
| pytest | >=8.0 | Testing mode switching, subprocess launch logic | Existing. May need `unittest.mock.patch` for subprocess tests. |
| PyInstaller | >=6.0 | Bundling (dev dependency) | Existing. `GestureKeys.spec` already configured with `console=False`. "View Camera" subprocess must account for frozen exe path. |

## What Changes (Control Flow, Not Dependencies)

### Feature 1: Unified Dev Mode (camera always on)

**Current:** `--preview` flag gates camera display. Without it, tray mode runs headless.
**Target:** `python -m gesture_keys` (no flags) shows camera + console logging. Tray/exe mode remains headless.

**Stdlib used:** `argparse` (already imported), `sys.frozen` check (already exists).

**Approach:** Detect frozen vs development context. When not frozen, default to showing camera. When frozen (PyInstaller exe), default to tray mode. The `--preview` flag becomes unnecessary -- dev mode always previews.

| Detection Method | How | Already Exists |
|-----------------|-----|----------------|
| Frozen exe | `getattr(sys, 'frozen', False)` | Yes, `__main__.py` line 178 |
| Dev mode | `not frozen` | Inverse of above |

### Feature 2: Tray "View Camera" Restart

**Current:** No way to show camera from tray mode.
**Target:** Menu item spawns a subprocess showing the camera preview, optionally stopping/restarting the tray app.

**Stdlib used:** `subprocess.Popen`, `sys.argv[0]`, `sys.executable`.

**Key integration points with pystray:**

| Concern | Solution | Notes |
|---------|----------|-------|
| Adding menu item | `pystray.MenuItem("View Camera", self._on_view_camera)` | pystray supports dynamic menu items. Same pattern as existing "Edit Config". |
| Spawning camera process | `subprocess.Popen([exe_path, "--camera", "--config", self._config_path])` | Non-blocking. New process gets its own console/window. |
| Frozen exe path | `sys.argv[0]` when frozen, `[sys.executable, "-m", "gesture_keys"]` when dev | Same pattern as existing frozen detection in `__main__.py`. |
| Pipeline conflict (two processes reading same camera) | Must stop tray's pipeline before spawning camera process, or accept that OpenCV will fail on double-open | Most USB webcams support only one consumer. Tray must pause detection while camera subprocess runs. |
| Subprocess cleanup on tray quit | Store `Popen` reference, call `.terminate()` in `_on_quit()` | Prevents orphan camera window. |

**Critical design decision:** The tray's detection loop must **stop** while the camera subprocess is running (camera device is exclusive on most hardware). When the camera subprocess exits, the tray should resume detection. This is a `threading.Event` coordination problem using existing patterns from `TrayApp._active` and `TrayApp._shutdown`.

### Feature 3: --debug Verbose Logging

**Current:** `--debug` flag already exists in `parse_args()` (line 36-37). Console handler already switches between DEBUG and INFO based on it (line 86). File logging always writes both `preview.log` (INFO) and `debug.log` (DEBUG).
**Target:** Make `--debug` work consistently across all modes (dev, tray, camera subprocess).

**Stdlib used:** `logging` (already fully configured in `logging_setup.py`).

**What's actually needed:** Wire the `--debug` flag through to `setup_logging()` so it can optionally add a console handler at DEBUG level. Currently `setup_logging()` only creates file handlers. The console handler is manually added in `run_preview_mode()`. This should be unified.

| Current State | Target State |
|--------------|-------------|
| Console handler added ad-hoc in `run_preview_mode()` | `setup_logging(console=True, level=DEBUG)` parameter |
| `--debug` only affects preview mode console | `--debug` affects any mode with console output |
| Tray mode has no console output | Tray mode with `--debug` could log to console (if console visible) |

## Alternatives Considered

### Subprocess vs Multiprocessing for Camera Launch

| Approach | Recommendation | Why |
|----------|---------------|-----|
| `subprocess.Popen` | **Use this** | Independent process. Clean separation. Works identically for frozen exe and dev mode. No shared memory complexity. Process can outlive tray if needed. |
| `multiprocessing.Process` | Don't use | Shared memory, pickle serialization overhead. OpenCV windows must be in the process that creates them (no cross-process window handles). Adds complexity for zero benefit since we want full process isolation. |
| `os.execv` (replace current process) | Don't use | Destroys tray icon. User loses tray functionality while camera is open. |
| `threading.Thread` with camera loop | Don't use | OpenCV `imshow` must run on main thread (or the thread that created the window). pystray already owns the main thread. Threading leads to GIL contention and window management issues. |

### Console Window Management

| Approach | Recommendation | Why |
|----------|---------------|-----|
| `ctypes.windll.user32.ShowWindow` | **Use this** (already in codebase) | Direct Win32 API. Already proven in `hide_console_window()`. Can also show window with `SW_SHOW = 5`. |
| `win32gui` (pywin32) | Don't use | External dependency for something achievable with ctypes in 3 lines. |
| `pythonw.exe` vs `python.exe` | Awareness only | PyInstaller's `console=False` in spec already handles this for frozen builds. Dev mode uses `python.exe` which has a console. |

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `multiprocessing` | Camera subprocess needs full process isolation, not shared memory. `subprocess.Popen` is simpler and works for both frozen and dev. | `subprocess.Popen` |
| `pywin32` / `win32gui` | Only need `ShowWindow` and `GetConsoleWindow` -- already done with `ctypes.windll` in 5 lines. | `ctypes.windll` (existing) |
| `click` (CLI framework) | 3 flags (`--debug`, `--camera`, `--config`). argparse handles this in 15 lines. Click adds a dependency for no benefit. | `argparse` (existing) |
| `rich` / `colorama` (colored logging) | Nice-to-have but adds dependency for cosmetic benefit. Plain `logging.StreamHandler` is sufficient. | `logging.StreamHandler` (existing) |
| `watchdog` (file watching for subprocess exit) | `Popen.poll()` in a timer or thread is sufficient to detect camera subprocess exit. | `Popen.poll()` or `Popen.wait()` in thread |
| `psutil` (process management) | Only need to terminate one known subprocess. `Popen.terminate()` handles this. | `subprocess.Popen.terminate()` |

## Version Compatibility

No new version constraints. Existing `requirements.txt` is unchanged.

| Concern | Status | Notes |
|---------|--------|-------|
| `subprocess.Popen` | Python 3.7+ | Available in all supported Python versions |
| `pystray` menu items | >=0.19.5 | Dynamic menu items supported. Already using lambda for "Active"/"Inactive" text. |
| PyInstaller frozen detection | Works | `sys.frozen` and `sys.argv[0]` patterns already validated in codebase |
| OpenCV single-camera exclusivity | Hardware dependent | Most USB cameras allow only one reader. Design must account for this. |

## Installation

```bash
# No changes to installation:
pip install -r requirements.txt

# requirements.txt remains unchanged:
# mediapipe>=0.10.33
# opencv-python>=4.8.0
# PyYAML>=6.0
# pytest>=8.0
# pynput>=1.7.6
# pystray>=0.19.5
# Pillow>=10.0
```

## Sources

- Codebase analysis of `__main__.py` (188 lines, argparse + mode switching), `tray.py` (141 lines, pystray menu + detection thread), `logging_setup.py` (73 lines, RotatingFileHandler setup), `GestureKeys.spec` (PyInstaller config with `console=False`) -- PRIMARY source, HIGH confidence
- Python `subprocess` stdlib docs -- `Popen` for non-blocking process spawn, HIGH confidence
- Python `logging` stdlib docs -- `StreamHandler`, `setLevel()`, handler management, HIGH confidence
- pystray existing usage in codebase -- `MenuItem` with lambdas, `Menu.SEPARATOR`, `icon.run(setup=)` pattern, HIGH confidence

---
*Stack research for: gesture-keys v3.2 unified preview & exec mode*
*Researched: 2026-03-30*
