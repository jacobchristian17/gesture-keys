# Phase 3: System Tray and Background Operation - Research

**Researched:** 2026-03-21
**Domain:** Windows system tray integration, background process management, Python GUI-less operation
**Confidence:** HIGH

## Summary

Phase 3 wraps the existing gesture detection pipeline (Phases 1-2) into a Windows system tray application that runs invisibly in the background. The current `__main__.py` runs a blocking `while True` loop with optional `--preview` mode. The tray integration must run `pystray` on the main thread (blocking `icon.run()`) while the detection loop runs on a worker thread. The active/inactive toggle must start and stop the camera and detection pipeline cleanly.

The standard library for Python system tray icons is **pystray** (v0.19.5), which requires **Pillow** for icon image creation. pystray's `Icon.run()` is blocking and takes a `setup` callback where the detection thread launches. Menu items support dynamic state via callables, enabling the active/inactive toggle. For opening config in the default editor, `os.startfile()` is the Windows-native solution. For hiding the console window, the app should be launched via `pythonw.exe` or with a `.pyw` entry point.

**Primary recommendation:** Use pystray with Pillow for the tray icon, run detection on a daemon thread started from the `setup` callback, use `threading.Event` for active/inactive signaling, and `os.startfile` for config editing.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TRAY-01 | Run as Windows system tray app with no camera preview by default | pystray `Icon.run()` on main thread; detection on worker thread; `pythonw.exe` or ctypes console hide for no-console launch |
| TRAY-02 | Active/inactive toggle in tray menu | pystray `MenuItem` with `checked` callable + `threading.Event` to pause/resume camera and detection |
| TRAY-03 | Edit Config option opens config.yaml in default editor | `os.startfile(config_path)` -- Windows-native, opens in associated YAML/text editor |
| TRAY-04 | Quit option stops camera and exits | `icon.stop()` from menu callback sets shutdown flag; worker thread joins; camera.stop() + detector.close() cleanup |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pystray | 0.19.5 | System tray icon and menu | Only mature Python system tray library; cross-platform; well-documented |
| Pillow | >=10.0 | Icon image creation for pystray | Required by pystray for icon images; industry standard imaging library |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| os.startfile | stdlib | Open config.yaml in default editor | Windows-only, zero dependencies, perfect for TRAY-03 |
| threading.Event | stdlib | Active/inactive signaling between tray and detection thread | Thread-safe flag for pause/resume |
| ctypes | stdlib | Hide console window on Windows | Alternative to pythonw.exe for console-less operation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pystray | wxPython system tray | Heavy dependency (full GUI framework) for one tray icon |
| pystray | infi.systray | Windows-only, less maintained, fewer features |
| Pillow icon generation | .ico file on disk | Pillow is already a pystray dependency; generated icon avoids asset management |
| os.startfile | subprocess + notepad | os.startfile respects user's default editor; subprocess hardcodes notepad |

**Installation:**
```bash
pip install pystray Pillow
```

Add to requirements.txt:
```
pystray>=0.19.5
Pillow>=10.0
```

## Architecture Patterns

### Recommended Project Structure
```
gesture_keys/
    __main__.py      # CLI entry point (existing, add --tray default behavior)
    tray.py          # NEW: TrayApp class - pystray setup, menu, thread management
    config.py        # Existing: load_config, ConfigWatcher
    detector.py      # Existing: CameraCapture, HandDetector
    ...              # Existing modules unchanged
```

### Pattern 1: Main Thread = Tray, Worker Thread = Detection
**What:** pystray `Icon.run()` blocks the main thread. The detection loop (currently in `main()`) runs on a daemon thread spawned from the `setup` callback.
**When to use:** Always -- pystray requires main thread on macOS, and it is the cleanest pattern on Windows too.
**Example:**
```python
# Source: pystray official docs (https://pystray.readthedocs.io/en/latest/usage.html)
import pystray
from PIL import Image, ImageDraw
import threading

class TrayApp:
    def __init__(self, config_path: str):
        self._config_path = config_path
        self._active = threading.Event()
        self._active.set()  # Start active
        self._shutdown = threading.Event()
        self._icon = None
        self._detection_thread = None

    def _create_icon_image(self) -> Image.Image:
        """Create a simple 64x64 tray icon."""
        img = Image.new('RGB', (64, 64), 'black')
        draw = ImageDraw.Draw(img)
        # Draw a hand-like shape or simple indicator
        draw.ellipse([12, 12, 52, 52], fill='green')
        return img

    def _on_toggle(self, icon, item):
        """Toggle active/inactive state."""
        if self._active.is_set():
            self._active.clear()  # Pause detection
        else:
            self._active.set()  # Resume detection

    def _on_edit_config(self, icon, item):
        """Open config.yaml in default editor."""
        import os
        os.startfile(self._config_path)

    def _on_quit(self, icon, item):
        """Signal shutdown and stop the tray icon."""
        self._shutdown.set()
        self._active.set()  # Unblock if paused
        icon.stop()

    def _detection_loop(self):
        """Run the gesture detection pipeline (worker thread)."""
        # Initialize camera, detector, etc.
        # Loop until self._shutdown.is_set()
        # Check self._active.wait() to pause when inactive
        pass

    def run(self):
        """Start the tray app (blocks on main thread)."""
        menu = pystray.Menu(
            pystray.MenuItem(
                'Active',
                self._on_toggle,
                checked=lambda item: self._active.is_set(),
            ),
            pystray.MenuItem('Edit Config', self._on_edit_config),
            pystray.MenuItem('Quit', self._on_quit),
        )
        self._icon = pystray.Icon(
            'gesture-keys',
            icon=self._create_icon_image(),
            title='Gesture Keys',
            menu=menu,
        )
        self._icon.run(setup=lambda icon: self._start_detection())

    def _start_detection(self):
        """Called by pystray after icon is visible."""
        self._detection_thread = threading.Thread(
            target=self._detection_loop, daemon=True
        )
        self._detection_thread.start()
```

### Pattern 2: Active/Inactive with Camera Release
**What:** When toggling to inactive, stop the camera capture thread and release the device so the camera LED turns off. When toggling back to active, re-initialize the camera.
**When to use:** Required by TRAY-02 -- "camera LED turns off when inactive."
**Example:**
```python
def _detection_loop(self):
    while not self._shutdown.is_set():
        if not self._active.wait(timeout=0.5):
            continue  # Check shutdown while waiting

        # Start camera + detector
        camera = CameraCapture(config.camera_index).start()
        detector = HandDetector()

        while self._active.is_set() and not self._shutdown.is_set():
            ret, frame = camera.read()
            if not ret or frame is None:
                continue
            # ... detection pipeline ...

        # Inactive or shutting down: release resources
        camera.stop()
        detector.close()
```

### Pattern 3: Console Window Hiding
**What:** Hide the console window when running as tray app (no --preview flag).
**When to use:** TRAY-01 requires no console window by default.
**Example:**
```python
import sys
import ctypes

def hide_console():
    """Hide the console window on Windows."""
    if sys.platform == 'win32':
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0
```
**Alternative:** Launch with `pythonw.exe -m gesture_keys` or rename entry to `.pyw`. The ctypes approach is more flexible as it works from any launch method and can be conditional on `--preview` not being set.

### Anti-Patterns to Avoid
- **Running pystray on a worker thread:** While technically possible on Windows, it breaks macOS compatibility and goes against the library's design. Always run on main thread.
- **Using `time.sleep()` for active/inactive polling:** Use `threading.Event.wait(timeout=...)` instead -- it is immediately responsive to state changes.
- **Keeping camera open when inactive:** The camera LED stays on, violating TRAY-02. Always release the camera device when going inactive.
- **Blocking menu callbacks:** pystray menu callbacks run on the tray's thread. Long operations (like camera init) must happen on the worker thread, not in the callback.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| System tray icon | Win32 API shell notify icon calls | pystray | Win32 tray API is complex (NOTIFYICONDATA struct, window message handling) |
| Icon image | Raw bitmap bytes | Pillow Image.new() + ImageDraw | Pillow handles format conversion pystray expects |
| Open file in default app | subprocess.Popen(['notepad', path]) | os.startfile(path) | startfile respects user's default editor, not just notepad |
| Thread synchronization | Custom flag with lock | threading.Event | Event is built for exactly this pattern; wait() with timeout is efficient |

**Key insight:** The entire tray integration is a thin orchestration layer. All detection logic already exists -- this phase is purely about lifecycle management and a menu interface.

## Common Pitfalls

### Pitfall 1: Camera Not Released on Inactive Toggle
**What goes wrong:** Camera LED stays on when user clicks "Inactive" because `CameraCapture.stop()` is not called.
**Why it happens:** Developer pauses the detection loop but forgets to release the OpenCV VideoCapture.
**How to avoid:** The detection loop must call `camera.stop()` when `_active` is cleared, and re-create the CameraCapture when `_active` is set again.
**Warning signs:** Camera LED stays on after toggling to inactive.

### Pitfall 2: Deadlock on Quit
**What goes wrong:** App hangs when clicking Quit because the detection thread is blocked waiting for `_active` Event.
**Why it happens:** `_shutdown` is set but `_active` Event is cleared (paused state), so `_active.wait()` never returns.
**How to avoid:** When quitting, set `_active` Event too (to unblock the wait), then set `_shutdown`. Or use `_active.wait(timeout=0.5)` so the thread periodically checks `_shutdown`.
**Warning signs:** Process hangs on exit; must be killed via Task Manager.

### Pitfall 3: pystray Icon Not Visible
**What goes wrong:** Tray icon does not appear in the system tray area.
**Why it happens:** Icon image is None, wrong size, or pystray initialization fails silently.
**How to avoid:** Always create a valid Pillow Image (64x64 RGB minimum). Test icon creation separately.
**Warning signs:** No icon visible; no errors in console.

### Pitfall 4: Console Window Flashes on Startup
**What goes wrong:** A console window briefly appears then hides when using the ctypes approach.
**Why it happens:** Console is created by Windows when python.exe starts, then hidden after Python code runs.
**How to avoid:** Use `pythonw.exe` for a completely console-free launch. The ctypes approach is a fallback. Document both options.
**Warning signs:** Brief black window flash on double-click.

### Pitfall 5: pynput KeystrokeSender Thread Safety
**What goes wrong:** Keystroke sends fail or cause deadlocks when called from the detection worker thread.
**Why it happens:** pynput Controller should be fine from any thread on Windows, but creating multiple Controllers can cause issues.
**How to avoid:** Create KeystrokeSender once and pass it to the detection thread. Do not create new instances per-cycle.
**Warning signs:** Intermittent keystroke failures.

## Code Examples

### Creating the Tray Icon with Menu
```python
# Source: pystray docs (https://pystray.readthedocs.io/en/latest/usage.html)
import pystray
from PIL import Image, ImageDraw

def create_icon_image():
    """Create a 64x64 green circle on black background."""
    image = Image.new('RGB', (64, 64), 'black')
    draw = ImageDraw.Draw(image)
    draw.ellipse([8, 8, 56, 56], fill='#00cc66')
    return image

def build_menu(on_toggle, on_edit, on_quit, is_active):
    return pystray.Menu(
        pystray.MenuItem(
            lambda item: 'Active' if is_active() else 'Inactive',
            on_toggle,
            checked=lambda item: is_active(),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Edit Config', on_edit),
        pystray.MenuItem('Quit', on_quit),
    )
```

### Opening Config in Default Editor (Windows)
```python
# Source: Python stdlib docs
import os

def open_config(config_path: str):
    """Open config file in the system default text editor."""
    os.startfile(os.path.abspath(config_path))
```

### Hiding Console Window
```python
# Source: ctypes Windows API
import sys
import ctypes

def hide_console_window():
    """Hide the console window. Call early in main()."""
    if sys.platform == 'win32':
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
```

### Refactored Main for Tray vs Preview Mode
```python
def main():
    args = parse_args()
    if args.preview:
        run_preview_mode(args)  # Existing behavior
    else:
        run_tray_mode(args)     # New tray behavior (default)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| infi.systray | pystray | ~2018 | pystray is cross-platform, actively maintained |
| win32gui shell notify | pystray | ~2018 | No need for pywin32 dependency |
| .pyw file extension | pythonw.exe or ctypes hide | Current | Both work; ctypes is more flexible for conditional hiding |

**Deprecated/outdated:**
- `infi.systray`: Windows-only, sparse maintenance, use pystray instead
- Manual Win32 `Shell_NotifyIcon` via ctypes: Fragile, use pystray abstraction

## Open Questions

1. **Icon design**
   - What we know: pystray requires a Pillow Image. Simple shapes (circle, square) work fine at 64x64.
   - What's unclear: Whether to use a hand emoji/shape or just a colored circle.
   - Recommendation: Start with a simple green circle (active) -- v2 TRAY-05 adds color changes for state. Keep it minimal for v1.

2. **Logging when console is hidden**
   - What we know: With no console, print() and logger output goes nowhere.
   - What's unclear: Whether to add file logging in this phase.
   - Recommendation: KEY-06 (file logging) is v2. For now, accept that tray mode has no visible logging. Preview mode retains console output.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 8.0 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TRAY-01 | TrayApp creates pystray Icon and runs without preview | unit | `python -m pytest tests/test_tray.py::test_tray_creates_icon -x` | Wave 0 |
| TRAY-02 | Toggle callback flips active Event; detection loop respects it | unit | `python -m pytest tests/test_tray.py::test_toggle_active_inactive -x` | Wave 0 |
| TRAY-03 | Edit config calls os.startfile with config path | unit | `python -m pytest tests/test_tray.py::test_edit_config_opens_file -x` | Wave 0 |
| TRAY-04 | Quit sets shutdown event, stops icon, detection thread exits | unit | `python -m pytest tests/test_tray.py::test_quit_stops_cleanly -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_tray.py` -- covers TRAY-01 through TRAY-04 (mock pystray.Icon, mock os.startfile)
- [ ] `pystray` and `Pillow` added to requirements.txt

## Sources

### Primary (HIGH confidence)
- [pystray official docs](https://pystray.readthedocs.io/en/latest/usage.html) - Icon creation, menu API, threading model, setup callback
- [pystray PyPI](https://pypi.org/project/pystray/) - Version 0.19.5, dependencies, release date Sep 2023
- [Python stdlib os.startfile](https://docs.python.org/3/library/os.html#os.startfile) - Windows-only file opener
- [Python stdlib threading.Event](https://docs.python.org/3/library/threading.html#event-objects) - Thread synchronization primitive

### Secondary (MEDIUM confidence)
- [GeeksforGeeks pystray tutorial](https://www.geeksforgeeks.org/python/create-a-responsive-system-tray-icon-using-python-pystray/) - Verified patterns match official docs
- [Python Tutorial - Tkinter System Tray](https://www.pythontutorial.net/tkinter/tkinter-system-tray/) - Threading pattern confirmed
- [CopyProgramming - Hide Console](https://copyprogramming.com/howto/python-python-hide-console-window-code-example) - ctypes console hiding pattern

### Tertiary (LOW confidence)
- None -- all findings verified against official sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pystray is the only mature Python system tray library; Pillow is its required dependency
- Architecture: HIGH - Threading model (main=tray, worker=detection) is well-documented in pystray docs and matches existing codebase patterns
- Pitfalls: HIGH - Camera release, deadlock on quit, and console hiding are well-known issues with documented solutions

**Research date:** 2026-03-21
**Valid until:** 2026-04-21 (pystray stable, no breaking changes expected)
