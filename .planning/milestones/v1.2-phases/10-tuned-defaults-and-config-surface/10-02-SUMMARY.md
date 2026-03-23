---
phase: 10-tuned-defaults-and-config-surface
plan: 02
subsystem: config
tags: [debounce, cooldown, per-gesture, yaml, config]

requires:
  - phase: 10-tuned-defaults-and-config-surface
    provides: "tuned defaults and settling_frames config surface (Plan 01)"
provides:
  - "Per-gesture cooldown overrides parsed from config.yaml gesture entries"
  - "Debouncer per-gesture cooldown lookup with global fallback"
  - "gesture_cooldowns wired in both __main__.py and tray.py with hot-reload"
  - "Commented config.yaml example showing per-gesture cooldown syntax"
affects: []

tech-stack:
  added: []
  patterns:
    - "Per-gesture config: extract from nested gesture dict, pass as flat dict to consumer"

key-files:
  created: []
  modified:
    - gesture_keys/config.py
    - gesture_keys/debounce.py
    - gesture_keys/__main__.py
    - gesture_keys/tray.py
    - config.yaml
    - tests/test_config.py
    - tests/test_debounce.py

key-decisions:
  - "Per-gesture cooldowns use gesture.value (string name) as dict key for config simplicity"
  - "Cooldown duration stored per-fire in _cooldown_duration_active to avoid state leakage"

patterns-established:
  - "Per-item config override: extract from nested config dict, pass flat dict to component, use .get() with global fallback"

requirements-completed: [TUNE-03]

duration: 3min
completed: 2026-03-23
---

# Phase 10 Plan 02: Per-Gesture Cooldown Overrides Summary

**Per-gesture cooldown overrides via config.yaml with debouncer lookup fallback to global cooldown_duration**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-23T10:17:34Z
- **Completed:** 2026-03-23T10:20:35Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Per-gesture cooldown overrides parsed from config.yaml gesture entries (e.g., pinch.cooldown: 0.6)
- Debouncer uses per-gesture cooldown when available, falls back to global cooldown_duration
- Both __main__.py and tray.py pass gesture_cooldowns to constructor and update on hot-reload
- config.yaml has commented example under pinch showing per-gesture cooldown syntax
- All 195 tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Per-gesture cooldown config parsing and debouncer lookup** - `b419c70` (feat, TDD)
2. **Task 2: Wire per-gesture cooldowns to both loops + config.yaml examples** - `4a0bc56` (feat)

## Files Created/Modified
- `gesture_keys/config.py` - Added gesture_cooldowns field, _extract_gesture_cooldowns helper, wired in load_config
- `gesture_keys/debounce.py` - Added gesture_cooldowns param, per-fire _cooldown_duration_active, updated _handle_fired/_handle_cooldown
- `gesture_keys/__main__.py` - Wired gesture_cooldowns to debouncer constructor and hot-reload
- `gesture_keys/tray.py` - Wired gesture_cooldowns to debouncer constructor and hot-reload
- `config.yaml` - Added commented cooldown example under pinch gesture
- `tests/test_config.py` - Added TestGestureCooldownsConfig class (5 tests)
- `tests/test_debounce.py` - Added TestPerGestureCooldowns class (4 tests)

## Decisions Made
- Per-gesture cooldowns use gesture.value (string name) as dict key for config simplicity
- Cooldown duration stored per-fire in _cooldown_duration_active to avoid state leakage between different gesture fires

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 10 (Tuned Defaults and Config Surface) is now complete
- All tuning values are code defaults, config.yaml ships with optimal values
- Per-gesture cooldown overrides available for power users

---
*Phase: 10-tuned-defaults-and-config-surface*
*Completed: 2026-03-23*
