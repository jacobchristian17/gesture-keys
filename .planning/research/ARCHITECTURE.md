# Architecture Research: Unified Preview & Exec Mode

**Domain:** Desktop gesture-to-keyboard app (Python, Windows)
**Researched:** 2026-03-30
**Confidence:** HIGH (all recommendations based on reading actual codebase; no external dependencies needed)

## Current Architecture (Baseline)

```
                    __main__.py
                   /           \
          --preview?            else (default)
             |                     |
      run_preview_mode()      run_tray_mode()
             |                     |
      Pipeline + OpenCV       TrayApp (pystray)
      + console logging         |
                            _detection_loop()
                                |
                             Pipeline (headless)
```

**Key observations from the code:**

1. `run_preview_mode()` and `run_tray_mode()` are entirely separate entry paths
2. Both instantiate `Pipeline` identically -- the Pipeline has no awareness of display mode
3. Preview mode owns the OpenCV window loop (frame read + render + waitKey)
4. Tray mode runs Pipeline.process_frame() in a daemon thread, pystray owns the main thread
5. `Pipeline.last_frame` already exposes the frame for external rendering
6. Logging is configured differently: tray calls `setup_logging()` alone; preview adds a console handler on top

## Target Architecture (v3.2)

```
                    __main__.py
                   /           \
          frozen/exe?           else (dev mode)
             |                     |
      run_tray_mode()       run_dev_mode()
             |                     |
        TrayApp              Pipeline + OpenCV
        (pystray)            + console logging
             |               (always shows camera)
      _detection_loop()
             |
          Pipeline (headless)
             |
      "View Camera" menu item
             |
      _restart_with_camera()
             |
      subprocess: self-exe --view-camera
             |
      run_camera_mode()
             |
      Pipeline + OpenCV (no tray, closeable window)
```

### Mode Matrix

| Entry | Camera | Tray Icon | Console Log | File Log | How Entered |
|-------|--------|-----------|-------------|----------|-------------|
| Dev mode | YES (always) | NO | YES (INFO, or DEBUG with --debug) | YES | `python -m gesture_keys` |
| Tray mode | NO | YES | NO (console hidden) | YES | `GestureKeys.exe` (frozen) |
| View Camera | YES | NO (parent keeps tray) | YES (INFO) | YES | Tray menu "View Camera" |

## Integration Design: Component by Component

### 1. __main__.py Changes (MODIFY)

**Current:** Two modes selected by `--preview` flag.
**New:** Three modes selected by frozen state + flags.

```python
def parse_args():
    parser = argparse.ArgumentParser(...)
    # REMOVE: --preview flag
    parser.add_argument("--debug", action="store_true",
        help="Enable verbose DEBUG logging to console")
    parser.add_argument("--view-camera", action="store_true",
        help="Show camera window (used internally by tray 'View Camera')")
    parser.add_argument("--config", default="config.yaml", ...)
    return parser.parse_args()

def main():
    args = parse_args()
    # Resolve config path for frozen
    if not os.path.isabs(args.config) and getattr(sys, 'frozen', False):
        base = os.path.dirname(os.path.abspath(sys.argv[0]))
        args.config = os.path.join(base, args.config)

    if args.view_camera:
        # Spawned by tray "View Camera" -- camera window, no tray
        run_camera_mode(args)
    elif getattr(sys, 'frozen', False):
        # Exe launch -- tray mode, no camera
        run_tray_mode(args)
    else:
        # Dev launch -- always camera + console logging
        run_dev_mode(args)
```

**Three run functions:**

- `run_dev_mode(args)` -- Replaces `run_preview_mode`. Always shows camera. Console logging at INFO (or DEBUG with `--debug`). No tray icon. This IS the old `--preview` behavior, just made the default for dev.
- `run_tray_mode(args)` -- Largely unchanged. Adds "View Camera" menu item. Hides console.
- `run_camera_mode(args)` -- New. Shows camera window like dev mode but intended for the frozen exe. Console logging at INFO. No tray icon (parent process keeps the tray). Exits cleanly when window closed.

**Rationale:** `run_dev_mode` and `run_camera_mode` share 95% of their loop logic. Extract a shared `_camera_loop(pipeline, args, log_level)` helper that both call.

### 2. Shared Camera Loop (NEW helper in __main__.py)

```python
def _camera_loop(pipeline: Pipeline, log_level: int) -> None:
    """Run detection loop with OpenCV camera window.

    Used by both dev mode and tray "View Camera" mode.
    Pipeline must already be started.
    """
    prev_time = time.perf_counter()
    fps = 0.0
    try:
        while True:
            current_time = time.perf_counter()
            dt = current_time - prev_time
            if dt > 0:
                fps = 1.0 / dt
            prev_time = current_time

            result = pipeline.process_frame()
            if not result.frame_valid:
                continue

            # Per-frame debug logging (existing logic, unchanged)
            if result.landmarks:
                # ... same debug logging as current run_preview_mode ...
                pass

            # Signal logging (existing logic, unchanged)
            if result.orchestrator and result.orchestrator.signals:
                # ... same signal logging ...
                pass

            # Preview rendering (always -- no conditional)
            frame = pipeline.last_frame
            if result.landmarks:
                draw_hand_landmarks(frame, result.landmarks)
            render_preview(frame, ...)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                break
            try:
                if cv2.getWindowProperty("Gesture Keys", cv2.WND_PROP_VISIBLE) < 1:
                    break
            except cv2.error:
                break
    except KeyboardInterrupt:
        pass
    finally:
        pipeline.stop()
        cv2.destroyAllWindows()
```

**Key difference from current `run_preview_mode`:** No `if args.preview:` guard around rendering. Camera is always shown.

### 3. TrayApp Changes (MODIFY tray.py)

**New menu item:** "View Camera" between "Active" toggle and "Edit Config".

```python
def _build_menu(self) -> pystray.Menu:
    return pystray.Menu(
        pystray.MenuItem(
            text=lambda item: "Active" if self._active.is_set() else "Inactive",
            action=self._on_toggle,
            checked=lambda item: self._active.is_set(),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("View Camera", self._on_view_camera),
        pystray.MenuItem("Edit Config", self._on_edit_config),
        pystray.MenuItem("Quit", self._on_quit),
    )
```

**"View Camera" handler:** Spawns a child process with `--view-camera` flag.

```python
def _on_view_camera(self, icon, item) -> None:
    """Spawn a camera window subprocess."""
    import subprocess
    exe = sys.executable if not getattr(sys, 'frozen', False) else sys.argv[0]
    cmd = [exe, "--view-camera", "--config", self._config_path]
    if not getattr(sys, 'frozen', False):
        cmd = [sys.executable, "-m", "gesture_keys",
               "--view-camera", "--config", self._config_path]
    subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
```

**Critical design decision -- subprocess, NOT in-process:**

Why not open the OpenCV window in the tray process?
- pystray owns the main thread on Windows (Win32 message loop).
- OpenCV's `cv2.imshow` / `cv2.waitKey` also needs a message-pumping thread.
- Running both in one process requires careful thread coordination and is fragile.
- A subprocess is clean: the tray keeps running, the camera window is independent, closing the window just kills the child process.

**Camera resource conflict:** The tray's detection thread holds the camera (via Pipeline). The child process would need its OWN camera access. Two options:

- **Option A (recommended):** Tray pauses its pipeline (releases camera) while "View Camera" is open, resumes when child exits. The child runs its own Pipeline with camera.
- **Option B:** Tray keeps running headless, child only reads frames for display without its own Pipeline. Requires shared memory or socket -- overengineered.

**Option A implementation:**

```python
def _on_view_camera(self, icon, item) -> None:
    """Pause tray detection, spawn camera window, resume on close."""
    import subprocess

    # Pause tray detection (releases camera in _detection_loop)
    self._active.clear()

    exe_cmd = self._build_view_camera_cmd()
    proc = subprocess.Popen(exe_cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)

    # Monitor child in background thread, re-activate when done
    def _wait_and_resume():
        proc.wait()
        if not self._shutdown.is_set():
            self._active.set()

    threading.Thread(target=_wait_and_resume, daemon=True).start()
```

When `_active` is cleared, the tray's `_detection_loop` exits its inner `while self._active.is_set()` loop and calls `pipeline.stop()` (releasing the camera). The child process can then open the camera. When the child exits, `_active` is re-set and the tray's detection loop re-creates a new Pipeline and resumes.

### 4. Logging Changes (MODIFY logging_setup.py + __main__.py)

**Current state:** `setup_logging()` creates file handlers only. Console handler is added ad-hoc in `run_preview_mode`.

**New design:** `setup_logging()` gains an optional `console` parameter.

```python
def setup_logging(console: bool = False, debug: bool = False) -> None:
    """Configure the 'gesture_keys' logger.

    Args:
        console: If True, add a StreamHandler for console output.
        debug: If True (and console=True), set console level to DEBUG.
               Otherwise console level is INFO.
    File handlers (preview.log, debug.log) are always added.
    """
    logger = logging.getLogger("gesture_keys")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return

    logs = _logs_dir()
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT)

    # File handlers (unchanged)
    # ... preview.log at INFO, debug.log at DEBUG ...

    # Console handler (new)
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
        console_handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(message)s", datefmt="%H:%M:%S"
        ))
        logger.addHandler(console_handler)
```

**Call sites:**

| Mode | Call |
|------|------|
| Dev mode | `setup_logging(console=True, debug=args.debug)` |
| Tray mode | `setup_logging()` (no console, unchanged) |
| View Camera | `setup_logging(console=True)` |

This centralizes the console handler logic that is currently scattered inline in `run_preview_mode`.

### 5. Pipeline (NO CHANGES)

The Pipeline class requires zero modifications. It already:
- Exposes `last_frame` for external rendering
- Has clean `start()` / `stop()` lifecycle
- Is mode-agnostic (caller decides what to do with FrameResult)
- Handles config hot-reload internally

This is a sign of good existing architecture -- the new features only touch the entry points and the tray wrapper.

## Data Flow: Mode Transitions

### Dev Mode (default for `python -m gesture_keys`)

```
main() -> run_dev_mode(args)
  -> setup_logging(console=True, debug=args.debug)
  -> Pipeline(config_path).start()
  -> _camera_loop(pipeline, log_level)
     -> pipeline.process_frame() per frame
     -> draw_hand_landmarks() + render_preview() per frame
     -> cv2.waitKey() for exit
  -> pipeline.stop()
```

### Tray Mode (default for frozen exe)

```
main() -> run_tray_mode(args)
  -> setup_logging()
  -> hide_console_window()
  -> TrayApp(config_path).run()
     -> pystray.Icon.run(setup=_on_setup)
        -> _start_detection() in daemon thread
           -> _detection_loop()
              -> Pipeline(config_path).start()
              -> pipeline.process_frame() in loop
              -> pipeline.stop() on pause/quit

  [User clicks "View Camera"]
     -> _on_view_camera()
        -> self._active.clear()  (pauses detection, releases camera)
        -> subprocess.Popen([exe, "--view-camera", ...])
        -> background thread waits for child exit
        -> self._active.set()  (resumes detection)
```

### View Camera Mode (spawned by tray)

```
main() -> run_camera_mode(args)
  -> setup_logging(console=True)
  -> Pipeline(config_path).start()
  -> _camera_loop(pipeline, logging.INFO)
  -> pipeline.stop()
  -> process exits -> parent tray resumes
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: OpenCV Window in the Tray Process

**What people do:** Try to open `cv2.imshow` from the tray's detection thread.
**Why it's wrong:** OpenCV's HighGUI needs a message loop. On Windows, `cv2.waitKey()` pumps messages for OpenCV's window, but pystray's main thread is already running the Win32 message loop. Two competing message loops in one process cause hangs and missed events.
**Do this instead:** Spawn a separate process for the camera window. The tray process stays headless.

### Anti-Pattern 2: Sharing Camera Between Processes

**What people do:** Try to have both tray detection and camera window read from the same physical camera simultaneously.
**Why it's wrong:** Most webcams only allow one process to hold the capture handle. The second `cv2.VideoCapture.open()` will fail silently or block.
**Do this instead:** Pause the tray's pipeline (which releases the camera) before spawning the camera window process. Resume after it exits.

### Anti-Pattern 3: Conditional Preview Rendering in the Detection Loop

**What people do:** Keep `if show_camera:` checks inside the frame loop, toggling a boolean.
**Why it's wrong:** Mixing "should I render?" logic into the frame loop makes it harder to reason about. The current codebase already has `if args.preview:` in 3 places inside the loop.
**Do this instead:** Have separate entry functions where camera-showing modes ALWAYS render, and headless modes NEVER render. The Pipeline stays agnostic.

### Anti-Pattern 4: Passing --debug to File Handler Levels

**What people do:** Make `--debug` change file handler levels.
**Why it's wrong:** File handlers already capture DEBUG to `debug.log`. The `--debug` flag should ONLY affect console verbosity.
**Do this instead:** `--debug` controls the StreamHandler level. File handlers are always INFO + DEBUG as they are today.

## Suggested Build Order

Dependencies flow top-down. Each step is testable independently.

### Step 1: Consolidate logging (logging_setup.py)

**Modify:** `setup_logging()` to accept `console` and `debug` parameters.
**Why first:** Zero risk, no behavior change to existing callers (default args preserve current behavior). Enables clean logging in all subsequent steps.
**Test:** Call `setup_logging(console=True, debug=True)`, verify console handler added at DEBUG. Call `setup_logging()`, verify no console handler (existing behavior).

### Step 2: Extract _camera_loop helper (__main__.py)

**Add:** `_camera_loop(pipeline, log_level)` function extracted from `run_preview_mode`.
**Modify:** `run_preview_mode` to call `_camera_loop` (proving extraction works).
**Why second:** Pure refactor. --preview still works exactly as before. Validates the extraction before building new modes on top.
**Test:** Run `python -m gesture_keys --preview` and confirm identical behavior.

### Step 3: Create run_dev_mode and run_camera_mode (__main__.py)

**Add:** `run_dev_mode(args)` -- calls `setup_logging(console=True, debug=args.debug)`, creates Pipeline, calls `_camera_loop`. Always shows camera (no --preview needed).
**Add:** `run_camera_mode(args)` -- calls `setup_logging(console=True)`, creates Pipeline, calls `_camera_loop`. Used by tray "View Camera".
**Modify:** `main()` routing logic: frozen -> tray, `--view-camera` -> camera mode, else -> dev mode.
**Remove:** `--preview` argument. `run_preview_mode` function (replaced by `run_dev_mode`).
**Test:** `python -m gesture_keys` shows camera (no --preview needed). `python -m gesture_keys --debug` shows verbose console. `python -m gesture_keys --view-camera` shows camera window and exits cleanly on close.

### Step 4: Add "View Camera" to TrayApp (tray.py)

**Modify:** `_build_menu()` -- add "View Camera" item.
**Add:** `_on_view_camera()` -- pauses detection, spawns subprocess, resumes on child exit.
**Why last:** Depends on `--view-camera` flag existing (Step 3). Most complex piece due to subprocess lifecycle.
**Test:** Build exe, launch, click "View Camera" -- camera window opens, tray stays running. Close camera window -- tray resumes detection. Click "View Camera" again -- works repeatedly.

## Integration Points Summary

| Component | Change Type | What Changes |
|-----------|-------------|--------------|
| `__main__.py` | MODIFY | New routing logic, 3 run functions, remove --preview |
| `__main__.py` | NEW | `_camera_loop()` helper |
| `logging_setup.py` | MODIFY | `setup_logging()` gains console/debug params |
| `tray.py` | MODIFY | "View Camera" menu item + subprocess spawn |
| `pipeline.py` | NONE | No changes needed |
| `preview.py` | NONE | No changes needed |
| `config.py` | NONE | No changes needed |
| All other modules | NONE | No changes needed |

**Total scope:** 2 files modified (main, tray), 1 file with minor signature change (logging_setup). ~80 lines added, ~30 lines removed, ~50 lines moved (extraction).

## Sources

- Direct codebase analysis: `gesture_keys/__main__.py`, `gesture_keys/tray.py`, `gesture_keys/pipeline.py`, `gesture_keys/logging_setup.py`, `gesture_keys/preview.py`
- pystray threading model: pystray requires main thread on Windows for Win32 message pump (confirmed by existing `_on_setup` callback pattern and daemon thread for detection)
- OpenCV HighGUI: `cv2.waitKey()` pumps the window message loop; must be called from the thread that created the window

---
*Architecture research for: Gesture Keys v3.2 Unified Preview & Exec Mode*
*Researched: 2026-03-30*
