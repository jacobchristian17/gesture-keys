# Feature Research

**Domain:** Unified preview & exec mode for Python desktop tray app (gesture detection)
**Researched:** 2026-03-30
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features required for the v3.2 milestone to deliver on "unified preview & exec mode." Without these the milestone is incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Dev mode always shows camera + console logging | Currently `python -m gesture_keys` launches headless tray mode by default, which is confusing during development -- you see nothing. Developers expect `python -m gesture_keys` to give immediate visual feedback. | LOW | Flip the default: non-frozen = camera+logging, frozen exe = tray. The code paths already exist in `run_preview_mode()` and `run_tray_mode()`; this is routing logic in `main()`. Key change: the `if args.preview:` guard on line 146 of `__main__.py` that controls camera rendering must become always-on for dev mode. |
| `--debug` flag for verbose console output | Standard CLI pattern. Every serious CLI tool supports `--debug` or `-v` for troubleshooting. | LOW | The argparse arg already exists (`__main__.py` lines 35-37). Console handler already uses it to set DEBUG level (line 87). Main gap: `--debug` only works in preview mode today because `run_tray_mode()` ignores the flag entirely and calls `setup_logging()` without a console handler. Need to wire it into both code paths. |
| Remove `--preview` as a separate concept | The milestone explicitly says "preview is default dev behavior." Keeping `--preview` alongside the new default creates confusion about which flag to use. | LOW | Deprecate or remove the flag. The `args.preview` condition gating camera rendering in `run_preview_mode()` changes to unconditional for dev mode. |

### Differentiators (Competitive Advantage)

Features that make this app more usable than the typical "run and hope" tray utility.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Tray "View Camera" menu item | Lets non-developer users (or developers running the .exe) see what the camera sees without restarting manually. Turns debugging from "quit, relaunch with flag" into a single click. | MEDIUM | **This is the hardest feature in the milestone.** `cv2.imshow` and `cv2.waitKey` must run on the main thread on Windows (confirmed by OpenCV issue #8407). pystray's `Icon.run()` also blocks the main thread. This means the tray app cannot open an OpenCV window in a thread -- it requires a subprocess restart approach. See Implementation Approaches below. |
| Tray icon state indicator (active vs camera-visible) | Visual feedback that camera mode is active. Users currently cannot tell if the app is detecting or idle without checking the menu. | LOW | Change icon color (green=active, blue=camera-active). Already have `_create_icon_image()` that draws a colored circle. Optional polish, not core. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| In-process camera window toggle (show/hide OpenCV window from tray thread) | Seems simpler than restarting. "Just open a window." | `cv2.imshow`/`cv2.waitKey` must run on the main thread on Windows. pystray's `Icon.run()` blocks the main thread. Attempting to call OpenCV GUI from a background thread produces hangs, crashes, or no display. This is a hard platform constraint, not a fixable bug. | Use subprocess restart (Approach A below). |
| `-v` / `-vv` counting verbosity pattern | Conventional in CLI tools for graduated verbosity. | Overkill for this app. There are exactly two useful log levels: normal (INFO signals/transitions) and debug (every-frame state). A third level adds nothing. The counting pattern adds argparse complexity for zero user benefit. | Single `--debug` boolean flag. Two levels: INFO (default) and DEBUG (with flag). |
| Embedded GUI framework (Tkinter/Qt) for camera display | Would allow proper window management, show/hide, no threading issues. | Adds a massive dependency (Qt) or fights with pystray for main thread (Tkinter). The app is ~9k LOC with zero GUI framework dependency. OpenCV's highgui is already used and sufficient. | Keep cv2.imshow for camera. Accept the subprocess restart trade-off for tray integration. |
| `--headless` flag for tray-only mode in development | "What if I'm developing but don't want the camera?" | Running a gesture detection app without seeing the camera in dev mode is not a real workflow. If you are developing, you want visual feedback. If you do not want the camera, you are running tests, and tests do not use the CLI. | Dev mode = camera always. No flag needed. |

## Implementation Approaches for "View Camera" (Critical Decision)

The core tension: **pystray needs the main thread. OpenCV GUI needs the main thread. Both on Windows.**

### Approach A: Subprocess Restart (Recommended)

"View Camera" menu item stops the current process and relaunches with a `--camera` flag (or equivalent internal flag) via `subprocess.Popen([sys.executable, ...])` then `os._exit(0)`.

**Pros:**
- Clean separation. New process owns the main thread for OpenCV.
- Simple to implement. `sys.executable` + `sys.argv` reconstruction.
- Works with both frozen (PyInstaller) and dev mode.
- Camera window gets proper main-thread event loop (`cv2.waitKey`).

**Cons:**
- Brief restart gap (camera release + reacquire ~1-2 seconds).
- User sees the tray icon disappear and reappear.

**Complexity:** MEDIUM -- need to handle frozen vs dev `sys.executable` paths, pass config path through, and ensure clean shutdown of the current pipeline before respawn.

**Implementation sketch:**
```python
# In tray.py _on_view_camera():
def _on_view_camera(self, icon, item):
    self._shutdown.set()
    self._active.set()  # unblock wait
    icon.stop()
    # Relaunch with camera flag
    args = [sys.executable] + sys.argv + ["--camera"]
    subprocess.Popen(args)
    os._exit(0)
```

For frozen exe, `sys.executable` is the .exe path. For dev, it is the Python interpreter and `sys.argv[0]` is the module. Both cases work with `sys.executable + sys.argv` reconstruction.

### Approach B: Separate Camera Process (Over-engineered)

Main process stays as tray. "View Camera" spawns a separate process that opens the camera in read-only/mirror mode.

**Pros:**
- Tray never restarts.

**Cons:**
- Two processes sharing the same camera = conflict. Only one process can hold `cv2.VideoCapture`.
- Need IPC (pipe, shared memory, socket) to share frame data or pipeline state.
- Massively more complex for a feature that will be used occasionally.

**Verdict:** Use Approach A (subprocess restart). The 1-2 second restart is acceptable for an infrequent user action.

## Feature Dependencies

```
[Remove --preview flag]
    └──enables──> [Dev mode always shows camera]
                      └──shares entry point logic with──> [Tray "View Camera" restart]

[--debug flag wired to both modes]
    └──independent (no dependencies on other features)

[Tray "View Camera" menu item]
    └──requires──> [Unified entry point that can launch camera OR tray based on args]
```

### Dependency Notes

- **Remove --preview requires updating entry point logic:** The `main()` function currently branches on `args.preview`. Removing the flag means the branch condition changes to "am I frozen?" or "was I launched with --camera?" (internal restart flag).
- **"View Camera" requires unified entry point:** The subprocess restart re-enters through `main()`, so `main()` must be able to launch camera mode when requested. This is the same entry point refactor needed for dev-mode-default.
- **--debug is independent:** It only affects logging handler configuration. Can be implemented in any order, in any phase.
- **Entry point refactor is the foundation:** Both dev-mode-default and "View Camera" depend on `main()` understanding three launch modes: (1) dev with camera, (2) tray headless, (3) tray-to-camera restart. This is the first thing to build.

## MVP Definition

### Launch With (v3.2)

These are the milestone deliverables. All three are needed to call the milestone complete.

- [ ] **Unified dev mode** -- `python -m gesture_keys` shows camera + console logging by default (no flag needed)
- [ ] **Tray "View Camera"** -- menu item that restarts the app with camera visible via subprocess
- [ ] **`--debug` flag** -- enables DEBUG-level console output in both dev and camera modes

### Add After Validation (v3.2.x)

Features to add once the core unification works and has been used for a few sessions.

- [ ] **Tray icon color change when camera is active** -- visual indicator without opening menu
- [ ] **"Hide Camera" / "Back to Tray" menu item when camera is showing** -- reverse of "View Camera", restarts back to tray-only
- [ ] **Log level in banner** -- print whether debug logging is active in the startup banner

### Future Consideration (v4+)

- [ ] **`--log-file` flag** -- redirect console logging to a custom file path
- [ ] **Camera window resize/position memory** -- remember window position across restarts (Windows registry or config file)

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority | Depends On |
|---------|------------|---------------------|----------|------------|
| Dev mode default camera | HIGH | LOW | P1 | Entry point refactor |
| Remove --preview | HIGH | LOW | P1 | Dev mode default |
| --debug flag (both modes) | MEDIUM | LOW | P1 | None |
| Tray "View Camera" restart | HIGH | MEDIUM | P1 | Entry point refactor |
| Tray icon state color | LOW | LOW | P2 | None |
| "Hide Camera" reverse toggle | MEDIUM | LOW | P2 | "View Camera" |
| Banner log level display | LOW | LOW | P3 | --debug flag |

**Priority key:**
- P1: Must have for v3.2 milestone completion
- P2: Should have, add in v3.2.x once core is stable
- P3: Nice to have, future consideration

## Existing Code to Reuse

The codebase already has almost everything needed. This milestone is primarily a **routing/entry-point refactor**, not new functionality.

| Existing Code | Location | Reuse For |
|---------------|----------|-----------|
| Camera preview loop | `__main__.py:run_preview_mode()` | Dev mode default camera display |
| Console logging handler setup | `__main__.py:87-89` | Both dev and camera-from-tray modes |
| `--debug` argparse arg | `__main__.py:35-37` | Already defined, needs wiring to tray path |
| File logging (rotating handlers) | `logging_setup.py:setup_logging()` | No changes needed, already writes to logs/ |
| Tray menu builder | `tray.py:_build_menu()` | Add "View Camera" item here |
| Pipeline start/stop | `pipeline.py:Pipeline` | Unchanged, both modes use it |
| Console window hide | `__main__.py:hide_console_window()` | Tray-only mode (already exists) |
| Frozen detection | `__main__.py:178` via `sys.frozen` | Dev vs tray mode branching |
| Banner printer | `__main__.py:print_banner()` | Dev and camera modes |
| Preview rendering | `preview.py:render_preview()` | Camera display in both dev and tray-restart modes |
| Config path resolution | `__main__.py:178-180` | Pass through on subprocess restart |

## Sources

- [OpenCV imshow threading issue #8407](https://github.com/opencv/opencv/issues/8407) -- confirms cv2.imshow/waitKey must be main thread on Windows
- [pystray issue #17 -- terminating from tray](https://github.com/moses-palmer/pystray/issues/17) -- pystray shutdown and Icon.stop() patterns
- [Python subprocess docs](https://docs.python.org/3/library/subprocess.html) -- subprocess.Popen for restart pattern
- [Python CLI logging with argparse patterns](https://gist.github.com/ms5/9f6df9c42a5f5435be0e) -- --debug flag conventions
- [CLI logging verbosity best practices](https://xahteiwi.eu/resources/hints-and-kinks/python-cli-logging-options/) -- two-level vs counting pattern analysis
- [pystray PyPI](https://pypi.org/project/pystray/) -- pystray threading model (setup callback runs in separate thread)
- Direct codebase analysis of `__main__.py`, `tray.py`, `pipeline.py`, `logging_setup.py`, `GestureKeys.spec`

---
*Feature research for: Unified preview & exec mode (v3.2)*
*Researched: 2026-03-30*
