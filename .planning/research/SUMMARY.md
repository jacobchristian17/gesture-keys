# Project Research Summary

**Project:** Gesture Keys v3.2 — Unified Preview & Exec Mode
**Domain:** Python desktop tray app with gesture detection (Windows)
**Researched:** 2026-03-30
**Confidence:** HIGH

## Executive Summary

Gesture Keys v3.2 is a control-flow refactor of an existing, well-structured Python desktop application. The milestone's goal is to unify how the app launches and behaves across development and end-user (frozen exe) contexts: developers running `python -m gesture_keys` should immediately see the camera and console logs without any flags, while the frozen `.exe` continues to launch silently as a system tray app. A new "View Camera" tray menu item lets users open the camera preview on demand. No new dependencies are required — every capability needed exists in the codebase or Python stdlib.

The recommended approach is a three-phase entry-point refactor. Phase 1 consolidates logging and restructures `main()` into three clearly-separated run functions (`run_dev_mode`, `run_tray_mode`, `run_camera_mode`). Phase 2 implements the "View Camera" tray feature using a subprocess restart pattern — the only viable design given that pystray and OpenCV both require the Windows main thread. Phase 3 polishes the debug flag behavior and cleans up minor technical debt. The `Pipeline` class, `preview.py`, and `config.py` require zero modifications; only `__main__.py`, `tray.py`, and `logging_setup.py` change.

The single most critical risk is the pystray/OpenCV thread conflict: both frameworks demand the Win32 main thread, making it impossible to open an OpenCV camera window inside a running tray process. This forces the "View Camera" feature to use process restart rather than an in-process window toggle. The restart sequence itself has three compounding hazards — camera resource exclusivity, ghost tray icons, and stuck keys — all prevented by the same pattern: set a flag in the menu callback, let `icon.run()` return cleanly, join the detection thread, confirm camera release, then spawn the subprocess.

## Key Findings

### Recommended Stack

The existing stack handles all v3.2 requirements without modification or addition. No new packages needed. The work is routing logic and control flow, not capability expansion.

**Core technologies:**

- mediapipe / opencv-python: camera capture and hand landmark detection — unchanged
- pystray: system tray icon and menu — gains one new `MenuItem("View Camera", ...)` entry, no API additions needed
- PyYAML / pynput / Pillow: config, keystroke simulation, icon rendering — all unchanged
- `subprocess.Popen` (stdlib): spawns the camera-window child process from the tray — non-blocking, works identically for frozen exe and dev mode
- `argparse` (stdlib): mode flags — `--preview` removed, `--view-camera` added as internal flag, `--debug` wired to both modes
- `ctypes.windll` (stdlib): console window show/hide — already implemented in `hide_console_window()`
- `logging` (stdlib): unified via `setup_logging(console, debug)` parameters — centralizes what is currently split between `logging_setup.py` and an ad-hoc handler in `run_preview_mode()`

See `.planning/research/STACK.md` for full rationale and alternatives considered.

### Expected Features

**Must have (v3.2 table stakes):**

- Unified dev mode — `python -m gesture_keys` shows camera + INFO console logging by default; no flag needed
- Remove `--preview` flag — deprecated alias that prints a warning and enters dev mode; preserves brief backward compatibility
- `--debug` flag wired to all modes — enables DEBUG-level console output in dev mode and camera mode; file handlers unchanged

**Should have (competitive differentiators):**

- Tray "View Camera" menu item — single-click subprocess restart that opens the camera window; tray pauses detection while camera is active and resumes when camera window closes
- "Hide Camera" reverse toggle (v3.2.x) — menu item to restart back to tray-only mode
- Tray icon color change when camera is active (v3.2.x) — visual state indicator using the existing `_create_icon_image()` pattern

**Defer to v4+:**

- `--log-file` flag for custom log destinations
- Camera window position memory across restarts (Windows registry or config file)
- Multi-level verbosity (`-v`/`-vv`) — overkill; two levels (INFO/DEBUG) are sufficient

See `.planning/research/FEATURES.md` for the full prioritization matrix and implementation approach comparison.

### Architecture Approach

The target architecture introduces three separate run functions behind a clean `main()` router: a frozen exe enters `run_tray_mode`, a `--view-camera` flag enters `run_camera_mode` (spawned by the tray), and all other (dev) launches enter `run_dev_mode`. A shared `_camera_loop()` helper extracted from the current `run_preview_mode` is called by both `run_dev_mode` and `run_camera_mode`, eliminating the conditional `if args.preview:` guards scattered through the current detection loop. Logging is centralized in `setup_logging(console, debug)` to remove the ad-hoc console handler currently added inline in `run_preview_mode`.

**Major components and their changes:**

1. `__main__.py` (MODIFY) — new routing logic, three run functions, `_camera_loop()` helper, remove `--preview`, add `--view-camera`
2. `logging_setup.py` (MODIFY) — `setup_logging()` gains `console: bool` and `debug: bool` parameters; all handler creation centralized here; `logger.propagate = False` added to block mediapipe/PIL log noise
3. `tray.py` (MODIFY) — "View Camera" menu item; `_on_view_camera()` handler using the flag-set-then-act-after-run pattern; background thread that waits for child exit and resumes detection
4. `pipeline.py` (NONE) — no changes; already exposes `last_frame`, has a clean start/stop lifecycle, and is fully mode-agnostic
5. `preview.py`, `config.py`, all other modules (NONE) — untouched

**Recommended build order (from ARCHITECTURE.md):**

1. Consolidate logging signature — zero risk, enables clean logging in all subsequent steps
2. Extract `_camera_loop()` helper and validate with the existing `--preview` flag
3. Add `run_dev_mode` / `run_camera_mode`, update `main()` routing, remove `--preview`
4. Add "View Camera" to TrayApp — most complex piece; depends on step 3

See `.planning/research/ARCHITECTURE.md` for full component diagrams, data flow diagrams, and concrete code sketches.

### Critical Pitfalls

1. **OpenCV and pystray cannot coexist in one process** — both require the Win32 main thread on Windows; attempting to open `cv2.imshow` from a tray menu callback hangs or crashes. Use subprocess restart exclusively for "View Camera." This is a Phase 1 design decision that must be locked in from the start.

2. **Camera must be released before spawning the subprocess** — the tray holds an exclusive USB camera lock; if the child process starts before `cap.release()` completes, it sees "camera in use." Fix: join the detection thread after `icon.run()` returns before spawning.

3. **Ghost tray icons from premature process exit** — calling `sys.exit()` from inside a pystray menu callback exits before `WM_QUIT` is processed, leaving stranded icons. Fix: set a flag in the callback, perform all spawn/exit logic only after `icon.run()` returns.

4. **Subprocess fork bomb in frozen PyInstaller builds** — `sys.executable` is `GestureKeys.exe` when frozen; spawning it without the right flags re-enters tray mode, which spawns again infinitely. Fix: branch on `getattr(sys, 'frozen', False)`, redirect stdio to `subprocess.DEVNULL`, forward the resolved `--config` path.

5. **Held keys not released before restart** — if the detection thread is bypassed, `pipeline.stop()` / `dispatcher.release_all()` never runs and OS keys remain pressed. Fix: the "View Camera" shutdown sequence must match `_on_quit` exactly: `_shutdown.set()` + `_active.set()` + `icon.stop()` + join detection thread + spawn.

6. **Logging handler accumulation** — the `gesture_keys` logger is a singleton; adding handlers from multiple call sites causes duplicate console output or missing file logs. Fix: centralize all handler creation in `setup_logging()` with per-type duplicate guards; set `logger.propagate = False`.

See `.planning/research/PITFALLS.md` for the full checklist, recovery strategies, and the "Looks Done But Isn't" acceptance checklist (11 items).

## Implications for Roadmap

Based on research, the milestone decomposes naturally into three phases following the dependency chain: logging foundation → entry point unification → tray subprocess integration. Each phase is independently testable and leaves the app functional.

### Phase 1: Logging and Entry Point Foundation

**Rationale:** Both dev-mode-default and "View Camera" depend on `main()` understanding three distinct launch modes. Logging must be centralized before restructuring the entry point — otherwise each new run function re-introduces the ad-hoc console handler anti-pattern. These are zero-risk changes that unlock everything else.

**Delivers:** `setup_logging(console, debug)` unified API; `run_dev_mode`, `run_camera_mode`, and `run_tray_mode` as separate functions; updated `main()` router; `--preview` deprecated as alias; `--view-camera` internal flag added; `_camera_loop()` helper extracted from `run_preview_mode`.

**Addresses:** Dev mode default camera (P1), `--debug` flag wired to both modes (P1), remove `--preview` (P1)

**Avoids:** Logging handler accumulation (Pitfall 6), conditional preview rendering anti-pattern, `_was_moving` function-attribute state debt

**Research flag:** Standard patterns — pure refactoring of well-understood code; no phase research needed.

### Phase 2: Tray "View Camera" Subprocess Integration

**Rationale:** Depends entirely on Phase 1's `--view-camera` flag and the unified entry point. This is the highest-complexity feature, with five distinct correctness hazards that must be addressed in a specific sequence. Testing must cover both the dev launch path and the frozen `dist/GestureKeys/GestureKeys.exe`.

**Delivers:** "View Camera" menu item in the tray; tray pauses detection and releases camera before spawning the child process; background thread resumes detection when child exits; clean subprocess lifecycle for both frozen and dev contexts.

**Uses:** `subprocess.Popen` with `CREATE_NEW_CONSOLE` + `DEVNULL` stdio; `sys.frozen` branching for command construction; `threading.Thread` for the wait-and-resume pattern; existing `TrayApp._active` / `_shutdown` events.

**Avoids:** OpenCV/pystray thread conflict (Pitfall 1), camera race condition (Pitfall 3), ghost tray icons (Pitfall 4), fork bomb in frozen exe (Pitfall 2), stuck keys on restart (Pitfall 5)

**Research flag:** Needs careful integration testing — subprocess lifecycle on Windows with frozen PyInstaller builds is a documented landmine. The 11-item "Looks Done But Isn't" checklist from PITFALLS.md must be used as the acceptance criterion for this phase.

### Phase 3: Polish and Technical Debt

**Rationale:** Low-risk cleanup that improves production quality but is not on the critical path. Should be done after Phase 2 is confirmed working in the frozen exe.

**Delivers:** `debug.log` made opt-in (only written when `--debug` is active) to eliminate continuous disk I/O in production tray mode; UX feedback tray notification ("Opening camera preview...") before shutdown begins; tray icon color change when camera is active (v3.2.x stretch goal); `logger.propagate = False` confirmed.

**Addresses:** Debug log disk I/O performance trap (RotatingFileHandler always active in current code), `--debug` invisible in tray mode UX pitfall, tray icon state indicator (P2)

**Research flag:** Standard patterns — logging and pystray icon color are well-documented; no phase research needed.

### Phase Ordering Rationale

- **Logging before entry point refactor:** The `setup_logging()` signature change has zero behavioral impact on existing callers (default arguments preserve current behavior). Doing it first means the new run functions use the clean API from day one.
- **Entry point unification before tray integration:** The `--view-camera` flag must exist before `_on_view_camera()` can construct the subprocess command. The `main()` routing must be proven with `python -m gesture_keys` before testing the frozen-exe restart path.
- **Tray integration last:** The highest-risk piece is built on a tested foundation. Subprocess command construction (`sys.frozen` branching, stdio redirection, config path forwarding) is only safe to implement after Phase 1's entry point handles `--view-camera` correctly.
- **Technical debt in Phase 3:** The `debug.log` opt-in change and `_was_moving` state migration are improvements, not blockers. Sequencing them last avoids scope creep in the critical phases.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** The frozen-exe subprocess restart on Windows has multiple documented failure modes. Integration tests must be executed against `dist/GestureKeys/GestureKeys.exe`, not just `python -m gesture_keys`. Rapid repeat testing (10 "View Camera" clicks in sequence) is required.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Pure refactoring of existing well-understood code. All patterns present in the codebase.
- **Phase 3:** Standard logging configuration and pystray icon updates. Well-documented APIs.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Research is based on direct codebase analysis; no new dependencies means no version uncertainty; alternatives evaluated and rejected with clear rationale |
| Features | HIGH | All three P1 features map to specific existing functions; implementation sketches provided; approach for "View Camera" (subprocess restart) confirmed from platform constraints |
| Architecture | HIGH | Build order confirmed by dependency analysis; concrete code sketches provided for all modified components; Pipeline confirmed unchanged |
| Pitfalls | HIGH | Each pitfall sourced from official docs (OpenCV issue #8407, PyInstaller issue #4067, pystray issues #17 and #94) plus direct codebase inspection with line references |

**Overall confidence:** HIGH

### Gaps to Address

- **Camera open latency UX:** The 2-5 second gap between "View Camera" click and the camera window appearing is inherent to USB camera initialization on Windows. Research notes a tray notification as the mitigation, but the exact notification text and timing should be validated during Phase 2 implementation.
- **`--debug` in tray mode (no console):** When the frozen exe is launched with `--debug`, there is no visible console. The research recommendation is documentation — clarify that `--debug` is a dev-mode flag. Confirm during Phase 3 whether a log-viewer or runtime warning is worthwhile.
- **`_was_moving` state migration:** The function-attribute state on `run_preview_mode` (lines 137-143 of `__main__.py`) needs to move to Pipeline or a dedicated state object during the Phase 1 refactor. The right home for it should be confirmed when reading the full `run_preview_mode` implementation at the start of Phase 1.

## Sources

### Primary (HIGH confidence)

- Direct codebase analysis: `gesture_keys/__main__.py`, `gesture_keys/tray.py`, `gesture_keys/pipeline.py`, `gesture_keys/logging_setup.py`, `gesture_keys/preview.py`, `GestureKeys.spec` — architecture, stack, and pitfall findings
- [OpenCV Issue #8407](https://github.com/opencv/opencv/issues/8407) — cv2.imshow/waitKey must be on the main thread on Windows (core architectural constraint)
- [PyInstaller Issue #4067](https://github.com/pyinstaller/pyinstaller/issues/4067) — exe spawning itself infinitely (fork bomb pitfall)
- [pystray Issue #17](https://github.com/moses-palmer/pystray/issues/17) — pystray shutdown and Icon.stop() patterns
- [pystray Issue #94](https://github.com/moses-palmer/pystray/issues/94) — Icon.stop() thread behavior (ghost icon pitfall)

### Secondary (MEDIUM confidence)

- [Python subprocess docs](https://docs.python.org/3/library/subprocess.html) — Popen for non-blocking process spawn
- [Python logging docs](https://docs.python.org/3/library/logging.handlers.html) — RotatingFileHandler, StreamHandler
- [PyInstaller common issues](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html) — subprocess in frozen apps, stdio handle requirements
- [CLI logging verbosity best practices](https://xahteiwi.eu/resources/hints-and-kinks/python-cli-logging-options/) — two-level vs counting pattern analysis
- [SigNoz — Fixing duplicate log messages in Python](https://signoz.io/guides/log-messages-appearing-twice-with-python-logging/) — logging handler accumulation patterns

---
*Research completed: 2026-03-30*
*Ready for roadmap: yes*
