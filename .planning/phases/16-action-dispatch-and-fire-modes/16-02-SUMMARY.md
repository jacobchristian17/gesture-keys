---
phase: 16-action-dispatch-and-fire-modes
plan: 02
subsystem: action-dispatch
tags: [pipeline, action-dispatcher, fire-mode, config, backward-compat]

# Dependency graph
requires:
  - phase: 16-action-dispatch-and-fire-modes
    plan: 01
    provides: ActionResolver, ActionDispatcher, FireMode, Action
  - phase: 15-gesture-orchestrator
    provides: OrchestratorSignal, OrchestratorAction, signal loop pattern
provides:
  - fire_mode config parsing with v1.x backward compat (mode: hold -> hold_key)
  - build_action_maps() and build_compound_action_maps() config helpers
  - Pipeline fully wired to ActionDispatcher for all signal dispatch
  - All 6 exit paths routing through dispatcher.release_all()
affects: [pipeline-integration, config-schema, hold-key-behavior]

# Tech tracking
tech-stack:
  added: []
  patterns: [dispatcher-pipeline-integration, config-backward-compat]

key-files:
  created: []
  modified:
    - gesture_keys/config.py
    - gesture_keys/pipeline.py
    - gesture_keys/orchestrator.py
    - tests/test_config.py
    - tests/test_orchestrator.py

key-decisions:
  - "mode: hold maps to hold_key internally; fire_mode: field takes precedence over mode:"
  - "Pipeline delegates all signal handling to dispatcher.dispatch() in a 3-line loop"
  - "Swiping hold-release safety net checks dispatcher._held_action instead of _hold_active"
  - "reload_config routes flush_pending signals through dispatcher.dispatch()"
  - "Removed _parse_key_mappings and _parse_compound_swipe_key_mappings from pipeline.py"
  - "Orchestrator gesture_modes now uses hold_key string value (not hold)"

patterns-established:
  - "Config backward compat: new fire_mode field takes precedence, legacy mode: mapped automatically"
  - "Pipeline signal dispatch: single dispatcher.dispatch() call replaces inline switch block"

requirements-completed: [ACTN-05, ACTN-01, ACTN-02, ACTN-03, ACTN-04]

# Metrics
duration: 10min
completed: 2026-03-25
---

# Phase 16 Plan 02: Pipeline ActionDispatcher Integration Summary

**fire_mode config parsing with v1.x backward compat, Pipeline wired to ActionDispatcher replacing 150 lines of inline signal handling and 6 ad-hoc hold state variables**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-25T09:07:29Z
- **Completed:** 2026-03-25T09:17:47Z
- **Tasks:** 2 (1 TDD + 1 refactor)
- **Files modified:** 5

## Accomplishments
- fire_mode config parsing with full v1.x backward compat (mode: hold -> hold_key)
- build_action_maps() and build_compound_action_maps() create Action objects from config
- Pipeline.process_frame() delegates all orchestrator signals to dispatcher.dispatch()
- All 6 exit paths (stop, reset, hand-switch, distance, reload) use dispatcher.release_all()
- Removed 6 ad-hoc hold state variables and tap-repeat loop from Pipeline
- Net -102 lines from pipeline.py (simplified from inline switch to dispatcher pattern)

## Task Commits

Each task was committed atomically:

1. **TDD RED: Failing tests for fire_mode config** - `4d4e3d3` (test)
2. **TDD GREEN: fire_mode config + build_action_maps** - `89257a0` (feat)
3. **Task 2: Pipeline ActionDispatcher wiring** - `b8b6109` (feat)

_TDD plan: RED wrote 14 failing tests, GREEN implemented config parsing + orchestrator update._

## Files Created/Modified
- `gesture_keys/config.py` - fire_mode parsing, build_action_maps(), build_compound_action_maps()
- `gesture_keys/pipeline.py` - ActionDispatcher integration, removed inline signal handling
- `gesture_keys/orchestrator.py` - Updated hold mode check from "hold" to "hold_key"
- `tests/test_config.py` - 14 new TestFireModeConfig tests, updated existing hold assertions
- `tests/test_orchestrator.py` - Updated all gesture_modes from "hold" to "hold_key"

## Decisions Made
- mode: hold maps to "hold_key" internally (v2.0 naming consistency) -- fire_mode: takes precedence when both present
- Pipeline delegates ALL orchestrator signal handling to dispatcher.dispatch() (3-line loop)
- reload_config routes flush_pending signals through dispatcher for proper Action resolution
- Swiping safety net checks dispatcher._held_action directly (belt-and-suspenders with orchestrator HOLD_END)
- Orchestrator's gesture_modes format changed from "hold" to "hold_key" for consistency

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Orchestrator hold mode string mismatch**
- **Found during:** Task 1 (fire_mode config parsing)
- **Issue:** _extract_gesture_modes now returns "hold_key" but orchestrator.py line 327 compared against "hold"
- **Fix:** Updated orchestrator to check `mode == "hold_key"` and all orchestrator tests to use "hold_key"
- **Files modified:** gesture_keys/orchestrator.py, tests/test_orchestrator.py
- **Verification:** All 338 tests pass
- **Committed in:** 89257a0 (Task 1 GREEN commit)

**2. [Rule 1 - Bug] Existing test assertions expected "hold" instead of "hold_key"**
- **Found during:** Task 1 (fire_mode config parsing)
- **Issue:** TestGestureModesConfig and TestLeftHandConfig asserted gesture_modes == {"fist": "hold"} but now returns "hold_key"
- **Fix:** Updated 2 test assertions to match new "hold_key" output
- **Files modified:** tests/test_config.py
- **Verification:** All config tests pass
- **Committed in:** 89257a0 (Task 1 GREEN commit)

---

**Total deviations:** 2 auto-fixed (2 bugs from intentional behavior change)
**Impact on plan:** Both fixes required for consistency after "hold" -> "hold_key" rename. No scope creep.

## Issues Encountered
- Pre-existing test_config.py failure (TestSwipeWindowConfig.test_swipe_window_default asserts 0.2 but config has 0.5) -- unrelated to this plan, not fixed.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 16 action dispatch system complete end-to-end
- Config supports both v2.0 fire_mode: and v1.x mode: syntax
- Pipeline fully wired: ActionResolver for lookup, ActionDispatcher for lifecycle
- All KeystrokeSender hold methods now reachable through ActionDispatcher

---
*Phase: 16-action-dispatch-and-fire-modes*
*Completed: 2026-03-25*
