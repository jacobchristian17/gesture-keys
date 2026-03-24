# Static-to-Swipe Compound Gesture

## Summary

A new compound gesture type where a static hand pose followed by a quick swipe fires a single configured keystroke. The static gesture's normal action is delayed by a swipe window; if a swipe is detected within that window, the compound action fires instead. If no swipe occurs, the static gesture fires normally after the window expires.

## Motivation

Expands the gesture vocabulary without requiring new hand poses. Users can combine existing static gestures with directional swipes to trigger additional actions, effectively multiplying the number of available bindings per gesture.

## Behavior

### Core Flow

1. User forms a static gesture (e.g. peace sign)
2. Gesture is recognized — debouncer enters ACTIVATING, then immediately transitions to SWIPE_WINDOW (if gesture has swipe mappings)
3. Swipe window timer starts from the SWIPE_WINDOW entry time
4. **Swipe detected within window**: fire the compound keystroke (looked up by gesture + direction), skip the static action entirely, enter COOLDOWN
5. **Window expires without swipe**: fire the static gesture's normal keystroke, enter COOLDOWN
6. **Gesture lost during window**: nothing fires, return to IDLE

### Timing

- The swipe window starts at gesture recognition, not after activation delay
- For gestures with swipe mappings, `swipe_window` replaces `activation_delay` entirely — the static action fires after `swipe_window` expires (not `swipe_window + activation_delay`)
- Gestures without swipe mappings are completely unaffected — no added latency

### Constraints

- **Tap mode only**: Hold mode gestures cannot have swipe mappings (rejected at config validation). Hold mode requires immediate key-down and is incompatible with the swipe window delay.
- **First swipe wins**: If a swipe fires during the window, the swipe detector enters its normal cooldown, preventing double-fires. The debouncer also transitions to COOLDOWN.
- **Unmapped directions**: If the user swipes in a direction that isn't configured (e.g. swipe_up when only left/right are mapped), the swipe is ignored and the static gesture fires normally after the window expires.

## Configuration

### New Global Setting

```yaml
detection:
  swipe_window: 0.2    # seconds to wait for swipe after gesture recognition
                        # default: 0.2
```

### Per-Gesture Swipe Block

```yaml
gestures:
  peace:
    key: "ctrl+z"
    mode: "tap"
    swipe:
      swipe_left:
        key: "ctrl+shift+left"
      swipe_right:
        key: "ctrl+shift+right"
      swipe_up:
        key: "ctrl+shift+up"
      swipe_down:
        key: "ctrl+shift+down"
```

- The `swipe` block is optional on any gesture
- Not all four directions need to be mapped — only configure what you need
- Each direction has a `key` field using the same format as all other key mappings
- Swipe detection reuses the existing global swipe thresholds (velocity, displacement, axis ratio) from the top-level `swipe` config section

### Left-Hand Support

Left-hand overrides for per-gesture swipe blocks follow the same pattern as existing left-hand config. The `left_gestures` section can include `swipe` blocks that override the right-hand defaults:

```yaml
left_gestures:
  peace:
    swipe:
      swipe_left:
        key: "ctrl+shift+right"    # mirrored direction
      swipe_right:
        key: "ctrl+shift+left"
```

### Hot Reload

Config hot-reload applies to `swipe_window` and per-gesture `swipe` blocks. If a gesture's swipe config is removed during a reload while the debouncer is in SWIPE_WINDOW state, the debouncer treats it as if the window expired — fires the static gesture's normal action and transitions to COOLDOWN.

## Module Changes

### `debounce.py`

- New state `SWIPE_WINDOW` in `DebounceState` enum
- `update()` accepts an optional `swipe_direction` parameter (a `SwipeDirection` or `None`)
- Constructor accepts a set of gesture names that have swipe mappings, and the `swipe_window` duration
- On entering ACTIVATING for a gesture with swipe mappings: immediately transition to `SWIPE_WINDOW`, record window start time
- During `SWIPE_WINDOW`:
  - Swipe direction received and direction is mapped → return `COMPOUND_FIRE`, transition to COOLDOWN
  - Swipe direction received but unmapped → ignore, continue waiting
  - Window expires → fire normal static action (return `FIRE`), transition to COOLDOWN
  - Gesture lost → transition to IDLE, return None
  - Gesture changes → transition to IDLE, then re-enter ACTIVATING for new gesture (same as existing behavior)
- New `DebounceAction.COMPOUND_FIRE` enum value
- `DebounceSignal` gets a new optional field `direction: Optional[SwipeDirection]` (default `None`). For `COMPOUND_FIRE` signals, this carries the swipe direction. For all other signals, it remains `None`.
- New property `in_swipe_window` → True when state is `SWIPE_WINDOW`

### `swipe.py`

- No changes to swipe detection logic or thresholds
- Swipe suppression is controlled by the caller (`__main__.py`), not internally

### `__main__.py`

- Swipe suppression logic changes: swipes are suppressed when `debouncer.is_activating` is True **and** `debouncer.in_swipe_window` is False. During `SWIPE_WINDOW`, swipes are allowed.
- Swipe results are always passed to `debouncer.update()` via the new `swipe_direction` parameter
- When debouncer returns `COMPOUND_FIRE`: look up the compound keystroke from config using the signal's gesture + direction, send it via keystroke sender. The swipe result is **consumed** — it is not also fired as a standalone swipe.
- When debouncer is not in `SWIPE_WINDOW` and a swipe fires: handle as standalone swipe (existing behavior)

### `config.py`

- Parse `swipe_window` under `detection` with default `0.2`
- Parse optional `swipe` block under each gesture into a dict of `{SwipeDirection: key_string}`
- Validate key strings in swipe mappings at startup (fail-fast, same as existing gesture key validation)
- Reject `swipe` block on hold mode gestures at config validation with a clear error message
- Left-hand gesture merge includes `swipe` block merging

### `keystroke.py`

- No structural changes — receives key strings as before

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| No static gesture active, user swipes | Standalone swipe fires as today |
| Gesture with swipe mapping, no swipe within window | Static keystroke fires after swipe_window expires |
| Gesture without swipe mapping | Fires at normal activation_delay, no swipe window |
| Swipe in unmapped direction during window | Ignored; static fires after window |
| Gesture lost during swipe window | Nothing fires, return to IDLE |
| Hold mode gesture with swipe block in config | Rejected at config validation |
| Multiple swipes during window | First swipe wins; swipe detector enters its own cooldown |
| Gesture changes during swipe window | Window cancelled, re-enter ACTIVATING for new gesture |
| Config reload removes swipe block during SWIPE_WINDOW | Treated as window expired; fire static action |

## State Machine

```
IDLE ──[gesture detected]──► ACTIVATING
                                │
                ┌───────────────┴───────────────┐
                │ has swipe mappings             │ no swipe mappings
                │ (immediate transition)         │
                ▼                                ▼
         SWIPE_WINDOW                    (normal activation)
         │      │      │                        │
  swipe  │      │      │ gesture                │ delay met
  found  │      │      │ lost                   ▼
  (mapped)      │      │                      FIRED
         │      │      ▼                        │
         ▼      │    IDLE                       ▼
   COMPOUND     │                            COOLDOWN
   FIRE         │ window expires                │
     │          ▼                               ▼
     ▼        FIRED                           IDLE
  COOLDOWN      │
     │          ▼
     ▼       COOLDOWN
   IDLE         │
                ▼
              IDLE
```
