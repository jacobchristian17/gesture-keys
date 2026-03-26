---
phase: 24-cleanup-and-config-migration
plan: 01
subsystem: config
tags: [yaml, config, cleanup, legacy-removal]

requires:
  - phase: 23-pipeline-integration
    provides: Pipeline using actions-based config path and MotionDetector

provides:
  - Clean codebase with no legacy swipe/gestures code paths
  - Actions-only config loading (no dual-path logic)
  - Renamed sequence_window config field (replacing swipe_window)

affects: []

tech-stack:
  added: []
  patterns:
    - Actions-only config: load_config requires actions: section, no legacy fallback

key-files:
  created: []
  modified:
    - gesture_keys/config.py
    - gesture_keys/pipeline.py
    - gesture_keys/__main__.py
    - config.yaml
    - tests/test_config.py
    - tests/test_pipeline.py
    - tests/test_activation.py
    - tests/test_integration.py
    - tests/test_tray.py

key-decisions:
  - "Actions-only config: removed legacy gestures:/swipe: path entirely rather than keeping backward compat"
  - "sequence_window replaces swipe_window with default 0.5s from YAML (0.2s AppConfig default)"

patterns-established:
  - "Config schema: actions: section is the sole entry point for gesture-to-key mappings"

requirements-completed: [CLNP-01, CLNP-02, CLNP-03]

duration: 8min
completed: 2026-03-27
---

# Phase 24 Plan 01: Cleanup and Config Migration Summary

**Delete all legacy swipe code and config paths, leaving clean actions-only codebase with 405 passing tests**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-26T20:55:49Z
- **Completed:** 2026-03-26T21:04:17Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Deleted gesture_keys/swipe.py, tests/test_swipe.py, tests/test_integration_mutual_exclusion.py (1,300+ LOC removed)
- Removed 10 legacy AppConfig fields and 8 legacy helper functions from config.py (900+ LOC removed)
- Simplified load_config to actions-only path with no dual gestures:/actions: logic
- Renamed swipe_window to sequence_window throughout codebase and config.yaml
- Updated all test files to use actions: format YAML fixtures

## Task Commits

Each task was committed atomically:

1. **Task 1: Delete swipe files and remove swipe references from pipeline and tests** - `62bae38` (feat)
2. **Task 2: Remove legacy config code and clean test_config.py** - `7b6e748` (feat)

## Files Created/Modified
- `gesture_keys/swipe.py` - Deleted (legacy SwipeDetector)
- `tests/test_swipe.py` - Deleted (SwipeDetector tests)
- `tests/test_integration_mutual_exclusion.py` - Deleted (swipe/static mutual exclusion tests)
- `gesture_keys/config.py` - Removed legacy fields, functions, and dual-path load_config
- `gesture_keys/pipeline.py` - Use config.actions for thresholds, sequence_window rename
- `gesture_keys/__main__.py` - Banner shows action count instead of gesture count
- `config.yaml` - Renamed swipe_window to sequence_window
- `tests/test_config.py` - Removed 6 legacy test classes, rewritten fixtures to actions: format
- `tests/test_pipeline.py` - Removed legacy mock config fields
- `tests/test_activation.py` - Rewritten config fixtures to actions: format
- `tests/test_integration.py` - Updated banner assertion from "gestures loaded" to "actions loaded"
- `tests/test_tray.py` - Removed gestures= kwarg from AppConfig construction

## Decisions Made
- Actions-only config: removed legacy gestures:/swipe: path entirely rather than keeping backward compat
- sequence_window replaces swipe_window with 0.5s default from YAML

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated test_activation.py config fixtures**
- **Found during:** Task 2 (full test suite verification)
- **Issue:** test_activation.py used gestures: YAML format in _write_config helper and inline fixtures
- **Fix:** Rewrote to use actions: format, renamed per_gesture_bypass tests to per_action_bypass
- **Files modified:** tests/test_activation.py
- **Verification:** All activation tests pass
- **Committed in:** 7b6e748 (Task 2 commit)

**2. [Rule 3 - Blocking] Updated test_integration.py banner assertion**
- **Found during:** Task 2 (full test suite verification)
- **Issue:** test_integration.py expected "gestures loaded" in banner, now says "actions loaded"
- **Fix:** Changed assertion string
- **Files modified:** tests/test_integration.py
- **Committed in:** 7b6e748 (Task 2 commit)

**3. [Rule 3 - Blocking] Updated test_tray.py AppConfig construction**
- **Found during:** Task 2 (full test suite verification)
- **Issue:** test_tray.py passed gestures= kwarg to AppConfig which no longer has that field
- **Fix:** Removed gestures kwarg, use default AppConfig()
- **Files modified:** tests/test_tray.py
- **Committed in:** 7b6e748 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 blocking)
**Impact on plan:** All auto-fixes were necessary to keep the full test suite passing after removing legacy fields. No scope creep.

## Issues Encountered
None.

## Known Stubs
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Codebase is clean: no legacy swipe code, no dual config paths
- All 405 tests pass with actions-only config loading
- Ready for any future phases that build on the v3.0 tri-state architecture

---
*Phase: 24-cleanup-and-config-migration*
*Completed: 2026-03-27*
