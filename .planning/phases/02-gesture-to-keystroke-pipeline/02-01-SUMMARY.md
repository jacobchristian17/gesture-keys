---
phase: 02-gesture-to-keystroke-pipeline
plan: 01
subsystem: gesture-processing
tags: [debounce, state-machine, pynput, keystroke, keyboard-automation]

requires:
  - phase: 01-detection-and-preview
    provides: Gesture enum from classifier.py used as debouncer input
provides:
  - GestureDebouncer state machine with IDLE/ACTIVATING/FIRED/COOLDOWN transitions
  - parse_key_string parser for config key combo strings
  - KeystrokeSender with try/finally modifier release safety
  - DebounceState enum for external state inspection
affects: [02-gesture-to-keystroke-pipeline, main-loop-integration]

tech-stack:
  added: [pynput>=1.7.6]
  patterns: [state-machine-with-explicit-timestamps, try-finally-modifier-release]

key-files:
  created:
    - gesture_keys/debounce.py
    - gesture_keys/keystroke.py
    - tests/test_debounce.py
    - tests/test_keystroke.py
  modified:
    - requirements.txt

key-decisions:
  - "Single None from smoother sufficient for release detection (smoother already smooths)"
  - "try/finally tracks pressed_modifiers list for safe cleanup on error"

patterns-established:
  - "State machine with explicit float timestamps for testability (no real time in tests)"
  - "SPECIAL_KEYS dict as single source of truth for key name resolution"

requirements-completed: [KEY-01, KEY-02, KEY-03, KEY-04]

duration: 2min
completed: 2026-03-21
---

# Phase 02 Plan 01: Debounce and Keystroke Summary

**Debounce state machine (IDLE/ACTIVATING/FIRED/COOLDOWN) with configurable timing, and keystroke sender with pynput key combo parsing and try/finally modifier safety**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-21T10:09:33Z
- **Completed:** 2026-03-21T10:11:45Z
- **Tasks:** 1
- **Files modified:** 5

## Accomplishments
- GestureDebouncer correctly transitions through all 4 states with proper timing
- Held gesture fires exactly once, cooldown prevents re-fire until released
- parse_key_string handles single keys, combos, special keys, case normalization, and error cases
- KeystrokeSender releases modifiers in finally block even on exceptions
- 30 new tests passing, 83 total suite green

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests** - `0e39a79` (test)
2. **Task 1 (GREEN): Implementation** - `5c251a9` (feat)

## Files Created/Modified
- `gesture_keys/debounce.py` - State machine: IDLE -> ACTIVATING -> FIRED -> COOLDOWN -> IDLE
- `gesture_keys/keystroke.py` - Key string parser and keystroke sender via pynput
- `tests/test_debounce.py` - 16 tests covering all state transitions with explicit timestamps
- `tests/test_keystroke.py` - 14 tests covering parsing, combos, errors, mock controller
- `requirements.txt` - Added pynput>=1.7.6

## Decisions Made
- Single None from smoother is sufficient for release detection -- the smoother already represents multiple raw frames of smoothing, so no additional frame counting needed
- KeystrokeSender tracks pressed_modifiers in a list and releases in finally block, rather than using pynput's pressed() context manager, for more explicit control and testability

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- debounce.py and keystroke.py are independently testable modules ready for main loop integration
- Plan 02-02 can wire these into __main__.py, extend config.py with timing fields, and add hot-reload

---
*Phase: 02-gesture-to-keystroke-pipeline*
*Completed: 2026-03-21*
