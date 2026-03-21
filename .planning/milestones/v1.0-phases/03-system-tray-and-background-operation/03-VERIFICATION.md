---
phase: 03-system-tray-and-background-operation
verified: 2026-03-21T12:45:00Z
status: gaps_found
score: 5/6 must-haves verified
gaps:
  - truth: "TrayApp creates a pystray Icon with 'Gesture Keys' title and a valid Pillow image"
    status: partial
    reason: "Implementation uses RGBA mode (correct for Windows tray) but the unit test asserts RGB mode — the test was not updated after the bug fix in c92cb76. The icon itself works correctly (human-verified), but test_create_icon_image fails."
    artifacts:
      - path: "tests/test_tray.py"
        issue: "Line 53 asserts img.mode == 'RGB' but tray.py creates Image.new('RGBA', ...) — test stale after intentional bug fix"
    missing:
      - "Update test_create_icon_image to assert img.mode == 'RGBA' to reflect the correct post-fix implementation"
human_verification:
  - test: "Complete tray experience end-to-end"
    expected: "Tray icon visible, menu shows Active/Inactive toggle, Edit Config opens config.yaml, Quit exits cleanly, --preview mode unchanged"
    why_human: "Visual and interactive behavior (tray icon render, camera LED, default editor open) cannot be verified programmatically"
---

# Phase 3: System Tray and Background Operation — Verification Report

**Phase Goal:** System tray icon with background operation, active/inactive toggle, edit config, and quit
**Verified:** 2026-03-21T12:45:00Z
**Status:** gaps_found (1 stale test; implementation correct, test not updated after intentional bug fix)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | TrayApp creates a pystray Icon with 'Gesture Keys' title and a valid Pillow image | PARTIAL | Icon created in RGBA (correct), but `test_create_icon_image` asserts RGB — stale test after RGBA fix in c92cb76 |
| 2 | Toggle callback flips the active threading.Event and detection loop respects it | VERIFIED | `_on_toggle` clears/sets `_active`; inner loop guards `while self._active.is_set()`; test passes |
| 3 | Edit Config callback calls os.startfile with the config path | VERIFIED | `_on_edit_config` calls `os.startfile(self._config_path)`; test passes |
| 4 | Quit sets shutdown event, sets active event (unblock), and calls icon.stop() | VERIFIED | `_on_quit` sets `_shutdown`, sets `_active`, calls `icon.stop()`; test passes |
| 5 | Detection loop releases camera when going inactive and re-creates it when going active | VERIFIED | `try/finally` block in `_detection_loop` calls `camera.stop()` and `detector.close()`; test passes |
| 6 | Detection loop exits cleanly when shutdown event is set | VERIFIED | Outer `while not self._shutdown.is_set()` guard; test passes |

**Score:** 5/6 truths verified (1 partial due to stale test)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `gesture_keys/tray.py` | TrayApp class with pystray integration, threading, and detection loop | VERIFIED | 225 lines; exports `TrayApp`; full detection pipeline wired |
| `tests/test_tray.py` | Unit tests for tray icon creation, toggle, edit config, quit, detection lifecycle | PARTIAL | 8 tests; 7 pass; `test_create_icon_image` fails — asserts RGB but implementation is RGBA |
| `requirements.txt` | pystray and Pillow dependencies added | VERIFIED | Contains `pystray>=0.19.5` and `Pillow>=10.0` |
| `gesture_keys/__main__.py` | Updated entry point that defaults to tray mode | VERIFIED | Dispatches to `run_tray_mode()` or `run_preview_mode()` based on `--preview` flag |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `gesture_keys/tray.py` | `pystray.Icon` | `Icon` constructor and `run(setup=...)` | WIRED | `pystray.Icon('gesture-keys', ...)` at line 218; `run(setup=self._on_setup)` at line 224 |
| `gesture_keys/tray.py` | `gesture_keys/detector.py` | `CameraCapture` and `HandDetector` in detection loop | WIRED | Both imported at top of file (lines 14-15) and instantiated in `_detection_loop` |
| `gesture_keys/tray.py` | `gesture_keys/config.py` | `load_config` and `ConfigWatcher` for hot-reload | WIRED | Both imported at line 12; used at lines 127 and 147 in `_detection_loop` |
| `gesture_keys/__main__.py` | `gesture_keys/tray.py` | Lazy import and instantiation of TrayApp | WIRED | `from gesture_keys.tray import TrayApp` inside `run_tray_mode()` at line 51 |
| `gesture_keys/__main__.py` | `ctypes.windll` | `hide_console_window` function | WIRED | `ctypes.windll.user32.ShowWindow(hwnd, 0)` at line 44 (SW_HIDE=0 verified) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| TRAY-01 | 03-01, 03-02 | Run as Windows system tray app with no camera preview by default | SATISFIED | `main()` defaults to `run_tray_mode()` which calls `TrayApp.run()`; pystray Icon created |
| TRAY-02 | 03-01 | Active/inactive toggle in tray menu | SATISFIED | `_on_toggle` flips `_active` Event; menu item uses lambda for dynamic text and checked state |
| TRAY-03 | 03-01 | Edit Config option opens config.yaml in default editor | SATISFIED | `_on_edit_config` calls `os.startfile(self._config_path)` |
| TRAY-04 | 03-01 | Quit option stops camera and exits | SATISFIED | `_on_quit` sets shutdown, unblocks active, calls `icon.stop()`; `_detection_loop` exits and runs `finally: camera.stop(), detector.close()` |

All 4 required TRAY-xx requirements from REQUIREMENTS.md are accounted for. No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_tray.py` | 53 | `assert img.mode == "RGB"` — stale after RGBA fix | Warning | Test fails; implementation is correct (RGBA required for Windows tray transparency) |
| `gesture_keys/tray.py` | 187 | `debouncer._activation_delay = new_config.activation_delay` | Info | Direct private-attribute mutation during hot-reload; functional but bypasses any future validation in GestureDebouncer |

### Human Verification Required

#### 1. Complete Tray Experience

**Test:** Run `python -m gesture_keys` with no flags from the project root (after `pip install pystray Pillow`)
**Expected:** No console window or preview window; green circle tray icon visible in Windows system tray; right-click menu shows Active (checked), separator, Edit Config, Quit; toggle turns camera LED off/on; Edit Config opens config.yaml; Quit exits cleanly
**Why human:** Visual tray icon render, camera LED state, OS default editor launch, and process exit cannot be verified by static analysis or unit tests

#### 2. Preview Mode Unchanged

**Test:** Run `python -m gesture_keys --preview`
**Expected:** Camera preview window opens with landmark overlay and FPS counter; exactly as before Phase 3
**Why human:** GUI window display requires a running process and visual confirmation

### Gaps Summary

One gap blocks a clean "all tests pass" status: `test_create_icon_image` asserts `img.mode == "RGB"` but the implementation correctly uses `RGBA` mode (changed during human verification in Plan 02 to fix the invisible tray icon on Windows — commit c92cb76). The test was written in Plan 01 against the original spec, then the implementation was fixed but the test was not updated.

The implementation is correct. The test is stale. The fix is a one-line change to the assertion.

Three other test failures exist in `test_config.py` (smoothing_window default, key_mappings, activation_delay default) but these predate Phase 3 — they reflect the config.yaml being customized by the user after Phase 2 (scout gesture addition in c92cb76 also changed timing values). These are not Phase 3 regressions.

---

_Verified: 2026-03-21T12:45:00Z_
_Verifier: Claude (gsd-verifier)_
