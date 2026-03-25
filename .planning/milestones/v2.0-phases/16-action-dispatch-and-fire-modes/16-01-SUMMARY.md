---
phase: 16-action-dispatch-and-fire-modes
plan: 01
subsystem: action-dispatch
tags: [pynput, dataclass, enum, fire-mode, key-lifecycle]

# Dependency graph
requires:
  - phase: 15-gesture-orchestrator
    provides: OrchestratorAction, OrchestratorSignal, FIRE/HOLD_START/HOLD_END/COMPOUND_FIRE signals
provides:
  - FireMode enum (TAP, HOLD_KEY)
  - Action frozen dataclass with pre-parsed key data
  - ActionResolver pure lookup for gesture -> Action (both hands + compound)
  - ActionDispatcher stateful key lifecycle routing signals to KeystrokeSender
  - release_all() idempotent safety mechanism
affects: [16-02, pipeline-integration, config-schema]

# Tech tracking
tech-stack:
  added: []
  patterns: [resolver-dispatcher, held-action-single-source-of-truth]

key-files:
  created:
    - gesture_keys/action.py
    - tests/test_action.py
  modified: []

key-decisions:
  - "FIRE signal always uses sender.send() regardless of fire_mode (tap behavior)"
  - "HOLD_START only activates hold behavior when fire_mode == HOLD_KEY"
  - "_held_action is None when no key is held (single source of truth)"
  - "ActionResolver uses separate dicts for compound vs simple actions"

patterns-established:
  - "Resolver-Dispatcher: pure lookup (ActionResolver) separated from stateful dispatch (ActionDispatcher)"
  - "Single held-action field prevents state desync vs multiple boolean flags"

requirements-completed: [ACTN-01, ACTN-02, ACTN-03, ACTN-04]

# Metrics
duration: 3min
completed: 2026-03-25
---

# Phase 16 Plan 01: ActionResolver and ActionDispatcher Summary

**ActionResolver pure lookup + ActionDispatcher with held-key lifecycle routing orchestrator signals through FireMode (TAP/HOLD_KEY) to KeystrokeSender**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-25T09:01:50Z
- **Completed:** 2026-03-25T09:04:56Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 2

## Accomplishments
- FireMode enum (TAP, HOLD_KEY) and Action frozen dataclass with pre-parsed key data
- ActionResolver maps gesture names to Actions for both hands with compound gesture support
- ActionDispatcher routes FIRE/HOLD_START/HOLD_END/COMPOUND_FIRE to correct KeystrokeSender methods
- release_all() clears all state and releases keys, idempotent and safe for all exit paths
- 23 unit tests covering all signal types, edge cases, and stuck-key prevention

## Task Commits

Each task was committed atomically:

1. **TDD RED: Failing tests** - `562ecc3` (test)
2. **TDD GREEN: Implementation** - `94026c5` (feat)

_TDD plan: RED wrote 23 failing tests, GREEN implemented to pass all._

## Files Created/Modified
- `gesture_keys/action.py` - FireMode, Action, ActionResolver, ActionDispatcher (184 lines)
- `tests/test_action.py` - Unit tests: resolver, tap, hold_key, compound, release_all (306 lines)

## Decisions Made
- FIRE signal always uses sender.send() regardless of fire_mode -- FIRE is tap behavior from orchestrator
- HOLD_START only activates hold when Action.fire_mode == HOLD_KEY; tap-mode gestures ignore HOLD_START
- Single _held_action field (None when idle) replaces multiple boolean flags from Pipeline
- ActionResolver uses separate dicts for simple vs compound lookups (no key collision risk)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SwipeDirection enum member names are UPPERCASE**
- **Found during:** TDD GREEN (test execution)
- **Issue:** Plan's interface section showed lowercase `swipe_left` but actual enum uses `SWIPE_LEFT`
- **Fix:** Updated test to use `SwipeDirection.SWIPE_LEFT` instead of `SwipeDirection.swipe_left`
- **Files modified:** tests/test_action.py
- **Verification:** All 23 tests pass
- **Committed in:** 94026c5 (GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor naming fix. No scope creep.

## Issues Encountered
- Pre-existing test_config.py failure (TestSwipeWindowConfig.test_swipe_window_default asserts 0.2 but config has 0.5) -- unrelated to this plan, not fixed.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ActionResolver and ActionDispatcher ready for Pipeline integration (Plan 16-02)
- Config schema update (ACTN-05) needed to build Action maps from config.yaml
- All KeystrokeSender hold methods (press_and_hold, release_held, release_all) now wired through ActionDispatcher

---
*Phase: 16-action-dispatch-and-fire-modes*
*Completed: 2026-03-25*
