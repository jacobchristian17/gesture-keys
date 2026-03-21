---
phase: 02-gesture-to-keystroke-pipeline
plan: 02
subsystem: gesture-processing
tags: [config, hot-reload, main-loop, debounce-wiring, keystroke-wiring, pynput]

requires:
  - phase: 02-gesture-to-keystroke-pipeline
    provides: GestureDebouncer and KeystrokeSender from plan 01
  - phase: 01-detection-and-preview
    provides: HandDetector, GestureClassifier, GestureSmoother, preview loop
provides:
  - Extended AppConfig with activation_delay and cooldown_duration timing fields
  - ConfigWatcher for mtime-based hot-reload with polling interval
  - Complete main loop wiring debouncer + keystroke sender + config watcher
  - Human-verified end-to-end gesture-to-keystroke pipeline
affects: [03-polish-and-packaging]

tech-stack:
  added: []
  patterns: [mtime-polling-hot-reload, pre-parsed-key-mappings, graceful-reload-fallback]

key-files:
  created: []
  modified:
    - gesture_keys/config.py
    - gesture_keys/__main__.py
    - config.yaml
    - tests/test_config.py
    - tests/test_integration.py

key-decisions:
  - "ConfigWatcher uses os.path.getmtime polling with configurable interval (default 2s)"
  - "Key mappings pre-parsed at startup and re-parsed on reload for performance"
  - "Invalid config reload keeps current config with WARNING log (no crash)"

patterns-established:
  - "Hot-reload pattern: poll mtime, try reload, fallback to current on error"
  - "Pre-parse config-derived data at startup, re-parse on reload"

requirements-completed: [KEY-01, KEY-04, KEY-05]

duration: 5min
completed: 2026-03-21
---

# Phase 02 Plan 02: Config Extension, Hot-Reload, and Main Loop Wiring Summary

**Extended config with timing fields and hot-reload via mtime polling, wired debouncer and keystroke sender into main loop, human-verified end-to-end gesture-to-key firing**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-21T10:17:00Z
- **Completed:** 2026-03-21T10:22:33Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- AppConfig extended with activation_delay and cooldown_duration fields, backward-compatible defaults
- ConfigWatcher polls file mtime with configurable interval, handles missing/unavailable files gracefully
- Main loop wires GestureDebouncer between smoother output and KeystrokeSender with pre-parsed key mappings
- Config hot-reload re-parses key mappings and updates debouncer timing without restart
- Human-verified all 10 end-to-end checks: single keys, combos, no repeat-fire, brief gesture rejection, hot-reload

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for config timing + hot-reload** - `1ffbcaf` (test)
2. **Task 1 (GREEN): Config extension, hot-reload, main loop wiring** - `be5cf74` (feat)
3. **Task 2: Verify keystroke firing in real application** - checkpoint:human-verify (approved)

## Files Created/Modified
- `gesture_keys/config.py` - Added activation_delay/cooldown_duration to AppConfig, added ConfigWatcher class
- `gesture_keys/__main__.py` - Wired debouncer, keystroke sender, config watcher into frame loop
- `config.yaml` - Added activation_delay and cooldown_duration under detection section
- `tests/test_config.py` - Added TestAppConfigTimingFields and TestConfigWatcher test classes
- `tests/test_integration.py` - Updated integration tests for new config fields

## Decisions Made
- ConfigWatcher uses os.path.getmtime polling with configurable interval (default 2s) -- simple, reliable, no external dependencies
- Key mappings pre-parsed at startup and re-parsed on reload -- avoids parsing on every fire event
- Invalid config reload keeps current config with WARNING log -- fail-safe over fail-fast for runtime reloads

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Complete gesture-to-keystroke pipeline is operational and human-verified
- Phase 3 (polish and packaging) can proceed with confidence that core functionality works end-to-end
- All config, debounce, keystroke, and hot-reload components are tested and integrated

## Self-Check: PASSED

All files verified present. All commits verified in git log.

---
*Phase: 02-gesture-to-keystroke-pipeline*
*Completed: 2026-03-21*
