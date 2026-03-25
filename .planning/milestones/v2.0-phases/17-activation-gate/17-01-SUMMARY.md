---
phase: 17-activation-gate
plan: 01
subsystem: activation-gate
tags: [tdd, config, pipeline, safety]
dependency_graph:
  requires: [gesture_keys/activation.py, gesture_keys/config.py, gesture_keys/pipeline.py]
  provides: [activation gate config parsing, signal filtering, gate expiry safety, hot-reload]
  affects: [gesture_keys/pipeline.py, gesture_keys/config.py, tests/test_pipeline.py]
tech_stack:
  added: []
  patterns: [TDD red-green, gate/filter pattern, null-object bypass]
key_files:
  created:
    - tests/test_activation.py
  modified:
    - gesture_keys/config.py
    - gesture_keys/pipeline.py
    - tests/test_pipeline.py
decisions:
  - ActivationGate stores single gesture (constructor requirement); Pipeline owns set-based multi-gesture filtering via _activation_gestures
  - gate=None is bypass mode (zero overhead for default config), not a disabled flag
  - signal.gesture.value (string) compared against _activation_gestures set (strings) for matching
  - Gate expiry triggers dispatcher.release_all() + orchestrator.reset() to prevent stuck keys and stale HOLD state
  - Re-arming gate within same frame works: arm() called during _filter_signals_through_gate, gate is_armed() checked per-signal
metrics:
  duration: 6min
  completed_date: "2026-03-25"
  tasks_completed: 2
  files_modified: 3
---

# Phase 17 Plan 01: Activation Gate Integration Summary

Activation gate config, Pipeline signal filtering, bypass mode, gate expiry safety, and hot-reload using TDD (red-green-refactor).

## What Was Built

**Config schema (config.py):**
- Added 3 fields to `AppConfig`: `activation_gate_enabled` (bool=False), `activation_gate_gestures` (list[str]=[]), `activation_gate_duration` (float=3.0)
- `load_config()` parses `activation_gate` YAML section; missing section returns defaults

**Pipeline integration (pipeline.py):**
- Import `ActivationGate` from `gesture_keys.activation`
- `__init__` initializes `_activation_gate = None` and `_activation_gestures = set()`
- `start()` creates `ActivationGate` when `activation_gate_enabled=True` and gestures non-empty; sets `None` otherwise (bypass mode)
- `_filter_signals_through_gate(signals, current_time)`: activation gesture signals arm/re-arm gate and are consumed; non-activation signals pass only when gate is armed; bypass when gate is `None`
- `process_frame()`: ticks gate, detects expiry (was_armed -> not armed -> `release_all()` + `orchestrator.reset()`), filters signals through gate, sets `activation_armed` in `FrameResult`
- `reload_config()`: updates duration in-place, creates new gate, or destroys gate and releases held keys based on new config
- `FrameResult` gains `activation_armed: bool = False` field

## Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED  | Failing tests for activation gate | d9b3b42 | tests/test_activation.py |
| GREEN | Implement activation gate integration | eb121ec | gesture_keys/config.py, gesture_keys/pipeline.py, tests/test_pipeline.py |

## Test Results

- 33 tests in `tests/test_activation.py`: all pass
- Full suite: 424 passed, 4 pre-existing failures (unrelated to this plan)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_start_creates_components regression**
- **Found during:** GREEN phase verification
- **Issue:** `_make_mock_config()` in `test_pipeline.py` didn't set `activation_gate_enabled/gestures/duration`; MagicMock auto-attributes returned truthy, causing `Gesture(mock_value)` to raise `ValueError` when `start()` tried to create a gate
- **Fix:** Added `config.activation_gate_enabled = False`, `config.activation_gate_gestures = []`, `config.activation_gate_duration = 3.0` to `_make_mock_config()`
- **Files modified:** `tests/test_pipeline.py`
- **Commit:** eb121ec

## Pre-existing Failures (out of scope)

Logged to deferred-items (not fixed):
- `tests/test_config.py::TestSwipeWindowConfig::test_swipe_window_default` — asserts `swipe_window == 0.2` but default config.yaml has `0.5`
- `tests/test_pipeline.py::TestPipelineInit::test_init_per_frame_state_defaults` — expects `_hold_active`, `_hold_modifiers` etc. that no longer exist (replaced by dispatcher pattern in phase 16)
- `tests/test_pipeline.py::TestPipelineStartStop::test_stop_releases_resources` — expects `_dispatcher.release_all()` called but dispatcher is None at stop time in test setup
- `tests/test_pipeline.py::TestPipelineReset::test_reset_pipeline_resets_components` — same dispatcher None issue

## Self-Check: PASSED
