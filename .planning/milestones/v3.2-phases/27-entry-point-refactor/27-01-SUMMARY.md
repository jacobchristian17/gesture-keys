---
phase: 27-entry-point-refactor
plan: 01
subsystem: cli
tags: [argparse, entry-point, mode-routing, python]

# Dependency graph
requires:
  - phase: 26-logging-setup
    provides: setup_logging(console, debug) parameterized logging
provides:
  - Three-way mode routing in main() (dev/tray/camera)
  - run_dev_mode with always-on camera preview
  - run_camera_mode for tray subprocess (no banner)
  - Hidden --view-camera flag for Phase 28 tray integration
  - --tray flag for forcing tray mode from Python
affects: [28-tray-camera-subprocess]

# Tech tracking
tech-stack:
  added: []
  patterns: [three-way mode routing via frozen/flag detection, hidden argparse flags with SUPPRESS]

key-files:
  created:
    - tests/test_main.py
  modified:
    - gesture_keys/__main__.py

key-decisions:
  - "Preview rendering always on in dev/camera modes (removed if args.preview guard)"
  - "run_camera_mode is a copy of run_dev_mode without print_banner for subprocess use"
  - "Routing priority: frozen > --tray > --view-camera > default dev mode"

patterns-established:
  - "Mode routing: getattr(sys, 'frozen', False) for PyInstaller detection, elif chain for flags"
  - "Hidden flags: argparse.SUPPRESS for internal-only CLI arguments"

requirements-completed: [ENTRY-01, ENTRY-02]

# Metrics
duration: 2min
completed: 2026-03-30
---

# Phase 27 Plan 01: Entry Point Refactor Summary

**Three-way mode routing in __main__.py: dev mode (camera+banner) by default, frozen exe to tray, --view-camera for subprocess camera**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-30T16:43:36Z
- **Completed:** 2026-03-30T16:45:37Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Refactored __main__.py with run_dev_mode (always-on camera preview), run_camera_mode (no banner), and clean main() routing
- Added --tray and --view-camera (hidden) flags; --preview prints deprecation warning
- 15 tests covering parse_args defaults, all flags, routing priority, and deprecation warning

## Task Commits

Each task was committed atomically:

1. **Task 1: Refactor __main__.py** - `36a3a3e` (feat)
2. **Task 2: Add test_main.py** - `f089b55` (test)

## Files Created/Modified
- `gesture_keys/__main__.py` - Refactored entry point with three-way mode routing
- `tests/test_main.py` - 15 tests for parse_args and main() routing logic

## Decisions Made
- Preview rendering guard (`if args.preview:`) removed entirely; dev and camera modes always show camera
- run_camera_mode duplicates the loop body from run_dev_mode rather than sharing a helper, keeping each mode self-contained and easy to modify independently
- Routing priority: frozen > --tray > --view-camera > default (dev mode)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- run_camera_mode and --view-camera flag ready for Phase 28 tray subprocess integration
- TrayApp can spawn `python -m gesture_keys --view-camera` to open camera window

---
*Phase: 27-entry-point-refactor*
*Completed: 2026-03-30*

## Self-Check: PASSED
