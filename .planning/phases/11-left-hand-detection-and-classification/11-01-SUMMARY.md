---
phase: 11-left-hand-detection-and-classification
plan: 01
subsystem: detection
tags: [mediapipe, hand-tracking, handedness, active-hand]

# Dependency graph
requires: []
provides:
  - "HandDetector.detect() returning (landmarks, handedness) tuple"
  - "Active hand selection logic (sticky, preferred, transition)"
  - "preferred_hand config field in AppConfig"
  - "HandDetector.reset() method for state resets"
affects: [11-02, main-loop-integration, tray-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Active hand selection: single-hand auto-select, two-hand sticky, startup preferred"
    - "Transition frame: empty return when active hand disappears while other present"

key-files:
  created: []
  modified:
    - gesture_keys/detector.py
    - gesture_keys/config.py
    - tests/test_detector.py
    - tests/test_config.py
    - config.yaml

key-decisions:
  - "Used dict-based hand lookup from MediaPipe results for O(1) active hand selection"
  - "Transition frame returns ([], None) to prevent jitter during hand switches"
  - "preferred_hand stored as capitalized label internally to match MediaPipe format"

patterns-established:
  - "detect() returns tuple (landmarks, handedness_label) instead of bare list"
  - "Active hand state tracked in HandDetector instance, reset via reset()"

requirements-completed: [DET-01, DET-02, DET-03]

# Metrics
duration: 5min
completed: 2026-03-24
---

# Phase 11 Plan 01: Left Hand Detection Summary

**HandDetector extended with active hand selection logic, (landmarks, handedness) return tuple, and configurable preferred_hand defaulting to left**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-23T21:59:47Z
- **Completed:** 2026-03-24T22:05:26Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 5

## Accomplishments
- HandDetector.detect() returns (landmarks, handedness) tuple instead of bare list
- Active hand selection: single hand auto-selects, both hands stick with current, startup selects preferred
- Transition frame returns empty when active hand disappears while other is present
- preferred_hand config field with validation (must be "left" or "right")
- reset() method added for hand-switch state resets needed by Plan 02
- 10 new detector tests and 5 new config tests all passing

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for hand detection and active hand selection** - `5fa3045` (test)
2. **Task 1 (GREEN): Extend HandDetector with active hand selection** - `ae70f3c` (feat)

## Files Created/Modified
- `gesture_keys/detector.py` - HandDetector with active hand selection, (landmarks, handedness) return, reset()
- `gesture_keys/config.py` - AppConfig.preferred_hand field, validation in load_config()
- `tests/test_detector.py` - 10 new tests for hand selection scenarios (left, right, both, sticky, transition, reset)
- `tests/test_config.py` - 5 new tests for preferred_hand parsing, defaults, and validation
- `config.yaml` - Documented preferred_hand option (commented out, defaults to left)

## Decisions Made
- Used dict-based hand lookup from MediaPipe results for cleaner active hand selection
- Transition frame returns ([], None) rather than immediately switching to prevent hand-switch jitter
- preferred_hand stored as capitalized string internally ("Left"/"Right") to match MediaPipe category_name format

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- 3 pre-existing test failures in test_config.py (test_key_mappings, test_default_config_has_timing_fields, test_load_config_settling_frames_from_default_config) due to config.yaml values drifting from test expectations. These are out of scope and not caused by this plan's changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- HandDetector API is ready for Plan 02 integration into main loop and tray
- Downstream consumers (__main__.py, tray.py) need updating to unpack the new (landmarks, handedness) tuple
- reset() method available for hand-switch state resets in Plan 02

---
*Phase: 11-left-hand-detection-and-classification*
*Completed: 2026-03-24*
