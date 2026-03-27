---
phase: quick
plan: 260327-nrq
type: execute
wave: 1
depends_on: []
files_modified:
  - gesture_keys/action.py
  - gesture_keys/pipeline.py
  - tests/test_action.py
autonomous: true
requirements: [dispatch_interval_throttling]
must_haves:
  truths:
    - "MOVING_FIRE dispatches are throttled when dispatch_interval has not elapsed"
    - "Per-action dispatch_interval overrides take precedence over global default"
    - "No throttling when dispatch_interval is 0 or unconfigured (backward compatible)"
    - "Pipeline passes dispatch_interval config to resolver and dispatcher on init and hot-reload"
  artifacts:
    - path: "gesture_keys/action.py"
      provides: "ActionDispatcher throttling logic in _handle_moving_fire"
      contains: "global_dispatch_interval"
    - path: "gesture_keys/pipeline.py"
      provides: "Wiring of dispatch_interval_overrides and global_dispatch_interval"
      contains: "dispatch_interval_overrides"
    - path: "tests/test_action.py"
      provides: "Throttle tests for per-action and global dispatch_interval"
      contains: "test_moving_fire_throttled_when_interval_not_elapsed"
  key_links:
    - from: "gesture_keys/pipeline.py"
      to: "gesture_keys/action.py (ActionResolver)"
      via: "dispatch_interval_overrides=derived.moving_dispatch_interval_overrides"
      pattern: "dispatch_interval_overrides=derived\\.moving_dispatch_interval_overrides"
    - from: "gesture_keys/pipeline.py"
      to: "gesture_keys/action.py (ActionDispatcher)"
      via: "global_dispatch_interval=config.motion_dispatch_interval"
      pattern: "global_dispatch_interval"
    - from: "gesture_keys/action.py (_handle_moving_fire)"
      to: "gesture_keys/action.py (ActionResolver.get_dispatch_interval)"
      via: "throttle check before send"
      pattern: "get_dispatch_interval"
---

<objective>
Wire dispatch_interval throttling end-to-end. The config plumbing exists (Plan 25-01 complete: ActionEntry, parse_actions, DerivedConfig, AppConfig, ActionResolver getter/setter) but the actual throttling in ActionDispatcher and pipeline wiring are missing.

Purpose: Moving gesture actions (swipe_left, swipe_right, etc.) fire on every frame during continuous motion. dispatch_interval throttles these to a configurable rate.
Output: Working dispatch_interval throttling with tests passing.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@gesture_keys/action.py
@gesture_keys/pipeline.py
@gesture_keys/config.py
@tests/test_action.py
@config.yaml
</context>

<interfaces>
<!-- Existing config plumbing from Plan 25-01 (already implemented) -->

From gesture_keys/config.py:
```python
@dataclass
class ActionEntry:
    dispatch_interval: Optional[float] = None  # line 49

@dataclass
class DerivedConfig:
    moving_dispatch_interval_overrides: dict[tuple[str, str], float]  # line 206

@dataclass
class AppConfig:
    motion_dispatch_interval: float = 0  # line 360
```

From gesture_keys/action.py (ActionResolver, already implemented):
```python
def get_dispatch_interval(self, gesture_name: str, direction: Direction) -> Optional[float]:
    return self._dispatch_interval_overrides.get((gesture_name, direction.value))

def set_dispatch_interval_overrides(self, overrides: dict[tuple[str, str], float]) -> None:
    self._dispatch_interval_overrides = overrides
```

From gesture_keys/action.py (ActionDispatcher -- needs modification):
```python
class ActionDispatcher:
    def __init__(self, sender, resolver, repeat_interval=0.03):
        # Currently NO global_dispatch_interval param
        # Currently NO _last_dispatch_times tracking

    def _handle_moving_fire(self, signal):
        # Currently: resolve action, check velocity, send -- NO throttle check
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add dispatch_interval throttling to ActionDispatcher</name>
  <files>gesture_keys/action.py, tests/test_action.py</files>
  <behavior>
    - test_moving_fire_throttled_when_interval_not_elapsed: ActionResolver with dispatch_interval_overrides={("open_palm", "up"): 0.2}. Mock time.perf_counter to 100.0 -> fires. Mock time to 100.1 -> throttled (skipped). Mock time to 100.25 -> fires again.
    - test_moving_fire_global_dispatch_interval_throttles: No per-action override, global_dispatch_interval=0.3. Mock time 100.0 -> fires. Mock time 100.1 -> throttled. Mock time 100.35 -> fires.
    - test_moving_fire_per_action_overrides_global: per-action dispatch_interval=0.1 AND global_dispatch_interval=0.5. Per-action wins (fires at 100.15, not held until 100.5).
    - test_moving_fire_no_throttle_when_unconfigured: global=0 and no per-action override -> fires every time (backward compat).
  </behavior>
  <action>
    1. In tests/test_action.py, add a new TestMovingFireDispatchThrottling class after the existing TestDispatchIntervalOverrides class (~line 712). Write all four failing tests first using unittest.mock.patch on time.perf_counter. Each test creates an ActionResolver with appropriate dispatch_interval_overrides, creates ActionDispatcher with global_dispatch_interval param, sends MOVING_FIRE signals, and asserts sender.send call count.

    2. In gesture_keys/action.py ActionDispatcher:
       - Add `global_dispatch_interval: float = 0` parameter to __init__ (after repeat_interval)
       - Store as `self._global_dispatch_interval = global_dispatch_interval`
       - Add `self._last_dispatch_times: dict[tuple[str, str], float] = {}` to track per-action last dispatch timestamps
       - In `_handle_moving_fire`, after the velocity check passes and before `self._sender.send(...)`:
         a. Build key = (signal.gesture.value, signal.direction.value)
         b. Get per-action interval: `interval = self._resolver.get_dispatch_interval(signal.gesture.value, signal.direction)`
         c. If interval is None, fall back to `self._global_dispatch_interval`
         d. If interval > 0: check `time.perf_counter() - self._last_dispatch_times.get(key, 0.0) < interval` -> skip with debug log
         e. After send, update `self._last_dispatch_times[key] = time.perf_counter()`
       - Add `import time` at top of file if not already present
  </action>
  <verify>
    <automated>cd C:/Users/wsenr/repos/source/gesture-keys && python -m pytest tests/test_action.py -x -q -k "dispatch" 2>&1 | tail -20</automated>
  </verify>
  <done>All four dispatch throttle tests pass. Per-action overrides take precedence over global. Backward compatible when unconfigured (0 = no throttle).</done>
</task>

<task type="auto">
  <name>Task 2: Wire dispatch_interval through Pipeline init and hot-reload</name>
  <files>gesture_keys/pipeline.py</files>
  <action>
    1. In Pipeline.__init__ (around line 190), add `dispatch_interval_overrides=derived.moving_dispatch_interval_overrides,` to the ActionResolver constructor call (after the velocity_overrides line 190).

    2. In Pipeline.__init__ (around line 194), add `global_dispatch_interval=config.motion_dispatch_interval,` to the ActionDispatcher constructor call (after repeat_interval).

    3. In Pipeline._reload_config hot-reload path (around line 435), add `dispatch_interval_overrides=derived.moving_dispatch_interval_overrides,` to the ActionResolver constructor call (after velocity_overrides line 435).

    4. In Pipeline._reload_config (around line 438, after `self._dispatcher._repeat_interval = new_config.hold_repeat_interval`), add:
       `self._dispatcher._global_dispatch_interval = new_config.motion_dispatch_interval`
  </action>
  <verify>
    <automated>cd C:/Users/wsenr/repos/source/gesture-keys && python -m pytest tests/ -x -q 2>&1 | tail -20</automated>
  </verify>
  <done>Pipeline passes dispatch_interval_overrides to ActionResolver and global_dispatch_interval to ActionDispatcher on both init and hot-reload. Full test suite passes.</done>
</task>

</tasks>

<verification>
1. `python -m pytest tests/test_action.py -x -q -k "dispatch"` -- all dispatch throttle tests pass
2. `python -m pytest tests/ -x -q` -- full suite passes, no regressions
3. `grep -n "dispatch_interval" gesture_keys/pipeline.py` -- confirms wiring present
4. `grep -n "global_dispatch_interval" gesture_keys/action.py` -- confirms throttle logic present
</verification>

<success_criteria>
- MOVING_FIRE dispatches are throttled per dispatch_interval (per-action or global)
- Per-action override takes precedence over global
- No throttling when interval is 0 (backward compatible)
- Pipeline wires dispatch_interval on init and hot-reload
- All tests pass including new throttle tests
</success_criteria>

<output>
After completion, create `.planning/quick/260327-nrq-debug-dispatch-interval-not-working/260327-nrq-SUMMARY.md`
</output>
