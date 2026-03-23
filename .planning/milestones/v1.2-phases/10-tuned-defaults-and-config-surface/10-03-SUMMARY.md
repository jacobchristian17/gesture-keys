---
phase: 10-tuned-defaults-and-config-surface
plan: 03
subsystem: detection
tags: [debounce, swipe, priority, state-machine]

requires:
  - phase: 10-01
    provides: tuned defaults for activation_delay and smoothing_window
  - phase: 10-02
    provides: settling_frames config surface and per-gesture cooldowns
provides:
  - debouncer.is_activating property for static gesture priority
  - is_swiping scoped to ARMED-only (COOLDOWN no longer suppresses static)
  - static-first priority gate in both detection loops
affects: [UAT, tray, main-loop]

tech-stack:
  added: []
  patterns: [static-first priority gate, debouncer-gated swipe arming]

key-files:
  created: []
  modified:
    - gesture_keys/debounce.py
    - gesture_keys/swipe.py
    - gesture_keys/__main__.py
    - gesture_keys/tray.py
    - tests/test_debounce.py
    - tests/test_swipe.py
    - tests/test_integration_mutual_exclusion.py

key-decisions:
  - "is_swiping scoped to ARMED-only so COOLDOWN does not suppress static gestures"
  - "Static classification runs before swipe detection for priority"
  - "debouncer.is_activating gates swipe arming with None landmarks"

patterns-established:
  - "Static-first priority: classify+debounce before swipe in detection loop"
  - "Debouncer-gated swipe: is_activating suppresses swipe arming"

requirements-completed: [TUNE-01]

duration: 4min
completed: 2026-03-23
---

# Phase 10 Plan 03: Static Gesture Priority Summary

**Static-first priority gate: debouncer.is_activating suppresses swipe arming, is_swiping narrowed to ARMED-only**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-23T11:07:43Z
- **Completed:** 2026-03-23T11:11:31Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Added is_activating property on GestureDebouncer exposing ACTIVATING state
- Narrowed is_swiping to ARMED-only so swipe COOLDOWN no longer blocks static detection
- Restructured both detection loops (__main__.py and tray.py) with static-first priority
- Swipe arming suppressed when debouncer is in ACTIVATING state

## Task Commits

Each task was committed atomically:

1. **Task 1: Add debouncer is_activating property and fix swipe is_swiping scope (TDD)**
   - `198a252` (test: failing tests for is_activating and is_swiping scope)
   - `048b30d` (feat: add is_activating property and fix is_swiping to ARMED-only)
2. **Task 2: Add static-first priority gate in both detection loops** - `7624fed` (feat)

## Files Created/Modified
- `gesture_keys/debounce.py` - Added is_activating read-only property
- `gesture_keys/swipe.py` - Changed is_swiping to ARMED-only (removed COOLDOWN)
- `gesture_keys/__main__.py` - Restructured loop: static classification before swipe detection
- `gesture_keys/tray.py` - Identical loop restructuring as __main__.py
- `tests/test_debounce.py` - Tests for is_activating in all 4 debounce states
- `tests/test_swipe.py` - Updated test: is_swiping False during COOLDOWN
- `tests/test_integration_mutual_exclusion.py` - Updated integration tests for ARMED-only semantics

## Decisions Made
- is_swiping returns True only for ARMED state (not COOLDOWN) -- COOLDOWN should not suppress static gestures since the swipe has already fired
- Static classification + debounce runs before swipe detection so debouncer state is available for gating
- When debouncer.is_activating is True, swipe detector receives None landmarks (cannot arm)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated integration tests for new is_swiping semantics**
- **Found during:** Task 2
- **Issue:** Integration tests in test_integration_mutual_exclusion.py asserted is_swiping=True during COOLDOWN (old behavior)
- **Fix:** Updated 3 assertions to expect is_swiping=False during COOLDOWN and updated docstrings
- **Files modified:** tests/test_integration_mutual_exclusion.py
- **Verification:** All 199 tests pass
- **Committed in:** 7624fed (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary test update for behavioral change. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Static gesture priority fix complete, ready for UAT re-test
- Both detection loops (__main__.py and tray.py) are synchronized

---
*Phase: 10-tuned-defaults-and-config-surface*
*Completed: 2026-03-23*
