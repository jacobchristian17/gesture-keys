---
phase: 19-motiondetector
plan: 01
subsystem: motion-detection
tags: [mediapipe, hysteresis, velocity, wrist-tracking, dataclass]

requires:
  - phase: 18-triggerparser
    provides: Direction enum for cardinal movement directions
provides:
  - MotionDetector class for continuous per-frame motion state reporting
  - MotionState frozen dataclass (moving + direction)
  - Velocity-based hysteresis with arm/disarm thresholds
  - Settling frames for hand-entry false-motion suppression
affects: [20-holddetector, 21-orchestrator]

tech-stack:
  added: []
  patterns: [velocity-hysteresis, continuous-signal-detector, settling-guard]

key-files:
  created:
    - gesture_keys/motion.py
    - tests/test_motion.py
  modified: []

key-decisions:
  - "MotionState uses frozen dataclass with _NOT_MOVING singleton to avoid per-frame allocation"
  - "Direction reused from trigger.py (single source of truth, not duplicated)"
  - "Hysteresis dead zone between disarm and arm thresholds holds current state"

patterns-established:
  - "Continuous detector pattern: update() returns state every frame (never None), unlike event-based SwipeDetector"
  - "Settling guard pattern: suppress N frames after hand entry to prevent false motion from landmark jitter"

requirements-completed: [MOTN-01, MOTN-02, MOTN-03, MOTN-04]

duration: 4min
completed: 2026-03-26
---

# Phase 19 Plan 01: MotionDetector Summary

**Continuous per-frame motion detector with velocity hysteresis, cardinal direction classification, and settling-frame suppression using Direction enum from trigger.py**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-26T08:49:42Z
- **Completed:** 2026-03-26T08:53:42Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- MotionDetector reports moving/not-moving with cardinal direction every frame
- Velocity-based hysteresis prevents flicker (arm_threshold=0.25, disarm_threshold=0.15 gap)
- Settling frames suppress false motion on hand entry (default 3 frames)
- Direction classification rejects diagonals via axis_ratio threshold
- All 20 tests pass covering MOTN-01 through MOTN-04 plus edge cases
- Full test suite green (475/475, 1 pre-existing config test excluded)

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests** - `a84ac7c` (test)
2. **Task 1 GREEN: MotionDetector implementation** - `2fe7f4f` (feat)

_TDD task with RED then GREEN commits._

## Files Created/Modified
- `gesture_keys/motion.py` - MotionDetector class and MotionState dataclass with velocity hysteresis
- `tests/test_motion.py` - 20 tests across 5 test classes (MOTN-01 through MOTN-04 + edge cases)

## Decisions Made
- MotionState uses frozen dataclass with _NOT_MOVING singleton to avoid per-frame allocation
- Direction enum reused from trigger.py (not duplicated) -- single source of truth
- Hysteresis dead zone (velocity between disarm and arm thresholds) holds current state unchanged
- Property setters for all config params follow hot-reload pattern from SwipeDetector

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- MotionDetector ready for orchestrator integration in Phase 21
- Continuous signal model (vs SwipeDetector's event model) enables MOVING_FIRE pattern
- No diagonal support implemented (deferred to ETRIG-01 as specified)

---
*Phase: 19-motiondetector*
*Completed: 2026-03-26*
