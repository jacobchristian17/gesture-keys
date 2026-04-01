# Feature Research: Scroll Gesture Support

**Domain:** Gesture-controlled mouse scrolling (adding scroll fire mode to existing gesture-keys app)
**Researched:** 2026-04-01
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features that any scroll-via-gesture implementation must have. Without these the feature feels broken.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| Vertical scroll (up/down) | Core scrolling use case -- web pages, documents, code editors | LOW | Existing `MotionDetector` direction + `pynput.mouse.Controller.scroll(dx, dy)` | `scroll(0, N)` for vertical. Positive dy = up, negative = down. Already have UP/DOWN from MotionDetector. |
| Horizontal scroll (left/right) | Spreadsheets, timelines, wide documents -- expected alongside vertical | LOW | Same MotionDetector LEFT/RIGHT directions | `scroll(N, 0)` for horizontal. Same integration path as vertical. |
| New `scroll` fire mode | Must be a distinct fire mode alongside `tap` and `hold_key` so config can declare scroll actions | LOW | `FireMode` enum, `ActionEntry`, config parsing, `ActionDispatcher` | New enum value, new handler in dispatcher. Needs explicit `fire_mode: scroll` in config since it cannot be inferred from trigger state alone (moving triggers default to TAP). |
| Velocity-proportional scroll speed | Faster hand movement = faster scrolling. Without this, scroll feels robotic and uncontrollable | MEDIUM | MotionDetector already reports `velocity` on every frame via `MotionState.velocity` | Map velocity to scroll step count. Linear mapping with floor/ceiling: `steps = clamp(velocity * scale_factor, min_steps, max_steps)`. |
| Configurable scroll sensitivity | Users need to tune how fast scrolling feels for their setup | LOW | Existing per-action config override pattern (like `min_velocity`, `dispatch_interval`) | Add `scroll_speed` per-action override in YAML. Global default in `motion:` section. |
| Continuous scroll while moving | Scroll fires repeatedly while hand is in motion, not just once per swipe | LOW | Existing MOVING_FIRE signal fires continuously. Dispatch interval throttling already exists. | Scroll actions use same MOVING_FIRE path but with shorter `dispatch_interval` (e.g. 0.05s for ~20 scroll events/sec). |

### Differentiators (Competitive Advantage)

Features that elevate the scroll experience beyond basic functionality. Not required for launch but add real value.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| Acceleration curve | Slow movement = precise scroll (1-2 steps), fast movement = rapid scroll (10+ steps). Feels natural like a trackpad. BetterTouchTool uses `output = input * (1 + strength * sqrt(abs(input)/4))`. | LOW | Velocity already available per-frame. Pure math in the scroll step calculation. | Apply nonlinear mapping: `steps = base + floor(velocity^exponent * scale)`. Configurable `scroll_acceleration` strength parameter (0 = linear, 1 = moderate curve). |
| Per-direction scroll tuning | Different sensitivity for vertical vs horizontal, or up vs down (e.g., scroll down faster for reading, scroll up slower for reviewing) | LOW | Per-action overrides already supported via existing config pattern | Each direction is already a separate action entry. User can set different `scroll_speed` on `pinch:moving:up` vs `pinch:moving:down`. No new code needed -- natural from existing per-action config. |
| Scroll preview overlay | Visual feedback showing scroll direction and relative speed in the camera preview | MEDIUM | Existing preview overlay system (distance, hand indicator) | Add scroll indicator (arrow + magnitude bar) to preview. Helps users calibrate their hand speed. |
| Configurable min/max scroll bounds | Prevent accidental micro-scrolls or dangerously fast scrolling by clamping output range | LOW | Pure config values applied during step calculation | `scroll_min_steps: 1` and `scroll_max_steps: 15` in motion section or per-action. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem appealing but create complexity without proportional value for this project.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Smooth/sub-pixel scroll interpolation | "Make it feel like a trackpad" with 60fps interpolated inertia | Requires a background scroll animation thread, momentum physics, and deceleration curves. Massively increases complexity for a webcam-based input that already has inherent jitter. OS smooth scroll settings handle this for discrete scroll events. | Send integer scroll steps at high frequency (~20/sec via dispatch_interval). OS-level smooth scroll settings interpolate these into fluid motion. Let the OS do what it does best. |
| Scroll inertia/momentum | Scroll continues after hand stops moving, decelerating gradually | MotionDetector disarms when velocity drops below threshold -- there is no "release velocity" event. Simulating momentum requires a timer thread that continues firing after MOVING_FIRE stops. Adds state complexity and feels unreliable with webcam input latency. | Use short dispatch_interval (0.05-0.1s) so scrolling feels responsive while hand is moving. Clean stop when hand stops. Users prefer predictable stop over momentum with webcam gestures. |
| Diagonal/free-axis scrolling | Scroll diagonally by moving hand at 45 degrees | MotionDetector's axis_ratio filter explicitly rejects diagonals (ratio < 1.5 = rejected). This is by design to prevent ambiguous input. Diagonal scroll is rarely useful and confusing to control via hand gestures. | Keep cardinal-only scrolling. Users who need diagonal can lower axis_ratio, but this is not recommended. |
| Pinch-to-zoom via scroll | Map pinch gesture changes to ctrl+scroll for zoom | Requires tracking pinch distance changes frame-over-frame (finger landmark distance), which is a different input signal than hand movement. Conflates two input dimensions. | Keep zoom as a separate feature (future milestone). Scroll is about hand movement direction/speed, not gesture geometry changes. |
| Scroll-then-click combos | Scroll to position then click without releasing gesture | Requires mouse cursor control (separate feature domain). Mixing scroll and click in one gesture flow adds significant state complexity. | Keep scroll and cursor control as separate feature domains. |

## Feature Dependencies

```
[velocity-proportional scroll speed]
    |-- requires --> [scroll fire mode in dispatcher]
    |-- requires --> [MotionDetector velocity (EXISTING)]
    |-- requires --> [pynput mouse Controller (NEW dependency)]

[scroll fire mode in dispatcher]
    |-- requires --> [FireMode.SCROLL enum value]
    |-- requires --> [config parsing: explicit fire_mode field for scroll]
    |-- requires --> [ActionDispatcher._handle_moving_fire scroll branch]

[configurable scroll sensitivity]
    |-- requires --> [scroll fire mode in dispatcher]
    |-- enhances --> [velocity-proportional scroll speed]

[acceleration curve]
    |-- requires --> [velocity-proportional scroll speed]
    |-- enhances --> [configurable scroll sensitivity]

[scroll preview overlay]
    |-- requires --> [scroll fire mode in dispatcher]
    |-- requires --> [preview overlay system (EXISTING)]
```

### Dependency Notes

- **scroll fire mode requires FireMode.SCROLL:** New enum value triggers new dispatch path. The existing `_handle_moving_fire` already receives velocity -- it just needs a branch that sends `mouse.scroll()` instead of `sender.send()`.
- **velocity-proportional speed requires MotionDetector velocity:** Already provided via `MotionState.velocity` on every frame. No changes to MotionDetector needed.
- **pynput mouse Controller is a NEW dependency for scroll sending:** The app currently only uses `pynput.keyboard.Controller`. Adding `pynput.mouse.Controller` is zero-install (pynput already in dependencies) but requires a new sender class or method.
- **config parsing needs explicit fire_mode field:** Currently fire_mode is inferred from trigger state (moving = TAP). Scroll actions use moving triggers but need SCROLL fire_mode. The `fire_mode: scroll` field on the action config entry solves this cleanly. This is the first config change needed.

## MVP Definition

### Launch With (v1.0.1)

Minimum viable scroll -- what validates the concept works.

- [ ] `FireMode.SCROLL` enum value and config recognition
- [ ] `ScrollSender` or mouse scroll method using `pynput.mouse.Controller.scroll(dx, dy)`
- [ ] Vertical scroll (up/down) via `pinch:moving:up` and `pinch:moving:down`
- [ ] Horizontal scroll (left/right) via `pinch:moving:left` and `pinch:moving:right`
- [ ] Velocity-to-steps mapping: `steps = clamp(int(velocity * scroll_speed), 1, max_steps)`
- [ ] `scroll_speed` config field per action (default sensible global value)
- [ ] Appropriate dispatch_interval default for scroll actions (~0.05s for responsive feel)

### Add After Validation (v1.0.x)

Features to add once core scroll is working and tested.

- [ ] Acceleration curve -- when linear mapping feels too flat at low speeds or too jumpy at high speeds
- [ ] Scroll preview overlay -- when users need visual feedback to calibrate hand speed
- [ ] Per-direction default tuning -- if vertical and horizontal need different default sensitivities

### Future Consideration (v2+)

- [ ] Pinch-to-zoom -- separate input signal, separate milestone
- [ ] Scroll inertia -- only if users report clean-stop feels abrupt (unlikely with webcam input)

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Vertical scroll (up/down) | HIGH | LOW | P1 |
| Horizontal scroll (left/right) | HIGH | LOW | P1 |
| `scroll` fire mode + dispatcher | HIGH | LOW | P1 |
| Velocity-proportional speed | HIGH | MEDIUM | P1 |
| Configurable scroll_speed | MEDIUM | LOW | P1 |
| Continuous scroll via dispatch_interval | HIGH | LOW | P1 (existing infrastructure) |
| Acceleration curve | MEDIUM | LOW | P2 |
| Min/max scroll bounds | LOW | LOW | P2 |
| Scroll preview overlay | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch -- core scroll functionality
- P2: Should have, add when possible -- polish and feel
- P3: Nice to have, future consideration -- visual feedback

## Integration Points With Existing Architecture

### Where Scroll Plugs Into Existing Code

| Component | Current State | Change Needed |
|-----------|---------------|---------------|
| `FireMode` enum (`action.py`) | `TAP`, `HOLD_KEY` | Add `SCROLL` |
| `Action` dataclass (`action.py`) | Has `key_string`, `modifiers`, `key` | Scroll actions don't use key_string/modifiers/key. Need either: (a) sentinel/placeholder values, or (b) make key fields Optional. Option (b) is cleaner but touches more code. Option (a) is pragmatic. |
| `ActionEntry` (`config.py`) | Has `trigger`, `key`, `min_velocity`, `dispatch_interval` | Add explicit `fire_mode` field (currently inferred from trigger state). Add `scroll_speed` field. For scroll actions, `key` field is unused -- make optional or accept placeholder. |
| `derive_from_actions()` (`config.py`) | Infers fire_mode from trigger state | Respect explicit `fire_mode: scroll` override. Moving + fire_mode:scroll = SCROLL instead of TAP. |
| `ActionDispatcher._handle_moving_fire()` (`action.py`) | Resolves action, checks velocity, sends keystroke | Branch on `action.fire_mode == FireMode.SCROLL`: compute steps from velocity, call `scroll_sender.scroll(dx, dy)`. |
| `KeystrokeSender` (`keystroke.py`) | Only keyboard Controller | Add `ScrollSender` with `pynput.mouse.Controller` or add scroll method to existing sender. Separate class is cleaner -- single responsibility. |
| Config YAML | `key: up` for moving actions | Scroll actions need `fire_mode: scroll` and optionally `scroll_speed: 5.0`. The `key` field becomes unused. |
| `release_all()` (`action.py`) | Releases held keyboard keys | Scroll has no held state -- no change needed. |

### Recommended Config Syntax

```yaml
actions:
  scroll_up:
    trigger: "pinch:moving:up"
    fire_mode: scroll
    scroll_speed: 5.0        # velocity multiplier (steps = velocity * scroll_speed)
    dispatch_interval: 0.05  # 20 scroll events/sec for smooth feel

  scroll_down:
    trigger: "pinch:moving:down"
    fire_mode: scroll
    scroll_speed: 5.0

  scroll_left:
    trigger: "pinch:moving:left"
    fire_mode: scroll
    scroll_speed: 3.0        # horizontal often needs less speed

  scroll_right:
    trigger: "pinch:moving:right"
    fire_mode: scroll
    scroll_speed: 3.0
```

Key design decision: scroll actions do not need a `key` field. The `fire_mode: scroll` field makes the action type unambiguous. The `key` field should be optional for scroll actions (validated at parse time).

## Scroll Step Calculation

### Recommended Algorithm

```python
def compute_scroll_steps(velocity: float, scroll_speed: float, max_steps: int = 15) -> int:
    """Convert hand velocity to scroll step count.

    Args:
        velocity: Hand velocity from MotionDetector (normalized coords/sec, typically 0.15-2.0).
        scroll_speed: Multiplier from config (default ~5.0).
        max_steps: Safety ceiling to prevent scroll explosion.

    Returns:
        Integer scroll steps, minimum 1 when moving.
    """
    raw = velocity * scroll_speed
    return max(1, min(int(raw), max_steps))
```

### Velocity-to-Steps Reference

With `scroll_speed: 5.0` and typical MotionDetector velocities:

| Hand Speed | Velocity | Steps | Feel |
|------------|----------|-------|------|
| Slow drift | 0.15-0.3 | 1 | Precise, line-by-line |
| Normal move | 0.3-0.6 | 1-3 | Comfortable reading pace |
| Fast swipe | 0.6-1.2 | 3-6 | Quick navigation |
| Very fast | 1.2-2.0+ | 6-10 | Rapid page skip |

### Direction-to-Axis Mapping

| MotionDetector Direction | pynput scroll(dx, dy) | Effect |
|--------------------------|----------------------|--------|
| Direction.UP | `scroll(0, steps)` | Scroll up (content moves down) |
| Direction.DOWN | `scroll(0, -steps)` | Scroll down (content moves up) |
| Direction.LEFT | `scroll(-steps, 0)` | Scroll left |
| Direction.RIGHT | `scroll(steps, 0)` | Scroll right |

Note: pynput's scroll dy convention -- positive = scroll up. This matches the natural expectation: move hand up = scroll up (content goes down, like pulling a page up).

## Sources

- [pynput mouse documentation](https://pynput.readthedocs.io/en/latest/mouse.html) -- `Controller.scroll(dx, dy)` API (HIGH confidence, pynput already in project dependencies)
- [PyTutorial: Mouse scrolling with pynput](https://pytutorial.com/master-mouse-scrolling-with-pynputmousescroll-in-python/) -- scroll(dx, dy) parameters and examples (HIGH confidence, verified against pynput source)
- [BetterTouchTool Scroll Modifiers](https://docs.folivora.ai/docs/4001_scroll_modifiers.html) -- acceleration formula `output = input * (1 + strength * sqrt(abs(input)/4))`, smooth scrolling patterns, dead zones (MEDIUM confidence, different platform but proven UX patterns)
- [Android fling/scroll gesture docs](https://developer.android.com/develop/ui/views/touch-and-input/gestures/scroll) -- velocity-based drag/swipe/fling distinction (MEDIUM confidence, mobile patterns but velocity mapping is transferable)
- Direct codebase analysis of `action.py`, `motion.py`, `keystroke.py`, `config.py`, `trigger.py` (HIGH confidence)

---
*Feature research for: scroll gesture support in gesture-keys v1.0.1*
*Researched: 2026-04-01*
