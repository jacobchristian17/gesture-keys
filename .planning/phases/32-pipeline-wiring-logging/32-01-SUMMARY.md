---
phase: 32-pipeline-wiring-logging
plan: 01
subsystem: pipeline
tags: [scroll, pipeline, wiring, lifecycle, ema]

# Dependency graph
requires:
  - phase: 31-dispatcher-integration
    provides: "ActionDispatcher scroll_sender kwarg and scroll dispatch branch"
  - phase: 29-scroll-sender
    provides: "ScrollSender class with direction routing, velocity-proportional ticks, EMA smoothing"
provides:
  - "ScrollSender wired into Pipeline.start(), reload_config(), reset_pipeline()"
  - "Scroll override maps passed to ActionResolver in start() and reload_config()"
  - "Scroll debug logging active at runtime via existing ScrollSender.scroll() logger.debug"
affects: [end-to-end-scroll, config-validation]

# Tech tracking
tech-stack:
  added: []
  patterns: ["ScrollSender lifecycle mirrors KeystrokeSender pattern in Pipeline"]

key-files:
  created: []
  modified:
    - gesture_keys/pipeline.py
    - tests/test_pipeline.py

key-decisions:
  - "Explicit scroll_sender.reset() in reset_pipeline() even though release_all() also resets -- ensures EMA cleared regardless of dispatcher internals"

patterns-established:
  - "Scroll wiring follows same lifecycle pattern as KeystrokeSender: instantiate in start(), inject into dispatcher, reset in reset_pipeline() and reload_config()"

requirements-completed: [SCROLL-11]

# Metrics
duration: 3min
completed: 2026-04-01
---

# Phase 32 Plan 01: Pipeline Wiring & Logging Summary

**ScrollSender wired into Pipeline lifecycle with instantiation, dispatcher injection, resolver scroll overrides, and EMA reset on hot-reload/reset**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-01T12:58:07Z
- **Completed:** 2026-04-01T13:01:33Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- ScrollSender instantiated in Pipeline.start() and injected into ActionDispatcher
- Scroll speed/min_ticks/max_ticks override maps passed to ActionResolver in both start() and reload_config()
- Scroll EMA state reset in both reset_pipeline() and reload_config()
- 6 new tests covering scroll wiring lifecycle (27 total pipeline tests pass)

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire ScrollSender into Pipeline.start() and ActionDispatcher** - `383e456` (feat)
2. **Task 2: Add tests for scroll wiring in Pipeline** - `34d4c15` (test)

## Files Created/Modified
- `gesture_keys/pipeline.py` - ScrollSender import, instantiation in start(), injection into ActionDispatcher, scroll overrides to ActionResolver, reset in reset_pipeline() and reload_config()
- `tests/test_pipeline.py` - 6 new scroll wiring tests plus updated existing reset test for scroll_sender mock

## Decisions Made
- Explicit scroll_sender.reset() in reset_pipeline() even though dispatcher's release_all() also resets internally -- ensures EMA state is cleared regardless of dispatcher path changes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing reset test to include scroll_sender mock**
- **Found during:** Task 1 (Pipeline wiring)
- **Issue:** Existing test_reset_pipeline_resets_components failed because it didn't mock the new _scroll_sender field
- **Fix:** Added `pipeline._scroll_sender = MagicMock()` and assertion for `scroll_sender.reset.assert_called_once()`
- **Files modified:** tests/test_pipeline.py
- **Verification:** All 21 existing tests pass
- **Committed in:** 383e456 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary fix for test correctness after adding scroll_sender to reset_pipeline(). No scope creep.

## Issues Encountered
- Pre-existing test failure in tests/test_tray.py::TestEditConfigOpensFile (unrelated to scroll changes, verified by running test on clean main branch)

## Known Stubs
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ScrollSender is now fully wired end-to-end: config parsing (Phase 30) -> ActionDispatcher scroll dispatch (Phase 31) -> Pipeline lifecycle (Phase 32)
- Ready for end-to-end manual testing of scroll gestures

---
*Phase: 32-pipeline-wiring-logging*
*Completed: 2026-04-01*
