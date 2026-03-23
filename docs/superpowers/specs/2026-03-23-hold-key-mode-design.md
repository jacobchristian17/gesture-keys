# Hold-Key Mode Design Spec

## Problem

Currently, all gesture-to-key mappings fire a single keystroke (press + immediate release). There is no way to hold a key down for the duration of a gesture — e.g., holding space while maintaining a fist pose.

## Solution

Add a `mode` config option per gesture: `tap` (default, existing behavior) or `hold` (key stays pressed while gesture is active, releases when gesture stops).

## Config Changes

Add an optional `mode` field to any gesture entry in `config.yaml`. Defaults to `tap` if omitted.

```yaml
detection:
  smoothing_window: 2
  activation_delay: 0.15
  cooldown_duration: 0.3
  hold_release_delay: 0.1   # seconds before releasing held key after gesture loss

gestures:
  fist:
    key: space
    mode: hold        # "tap" (default) or "hold"
    threshold: 0.7
  open_palm:
    key: win+tab
    # mode defaults to "tap" if omitted
    threshold: 0.7
```

Valid values: `"tap"`, `"hold"`. Invalid values raise `ValueError` at config load time.

## Debouncer State Machine Changes

### Current flow (tap mode, unchanged)

```
IDLE -> ACTIVATING -> FIRED -> COOLDOWN -> IDLE
```

### New flow (hold mode)

```
IDLE -> ACTIVATING -> HOLDING -> COOLDOWN -> IDLE
```

### State descriptions

- **IDLE**: No gesture detected. Waiting.
- **ACTIVATING**: Gesture detected, counting down `activation_delay`. Prevents accidental triggers. Same behavior for both tap and hold modes. `_handle_activating` checks the gesture's mode to determine whether to transition to FIRED (tap) or HOLDING (hold).
- **FIRED** (tap only): Fire keystroke once, immediately transition to COOLDOWN.
- **HOLDING** (hold only): Key is pressed on entry to this state (emits `hold_start`). Remains pressed while the same gesture continues (`update()` returns `None`). On gesture loss, starts a release delay timer. On release delay expiry, emits `hold_end` exactly once on that frame, then transitions to COOLDOWN.
- **COOLDOWN**: After key release (hold) or fire (tap), blocks re-triggering for `cooldown_duration`.

### Gesture change during HOLDING

If a **different** gesture appears while in HOLDING state:
1. Immediately emit `hold_end` for the current gesture (release the held key).
2. Transition to ACTIVATING for the new gesture (start the activation delay for the new gesture).

This enables fluid transitions — e.g., switch from holding space (fist) to firing enter (thumbs_up).

### Debouncer interface changes

- Constructor accepts `gesture_modes: dict[str, str]` mapping gesture name to `"tap"` or `"hold"`.
- `update()` return type changes from `Optional[Gesture]` to `Optional[DebounceSignal]`.

```python
class DebounceAction(Enum):
    """Actions emitted by the debounce state machine."""
    FIRE = "fire"
    HOLD_START = "hold_start"
    HOLD_END = "hold_end"

class DebounceSignal(NamedTuple):
    """Signal emitted by debouncer update()."""
    action: DebounceAction
    gesture: Gesture
```

- The debouncer tracks the currently-held gesture internally for release delay logic.

**Migration note:** This is a breaking change to `update()`'s return type. Both main loops (`__main__.py`, `tray.py`) and all debouncer tests must be updated atomically. Callers change from `if result is not None: result.value` to `if result is not None: result.action, result.gesture`.

### Release delay

When in HOLDING state and the gesture disappears:
1. Start an internal release timer using `hold_release_delay` (default 0.1s).
2. If the **same** gesture reappears within the delay, cancel the timer and stay in HOLDING. `update()` returns `None`.
3. If a **different** gesture appears within the delay, emit `hold_end` immediately, transition to ACTIVATING for the new gesture.
4. If the delay expires (no gesture), emit `hold_end` exactly once on the expiry frame, then transition to COOLDOWN.

This prevents flicker-drops from momentary hand-tracking loss.

### Reset behavior

`reset()` is a void method. It does NOT emit signals. Callers MUST call `sender.release_all()` before calling `debouncer.reset()` whenever the debouncer might be in HOLDING state. This is the contract.

## KeystrokeSender Changes

Add three methods to `KeystrokeSender`:

```python
def press_and_hold(self, modifiers: list[Key], key: Union[Key, str]) -> None:
    """Press modifiers and key without releasing. Track held keys."""

def release_held(self) -> None:
    """Release all held keys in reverse order. Clear tracking."""

def release_all(self) -> None:
    """Force-release all currently held keys. Safety mechanism."""
```

- `press_and_hold`: Presses each modifier then the key. Records all pressed keys in `self._held_keys` (a flat `list` of pynput key objects, in press order).
- `release_held`: Takes no parameters. Releases all keys in `self._held_keys` in reverse order. Clears the list.
- `release_all`: Same as `release_held` — releases everything in `self._held_keys` in reverse. Idempotent (no-op if list is empty). Called on shutdown, config reload, hand-out-of-range, swipe-triggered reset, and error recovery.
- `_held_keys` is a simple flat list since only one hold can be active at a time (enforced by the debouncer).
- Existing `send()` method is unchanged.

## AppConfig Changes

Add to `AppConfig` dataclass:

```python
gesture_modes: dict[str, str] = field(default_factory=dict)  # gesture_name -> "tap" or "hold"
hold_release_delay: float = 0.1  # seconds
```

### load_config changes

- Extract `mode` from each gesture entry (default `"tap"`)
- Validate mode is `"tap"` or `"hold"`, raise `ValueError` otherwise
- Extract `hold_release_delay` from `detection` section (default `0.1`)
- Populate `gesture_modes` dict

## Main Loop Changes (both __main__.py and tray.py)

### Keystroke handling

Replace the current fire-and-send block:

```python
# Current
if fire_gesture is not None:
    gesture_name = fire_gesture.value
    if gesture_name in key_mappings:
        modifiers, key, key_string = key_mappings[gesture_name]
        sender.send(modifiers, key)
        logger.info("FIRED: %s -> %s", gesture_name, key_string)
```

With signal-based handling:

```python
# New
debounce_signal = debouncer.update(gesture, current_time)
if debounce_signal is not None:
    gesture_name = debounce_signal.gesture.value
    if gesture_name in key_mappings:
        modifiers, key, key_string = key_mappings[gesture_name]
        if debounce_signal.action == DebounceAction.FIRE:
            sender.send(modifiers, key)
            logger.info("FIRED: %s -> %s", gesture_name, key_string)
        elif debounce_signal.action == DebounceAction.HOLD_START:
            sender.press_and_hold(modifiers, key)
            logger.info("HOLD START: %s -> %s", gesture_name, key_string)
        elif debounce_signal.action == DebounceAction.HOLD_END:
            sender.release_held(modifiers, key)
            logger.info("HOLD END: %s -> %s", gesture_name, key_string)
```

### Safety: force-release on state transitions

Call `sender.release_all()` before `debouncer.reset()` in ALL of these scenarios:

1. **Shutdown** (`finally` block in main loop)
2. **Config reload** (before applying new config)
3. **Hand leaves distance range** (distance filter triggers)
4. **Toggle inactive** (tray mode only)
5. **Swipe enters ARMED state** (swipe-triggered debouncer reset)
6. **Swipe exits ARMED state** (swipe-triggered debouncer reset)

### Hot-reload

On config reload:
1. `sender.release_all()` — release any held keys
2. `debouncer.reset()` — clears any HOLDING state
3. Reload gesture modes into debouncer
4. Re-parse key mappings

### Logging

All HOLDING state transitions are logged at DEBUG level:
- `ACTIVATING -> HOLDING: <gesture>` on hold entry
- `HOLDING: release delay started` on gesture loss
- `HOLDING: release delay cancelled` on gesture return during delay
- `HOLDING -> COOLDOWN: <gesture> released` on release delay expiry
- `HOLDING -> ACTIVATING: <gesture> released, switching to <new_gesture>` on gesture change

## Scope Exclusions

- No hold mode for swipe gestures
- No repeat-rate emulation (OS handles key repeat natively)
- No simultaneous multi-gesture holds (one hold at a time, enforced by debouncer's single-gesture tracking)
- No hold-specific activation delay (uses the same `activation_delay` as tap)

## Testing Strategy

### Debouncer hold state transitions
- IDLE -> ACTIVATING -> HOLDING (hold-mode gesture held past activation_delay)
- HOLDING -> COOLDOWN (gesture lost, release delay expires)
- HOLDING -> COOLDOWN -> IDLE (full cycle)

### Release delay edge cases
- Gesture drops and returns within delay -> cancel timer, stay HOLDING, no signal emitted
- Gesture drops and delay expires -> emit `hold_end` exactly once on expiry frame
- Gesture drops, different gesture appears within delay -> emit `hold_end`, transition to ACTIVATING
- Multiple rapid drops within delay -> only one `hold_end` emitted

### Gesture change during HOLDING
- Different gesture during HOLDING -> `hold_end` for current, ACTIVATING for new
- Same gesture during HOLDING -> no signal, stay HOLDING

### KeystrokeSender
- `press_and_hold` populates `_held_keys`
- `release_held` clears `_held_keys` and releases in reverse order
- `release_all` is idempotent (no-op when empty)

### Config parsing
- `mode: hold` parsed correctly
- `mode: tap` parsed correctly
- Missing `mode` defaults to `tap`
- Invalid `mode` raises `ValueError`
- `hold_release_delay` parsed from detection section

### Safety
- Force-release on shutdown path
- Force-release before debouncer reset
- Force-release on config reload
