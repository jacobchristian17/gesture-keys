---
phase: 20-config-loader-for-actions
plan: 02
subsystem: config
tags: [yaml, dataclass, action-library, derive, load-config]

# Dependency graph
requires:
  - phase: 20-config-loader-for-actions
    provides: "ActionEntry dataclass, parse_actions() function"
provides:
  - "DerivedConfig frozen dataclass for orchestrator inputs"
  - "derive_from_actions() converting ActionEntry list to gesture_modes, cooldowns, bypass, action maps"
  - "load_config() actions: path with mutual exclusion enforcement"
  - "config.yaml converted to actions: format"
affects: [20-03, 20-04, 21-orchestrator-integration, 22-action-resolver]

# Tech tracking
tech-stack:
  added: []
  patterns: ["DerivedConfig as intermediate derivation output", "actions: path in load_config with legacy fallback"]

key-files:
  created: []
  modified:
    - gesture_keys/config.py
    - gesture_keys/pipeline.py
    - config.yaml
    - tests/test_config.py
    - tests/test_pipeline.py

key-decisions:
  - "Fire mode inferred from trigger state: static->tap, holding->hold_key, moving->tap, sequence->tap"
  - "DerivedConfig is frozen dataclass to prevent accidental mutation"
  - "Mutual exclusion: actions: and gestures:/swipe: cannot coexist in same config"
  - "Left-hand parsing removed now (not deferred) per user decision"
  - "Old swipe settings preserved in motion: YAML section for Phase 23 consumption"

patterns-established:
  - "derive_from_actions() pattern: iterate entries, infer fire_mode, build Action maps, collect cooldowns/bypass"
  - "Two-path config loading: actions: (new) vs gestures:/swipe: (legacy fallback)"

requirements-completed: [CONF-04, CONF-05]

# Metrics
duration: 6min
completed: 2026-03-26
---

# Phase 20 Plan 02: Derive and Wire Actions into load_config Summary

**derive_from_actions() with DerivedConfig, actions: path in load_config, config.yaml conversion to actions format, left-hand parsing removal**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-26T09:58:48Z
- **Completed:** 2026-03-26T10:05:37Z
- **Tasks:** 2 (Task 1: TDD RED+GREEN, Task 2: integration)
- **Files modified:** 5

## Accomplishments
- DerivedConfig frozen dataclass with gesture_modes, gesture_cooldowns, activation_gate_bypass, right_actions, left_actions
- derive_from_actions() infers fire mode from trigger state and builds per-hand Action maps
- load_config() supports new actions: path with automatic derivation, enforces mutual exclusion with legacy format
- config.yaml converted from gestures:/swipe: to actions: format with 11 action entries
- Removed all left_gestures/left_swipe parsing code and AppConfig fields
- 499 tests pass with 0 regressions

## Task Commits

Each task was committed atomically:

1. **TDD RED: Failing tests for derive_from_actions** - `bd353e9` (test)
2. **TDD GREEN: Implement derive_from_actions and DerivedConfig** - `61cd4d4` (feat)
3. **Task 2: Wire into load_config, remove left-hand, convert config.yaml** - `2fb8fd4` (feat)

_Note: TDD task with RED and GREEN commits. REFACTOR skipped - code already clean._

## Files Created/Modified
- `gesture_keys/config.py` - Added DerivedConfig, derive_from_actions(), updated load_config() with actions: path, removed left-hand fields/parsing
- `gesture_keys/pipeline.py` - Removed left-hand override references in start() and reload_config()
- `config.yaml` - Converted to actions: format with 11 entries, added motion: section
- `tests/test_config.py` - Added TestDeriveFromActions (10 tests), TestLoadConfigActions (8 tests), updated TestLoadConfigDefault, removed TestLeftHandConfig/TestLeftHandSwipeMerge
- `tests/test_pipeline.py` - Removed left-hand field references from mock config

## Decisions Made
- Fire mode inference: static->tap, holding->hold_key, moving->tap, sequence->tap (matches plan specification)
- DerivedConfig uses frozen=True for immutability consistency with ActionEntry
- Mutual exclusion check covers both gestures: and swipe: as legacy indicators
- Left-hand parsing removed immediately per user decision (not deferred to Phase 24)
- Motion detection settings (settling_frames, min_velocity, etc.) preserved in new motion: YAML section for Phase 23

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing TriggerState import in config.py**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** derive_from_actions() referenced TriggerState but it was not imported
- **Fix:** Added TriggerState to imports from gesture_keys.trigger
- **Files modified:** gesture_keys/config.py
- **Verification:** All tests pass
- **Committed in:** 61cd4d4 (part of GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Missing import was a trivial oversight. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- DerivedConfig and derive_from_actions() ready for plan 03 (pipeline integration with new action maps)
- config.yaml converted; downstream phases can consume actions: format
- Legacy fallback path preserved for backward compatibility

---
*Phase: 20-config-loader-for-actions*
*Completed: 2026-03-26*
