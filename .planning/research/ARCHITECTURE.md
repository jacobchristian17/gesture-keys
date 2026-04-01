# Architecture Research: Scroll Gesture Integration

**Domain:** Scroll fire mode for gesture-keys desktop app
**Researched:** 2026-04-01
**Confidence:** HIGH

## System Overview: Current Architecture

```
Camera Frame
    |
    v
Pipeline.process_frame()
    |
    +-- HandDetector.detect() --> landmarks, handedness
    +-- GestureClassifier.classify() --> raw_gesture
    +-- GestureSmoother.update() --> gesture
    +-- MotionDetector.update() --> MotionState(moving, direction, velocity)
    +-- GestureOrchestrator.update() --> OrchestratorResult(signals[])
    |       |
    |       +-- FIRE, HOLD_START, HOLD_END, MOVING_FIRE, SEQUENCE_FIRE
    |
    +-- ActivationGate filter
    +-- ActionDispatcher.dispatch(signal)
    |       |
    |       +-- ActionResolver.resolve_{static,holding,moving,sequence}()
    |       +-- KeystrokeSender.send() / tick()
    |
    +-- ActionDispatcher.tick() --> held-key tap-repeat
    |
    v
FrameResult
```

### Where Scroll Fits

Scroll is a new **fire mode**, not a new signal type. The orchestrator already emits `MOVING_FIRE` signals with velocity and direction when a gesture is held while the hand moves. The only missing piece is that `ActionDispatcher._handle_moving_fire()` currently always routes to `KeystrokeSender.send()` -- it needs a branch for scroll-type actions.

## Recommended Architecture: Scroll Integration

### Core Decision: ScrollSender as Peer to KeystrokeSender

Create a `ScrollSender` class alongside `KeystrokeSender` rather than adding scroll logic into KeystrokeSender. Rationale:

1. **Single Responsibility** -- KeystrokeSender owns keyboard via `pynput.keyboard.Controller`; ScrollSender owns mouse scroll via `pynput.mouse.Controller`. Different pynput subsystems, different controllers.
2. **No keystroke state** -- Scroll has no held-key state (no press/release lifecycle). It fires discrete `mouse.scroll(dx, dy)` calls. Mixing this into KeystrokeSender's held-key tracking would muddy the interface.
3. **Clean testing** -- ScrollSender can be mocked independently in tests without touching keyboard mocks.

### New Fire Mode: SCROLL

Add `FireMode.SCROLL = "scroll"` to the existing enum. This is checked in `ActionDispatcher._handle_moving_fire()` to route to ScrollSender instead of KeystrokeSender.

### Modified Component Map

| Component | Change | What Changes |
|-----------|--------|--------------|
| `FireMode` (action.py) | **ADD** | New `SCROLL = "scroll"` enum value |
| `Action` (action.py) | **NONE** | Already has `fire_mode` field; scroll actions just use `FireMode.SCROLL`. The `key_string`, `modifiers`, `key` fields are unused for scroll actions (set to empty/None sentinels). |
| `ScrollSender` (scroll.py) | **NEW** | Wraps `pynput.mouse.Controller`, exposes `scroll(direction, velocity)` |
| `ActionDispatcher` (action.py) | **MODIFY** | Accept `ScrollSender` in constructor; `_handle_moving_fire()` branches on `fire_mode == SCROLL` |
| `ActionEntry` (config.py) | **MODIFY** | Allow `key` field to be optional/empty for scroll actions; add `fire_mode` field to ActionEntry |
| `derive_from_actions()` (config.py) | **MODIFY** | Detect `fire_mode: scroll` in YAML and set `FireMode.SCROLL` instead of inferring from trigger state |
| `Pipeline` (pipeline.py) | **MODIFY** | Create `ScrollSender` in `start()`, pass to `ActionDispatcher` |

### Components That Do NOT Change

| Component | Why Unchanged |
|-----------|---------------|
| `MotionDetector` | Already provides velocity and direction per frame -- scroll consumes these, does not need to modify them |
| `GestureOrchestrator` | Already emits `MOVING_FIRE` with velocity for holding+moving gestures. No new signal needed. |
| `ActionResolver` | Already resolves `(gesture, direction)` -> `Action` for moving triggers. Scroll actions are just Actions with `fire_mode=SCROLL`. |
| `Trigger` / `parse_trigger()` | Trigger syntax `pinch:moving:up` already works. Fire mode is an Action property, not a Trigger property. |
| `KeystrokeSender` | Scroll does not touch keyboard. No changes needed. |
| `ActivationGate` | Gate filters signals, not fire modes. Scroll actions pass through the same gate logic. |
| `GestureSmoother` | Upstream of action dispatch, unaffected. |
| `DistanceFilter` | Upstream of action dispatch, unaffected. |

## Data Flow: Scroll Path

### Current MOVING_FIRE Flow (keystroke)

```
MotionDetector.update()
    --> MotionState(moving=True, direction=UP, velocity=0.8)

GestureOrchestrator.update()
    --> OrchestratorSignal(MOVING_FIRE, gesture=pinch, direction=UP, velocity=0.8)

ActionDispatcher._handle_moving_fire()
    --> resolver.resolve_moving("pinch", UP) --> Action(key="up", fire_mode=TAP)
    --> velocity check (min_velocity)
    --> dispatch interval throttle
    --> sender.send(modifiers=[], key="up")
```

### New MOVING_FIRE Flow (scroll)

```
MotionDetector.update()
    --> MotionState(moving=True, direction=UP, velocity=0.8)

GestureOrchestrator.update()
    --> OrchestratorSignal(MOVING_FIRE, gesture=pinch, direction=UP, velocity=0.8)

ActionDispatcher._handle_moving_fire()
    --> resolver.resolve_moving("pinch", UP) --> Action(fire_mode=SCROLL)
    --> velocity check (min_velocity)        <-- reuse existing logic
    --> dispatch interval throttle            <-- reuse existing logic
    --> velocity_to_scroll_amount(0.8, UP)   <-- NEW: map velocity to scroll ticks
    --> scroll_sender.scroll(dx=0, dy=3)     <-- NEW: scroll instead of keystroke
```

The only divergence point is AFTER velocity/throttle checks, at the final dispatch step.

## Architectural Patterns

### Pattern 1: Velocity-to-Scroll Mapping

**What:** Convert MotionDetector velocity (normalized coords/sec, typically 0.15-2.0 range) to integer scroll ticks (1-10 range).

**Approach:** Linear mapping with floor/ceiling clamps.

```python
def velocity_to_scroll(velocity: float, min_ticks: int = 1, max_ticks: int = 5,
                        velocity_floor: float = 0.15, velocity_ceiling: float = 1.5) -> int:
    """Map continuous velocity to discrete scroll ticks."""
    if velocity <= velocity_floor:
        return min_ticks
    if velocity >= velocity_ceiling:
        return max_ticks
    # Linear interpolation
    ratio = (velocity - velocity_floor) / (velocity_ceiling - velocity_floor)
    return min_ticks + int(ratio * (max_ticks - min_ticks))
```

**Why linear:** Simple, predictable, tunable with 4 parameters. Non-linear (exponential, sigmoid) curves add complexity without proven UX benefit for this use case. Start linear, tune later if needed.

**Where it lives:** Inside `ScrollSender` or as a module-level function in `scroll.py`. NOT in ActionDispatcher -- keep the dispatcher routing-only.

**Trade-offs:** Linear may feel too slow at low velocities or too fast at high. But dispatch_interval throttling already gates how many scroll events fire per second, providing a separate speed control.

### Pattern 2: Direction-to-Scroll-Axis Mapping

**What:** Convert Direction enum to (dx, dy) sign pairs for `mouse.scroll(dx, dy)`.

```python
_DIRECTION_TO_SCROLL = {
    Direction.UP:    (0, 1),    # pynput: positive dy = scroll up
    Direction.DOWN:  (0, -1),   # pynput: negative dy = scroll down
    Direction.LEFT:  (-1, 0),   # pynput: negative dx = scroll left
    Direction.RIGHT: (1, 0),    # pynput: positive dx = scroll right
}
```

**Note on pynput convention:** `mouse.scroll(0, 2)` scrolls UP (positive = up). This is the opposite of MediaPipe's Y-axis convention (positive = down). The MotionDetector already handles this inversion when classifying direction, so Direction.UP correctly means "user moved hand up" and should map to scroll-up (positive dy).

### Pattern 3: Fire Mode Override in Config

**What:** Currently, fire mode is inferred from trigger state (`holding` -> `hold_key`, `static` -> `tap`, `moving` -> `tap`). For scroll, the user must explicitly set `fire_mode: scroll` in the action config to override the default inference.

**Config syntax:**

```yaml
actions:
  scroll_up:
    trigger: "pinch:moving:up"
    fire_mode: scroll          # <-- NEW: override inferred fire mode
    # key field omitted -- not needed for scroll

  scroll_down:
    trigger: "pinch:moving:down"
    fire_mode: scroll
```

**Why explicit:** Inferring scroll from trigger state would require a new trigger state or magic values. Explicit `fire_mode` is clearer, opt-in, and extends naturally (future fire modes like `mouse_click` follow the same pattern).

**Impact on ActionEntry:** Add optional `fire_mode` field. When present, it overrides the state-inferred mode. When absent, behavior is identical to today.

### Pattern 4: Scroll Config Parameters

**What:** Scroll-specific tuning parameters. Two options for where they live:

**Option A -- Per-action config (recommended):**

```yaml
actions:
  scroll_up:
    trigger: "pinch:moving:up"
    fire_mode: scroll
    dispatch_interval: 0.05     # reuse existing field -- controls scroll event rate
    min_velocity: 0.2           # reuse existing field -- minimum hand speed to start scrolling
```

This reuses the existing `dispatch_interval` and `min_velocity` per-action overrides. No new config fields needed. The dispatch_interval effectively controls scroll smoothness (lower = more frequent smaller scrolls = smoother).

**Option B -- Global scroll section (defer):**

```yaml
scroll:
  min_ticks: 1
  max_ticks: 5
  velocity_floor: 0.15
  velocity_ceiling: 1.5
```

Defer this. Hard-code the velocity-to-ticks mapping initially; tune after real-world testing. If users need per-action scroll speed tuning, the velocity thresholds already provide that.

## Integration Points

### ActionDispatcher Changes (action.py)

The dispatcher is the single modification point. Current `_handle_moving_fire()` unconditionally calls `self._sender.send()`. Change to:

```python
def _handle_moving_fire(self, signal: OrchestratorSignal) -> None:
    action = self._resolver.resolve_moving(signal.gesture.value, signal.direction)
    if action is None:
        return

    # Existing velocity check (unchanged)
    min_vel = self._resolver.get_min_velocity(signal.gesture.value, signal.direction)
    if min_vel is not None and signal.velocity < min_vel:
        return

    # Existing dispatch interval throttle (unchanged)
    key = (signal.gesture.value, signal.direction.value)
    interval = self._resolver.get_dispatch_interval(signal.gesture.value, signal.direction)
    if interval is None:
        interval = self._global_dispatch_interval
    if interval > 0:
        now = time.perf_counter()
        last = self._last_dispatch_times.get(key, 0.0)
        if now - last < interval:
            return

    # NEW: branch on fire_mode
    if action.fire_mode == FireMode.SCROLL:
        self._scroll_sender.scroll(signal.direction, signal.velocity)
    else:
        self._sender.send(action.modifiers, action.key)

    if interval > 0:
        self._last_dispatch_times[key] = time.perf_counter()
```

### ActionDispatcher Constructor Change

```python
def __init__(self, sender, resolver, scroll_sender=None, ...):
    self._scroll_sender = scroll_sender  # None = no scroll support (backward compat)
```

### Config Parsing Changes (config.py)

In `ActionEntry`: add `fire_mode: Optional[str] = None` field, parsed from YAML.

In `derive_from_actions()`: when `entry.fire_mode == "scroll"`, set `FireMode.SCROLL` instead of inferring from trigger state. For scroll actions, skip `parse_key_string()` (no key to parse). Use sentinel values for Action's key fields:

```python
if entry.fire_mode == "scroll":
    fire_mode = FireMode.SCROLL
    modifiers, key = [], ""  # Unused for scroll
else:
    fire_mode = _trigger_state_to_fire_mode[entry.trigger.state]
    modifiers, key = parse_key_string(entry.key)
```

Also make `key` field optional in ActionEntry validation (skip "missing required 'key' field" error when `fire_mode: scroll`).

### Pipeline Changes (pipeline.py)

In `start()`:

```python
from gesture_keys.scroll import ScrollSender
self._scroll_sender = ScrollSender()
self._dispatcher = ActionDispatcher(
    self._sender, self._resolver,
    scroll_sender=self._scroll_sender,  # NEW
    ...
)
```

In `reload_config()`: pass `scroll_sender` when rebuilding dispatcher (or just keep the existing reference -- ScrollSender is stateless).

## Anti-Patterns

### Anti-Pattern 1: Encoding Scroll as Keystroke

**What people do:** Map scroll to Page Up/Page Down keystrokes instead of using mouse scroll events.
**Why it's wrong:** Page Up/Down is not scroll. It jumps by page in some apps, does nothing in others (maps, games), and does not support horizontal scroll. Mouse scroll events are universally handled by the foreground window's scroll handler.
**Do this instead:** Use `pynput.mouse.Controller.scroll(dx, dy)` for native scroll events.

### Anti-Pattern 2: New Orchestrator Signal for Scroll

**What people do:** Add `OrchestratorAction.SCROLL_FIRE` signal type.
**Why it's wrong:** The orchestrator reports WHAT happened (gesture + motion), not HOW to respond. Scroll vs keystroke is a dispatch concern, not an orchestration concern. Adding scroll-specific signals couples the orchestrator to fire modes, violating the existing separation.
**Do this instead:** Keep `MOVING_FIRE` as the signal. Branch on `Action.fire_mode` in the dispatcher.

### Anti-Pattern 3: Velocity-to-Ticks in the Orchestrator

**What people do:** Put velocity mapping logic in the orchestrator or MotionDetector.
**Why it's wrong:** The orchestrator and MotionDetector are fire-mode-agnostic. They report raw velocity. Mapping velocity to scroll ticks is a scroll-specific dispatch concern.
**Do this instead:** Put velocity-to-ticks conversion in ScrollSender or a helper function called by the dispatcher.

### Anti-Pattern 4: Continuous Scroll Without Dispatch Interval

**What people do:** Fire scroll on every frame (30+ Hz) with no throttle.
**Why it's wrong:** At 30 FPS with 3 ticks per event, that is 90 scroll ticks per second -- unusably fast. The existing `dispatch_interval` throttle is essential for scroll usability.
**Do this instead:** Set a sane default `dispatch_interval` for scroll actions (0.05-0.1s recommended, yielding 10-20 scroll events/sec).

## Suggested Build Order

Based on dependency analysis, build in this order:

### Phase 1: ScrollSender (leaf node, no dependencies on existing code)

1. Create `gesture_keys/scroll.py` with `ScrollSender` class
2. `scroll(direction: Direction, velocity: float)` method
3. Velocity-to-ticks mapping (internal)
4. Direction-to-axis mapping (internal)
5. Tests: `tests/test_scroll.py`

### Phase 2: FireMode + Config Changes (modifies shared types)

1. Add `FireMode.SCROLL` to enum
2. Add `fire_mode` field to `ActionEntry`
3. Update `parse_actions()` to read `fire_mode` from YAML
4. Update `derive_from_actions()` to handle `fire_mode: scroll` (skip key parsing, set FireMode.SCROLL)
5. Make `key` field optional when `fire_mode: scroll`
6. Tests: update `tests/test_config.py`, `tests/test_action.py`

### Phase 3: ActionDispatcher Integration (consumes Phase 1 + 2)

1. Add `scroll_sender` parameter to `ActionDispatcher.__init__()`
2. Branch in `_handle_moving_fire()` on `fire_mode == SCROLL`
3. Tests: `tests/test_action.py` -- mock ScrollSender, verify dispatch routing

### Phase 4: Pipeline Wiring (consumes Phase 3)

1. Create `ScrollSender` in `Pipeline.start()`
2. Pass to `ActionDispatcher`
3. Handle in `reload_config()`
4. Tests: `tests/test_pipeline.py` -- integration test with scroll config

### Phase 5: Config + Documentation

1. Add example scroll actions to `config.yaml`
2. Verify hot-reload works with scroll actions

**Why this order:** Phase 1 is pure-new code with no risk to existing functionality. Phase 2 modifies shared types but is backward compatible (new enum value, optional field). Phase 3 is the critical integration point. Phase 4 is wiring. Each phase is independently testable.

## Scaling Considerations

| Concern | Current | With Scroll |
|---------|---------|-------------|
| Frame budget | ~5ms for dispatch path | +negligible: one `mouse.scroll()` call is <0.1ms |
| Controller instances | 1 keyboard Controller | +1 mouse Controller (created once in start()) |
| Config complexity | 4 trigger types x 2 hands = 8 maps | Same 8 maps; scroll is a fire_mode, not a trigger type |
| Memory | Action objects per trigger | Same; scroll Actions are identical size (unused key fields are empty strings) |

No performance concerns. Scroll adds one conditional branch in `_handle_moving_fire()` and one `mouse.scroll()` call per dispatch event.

## Sources

- [pynput mouse documentation](https://pynput.readthedocs.io/en/latest/mouse.html) -- `Controller.scroll(dx, dy)` API, positive dy = scroll up (HIGH confidence)
- [pynput mouse base source](https://pynput.readthedocs.io/en/latest/_modules/pynput/mouse/_base.html) -- scroll method signature verification (HIGH confidence)
- Existing codebase analysis: action.py, config.py, pipeline.py, orchestrator.py, motion.py, trigger.py, keystroke.py (HIGH confidence -- direct code reading)

---
*Architecture research for: Scroll gesture integration into gesture-keys*
*Researched: 2026-04-01*
