---
phase: quick
plan: 260327-jjq
type: execute
wave: 1
depends_on: []
files_modified:
  - gesture_keys/motion.py
  - gesture_keys/config.py
  - gesture_keys/action.py
  - gesture_keys/pipeline.py
  - gesture_keys/orchestrator.py
  - tests/test_config.py
  - tests/test_motion.py
  - tests/test_action.py
  - config.yaml
autonomous: true
requirements: []

must_haves:
  truths:
    - "Global motion: config section values are used by MotionDetector instead of hardcoded defaults"
    - "Per-action: a moving action with min_velocity override only fires when velocity exceeds that threshold"
    - "Per-action: a moving action without min_velocity uses the global MotionDetector threshold as before"
    - "Hot-reload: editing motion config values in config.yaml takes effect without restart"
  artifacts:
    - path: "gesture_keys/motion.py"
      provides: "MotionState with velocity field; MotionDetector using config values"
      contains: "velocity"
    - path: "gesture_keys/config.py"
      provides: "AppConfig with motion fields; ActionEntry with optional min_velocity"
      contains: "min_velocity"
    - path: "gesture_keys/action.py"
      provides: "ActionDispatcher filters MOVING_FIRE by per-action min_velocity"
    - path: "gesture_keys/pipeline.py"
      provides: "MotionDetector initialized from config; hot-reload applies motion settings"
  key_links:
    - from: "config.yaml motion:"
      to: "AppConfig"
      via: "load_config reads motion section"
      pattern: "motion_arm_threshold|motion_settling"
    - from: "AppConfig"
      to: "MotionDetector.__init__"
      via: "pipeline.py passes config values"
      pattern: "MotionDetector\\(.*arm_threshold"
    - from: "ActionEntry.min_velocity"
      to: "ActionDispatcher._handle_moving_fire"
      via: "resolver returns action, dispatcher checks velocity"
      pattern: "min_velocity"
    - from: "MotionState.velocity"
      to: "OrchestratorSignal"
      via: "orchestrator passes velocity through signal"
      pattern: "velocity"
---

<objective>
Wire the existing `motion:` config.yaml section into MotionDetector initialization, add per-action `min_velocity` overrides for moving gestures, and expose velocity through the signal chain so ActionDispatcher can filter by per-action thresholds.

Purpose: Allow users to tune motion sensitivity globally and per-action, so different moving gestures can have different velocity thresholds (e.g., swipe_up needs faster motion than swipe_left).

Output: Working global + per-action motion config with hot-reload support and tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@gesture_keys/motion.py
@gesture_keys/config.py
@gesture_keys/action.py
@gesture_keys/pipeline.py
@gesture_keys/orchestrator.py
@config.yaml
@tests/test_config.py
@tests/test_motion.py
@tests/test_action.py

<interfaces>
<!-- Key types and contracts the executor needs -->

From gesture_keys/motion.py:
```python
@dataclass(frozen=True)
class MotionState:
    moving: bool
    direction: Optional[Direction] = None
    # velocity field needs to be ADDED

class MotionDetector:
    def __init__(self, buffer_size=5, arm_threshold=0.25, disarm_threshold=0.15, axis_ratio=2.0, settling_frames=3):
    # Has property setters for all params (hot-reload ready)
    def update(self, landmarks, timestamp) -> MotionState:
```

From gesture_keys/config.py:
```python
@dataclass(frozen=True)
class ActionEntry:
    name: str
    trigger: Union[Trigger, SequenceTrigger]
    key: str
    cooldown: Optional[float] = None
    bypass_gate: bool = False
    hand: str = "both"
    threshold: Optional[float] = None
    # min_velocity field needs to be ADDED

@dataclass
class AppConfig:
    # motion fields need to be ADDED
    # (motion_arm_threshold, motion_disarm_threshold, motion_axis_ratio, motion_settling_frames)

class DerivedConfig:
    # moving_velocity_overrides needs to be ADDED
    # dict mapping (gesture_value, direction_value) -> min_velocity
    right_moving: dict[tuple[str, str], Action]
    left_moving: dict[tuple[str, str], Action]
```

From gesture_keys/action.py:
```python
class ActionDispatcher:
    def _handle_moving_fire(self, signal: OrchestratorSignal) -> None:
        action = self._resolver.resolve_moving(signal.gesture.value, signal.direction)
        if action is not None:
            self._sender.send(action.modifiers, action.key)
        # needs velocity check BEFORE send
```

From gesture_keys/orchestrator.py:
```python
class OrchestratorSignal(NamedTuple):
    action: OrchestratorAction
    gesture: Gesture
    direction: Optional[Direction] = None
    second_gesture: Optional[Gesture] = None
    # velocity field needs to be ADDED
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Wire global motion config and expose velocity through signal chain</name>
  <files>
    gesture_keys/motion.py,
    gesture_keys/config.py,
    gesture_keys/orchestrator.py,
    gesture_keys/pipeline.py,
    config.yaml,
    tests/test_motion.py,
    tests/test_config.py
  </files>
  <behavior>
    - MotionState(moving=True, direction=Direction.RIGHT).velocity returns computed velocity float
    - MotionState(moving=False).velocity returns 0.0
    - MotionDetector initialized with arm_threshold=0.5 arms at 0.5 (not default 0.25)
    - load_config() with motion: section populates AppConfig.motion_arm_threshold etc.
    - load_config() without motion: section uses MotionDetector defaults
    - ActionEntry with min_velocity=0.5 parses correctly from YAML
    - ActionEntry without min_velocity has min_velocity=None
    - OrchestratorSignal with velocity=0.35 carries velocity through
    - Pipeline creates MotionDetector with config values, not defaults
    - Hot-reload updates MotionDetector properties from new config
  </behavior>
  <action>
    1. **MotionState** (motion.py): Add `velocity: float = 0.0` field to the frozen dataclass. Update `_NOT_MOVING` singleton to include `velocity=0.0`. In `MotionDetector.update()`, when returning a moving MotionState, include the computed `velocity` value. In `_current_state()`, store the last computed velocity as `self._velocity` and include it in the returned MotionState.

    2. **AppConfig** (config.py): Add fields to AppConfig: `motion_arm_threshold: float = 0.25`, `motion_disarm_threshold: float = 0.15`, `motion_axis_ratio: float = 2.0`, `motion_settling_frames: int = 3`. In `load_config()`, read the `motion:` YAML section mapping: `min_velocity` -> `motion_arm_threshold`, `axis_ratio` -> `motion_axis_ratio`, `settling_frames` -> `motion_settling_frames`. Add `motion_disarm_threshold` with default 0.15 (not in YAML yet, but needed by MotionDetector). The existing `cooldown` and `min_displacement` in the YAML motion section are NOT consumed yet (future work).

    3. **ActionEntry** (config.py): Add `min_velocity: Optional[float] = None` field. In `parse_actions()`, read `settings.get("min_velocity")` same pattern as cooldown/threshold.

    4. **DerivedConfig** (config.py): Add `moving_velocity_overrides: dict[tuple[str, str], float]` field. In `derive_from_actions()`, when processing a MOVING trigger with `entry.min_velocity is not None`, add `(gesture_value, direction_value) -> min_velocity` to this dict. Populate for both hands (the override is per-trigger, not per-hand).

    5. **OrchestratorSignal** (orchestrator.py): Add `velocity: float = 0.0` field to the NamedTuple (after second_gesture, before any other new fields). In `_maybe_emit_moving_fire()`, pass `velocity=motion_state.velocity` when constructing the MOVING_FIRE signal.

    6. **Pipeline** (pipeline.py):
       - In `__init__` (line ~208): Change `MotionDetector()` to `MotionDetector(arm_threshold=config.motion_arm_threshold, disarm_threshold=config.motion_disarm_threshold, axis_ratio=config.motion_axis_ratio, settling_frames=config.motion_settling_frames)`.
       - In the hot-reload section (line ~453): Replace the comment with actual property assignments: `self._motion_detector.arm_threshold = new_config.motion_arm_threshold`, same for disarm_threshold, axis_ratio, settling_frames.
       - Store `derived.moving_velocity_overrides` on `self._dispatcher` (or pass to resolver) for Task 2 to use.

    7. **config.yaml**: Add a comment after the motion section noting that `min_velocity` can be set per-action. No changes to existing motion values.

    8. **Tests**: Add tests for MotionState.velocity field, load_config reading motion section, ActionEntry.min_velocity parsing, OrchestratorSignal.velocity field, MotionDetector init with custom params.
  </action>
  <verify>
    <automated>python -m pytest tests/test_motion.py tests/test_config.py -x -q</automated>
  </verify>
  <done>
    - MotionState carries velocity float
    - OrchestratorSignal carries velocity float
    - AppConfig has motion_* fields populated from config.yaml
    - ActionEntry has optional min_velocity field
    - DerivedConfig has moving_velocity_overrides dict
    - Pipeline initializes MotionDetector from config
    - Hot-reload updates MotionDetector properties
    - All tests pass
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Apply per-action velocity filtering in ActionDispatcher</name>
  <files>
    gesture_keys/action.py,
    tests/test_action.py
  </files>
  <behavior>
    - MOVING_FIRE with velocity=0.3 and action min_velocity=0.5 does NOT send keystroke
    - MOVING_FIRE with velocity=0.6 and action min_velocity=0.5 DOES send keystroke
    - MOVING_FIRE with velocity=0.3 and action min_velocity=None DOES send keystroke (no override, global threshold already passed)
    - ActionResolver exposes velocity overrides for lookup
  </behavior>
  <action>
    1. **ActionResolver** (action.py): Add a `_velocity_overrides: dict[tuple[str, str], float]` field. Add a `set_velocity_overrides(overrides: dict[tuple[str, str], float])` method. Add a `get_min_velocity(gesture_value: str, direction: Direction) -> Optional[float]` method that looks up `(gesture_value, direction.value)` in the dict.

    2. **ActionResolver construction** (action.py): Update the constructor to accept an optional `velocity_overrides` parameter. The legacy 4-arg constructor must remain backward compatible (add velocity_overrides as a keyword arg with default empty dict).

    3. **ActionDispatcher._handle_moving_fire** (action.py): After resolving the action but before sending, check if there's a per-action velocity override: `min_vel = self._resolver.get_min_velocity(signal.gesture.value, signal.direction)`. If `min_vel is not None and signal.velocity < min_vel`, skip the send (return early). Log at debug level when skipping: "MOVING_FIRE skipped: velocity %.3f < min_velocity %.3f for %s".

    4. **Pipeline wiring** (already mostly done in Task 1): Ensure `derived.moving_velocity_overrides` is passed to ActionResolver construction. In the hot-reload path, call `self._resolver.set_velocity_overrides(derived.moving_velocity_overrides)` (or rebuild resolver).

    5. **Tests** (test_action.py): Test the three behavior cases above. Use mock sender to verify send called/not called. Test get_min_velocity returns None for unmapped actions.
  </action>
  <verify>
    <automated>python -m pytest tests/test_action.py -x -q</automated>
  </verify>
  <done>
    - Per-action min_velocity filtering works in ActionDispatcher
    - Actions without min_velocity override fire normally (global threshold is the only gate)
    - Actions with min_velocity only fire when velocity meets or exceeds the override
    - Hot-reload updates velocity overrides
    - All tests pass
  </done>
</task>

</tasks>

<verification>
Run the full test suite to confirm no regressions:
```bash
python -m pytest tests/ -x -q
```

Manual smoke test with config.yaml:
1. Add `min_velocity: 0.5` to `swipe_up` action in config.yaml
2. Run the app and verify swipe_up requires faster motion than swipe_left/right/down
3. Edit min_velocity while running and verify hot-reload applies the change
</verification>

<success_criteria>
- Global motion config values from config.yaml are used by MotionDetector (not hardcoded defaults)
- Per-action min_velocity field works in config.yaml for moving actions
- Velocity flows through: MotionDetector -> MotionState -> OrchestratorSignal -> ActionDispatcher
- ActionDispatcher filters MOVING_FIRE by per-action velocity threshold
- Hot-reload updates both global motion settings and per-action velocity overrides
- All existing + new tests pass
</success_criteria>

<output>
After completion, create `.planning/quick/260327-jjq-add-per-action-motion-sensitivity-overri/260327-jjq-SUMMARY.md`
</output>
