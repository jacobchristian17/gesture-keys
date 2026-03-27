---
phase: 21-orchestrator-refactor
plan: 01
subsystem: orchestrator
tags: [fsm, state-machine, refactor, lifecycle]

requires:
  - phase: 18-trigger-model
    provides: Direction enum in trigger.py
provides:
  - Simplified orchestrator FSM with 4 lifecycle states (IDLE, ACTIVATING, ACTIVE, COOLDOWN)
  - Clean foundation for MOVING_FIRE and SEQUENCE_FIRE signals in Plan 02
affects: [21-02, pipeline, action-dispatcher]

tech-stack:
  added: []
  patterns:
    - "Orchestrator uses Direction from trigger.py instead of SwipeDirection"

key-files:
  created: []
  modified:
    - gesture_keys/orchestrator.py
    - tests/test_orchestrator.py
    - gesture_keys/action.py
    - tests/test_action.py
    - gesture_keys/pipeline.py
    - tests/test_pipeline.py
    - tests/test_activation.py

key-decisions:
  - "Removed COMPOUND_FIRE from ActionDispatcher alongside orchestrator cleanup to maintain passing test suite"
  - "Kept DebounceState.SWIPE_WINDOW enum value as legacy (commented) to avoid breaking preview.py string comparisons"
  - "Simplified flush_pending() to always return empty result since SWIPE_WINDOW no longer exists"

patterns-established:
  - "Orchestrator lifecycle: IDLE -> ACTIVATING -> ACTIVE -> COOLDOWN (no SWIPE_WINDOW)"
  - "Orchestrator temporal states: CONFIRMED, HOLD (no SWIPING)"

requirements-completed: [ORCH-03]

duration: 6min
completed: 2026-03-26
---

# Phase 21 Plan 01: Strip Swipe Code Summary

**Stripped all swipe-related code from orchestrator FSM leaving simplified 4-state lifecycle with tap and hold modes, plus downstream fixes in action.py and pipeline.py**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-26T13:36:22Z
- **Completed:** 2026-03-26T13:42:37Z
- **Tasks:** 2
- **Files modified:** 8 (including 1 deleted)

## Accomplishments
- Removed SWIPE_WINDOW lifecycle state, SWIPING temporal state, and COMPOUND_FIRE action from orchestrator
- Removed swipe_direction/swiping parameters from update(), suppress_standalone_swipe from OrchestratorResult
- Deleted _handle_swiping_transitions() and _handle_swipe_window() methods entirely
- Replaced SwipeDirection import with Direction from trigger.py
- Zero "swipe" references in orchestrator.py and test_orchestrator.py
- Full test suite green (461 tests pass)

## Task Commits

Each task was committed atomically:

1. **Task 1: Strip swipe code from orchestrator.py** - `7f1e5c3` (feat)
2. **Task 2: Update test_orchestrator.py and fix downstream** - `3cd0323` (feat)

## Files Created/Modified
- `gesture_keys/orchestrator.py` - Simplified FSM: 4 lifecycle states, 2 temporal states, 3 actions
- `tests/test_orchestrator.py` - 64 tests remaining, all swipe tests deleted
- `gesture_keys/action.py` - Removed COMPOUND_FIRE handler
- `tests/test_action.py` - Removed TestCompoundFire class and SwipeDirection import
- `tests/test_compound_gesture.py` - DELETED (all tests referenced removed flow)
- `gesture_keys/pipeline.py` - Removed swipe_direction/swiping kwargs from orchestrator.update(), removed SWIPE_WINDOW mapping and suppress_standalone_swipe check
- `tests/test_pipeline.py` - Removed SWIPE_WINDOW mapping test
- `tests/test_activation.py` - Updated docstring removing COMPOUND_FIRE reference

## Decisions Made
- Removed COMPOUND_FIRE from ActionDispatcher alongside orchestrator cleanup to keep full test suite passing
- Kept DebounceState.SWIPE_WINDOW enum value as legacy comment to avoid breaking any downstream string comparisons in preview.py
- Simplified flush_pending() to always return empty result (no SWIPE_WINDOW to flush)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed downstream COMPOUND_FIRE references in action.py**
- **Found during:** Task 2 (full test suite verification)
- **Issue:** action.py and test_action.py referenced OrchestratorAction.COMPOUND_FIRE which no longer exists
- **Fix:** Removed _handle_compound_fire() from ActionDispatcher, deleted TestCompoundFire test class, removed SwipeDirection import
- **Files modified:** gesture_keys/action.py, tests/test_action.py
- **Verification:** Full test suite passes
- **Committed in:** 3cd0323

**2. [Rule 3 - Blocking] Fixed pipeline.py orchestrator.update() call signature**
- **Found during:** Task 2 (full test suite verification)
- **Issue:** pipeline.py passed swipe_direction and swiping kwargs to orchestrator.update() which no longer accepts them
- **Fix:** Removed kwargs from update() call, removed SWIPE_WINDOW mapping from _map_to_debounce_state, removed in_swipe_window unmapped direction reset logic, removed suppress_standalone_swipe check
- **Files modified:** gesture_keys/pipeline.py, tests/test_pipeline.py
- **Verification:** Full test suite passes
- **Committed in:** 3cd0323

**3. [Rule 3 - Blocking] Deleted test_compound_gesture.py**
- **Found during:** Task 2 (full test suite verification)
- **Issue:** Entire test file tested compound gesture flow using removed COMPOUND_FIRE, SWIPE_WINDOW, and SwipeDirection
- **Fix:** Deleted the file via git rm
- **Files modified:** tests/test_compound_gesture.py (deleted)
- **Verification:** Full test suite passes
- **Committed in:** 3cd0323

---

**Total deviations:** 3 auto-fixed (3 blocking)
**Impact on plan:** All auto-fixes necessary to achieve the plan's stated success criterion of "full test suite green." No scope creep -- strictly removed downstream references to the same swipe code stripped from orchestrator.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Orchestrator FSM is clean with 4 lifecycle states, ready for MOVING_FIRE and SEQUENCE_FIRE signal additions in Plan 02
- Direction enum already imported from trigger.py, prepared for direction-aware signals
- All 461 tests passing

---
*Phase: 21-orchestrator-refactor*
*Completed: 2026-03-26*
