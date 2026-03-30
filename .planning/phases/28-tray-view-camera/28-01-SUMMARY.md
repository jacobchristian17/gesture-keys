---
phase: 28-tray-view-camera
plan: 01
subsystem: tray
tags: [pystray, subprocess, threading, camera-preview]

# Dependency graph
requires:
  - phase: 27-entry-point-refactor
    provides: run_camera_mode and --view-camera flag
provides:
  - View Camera menu item in system tray
  - Camera subprocess spawn/monitor lifecycle
  - Fixed frozen+view-camera routing
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Subprocess spawn with monitor thread for lifecycle management"
    - "Threading.Event for cross-thread camera state signaling"

key-files:
  created: []
  modified:
    - gesture_keys/tray.py
    - gesture_keys/__main__.py
    - tests/test_tray.py
    - tests/test_main.py

key-decisions:
  - "Monitor thread with proc.wait() for camera subprocess lifecycle -- simple, reliable"
  - "Mock threading.Thread in tests to prevent monitor race condition"

patterns-established:
  - "Subprocess lifecycle: set state, spawn, monitor thread waits, restore state on exit"

requirements-completed: [TRAY-01]

# Metrics
duration: 3min
completed: 2026-03-31
---

# Phase 28 Plan 01: View Camera Tray Lifecycle Summary

**View Camera tray menu item with subprocess spawn, monitor thread, and automatic detection resume on camera close**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-30T19:10:03Z
- **Completed:** 2026-03-30T19:13:23Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added View Camera menu item to tray with dynamic text and enabled state
- Implemented full camera subprocess lifecycle: spawn, monitor, resume detection
- Fixed frozen exe + --view-camera routing bug (now routes to camera mode, not tray)
- Added 8 new tests covering spawn state, frozen/non-frozen commands, monitor resume, error handling, and detection loop exit

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix frozen+view-camera routing and add View Camera tray lifecycle** - `13036f3` (feat)
2. **Task 2: Add tests for View Camera lifecycle and frozen routing fix** - `54093b2` (test)

## Files Created/Modified
- `gesture_keys/tray.py` - Added _camera_active Event, _on_view_camera, _monitor_camera_process, updated _build_menu and _detection_loop
- `gesture_keys/__main__.py` - Fixed routing: frozen + --view-camera now routes to run_camera_mode
- `tests/test_tray.py` - Added TestViewCamera class with 8 tests
- `tests/test_main.py` - Updated frozen+view_camera routing test for new behavior

## Decisions Made
- Used threading.Thread mock in tests to prevent monitor thread race condition (mock proc.wait() returns immediately, causing state reset before assertions)
- Error handling wraps entire _on_view_camera body in try/except, restoring state on failure

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test race condition with monitor thread**
- **Found during:** Task 2 (test writing)
- **Issue:** Mock proc.wait() returns immediately, so monitor thread resets _camera_active before test assertions run
- **Fix:** Added @patch("gesture_keys.tray.threading.Thread") to tests that check state after _on_view_camera
- **Files modified:** tests/test_tray.py
- **Verification:** All 8 TestViewCamera tests pass reliably
- **Committed in:** 54093b2 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Test mock strategy adjustment for correctness. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- View Camera lifecycle complete and tested
- 475 tests passing across full suite
- Ready for phase transition

---
*Phase: 28-tray-view-camera*
*Completed: 2026-03-31*
