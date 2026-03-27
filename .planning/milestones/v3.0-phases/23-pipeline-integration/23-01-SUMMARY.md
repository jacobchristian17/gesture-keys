---
phase: 23-pipeline-integration
plan: 01
title: "Pipeline Integration - MotionDetector and DerivedConfig Wiring"
one_liner: "Replaced SwipeDetector with MotionDetector and switched pipeline to DerivedConfig-based 8-map ActionResolver"
completed: 2026-03-27
duration: "4m 21s"
tasks_completed: 2
tasks_total: 2
subsystem: pipeline
tags: [integration, motion-detector, derived-config, pipeline]
dependency_graph:
  requires: [motion.py, config.py (DerivedConfig), action.py (8-map ActionResolver), orchestrator.py (motion_state kwarg)]
  provides: [Pipeline with MotionDetector + DerivedConfig integration]
  affects: [tray.py (FrameResult shape change), preview.py (motion_state replaces swiping)]
tech_stack:
  patterns: [DerivedConfig single source of truth, 8-map ActionResolver, continuous motion detection]
key_files:
  created: []
  modified: [gesture_keys/pipeline.py, tests/test_pipeline.py, gesture_keys/activation.py]
decisions:
  - "SEQUENCE_FIRE gate filtering falls back to gesture.value when second_gesture is None (safety for edge cases)"
  - "Activation bypass merges config-level and DerivedConfig bypass lists using set union"
  - "MotionDetector uses default thresholds (no AppConfig fields for motion yet)"
metrics:
  duration: "4m 21s"
  completed: "2026-03-27"
---

# Phase 23 Plan 01: Pipeline Integration - MotionDetector and DerivedConfig Wiring Summary

Replaced SwipeDetector with MotionDetector and switched pipeline to DerivedConfig-based 8-map ActionResolver with SEQUENCE_FIRE gate filtering.

## What Was Done

### Task 1: Replace SwipeDetector with MotionDetector and switch to DerivedConfig
**Commit:** bfe57f7

- Replaced all SwipeDetector imports/usage with MotionDetector
- Switched from `build_action_maps`/`build_compound_action_maps`/`resolve_hand_gestures` to `parse_actions`/`derive_from_actions` (DerivedConfig)
- Replaced `FrameResult.swiping: bool` with `motion_state: MotionState | None`
- Built ActionResolver with new 8-map constructor from DerivedConfig
- Passed `motion_state` to `orchestrator.update()` every frame
- Updated `_filter_signals_through_gate` to check `second_gesture` for SEQUENCE_FIRE signals
- Updated `reload_config` to rebuild DerivedConfig and update orchestrator/resolver
- Removed all standalone swipe handling blocks, swipe key mappings, and `_parse_swipe_key_mappings`
- Removed swiping-based classification suppression (always classify when landmarks present)

### Task 2: Update pipeline tests for MotionDetector and DerivedConfig integration
**Commit:** 55ecdac

- Updated FrameResult tests to verify `motion_state` field instead of `swiping`
- Updated Pipeline init test to assert `_motion_detector` instead of `_swipe_detector`
- Updated start test to patch `MotionDetector` and `derive_from_actions` instead of `SwipeDetector`
- Updated reset test to verify `_motion_detector.reset()` called
- Added `TestActivationGateSequenceFire` class with 4 tests for gate filtering
- Added `keep_alive` method to ActivationGate (missing from worktree sync)
- Fixed SEQUENCE_FIRE gate filtering for None `second_gesture` edge case

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SEQUENCE_FIRE with None second_gesture**
- **Found during:** Task 1 verification (existing test_activation.py test)
- **Issue:** `_filter_signals_through_gate` crashed when SEQUENCE_FIRE signal had `second_gesture=None`
- **Fix:** Added None guard: fall back to `gesture.value` when `second_gesture` is None
- **Files modified:** gesture_keys/pipeline.py
- **Commit:** 55ecdac

**2. [Rule 3 - Blocking] Missing keep_alive method on ActivationGate**
- **Found during:** Task 2 (full test suite run)
- **Issue:** Worktree's activation.py was behind main repo -- missing `keep_alive()` method that existing tests depend on
- **Fix:** Added `keep_alive` method (copied from main repo's uncommitted change)
- **Files modified:** gesture_keys/activation.py
- **Commit:** 55ecdac

**3. [Rule 1 - Bug] Restored keep_alive call in gate filter**
- **Found during:** Task 2 (test_activation.py signal filtering test)
- **Issue:** `_filter_signals_through_gate` was missing `keep_alive(current_time)` call when non-activation signals pass through armed gate
- **Fix:** Added `self._activation_gate.keep_alive(current_time)` in the armed pass-through branch
- **Files modified:** gesture_keys/pipeline.py
- **Commit:** 55ecdac

## Verification Results

- `python -m pytest tests/test_pipeline.py -x -q` -- 20 passed
- `python -c "from gesture_keys.pipeline import Pipeline"` -- imports cleanly
- No legacy imports (SwipeDetector, build_action_maps) in pipeline.py
- `python -m pytest tests/ -x -q` -- 505 passed, 0 failed

## Known Stubs

None -- all data paths are fully wired.

## Self-Check: PASSED
