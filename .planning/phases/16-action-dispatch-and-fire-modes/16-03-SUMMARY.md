---
phase: 16-action-dispatch-and-fire-modes
plan: 03
subsystem: action-dispatch
tags: [hold-key, tap-repeat, tick, gap-closure, windows-sendinput]
dependency_graph:
  requires: [16-01, 16-02]
  provides: [continuous-hold-key-output]
  affects: [action.py, pipeline.py]
tech_stack:
  added: []
  patterns: [app-controlled-tap-repeat, frame-tick-loop]
key_files:
  created: []
  modified:
    - gesture_keys/action.py
    - gesture_keys/pipeline.py
    - tests/test_action.py
decisions:
  - "App-controlled tap-repeat replaces OS key-hold (press_and_hold) since Windows does not auto-repeat programmatic SendInput key-down events"
  - "HOLD_START sets _last_repeat_time=0.0 so first tick() fires immediately on same frame"
  - "HOLD_END simply clears _held_action (no physical release needed for tap-repeat)"
  - "release_all() still calls sender.release_all() as safety belt for edge cases"
metrics:
  duration: 3min
  completed: "2026-03-25T10:28:29Z"
---

# Phase 16 Plan 03: Hold Key Tap-Repeat Fix Summary

App-controlled tap-repeat at 30ms/33Hz replaces OS press_and_hold for hold_key fire mode, fixing Windows SendInput non-repeat behavior.

## What Was Done

### Task 1: Add tick() repeat mechanism to ActionDispatcher (TDD)

**RED:** Added 8 new tests in TestHoldKeyTick and updated TestHoldKeyFireMode to expect send() instead of press_and_hold()/release_held(). All new tests failed as expected.

**GREEN:** Refactored ActionDispatcher:
- Added `tick(current_time)` method that sends repeated keystrokes when `_repeat_interval` has elapsed
- Changed `_handle_hold_start()` to set `_held_action` and `_last_repeat_time=0.0` (replacing `press_and_hold()`)
- Changed `_handle_hold_end()` to clear `_held_action` only (replacing `release_held()`)
- Added `repeat_interval` constructor parameter (default 30ms)
- All 31 tests passed

**Commits:** `315270a` (RED), `5857d91` (GREEN)

### Task 2: Wire dispatcher.tick() into Pipeline.process_frame()

- Added `self._dispatcher.tick(current_time)` after signal dispatch loop in `process_frame()`
- Passed `config.hold_repeat_interval` to ActionDispatcher constructor in `start()`
- Added `_repeat_interval` update in `reload_config()` for hot-reload support
- 246 tests passed (full safe suite)

**Commit:** `11bd1e5`

## Deviations from Plan

None - plan executed exactly as written.

## Verification

1. `python -m pytest tests/test_action.py -x -q` -- 31 passed
2. `python -m pytest tests/ -x -q --ignore=tests/test_pipeline.py --ignore=tests/test_preview.py --ignore=tests/test_tray.py --ignore=tests/test_detector.py --ignore=tests/test_config.py` -- 246 passed
3. Manual verification deferred to UAT (requires camera + physical gesture)

## Commit Log

| Task | Commit    | Type     | Description                                  |
| ---- | --------- | -------- | -------------------------------------------- |
| 1    | `315270a` | test     | Failing tests for tick() repeat mechanism    |
| 1    | `5857d91` | feat     | Implement tick() tap-repeat in ActionDispatcher |
| 2    | `11bd1e5` | feat     | Wire dispatcher.tick() into Pipeline         |
