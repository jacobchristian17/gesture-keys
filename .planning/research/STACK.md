# Stack Research: Scroll Gesture Support

**Domain:** Mouse scroll events for gesture-keys app
**Researched:** 2026-04-01
**Confidence:** HIGH

## Verdict: No New Dependencies

The scroll fire mode requires **zero new packages**. The existing pynput 1.8.1 includes `pynput.mouse.Controller` with a `scroll(dx, dy)` method that supports both vertical and horizontal scrolling on Windows via `SendInput` with `MOUSEEVENTF_WHEEL` / `MOUSEEVENTF_HWHEEL`. The MotionDetector already provides per-frame velocity and direction. The work is purely integration: a new `FireMode.SCROLL`, a `ScrollSender` class wrapping pynput's mouse Controller, and velocity-to-scroll-amount mapping in the ActionDispatcher.

## Recommended Stack

### Core Technologies (no changes)

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| pynput | 1.8.1 (installed) | Mouse scroll via `pynput.mouse.Controller.scroll(dx, dy)` | Already in requirements.txt as `>=1.7.6`. No version bump needed. Scroll support exists since pynput 1.4+. |

### New Internal Components (no new packages)

| Component | Purpose | Why |
|-----------|---------|-----|
| `ScrollSender` (new class in `scroll.py`) | Wraps `pynput.mouse.Controller` for scroll events with velocity-to-amount mapping | Mirrors `KeystrokeSender` pattern; separates scroll concern from keyboard concern; testable via dependency injection |
| `FireMode.SCROLL` (new enum value in `action.py`) | Routes resolved actions to scroll dispatch instead of keyboard dispatch | Extends existing `FireMode` enum -- dispatcher already branches on fire_mode |
| Velocity-to-scroll mapping (in `ScrollSender`) | Converts MotionDetector velocity (normalized coords/sec) to scroll amount per call | Core logic for variable-speed scrolling |

## pynput Mouse Scroll API

### Method Signature

```python
from pynput.mouse import Controller
mouse = Controller()
mouse.scroll(dx: int, dy: int)
```

- `dx`: Horizontal scroll. Positive = right, negative = left.
- `dy`: Vertical scroll. Positive = up, negative = down.
- Docstring says `int` but implementation accepts and handles floats correctly.

### Windows Implementation (verified from installed pynput 1.8.1 source)

```python
# pynput/mouse/_win32.py -- actual installed code
def _scroll(self, dx, dy):
    if dy:
        SendInput(1, INPUT(MOUSE, MOUSEINPUT(
            dwFlags=MOUSEINPUT.WHEEL,
            mouseData=int(dy * WHEEL_DELTA))))  # WHEEL_DELTA = 120
    if dx:
        SendInput(1, INPUT(MOUSE, MOUSEINPUT(
            dwFlags=MOUSEINPUT.HWHEEL,
            mouseData=int(dx * WHEEL_DELTA))))
```

**Key findings verified from source:**

1. **Fractional values work.** `scroll(0, 0.5)` sends `int(0.5 * 120) = 60` wheel units -- half a notch. Enables smooth sub-notch scrolling without an accumulator.
2. **Horizontal scroll uses HWHEEL.** Separate `SendInput` call with `MOUSEEVENTF_HWHEEL`. Full Windows horizontal scroll support out of the box.
3. **Two separate SendInput calls** for combined dx+dy. Each axis is an independent event.
4. **Cast to int truncates.** Values below `1/120 = 0.0083` produce `mouseData=0` which is a no-op. This is our effective minimum.
5. **WHEEL_DELTA = 120.** Verified: one pynput scroll unit = one physical scroll notch = 120 Windows wheel units.

### Scroll Units Mental Model

| pynput `scroll()` value | Windows wheel units | User experience |
|-------------------------|--------------------|-----------------| 
| 0.25 | 30 | Quarter-notch -- very smooth, subtle |
| 0.5 | 60 | Half-notch -- smooth |
| 1.0 | 120 | One full notch -- standard click |
| 3.0 | 360 | Three notches -- fast scroll |
| 5.0 | 600 | Five notches -- very fast |

## Velocity-to-Scroll Mapping

### Available Data from MotionDetector

Per frame, the orchestrator's `MOVING_FIRE` signal provides:
- `velocity: float` -- wrist displacement in normalized coords/sec. Range: 0.15 (disarm threshold) to ~2.0+ for fast movements. Typical gesture range: 0.25-1.5.
- `direction: Direction` -- cardinal (UP, DOWN, LEFT, RIGHT).
- Signals fire every frame (~30 FPS) while in MOVING state.

### Recommended Approach: Linear Mapping with Clamp

```python
def velocity_to_scroll(velocity: float, scroll_speed: float = 3.0) -> float:
    """Convert motion velocity to scroll amount.
    
    Returns value suitable for pynput scroll() -- 1.0 = one notch.
    """
    MIN_SCROLL = 0.15   # Floor: prevents dead zone at low velocities
    MAX_SCROLL = 5.0    # Cap: prevents runaway from sudden fast movements
    amount = velocity * scroll_speed
    return max(MIN_SCROLL, min(MAX_SCROLL, amount))
```

**Why linear:** The MotionDetector velocity range is narrow (0.15-2.0). Linear mapping provides intuitive proportional control within this range. Non-linear curves (exponential, logarithmic) add complexity without benefit given the narrow input range. If tuning is needed later, adjusting `scroll_speed` is simpler than parameterizing a curve.

**Why these defaults:**
- `scroll_speed = 3.0`: Maps velocity 0.25 (arm threshold) to 0.75 scroll units/frame. At 30 FPS, steady slow movement = ~22 notches/sec (comfortable reading speed scroll). Fast movement (velocity 1.5) = 4.5 units/frame = ~135 notches/sec (page-flip speed).
- `MIN_SCROLL = 0.15`: Prevents zero-output dead zone just above the motion arm threshold. Even the slowest detected movement produces some scroll.
- `MAX_SCROLL = 5.0`: Caps sudden spikes. Without this, a fast hand jerk could send 20+ notches in one frame.

### Direction Mapping

| MotionDetector Direction | Scroll Call | User Experience |
|--------------------------|-------------|-----------------|
| UP | `scroll(0, +amount)` | Page scrolls up (content moves down) |
| DOWN | `scroll(0, -amount)` | Page scrolls down (content moves up) |
| LEFT | `scroll(-amount, 0)` | Content scrolls left |
| RIGHT | `scroll(+amount, 0)` | Content scrolls right |

pynput positive dy = "scroll up" matches the natural mapping: hand moves up, page scrolls up.

### Dispatch Throttling

The existing `dispatch_interval` throttling in `_handle_moving_fire()` applies to scroll actions too. For scroll, the default `global_dispatch_interval` of 0 (no throttle) is correct -- we want per-frame scroll delivery for smoothness. Per-action `dispatch_interval` overrides remain available if a user wants to throttle scroll rate.

## Integration Architecture

### Data Flow (scroll path bolded)

```
Pipeline.process_frame()
  -> GestureOrchestrator  (emits MOVING_FIRE signal -- unchanged)
  -> ActionDispatcher.dispatch()
    -> _handle_moving_fire()
      -> ActionResolver.resolve_moving()
      -> action.fire_mode == FireMode.SCROLL?
           YES -> scroll_sender.scroll(direction, velocity, scroll_speed)
           NO  -> sender.send(action.modifiers, action.key)  [existing]
```

### Files That Change

| File | Change | Scope |
|------|--------|-------|
| `gesture_keys/action.py` | Add `FireMode.SCROLL` enum value | 1 line |
| `gesture_keys/action.py` | `Action` dataclass: make `key_string`/`modifiers`/`key` optional for scroll actions, add `scroll_speed: float` | ~5 lines |
| `gesture_keys/action.py` | `ActionDispatcher._handle_moving_fire()`: branch on `fire_mode == SCROLL` | ~10 lines |
| `gesture_keys/action.py` | `ActionDispatcher.__init__()`: accept `scroll_sender` parameter | ~3 lines |
| `gesture_keys/scroll.py` (new) | `ScrollSender` class: wraps `pynput.mouse.Controller`, velocity-to-scroll mapping, direction routing | ~40 lines |
| `gesture_keys/config.py` | Parse `fire_mode: scroll` + `scroll_speed` from YAML action entries | ~15 lines |
| `gesture_keys/pipeline.py` | Create `ScrollSender`, inject into `ActionDispatcher` | ~5 lines |

### Action Data Model

**Use optional fields on existing `Action` (not a separate type).** Make `key_string` default to `""`, `modifiers` to `[]`, `key` to `None`. Add `scroll_speed: float = 3.0`.

Why not a separate `ScrollAction` type: Would require `Union[Action, ScrollAction]` in every resolver map type signature and every method that handles actions. The dispatcher already discriminates on `fire_mode` -- one more branch is clean. One type with optional fields is pragmatic for a single new fire mode.

### Config Format

```yaml
actions:
  # Scroll actions -- no key: field needed
  - trigger: "pinch:moving:up"
    fire_mode: scroll
    scroll_speed: 3.0      # optional, default 3.0

  - trigger: "pinch:moving:down"
    fire_mode: scroll       # uses default scroll_speed

  - trigger: "pinch:moving:left"
    fire_mode: scroll

  - trigger: "pinch:moving:right"
    fire_mode: scroll

  # Existing keyboard actions remain unchanged
  - trigger: "fist:static"
    key: "space"
    fire_mode: tap
```

`fire_mode: scroll` actions have no `key:` field. The config parser validates: if `fire_mode` is `scroll`, `key` is not required; if `fire_mode` is `tap` or `hold_key`, `key` is required.

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| pyautogui | Adds ~30MB dependency (Pillow, pytweening, etc.) for the same `SendInput` scroll call pynput already makes | `pynput.mouse.Controller.scroll()` |
| ctypes SendInput directly | Reinventing what pynput already wraps correctly, including HWHEEL for horizontal | `pynput.mouse.Controller.scroll()` |
| pywin32 / win32api | ~30MB COM-heavy dependency for identical scroll functionality | pynput (already a dependency) |
| Scroll accumulator pattern | Over-engineering. pynput natively supports sub-notch fractional values. `scroll(0, 0.25)` sends 30 wheel units. No need to accumulate across frames. | Direct per-frame `scroll()` calls with fractional amounts |
| Non-linear velocity curves | Premature complexity. Linear mapping is intuitive and tunable via single `scroll_speed` multiplier. Add curves later only if user testing demands it. | Linear mapping: `amount = clamp(velocity * scroll_speed, min, max)` |
| Separate mouse controller library | Would fragment input abstraction. Using pynput for both keyboard AND mouse keeps one library for all input simulation. | pynput handles both |
| Inertial/momentum scrolling | Significant state complexity (deceleration curves, timers). Not needed for direct gesture control where user hand position IS the scroll intent. | Stop scrolling when hand stops moving (existing MotionDetector disarm handles this) |

## Version Compatibility

No new version constraints. `requirements.txt` unchanged.

| Package | Version | Scroll Support | Notes |
|---------|---------|----------------|-------|
| pynput | >= 1.4.0 | Full (WHEEL + HWHEEL) | Horizontal scroll via HWHEEL added in 1.4 |
| pynput | 1.8.1 (installed) | Full | Verified from installed source |
| Windows 11 | 10.0.26200 | Full | `WM_MOUSEWHEEL` and `WM_MOUSEHWHEEL` fully supported |
| Python | 3.x | N/A | No new stdlib modules needed |

## Installation

```bash
# No changes to installation:
pip install -r requirements.txt

# requirements.txt remains unchanged:
# mediapipe>=0.10.33
# opencv-python>=4.8.0
# PyYAML>=6.0
# pytest>=8.0
# pynput>=1.7.6
# pystray>=0.19.5
# Pillow>=10.0
```

## Sources

- **pynput 1.8.1 installed source** (`pynput/mouse/_win32.py`) -- verified `_scroll()` implementation, `WHEEL_DELTA=120`, fractional value support, HWHEEL for horizontal (HIGH confidence)
- **pynput 1.8.1 docstring** (`Controller.scroll`) -- parameter types, method signature (HIGH confidence)
- **[Microsoft WM_MOUSEWHEEL docs](https://learn.microsoft.com/en-us/windows/win32/inputdev/wm-mousewheel)** -- WHEEL_DELTA=120 standard, sub-notch scrolling design (HIGH confidence)
- **[Microsoft WM_MOUSEHWHEEL docs](https://learn.microsoft.com/en-us/windows/win32/inputdev/wm-mousehwheel)** -- horizontal scroll message support (HIGH confidence)
- **[Raymond Chen: Why WHEEL_DELTA is 120](https://devblogs.microsoft.com/oldnewthing/?p=5473/)** -- historical context on sub-notch scrolling (HIGH confidence)
- **Codebase**: `gesture_keys/motion.py` (MotionDetector velocity/direction), `gesture_keys/action.py` (FireMode/Action/ActionDispatcher), `gesture_keys/keystroke.py` (KeystrokeSender pattern), `gesture_keys/config.py` (action parsing) -- architecture and integration points (HIGH confidence)

---
*Stack research for: gesture-keys v1.0.1 scroll gesture support*
*Researched: 2026-04-01*
