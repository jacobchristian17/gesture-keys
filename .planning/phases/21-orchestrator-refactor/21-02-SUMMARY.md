---
phase: 21-orchestrator-refactor
plan: 02
subsystem: orchestrator
tags: [fsm, signals, motion, sequences, tdd]

requires:
  - phase: 21-01
    provides: "Cleaned orchestrator with MOVING_FIRE stub and swipe code removed"
  - phase: 19-motion-detector
    provides: "MotionState frozen dataclass for per-frame motion reporting"
  - phase: 18-trigger-model
    provides: "Direction enum for cardinal directions"
provides:
  - "Orchestrator with 5 action types: FIRE, HOLD_START, HOLD_END, MOVING_FIRE, SEQUENCE_FIRE"
  - "MOVING_FIRE emission during FIRE (tap+moving) and ACTIVE(HOLD)+moving"
  - "SEQUENCE_FIRE emission for registered gesture pairs within configurable time window"
  - "motion_state keyword parameter on update()"
  - "sequence_definitions and sequence_window constructor parameters"
affects: [22-action-resolver, 23-pipeline-wiring]

tech-stack:
  added: []
  patterns: ["dict[Gesture, float] for last-fire timestamp tracking", "_check_sequences after FIRE emission"]

key-files:
  created: []
  modified:
    - gesture_keys/orchestrator.py
    - tests/test_orchestrator.py

key-decisions:
  - "Sequence tracking uses dict[Gesture, float] mapping each gesture to its last FIRE timestamp"
  - "SEQUENCE_FIRE fires only on FIRE signals (not HOLD_START) per user constraint"
  - "_last_fire_time cleared on reset() to prevent stale sequence matches across hand switches"

patterns-established:
  - "Additive signal pattern: MOVING_FIRE and SEQUENCE_FIRE are emitted alongside existing signals, never replacing them"
  - "Sequence window boundary check uses <= (inclusive) for deterministic behavior"

requirements-completed: [ORCH-01, ORCH-02, ORCH-04]

duration: 4min
completed: 2026-03-26
---

# Phase 21 Plan 02: MOVING_FIRE and SEQUENCE_FIRE Signals Summary

**Orchestrator with MOVING_FIRE (gesture+motion) and SEQUENCE_FIRE (two-gesture sequence within configurable 0.5s window) using TDD**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-26T13:49:27Z
- **Completed:** 2026-03-26T13:53:36Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- MOVING_FIRE emitted alongside FIRE on tap and each frame during ACTIVE(HOLD) when motion_state indicates movement with direction
- SEQUENCE_FIRE emitted when registered (A, B) gesture pair fires within sequence_window (default 0.5s, configurable)
- Both standalone FIRE and SEQUENCE_FIRE emitted on sequence completion (additive, not replacing)
- Full TDD: 10 SEQUENCE_FIRE tests, 9 MOVING_FIRE tests, all 85 orchestrator tests green, full suite 482 green

## Task Commits

Each task was committed atomically:

1. **Task 1: Add MOVING_FIRE signal with TDD** - `0e03c84` (feat) - completed in prior session
2. **Task 2 RED: Add failing SEQUENCE_FIRE tests** - `5b970d6` (test)
3. **Task 2 GREEN: Implement SEQUENCE_FIRE signal** - `e5e1a11` (feat)

_Note: Task 1 was completed and committed in a prior session. Task 2 follows TDD with separate RED/GREEN commits._

## Files Created/Modified
- `gesture_keys/orchestrator.py` - Added SEQUENCE_FIRE enum, sequence_definitions/sequence_window constructor params, _check_sequences() method, _last_fire_time tracking
- `tests/test_orchestrator.py` - Added TestSequenceFire class (10 tests), updated TestConstructor and TestTypeDefinitions

## Decisions Made
- Sequence tracking uses `dict[Gesture, float]` for O(1) lookup of last fire time per gesture (per RESEARCH.md Pattern 2)
- SEQUENCE_FIRE only triggers on FIRE signals, not HOLD_START (per user constraint in CONTEXT.md)
- `_last_fire_time` cleared on `reset()` to prevent stale matches across hand switches

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed floating point timestamp precision in RED phase tests**
- **Found during:** Task 2 GREEN phase
- **Issue:** Test timestamps like 2.0-1.6=0.3999... caused activation_delay (0.4) check to fail, preventing gesture FIRE emission
- **Fix:** Adjusted test timestamps from 1.6 to 1.5 (delta 0.5 cleanly > 0.4) across 8 test methods
- **Files modified:** tests/test_orchestrator.py
- **Verification:** All 85 orchestrator tests pass
- **Committed in:** e5e1a11 (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug in test timestamps)
**Impact on plan:** Necessary correction for test correctness. No scope creep.

## Issues Encountered
None beyond the floating point test timestamp fix documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Orchestrator now emits all 5 signal types needed for Phase 22 (ActionResolver)
- OrchestratorSignal has direction (for MOVING_FIRE) and second_gesture (for SEQUENCE_FIRE) fields ready for action resolution
- Full test suite green (482 tests)

---
*Phase: 21-orchestrator-refactor*
*Completed: 2026-03-26*
