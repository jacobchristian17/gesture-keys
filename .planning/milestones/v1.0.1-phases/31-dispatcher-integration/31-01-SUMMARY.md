---
phase: 31-dispatcher-integration
plan: 01
subsystem: action-dispatch
tags: [scroll, pynput, action-dispatcher, scroll-sender, fire-mode]

requires:
  - phase: 29-scrollsender
    provides: ScrollSender class with direction routing, velocity-proportional ticks, EMA smoothing
  - phase: 30-fire-mode-config
    provides: FireMode.SCROLL enum, ActionResolver scroll param accessors, scroll override maps
provides:
  - ScrollSender.scroll() per-call override params (scroll_speed, min_ticks, max_ticks)
  - ActionDispatcher scroll branch routing MOVING_FIRE SCROLL signals to ScrollSender
  - release_all() ScrollSender reset integration
affects: [32-pipeline-wiring, scroll-tuning]

tech-stack:
  added: []
  patterns: [per-call-override-kwargs, fire-mode-branching-in-dispatcher]

key-files:
  created: []
  modified:
    - gesture_keys/scroll.py
    - gesture_keys/action.py
    - tests/test_scroll.py
    - tests/test_action.py

key-decisions:
  - "Per-call overrides use keyword-only args with None defaults for backward compatibility"
  - "Scroll branch placed before keystroke send with early return to prevent dual dispatch"
  - "Dispatch interval throttling shared between scroll and keystroke paths"

patterns-established:
  - "Per-call override pattern: Optional kwargs that fall back to instance defaults when None"
  - "Fire mode branching: check fire_mode before dispatch, early return for non-keystroke paths"

requirements-completed: [SCROLL-06, SCROLL-10]

duration: 3min
completed: 2026-04-01
---

# Phase 31 Plan 01: Dispatcher Integration Summary

**ScrollSender wired into ActionDispatcher with per-call override params and fire_mode=SCROLL branch routing**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-01T12:46:35Z
- **Completed:** 2026-04-01T12:49:41Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- ScrollSender.scroll() now accepts optional per-call scroll_speed, min_ticks, max_ticks kwargs
- ActionDispatcher routes MOVING_FIRE signals with fire_mode=SCROLL to ScrollSender instead of KeystrokeSender
- Per-action scroll tuning from ActionResolver forwarded through dispatcher to ScrollSender
- Dispatch interval throttling works for both scroll and keystroke paths
- release_all() resets ScrollSender EMA state for clean shutdown

## Task Commits

Each task was committed atomically:

1. **Task 1: Add per-call override params to ScrollSender.scroll()** - `830e005` (feat)
2. **Task 2: Add scroll branch to ActionDispatcher._handle_moving_fire()** - `9226025` (feat)

## Files Created/Modified
- `gesture_keys/scroll.py` - Added optional scroll_speed, min_ticks, max_ticks kwargs to scroll()
- `gesture_keys/action.py` - Added scroll_sender constructor param, scroll branch in _handle_moving_fire, reset in release_all
- `tests/test_scroll.py` - 5 new tests for per-call override behavior
- `tests/test_action.py` - 11 new tests for scroll dispatch branch

## Decisions Made
- Per-call overrides use keyword-only args (after `*`) with None defaults -- backward compatible, no existing callers need changes
- Scroll branch placed before the keystroke send with early `return` to prevent scroll actions from also firing keystrokes
- Dispatch interval throttling time tracking covers both scroll and keystroke paths identically

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing test failure in tests/test_tray.py::TestEditConfigOpensFile (unrelated to this plan's changes). All 510 tests in scope pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- ScrollSender is fully integrated into ActionDispatcher
- Ready for Phase 32 pipeline wiring to pass scroll_sender through Pipeline constructor
- No blockers or concerns

---
*Phase: 31-dispatcher-integration*
*Completed: 2026-04-01*
