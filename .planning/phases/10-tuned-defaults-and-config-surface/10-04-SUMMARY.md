---
phase: 10-tuned-defaults-and-config-surface
plan: 04
subsystem: detection
tags: [swipe, settling, hand-tracking, state-machine]

# Dependency graph
requires:
  - phase: 10-03
    provides: "is_activating gate and static-before-swipe priority ordering"
provides:
  - "Hand-entry settling guard in SwipeDetector preventing swipe on approach motion"
  - "suppressed parameter on SwipeDetector.update() for clean is_activating gating"
  - "Non-destructive swipe arm transition preserving static gesture pipeline"
affects: [swipe-detection, detection-loop]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "suppressed keyword-only parameter for clean signal separation (hand absent vs suppressed)"
    - "Hand-entry settling guard reusing existing settling_frames infrastructure"

key-files:
  created: []
  modified:
    - gesture_keys/swipe.py
    - gesture_keys/__main__.py
    - gesture_keys/tray.py
    - tests/test_swipe.py
    - tests/test_integration_mutual_exclusion.py

key-decisions:
  - "suppressed=True skips all SwipeDetector processing without clearing _hand_present, cleanly separating physical absence from suppression"
  - "Removed smoother/debouncer reset on swipe arm transition (only exit reset preserved) to prevent destroying in-progress static classification"
  - "Hand-entry settling reuses existing settling_frames config -- no new config surface needed"

patterns-established:
  - "suppressed kwarg pattern: callers pass suppressed=True instead of faking None landmarks"

requirements-completed: []

# Metrics
duration: 6min
completed: 2026-03-23
---

# Phase 10 Plan 04: Hand-Entry Settling Guard Summary

**SwipeDetector hand-entry settling guard with suppressed parameter, removing destructive pipeline reset on swipe arm transition**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-23T11:42:17Z
- **Completed:** 2026-03-23T11:48:11Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- SwipeDetector now suppresses swipe arming when hand first appears after absence (settling guard on entry)
- suppressed parameter on update() cleanly separates "hand physically absent" from "hand present but deprioritized by debouncer"
- Removed destructive smoother/debouncer reset on swipe arm transition -- static gesture pipeline preserved during swiping
- Both detection loops (__main__.py and tray.py) modified identically

## Task Commits

Each task was committed atomically:

1. **Task 1: Add hand-entry settling guard with suppressed parameter** - `e046862` (test) + `ec5f514` (feat)
2. **Task 2: Remove destructive pipeline reset and wire suppressed flag** - `41a1ddb` (fix)

_Note: Task 1 followed TDD with separate test and implementation commits_

## Files Created/Modified
- `gesture_keys/swipe.py` - Added _hand_present tracking, suppressed kwarg, hand-entry settling logic
- `gesture_keys/__main__.py` - Removed swipe-arm pipeline reset, wired suppressed=debouncer.is_activating
- `gesture_keys/tray.py` - Same changes as __main__.py (identical loop structure)
- `tests/test_swipe.py` - 5 new hand-entry tests, updated existing tests for initial settling
- `tests/test_integration_mutual_exclusion.py` - Updated distance reset test for initial settling

## Decisions Made
- suppressed=True skips all processing without clearing _hand_present -- cleanly separates physical hand absence from debouncer suppression, preventing false settling triggers when is_activating clears
- Removed swipe-arm pipeline reset entirely (not just gated) because static classification is already gated by `if landmarks and not swiping` and smoother naturally decays when fed None
- Hand-entry settling reuses existing settling_frames count (default 3) -- no new config parameter needed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing tests broken by hand-entry settling**
- **Found during:** Task 1 (TDD GREEN phase)
- **Issue:** 5 existing tests assumed immediate ARMED state from fresh detector, but initial hand-entry settling now consumes first 3 frames
- **Fix:** Added stable-position warm-up frames before swipe sequences in affected tests (TestSwipeIsSwiping, TestSwipeReset, TestSwipeSettlingGuard, TestMutualExclusionIntegration)
- **Files modified:** tests/test_swipe.py, tests/test_integration_mutual_exclusion.py
- **Verification:** All 157 tests pass
- **Committed in:** ec5f514 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Test updates necessary for correctness. No scope creep.

## Issues Encountered
- Pre-existing test_config.py failure (config.yaml modified with different key mappings) -- unrelated to this plan, not fixed

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Hand-entry settling guard and suppressed parameter complete
- UAT re-test recommended to verify swipe-preempts-static is resolved
- Both detection loops remain structurally identical for future changes

## Self-Check: PASSED

All 5 modified files exist. All 3 commits (e046862, ec5f514, 41a1ddb) verified in git log.

---
*Phase: 10-tuned-defaults-and-config-surface*
*Completed: 2026-03-23*
