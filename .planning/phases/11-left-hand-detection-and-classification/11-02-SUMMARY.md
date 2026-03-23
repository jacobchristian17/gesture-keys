---
phase: 11-left-hand-detection-and-classification
plan: 02
subsystem: classification
tags: [mediapipe, hand-tracking, handedness, classifier, hand-switch]

# Dependency graph
requires:
  - phase: 11-01
    provides: "HandDetector.detect() returning (landmarks, handedness) tuple"
provides:
  - "Left-hand classification parity verified (7 gestures, all hand-agnostic)"
  - "Hand-switch pipeline reset logic in both main and tray loops"
  - "preferred_hand wired to HandDetector in both detection loops"
affects: [12-hand-indicator, 13-settings-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Hand-switch reset: release holds, reset smoother/debouncer/swipe on L<->R transition"
    - "prev_handedness tracking: only update when hand visible, ignore no-hand gaps"

key-files:
  created: []
  modified:
    - gesture_keys/__main__.py
    - gesture_keys/tray.py
    - tests/conftest.py
    - tests/test_classifier.py
    - tests/test_integration.py
    - tests/test_tray.py

key-decisions:
  - "Classifier confirmed hand-agnostic -- no code changes needed for left-hand classification"
  - "Hand-switch resets all pipeline state (smoother, debouncer, swipe, holds) for clean transition"
  - "prev_handedness only updated when hand is visible to avoid false switches from no-hand gaps"

patterns-established:
  - "Left-hand mirrored fixtures: reflect thumb x-positions around wrist center"
  - "Hand-switch detection pattern: check handedness != prev_handedness with None guards"

requirements-completed: [CLS-01, CLS-02, CLS-03]

# Metrics
duration: 4min
completed: 2026-03-24
---

# Phase 11 Plan 02: Left Hand Classification Parity and Hand-Switch Logic Summary

**Left-hand gesture classification verified hand-agnostic across all 7 gestures with hand-switch pipeline reset wired into both detection loops**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-23T22:08:34Z
- **Completed:** 2026-03-23T22:12:34Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Confirmed classifier is fully hand-agnostic: all 7 left-hand mirrored fixtures classify identically to right-hand
- Hand-switch detection resets smoother, debouncer, swipe detector, and releases holds in both main and tray loops
- preferred_hand config wired to HandDetector constructor in both detection loops
- Updated integration and tray test mocks for new detect() (landmarks, handedness) return type

## Task Commits

Each task was committed atomically:

1. **Task 1: Create left-hand fixtures and verify classification parity** - `96d3b8f` (test)
2. **Task 2: Wire hand-switch logic into both detection loops** - `2f0f463` (feat)

## Files Created/Modified
- `tests/conftest.py` - 7 left-hand mirrored landmark fixtures
- `tests/test_classifier.py` - TestLeftHandClassification with 7 parity tests
- `gesture_keys/__main__.py` - Hand-switch detection, (landmarks, handedness) unpack, preferred_hand
- `gesture_keys/tray.py` - Hand-switch detection, (landmarks, handedness) unpack, preferred_hand
- `tests/test_integration.py` - Updated detect() mock return values to (landmarks, handedness) tuples
- `tests/test_tray.py` - Updated detect() mock return value to ([], None) tuple

## Decisions Made
- Classifier confirmed hand-agnostic: _is_thumb_extended uses abs() and _is_finger_extended uses y-axis only, so no classifier changes needed
- Hand-switch only triggers when both prev_handedness and current handedness are non-None and differ, avoiding false resets from no-hand frames
- prev_handedness preserved through no-hand gaps (only updated when hand visible)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated integration and tray test mocks for new detect() return type**
- **Found during:** Task 2 (wire hand-switch logic)
- **Issue:** Integration tests and tray tests mocked detect() to return bare list instead of (landmarks, handedness) tuple
- **Fix:** Updated detect_side_effect functions to return (landmarks, "Right") or ([], None) tuples
- **Files modified:** tests/test_integration.py, tests/test_tray.py
- **Verification:** All 192 tests pass (excluding 1 pre-existing config test failure)
- **Committed in:** 2f0f463 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Auto-fix necessary for test compatibility with new detect() API. No scope creep.

## Issues Encountered
- 1 pre-existing test failure in test_config.py::TestLoadConfigDefault::test_key_mappings (config.yaml values drifted from test expectations). Out of scope, not caused by this plan's changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 11 complete: left hand detection and classification fully operational
- Both detection loops handle hand switches cleanly
- Ready for Phase 12 (hand indicator UI) or Phase 13 (settings)

---
*Phase: 11-left-hand-detection-and-classification*
*Completed: 2026-03-24*
