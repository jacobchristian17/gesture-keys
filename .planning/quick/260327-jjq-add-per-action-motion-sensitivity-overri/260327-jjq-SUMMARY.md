---
phase: quick
plan: 260327-jjq
subsystem: motion-config
tags: [motion, config, velocity, per-action]
dependency_graph:
  requires: []
  provides: [per-action-min-velocity, global-motion-config, velocity-signal-chain]
  affects: [motion.py, config.py, action.py, orchestrator.py, pipeline.py]
tech_stack:
  added: []
  patterns: [velocity-hysteresis, per-action-override, hot-reload]
key_files:
  created: []
  modified:
    - gesture_keys/motion.py
    - gesture_keys/config.py
    - gesture_keys/action.py
    - gesture_keys/orchestrator.py
    - gesture_keys/pipeline.py
    - config.yaml
    - tests/test_motion.py
    - tests/test_config.py
    - tests/test_action.py
decisions:
  - Sequence triggers no longer overwrite gesture_modes (fixes fist hold_key being overridden by fist>open_palm sequence)
  - motion.min_velocity YAML key maps to AppConfig.motion_arm_threshold (consistent with MotionDetector naming)
  - velocity_overrides keyed by (gesture_value, direction_value) tuple, same as moving action maps
metrics:
  duration: 509s
  completed: "2026-03-27T06:20:00Z"
  tasks: 2
  files_modified: 9
---

# Quick Task 260327-jjq: Per-Action Motion Sensitivity Overrides Summary

Velocity flows through MotionDetector -> MotionState -> OrchestratorSignal -> ActionDispatcher, with global motion config from YAML and per-action min_velocity filtering.

## Task Results

| Task | Name | Commit(s) | Status |
|------|------|-----------|--------|
| 1 | Wire global motion config and expose velocity | 36bba44 (RED), b1482ff (GREEN) | Done |
| 2 | Per-action velocity filtering in ActionDispatcher | 00728ed (RED), fe08a88 (GREEN) | Done |

## Changes Made

### Task 1: Global Motion Config + Velocity Signal Chain

- **MotionState** (motion.py): Added `velocity: float = 0.0` field. MotionDetector stores computed velocity and returns it in MotionState when moving.
- **AppConfig** (config.py): Added `motion_arm_threshold`, `motion_disarm_threshold`, `motion_axis_ratio`, `motion_settling_frames` fields. `load_config()` reads from YAML `motion:` section (min_velocity -> arm_threshold mapping).
- **ActionEntry** (config.py): Added `min_velocity: Optional[float] = None` field. `parse_actions()` reads from YAML.
- **DerivedConfig** (config.py): Added `moving_velocity_overrides: dict[tuple[str, str], float]` field. Populated in `derive_from_actions()` for MOVING triggers with min_velocity set.
- **OrchestratorSignal** (orchestrator.py): Added `velocity: float = 0.0` field. `_maybe_emit_moving_fire()` passes `motion_state.velocity`.
- **Pipeline** (pipeline.py): MotionDetector initialized from config values. Hot-reload updates MotionDetector properties.
- **config.yaml**: Updated motion section comment noting per-action min_velocity support.

### Task 2: Per-Action Velocity Filtering

- **ActionResolver** (action.py): Added `velocity_overrides` constructor kwarg, `get_min_velocity()` lookup, and `set_velocity_overrides()` for hot-reload.
- **ActionDispatcher._handle_moving_fire** (action.py): Checks per-action velocity override before sending. Skips send when `velocity < min_velocity`.
- **Pipeline** (pipeline.py): Passes `derived.moving_velocity_overrides` to ActionResolver at init and during reload.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Sequence triggers overwriting gesture_modes**
- **Found during:** Task 1
- **Issue:** `fist > open_palm` sequence trigger set `gesture_modes["fist"] = "tap"`, overriding `fist:holding`'s `hold_key` mode.
- **Fix:** Sequence triggers no longer set gesture_modes. Each gesture's lifecycle is determined by its own trigger, not sequences.
- **Files modified:** gesture_keys/config.py, tests/test_config.py
- **Commit:** b1482ff

**2. [Rule 3 - Blocking] config.yaml key "escape" not in SPECIAL_KEYS**
- **Found during:** Task 1
- **Issue:** `fist_to_palm` action used key `escape` but keystroke.py only has `esc`. Config loading failed.
- **Fix:** Changed `escape` to `esc` in config.yaml.
- **Files modified:** config.yaml
- **Commit:** b1482ff

**3. [Rule 1 - Bug] Test count mismatch after sequence action added**
- **Found during:** Task 1
- **Issue:** Test expected 11 actions but config.yaml now has 12 (fist_to_palm was added).
- **Fix:** Updated test to expect 12 and include "fist_to_palm" in expected names.
- **Files modified:** tests/test_config.py
- **Commit:** b1482ff

## Verification

```
431 passed in 7.79s (full test suite, zero failures)
```

## Known Stubs

None. All data paths are fully wired.

## Self-Check: PASSED

All 9 modified files exist. All 4 task commits verified.
