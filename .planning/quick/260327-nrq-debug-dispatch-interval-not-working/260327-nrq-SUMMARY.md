---
phase: quick
plan: 260327-nrq
subsystem: action-dispatch
tags: [dispatch-throttling, moving-fire, pipeline-wiring]
dependency_graph:
  requires: [25-01-dispatch-interval-config-plumbing]
  provides: [dispatch-interval-throttling-end-to-end]
  affects: [gesture_keys/action.py, gesture_keys/pipeline.py, tests/test_action.py]
tech_stack:
  added: []
  patterns: [per-action-override-with-global-fallback, time.perf_counter-throttling]
key_files:
  created: []
  modified:
    - gesture_keys/action.py
    - gesture_keys/pipeline.py
    - tests/test_action.py
decisions:
  - "Throttle check uses time.perf_counter() for monotonic high-resolution timing"
  - "Per-action dispatch_interval takes precedence over global; 0 = no throttle (backward compatible)"
metrics:
  duration: 3m
  completed: 2026-03-27
---

# Quick Task 260327-nrq: Wire dispatch_interval Throttling End-to-End Summary

Dispatch interval throttling for MOVING_FIRE signals with per-action override precedence over global fallback, using time.perf_counter timestamp tracking per (gesture, direction) key.

## What Was Done

### Task 1: Add dispatch_interval throttling to ActionDispatcher (TDD)

- Added `import time` to action.py
- Added `global_dispatch_interval` parameter and `_last_dispatch_times` dict to ActionDispatcher.__init__
- Added throttle check in `_handle_moving_fire` after velocity check and before send:
  - Builds (gesture, direction) key for tracking
  - Checks per-action interval via resolver, falls back to global
  - Skips dispatch if interval > 0 and elapsed time < interval
  - Records dispatch timestamp after successful send
- Four new tests in TestMovingFireDispatchThrottling class, all passing

### Task 2: Wire dispatch_interval through Pipeline init and hot-reload

- Pipeline.start(): pass `dispatch_interval_overrides` to ActionResolver, `global_dispatch_interval` to ActionDispatcher
- Pipeline.reload_config(): pass `dispatch_interval_overrides` to rebuilt ActionResolver, update `_global_dispatch_interval` on dispatcher

## Commits

| # | Hash | Message | Files |
|---|------|---------|-------|
| 1a | 7544f00 | test: add failing dispatch_interval throttle tests | tests/test_action.py |
| 1b | 422834f | feat: add dispatch_interval throttling to ActionDispatcher | gesture_keys/action.py |
| 2 | d4c54d8 | feat: wire dispatch_interval through Pipeline init and hot-reload | gesture_keys/pipeline.py |

## Verification

- `python -m pytest tests/test_action.py -x -q -k "dispatch"` -- 12 passed
- `python -m pytest tests/ -x -q` -- 446 passed, no regressions
- grep confirms wiring in pipeline.py (init + reload) and throttle logic in action.py

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED
