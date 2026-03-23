# Hold-Key Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow gestures to hold a key down for their duration instead of firing once, configured per-gesture via `mode: hold` in config.yaml.

**Architecture:** Extend the debounce state machine with a HOLDING state that presses a key on entry and releases on exit. Add `press_and_hold` / `release_held` / `release_all` methods to `KeystrokeSender`. Use a `DebounceSignal` NamedTuple as the new return type from `debouncer.update()` to communicate fire/hold_start/hold_end actions.

**Tech Stack:** Python 3, pynput, pytest, YAML config

**Spec:** `docs/superpowers/specs/2026-03-23-hold-key-mode-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `gesture_keys/debounce.py` | Modify | Add `DebounceAction` enum, `DebounceSignal` NamedTuple, `HOLDING` state, release delay logic, gesture mode awareness |
| `gesture_keys/keystroke.py` | Modify | Add `press_and_hold`, `release_held`, `release_all` methods |
| `gesture_keys/config.py` | Modify | Parse `mode` field, add `gesture_modes` and `hold_release_delay` to `AppConfig` |
| `gesture_keys/__main__.py` | Modify | Signal-based keystroke handling, force-release safety calls |
| `gesture_keys/tray.py` | Modify | Same signal-based handling and safety calls as `__main__.py` |
| `tests/test_debounce.py` | Modify | Update all existing tests for new return type, add hold-mode tests |
| `tests/test_keystroke.py` | Modify | Add tests for new methods |
| `tests/test_config.py` | Modify | Add tests for `mode` and `hold_release_delay` parsing |

---

### Task 1: Add DebounceAction enum and DebounceSignal NamedTuple

**Files:**
- Modify: `gesture_keys/debounce.py:1-21`
- Modify: `tests/test_debounce.py`

- [ ] **Step 1: Write test for DebounceSignal import and structure**

```python
# tests/test_debounce.py - add at top of file after existing imports
from gesture_keys.debounce import DebounceAction, DebounceSignal

class TestDebounceSignal:
    """Test DebounceSignal and DebounceAction types."""

    def test_debounce_action_values(self):
        assert DebounceAction.FIRE.value == "fire"
        assert DebounceAction.HOLD_START.value == "hold_start"
        assert DebounceAction.HOLD_END.value == "hold_end"

    def test_debounce_signal_creation(self):
        signal = DebounceSignal(DebounceAction.FIRE, Gesture.FIST)
        assert signal.action == DebounceAction.FIRE
        assert signal.gesture == Gesture.FIST

    def test_debounce_signal_unpacking(self):
        signal = DebounceSignal(DebounceAction.HOLD_START, Gesture.PEACE)
        action, gesture = signal
        assert action == DebounceAction.HOLD_START
        assert gesture == Gesture.PEACE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_debounce.py::TestDebounceSignal -v`
Expected: FAIL with `ImportError: cannot import name 'DebounceAction'`

- [ ] **Step 3: Implement DebounceAction and DebounceSignal**

In `gesture_keys/debounce.py`, add after existing imports:

```python
from typing import NamedTuple, Optional

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

Note: `NamedTuple` import replaces existing `Optional` import from `typing`. Keep `Optional` in the same import line.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_debounce.py::TestDebounceSignal -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gesture_keys/debounce.py tests/test_debounce.py
git commit -m "feat: add DebounceAction enum and DebounceSignal NamedTuple"
```

---

### Task 2: Change debouncer.update() to return DebounceSignal for tap mode

This is the breaking change. Update `update()` to return `Optional[DebounceSignal]` instead of `Optional[Gesture]`, wrapping tap-mode fires in `DebounceSignal(DebounceAction.FIRE, gesture)`.

**Files:**
- Modify: `gesture_keys/debounce.py:80-101` (update method and _handle_activating)
- Modify: `tests/test_debounce.py` (update ALL existing assertions)

- [ ] **Step 1: Update all existing test assertions**

Every test that checks `result == Gesture.FIST` (or similar) must change to `result == DebounceSignal(DebounceAction.FIRE, Gesture.FIST)`. Every test that checks `result is None` stays unchanged.

Update these specific assertions:

```python
# TestDebounceStateTransitions
# test_activating_to_fired_after_delay (line 34):
assert result == DebounceSignal(DebounceAction.FIRE, Gesture.FIST)

# test_activating_resets_on_gesture_switch (line 53):
assert result == DebounceSignal(DebounceAction.FIRE, Gesture.PEACE)

# TestDirectTransitions
# test_different_gesture_during_cooldown_eventually_fires (line 149):
assert result == DebounceSignal(DebounceAction.FIRE, Gesture.PEACE)

# test_rapid_switch_during_cooldown_fires_final_gesture (line 175):
assert result == DebounceSignal(DebounceAction.FIRE, Gesture.POINTING)

# TestDebounceStateTransitions
# test_fires_exactly_once_per_hold (line 115):
assert fire1 == DebounceSignal(DebounceAction.FIRE, Gesture.FIST)
```

Also add the import `from gesture_keys.debounce import DebounceAction, DebounceSignal` to the top of the test file (if not already added in Task 1).

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_debounce.py -v`
Expected: FAIL — tests expect `DebounceSignal` but `update()` still returns `Gesture`

- [ ] **Step 3: Update _handle_activating to return DebounceSignal**

In `gesture_keys/debounce.py`, change `_handle_activating` return on fire:

```python
def _handle_activating(
    self, gesture: Optional[Gesture], timestamp: float
) -> Optional[DebounceSignal]:
    if gesture is None:
        self._state = DebounceState.IDLE
        self._activating_gesture = None
        logger.debug("ACTIVATING -> IDLE: gesture released")
        return None

    if gesture != self._activating_gesture:
        self._activating_gesture = gesture
        self._activation_start = timestamp
        logger.debug("ACTIVATING reset: switched to %s", gesture.value)
        return None

    if timestamp - self._activation_start >= self._activation_delay:
        self._state = DebounceState.FIRED
        logger.debug("ACTIVATING -> FIRED: %s", gesture.value)
        return DebounceSignal(DebounceAction.FIRE, gesture)

    return None
```

Also update the `update()` return type annotation:

```python
def update(
    self, gesture: Optional[Gesture], timestamp: float
) -> Optional[DebounceSignal]:
```

And update all other `_handle_*` method return type annotations to `Optional[DebounceSignal]`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_debounce.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add gesture_keys/debounce.py tests/test_debounce.py
git commit -m "refactor: change debouncer.update() to return DebounceSignal"
```

---

### Task 3: Add press_and_hold, release_held, release_all to KeystrokeSender

**Files:**
- Modify: `gesture_keys/keystroke.py:87-119`
- Modify: `tests/test_keystroke.py`

- [ ] **Step 1: Write failing tests for press_and_hold**

```python
# tests/test_keystroke.py - add new test class

class TestKeystrokeSenderHold:
    """Test hold-mode keystroke methods."""

    def test_press_and_hold_single_key(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        sender.press_and_hold([], Key.space)

        mock_ctrl.press.assert_called_once_with(Key.space)
        mock_ctrl.release.assert_not_called()

    def test_press_and_hold_with_modifiers(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        sender.press_and_hold([Key.ctrl, Key.shift], "a")

        expected_presses = [call(Key.ctrl), call(Key.shift), call("a")]
        assert mock_ctrl.press.call_args_list == expected_presses
        mock_ctrl.release.assert_not_called()

    def test_press_and_hold_tracks_held_keys(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        sender.press_and_hold([Key.ctrl], "z")

        assert len(sender._held_keys) == 2
        assert sender._held_keys == [Key.ctrl, "z"]

    def test_release_held_releases_in_reverse(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        sender.press_and_hold([Key.ctrl, Key.shift], "s")
        mock_ctrl.reset_mock()

        sender.release_held()

        expected_releases = [call("s"), call(Key.shift), call(Key.ctrl)]
        assert mock_ctrl.release.call_args_list == expected_releases
        assert sender._held_keys == []

    def test_release_held_noop_when_empty(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        sender.release_held()  # should not raise

        mock_ctrl.release.assert_not_called()

    def test_release_all_releases_everything(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        sender.press_and_hold([Key.alt], Key.tab)
        mock_ctrl.reset_mock()

        sender.release_all()

        expected_releases = [call(Key.tab), call(Key.alt)]
        assert mock_ctrl.release.call_args_list == expected_releases
        assert sender._held_keys == []

    def test_release_all_idempotent(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        sender.release_all()
        sender.release_all()

        mock_ctrl.release.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_keystroke.py::TestKeystrokeSenderHold -v`
Expected: FAIL with `AttributeError: 'KeystrokeSender' object has no attribute 'press_and_hold'`

- [ ] **Step 3: Implement the three methods**

In `gesture_keys/keystroke.py`, add to `KeystrokeSender`:

```python
class KeystrokeSender:
    def __init__(self) -> None:
        self._controller = Controller()
        self._held_keys: list[Union[Key, str]] = []

    # ... existing send() method stays unchanged ...

    def press_and_hold(
        self, modifiers: list[Key], key: Union[Key, str]
    ) -> None:
        """Press modifiers and key without releasing. Tracks held keys.

        Args:
            modifiers: List of modifier Key objects to press.
            key: Final key to press (Key enum or single character str).

        Raises:
            Any exception from pynput, after releasing all pressed keys.
        """
        try:
            for mod in modifiers:
                self._controller.press(mod)
                self._held_keys.append(mod)
            self._controller.press(key)
            self._held_keys.append(key)
        except Exception:
            self.release_held()
            raise

    def release_held(self) -> None:
        """Release all currently held keys in reverse order."""
        for k in reversed(self._held_keys):
            self._controller.release(k)
        self._held_keys.clear()

    def release_all(self) -> None:
        """Force-release all held keys. Idempotent safety mechanism."""
        self.release_held()
```

Also add `self._held_keys: list[Union[Key, str]] = []` to `__init__`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_keystroke.py -v`
Expected: ALL PASS (both old and new tests)

- [ ] **Step 5: Commit**

```bash
git add gesture_keys/keystroke.py tests/test_keystroke.py
git commit -m "feat: add press_and_hold, release_held, release_all to KeystrokeSender"
```

---

### Task 4: Add gesture_modes and hold_release_delay to config

**Files:**
- Modify: `gesture_keys/config.py:14-32` (AppConfig), `gesture_keys/config.py:91-162` (load_config)
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for mode parsing**

```python
# tests/test_config.py - add new test class

class TestGestureModesConfig:
    """Test gesture mode config parsing."""

    MINIMAL_YAML = (
        "camera:\n  index: 0\n"
        "gestures:\n"
        "  open_palm:\n    key: space\n    threshold: 0.7\n"
    )

    def test_appconfig_default_gesture_modes_empty(self):
        config = AppConfig()
        assert config.gesture_modes == {}

    def test_appconfig_default_hold_release_delay(self):
        config = AppConfig()
        assert config.hold_release_delay == 0.1

    def test_mode_hold_parsed(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "gestures:\n"
            "  fist:\n    key: space\n    threshold: 0.7\n    mode: hold\n"
        )
        config = load_config(str(cfg))
        assert config.gesture_modes == {"fist": "hold"}

    def test_mode_tap_parsed(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "gestures:\n"
            "  fist:\n    key: space\n    threshold: 0.7\n    mode: tap\n"
        )
        config = load_config(str(cfg))
        assert config.gesture_modes == {"fist": "tap"}

    def test_mode_defaults_to_tap_when_missing(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(self.MINIMAL_YAML)
        config = load_config(str(cfg))
        assert config.gesture_modes == {"open_palm": "tap"}

    def test_invalid_mode_raises_valueerror(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "gestures:\n"
            "  fist:\n    key: space\n    threshold: 0.7\n    mode: toggle\n"
        )
        with pytest.raises(ValueError, match="mode"):
            load_config(str(cfg))

    def test_hold_release_delay_from_config(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "detection:\n  hold_release_delay: 0.2\n"
            "gestures:\n"
            "  open_palm:\n    key: space\n    threshold: 0.7\n"
        )
        config = load_config(str(cfg))
        assert config.hold_release_delay == 0.2

    def test_hold_release_delay_default_when_missing(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(self.MINIMAL_YAML)
        config = load_config(str(cfg))
        assert config.hold_release_delay == 0.1

    def test_mixed_modes(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "gestures:\n"
            "  fist:\n    key: space\n    threshold: 0.7\n    mode: hold\n"
            "  open_palm:\n    key: enter\n    threshold: 0.7\n"
            "  pinch:\n    key: tab\n    threshold: 0.06\n    mode: tap\n"
        )
        config = load_config(str(cfg))
        assert config.gesture_modes == {
            "fist": "hold",
            "open_palm": "tap",
            "pinch": "tap",
        }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py::TestGestureModesConfig -v`
Expected: FAIL with `AttributeError: 'AppConfig' has no attribute 'gesture_modes'`

- [ ] **Step 3: Implement config changes**

In `gesture_keys/config.py`, add fields to `AppConfig`:

```python
@dataclass
class AppConfig:
    # ... existing fields ...
    gesture_modes: dict[str, str] = field(default_factory=dict)
    hold_release_delay: float = 0.1
```

Add extraction function:

```python
def _extract_gesture_modes(gestures: dict) -> dict[str, str]:
    """Extract per-gesture mode from gesture config entries.

    Args:
        gestures: Gesture config dict {name: {key: ..., mode: ...}}.

    Returns:
        Dict mapping gesture_name -> "tap" or "hold" for all gestures.

    Raises:
        ValueError: If a gesture has an invalid mode value.
    """
    valid_modes = {"tap", "hold"}
    modes: dict[str, str] = {}
    for name, settings in gestures.items():
        if isinstance(settings, dict):
            mode = str(settings.get("mode", "tap")).lower()
            if mode not in valid_modes:
                raise ValueError(
                    f"Gesture '{name}' has invalid mode '{mode}'. "
                    f"Valid modes: {valid_modes}"
                )
            modes[name] = mode
    return modes
```

In `load_config`, add before the `return AppConfig(...)`:

```python
gesture_modes = _extract_gesture_modes(gestures)
```

And add to the `return AppConfig(...)` call:

```python
gesture_modes=gesture_modes,
hold_release_delay=float(detection.get("hold_release_delay", 0.1)),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add gesture_keys/config.py tests/test_config.py
git commit -m "feat: add gesture_modes and hold_release_delay to config"
```

---

### Task 5: Add HOLDING state and release delay to debouncer

This is the core logic. The debouncer needs to know each gesture's mode to decide between FIRED and HOLDING transitions.

**Files:**
- Modify: `gesture_keys/debounce.py`
- Modify: `tests/test_debounce.py`

- [ ] **Step 1: Write failing tests for HOLDING state transitions**

```python
# tests/test_debounce.py - add new test classes

class TestHoldModeBasic:
    """Test HOLDING state for hold-mode gestures."""

    def test_hold_mode_activating_to_holding(self):
        """Hold gesture transitions ACTIVATING -> HOLDING (not FIRED)."""
        d = GestureDebouncer(
            activation_delay=0.4,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)  # IDLE -> ACTIVATING
        result = d.update(Gesture.FIST, 0.5)  # ACTIVATING -> HOLDING
        assert result == DebounceSignal(DebounceAction.HOLD_START, Gesture.FIST)
        assert d.state == DebounceState.HOLDING

    def test_hold_mode_stays_holding_while_gesture_continues(self):
        """While gesture is maintained, stay in HOLDING and return None."""
        d = GestureDebouncer(
            activation_delay=0.4,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        result = d.update(Gesture.FIST, 0.6)
        assert result is None
        assert d.state == DebounceState.HOLDING

    def test_hold_mode_release_delay_absorbs_flicker(self):
        """Gesture drops briefly but returns within release delay -> stays HOLDING."""
        d = GestureDebouncer(
            activation_delay=0.4,
            hold_release_delay=0.1,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        result = d.update(None, 0.55)  # gesture lost, release delay starts
        assert result is None
        assert d.state == DebounceState.HOLDING
        # Gesture returns within 0.1s
        result = d.update(Gesture.FIST, 0.6)
        assert result is None
        assert d.state == DebounceState.HOLDING

    def test_hold_mode_release_after_delay_expires(self):
        """Gesture lost and release delay expires -> emit hold_end, COOLDOWN."""
        d = GestureDebouncer(
            activation_delay=0.4,
            hold_release_delay=0.1,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        d.update(None, 0.55)  # gesture lost
        result = d.update(None, 0.7)  # release delay expired (0.55 + 0.1 < 0.7)
        assert result == DebounceSignal(DebounceAction.HOLD_END, Gesture.FIST)
        assert d.state == DebounceState.COOLDOWN

    def test_hold_mode_emits_hold_end_exactly_once(self):
        """After hold_end is emitted, subsequent updates return None."""
        d = GestureDebouncer(
            activation_delay=0.4,
            cooldown_duration=0.3,
            hold_release_delay=0.1,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        d.update(None, 0.55)  # gesture lost
        d.update(None, 0.7)  # hold_end emitted
        result = d.update(None, 0.8)  # should be None (in COOLDOWN)
        assert result is None

    def test_tap_mode_unchanged_when_hold_modes_exist(self):
        """Tap-mode gestures still use FIRED path even when hold modes configured."""
        d = GestureDebouncer(
            activation_delay=0.4,
            gesture_modes={"fist": "hold", "peace": "tap"},
        )
        d.update(Gesture.PEACE, 0.0)
        result = d.update(Gesture.PEACE, 0.5)
        assert result == DebounceSignal(DebounceAction.FIRE, Gesture.PEACE)
        assert d.state == DebounceState.FIRED

    def test_multiple_rapid_drops_within_delay(self):
        """Rapid flicker: gesture drops and returns multiple times within delay."""
        d = GestureDebouncer(
            activation_delay=0.4,
            hold_release_delay=0.1,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        # Rapid flicker
        assert d.update(None, 0.55) is None         # drop 1
        assert d.update(Gesture.FIST, 0.57) is None # return 1
        assert d.update(None, 0.59) is None         # drop 2
        assert d.update(Gesture.FIST, 0.61) is None # return 2
        assert d.state == DebounceState.HOLDING
        # No hold_end was emitted

    def test_is_activating_false_in_holding(self):
        """is_activating property returns False during HOLDING state."""
        d = GestureDebouncer(
            activation_delay=0.4,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        assert d.is_activating is False


class TestHoldModeGestureChange:
    """Test gesture changes during HOLDING state."""

    def test_different_gesture_during_holding_emits_hold_end(self):
        """Different gesture while HOLDING -> hold_end for current."""
        d = GestureDebouncer(
            activation_delay=0.4,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        result = d.update(Gesture.PEACE, 0.6)
        assert result == DebounceSignal(DebounceAction.HOLD_END, Gesture.FIST)
        assert d.state == DebounceState.ACTIVATING

    def test_different_gesture_during_holding_starts_activating_new(self):
        """After hold_end from gesture change, new gesture is activating."""
        d = GestureDebouncer(
            activation_delay=0.4,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        d.update(Gesture.PEACE, 0.6)  # -> hold_end + ACTIVATING(PEACE)
        # Now hold PEACE for activation_delay
        result = d.update(Gesture.PEACE, 1.1)
        assert result == DebounceSignal(DebounceAction.FIRE, Gesture.PEACE)

    def test_different_gesture_during_release_delay(self):
        """Different gesture appears during release delay -> hold_end + ACTIVATING."""
        d = GestureDebouncer(
            activation_delay=0.4,
            hold_release_delay=0.1,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        d.update(None, 0.55)  # gesture lost, release delay starts
        result = d.update(Gesture.PEACE, 0.58)  # different gesture within delay
        assert result == DebounceSignal(DebounceAction.HOLD_END, Gesture.FIST)
        assert d.state == DebounceState.ACTIVATING


class TestHoldModeCooldownCycle:
    """Test full hold cycle including cooldown."""

    def test_full_hold_cycle(self):
        """IDLE -> ACTIVATING -> HOLDING -> COOLDOWN -> IDLE."""
        d = GestureDebouncer(
            activation_delay=0.4,
            cooldown_duration=0.3,
            hold_release_delay=0.1,
            gesture_modes={"fist": "hold"},
        )
        # IDLE -> ACTIVATING
        d.update(Gesture.FIST, 0.0)
        assert d.state == DebounceState.ACTIVATING

        # ACTIVATING -> HOLDING
        result = d.update(Gesture.FIST, 0.5)
        assert result == DebounceSignal(DebounceAction.HOLD_START, Gesture.FIST)
        assert d.state == DebounceState.HOLDING

        # Stay HOLDING
        assert d.update(Gesture.FIST, 0.6) is None

        # Gesture lost
        d.update(None, 0.7)
        assert d.state == DebounceState.HOLDING  # release delay

        # Release delay expires -> COOLDOWN
        result = d.update(None, 0.85)
        assert result == DebounceSignal(DebounceAction.HOLD_END, Gesture.FIST)
        assert d.state == DebounceState.COOLDOWN

        # Cooldown expires + release -> IDLE
        d.update(None, 1.2)
        assert d.state == DebounceState.IDLE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_debounce.py::TestHoldModeBasic tests/test_debounce.py::TestHoldModeGestureChange tests/test_debounce.py::TestHoldModeCooldownCycle -v`
Expected: FAIL — `HOLDING` state doesn't exist, `gesture_modes` parameter not accepted

- [ ] **Step 3: Implement HOLDING state in debouncer**

In `gesture_keys/debounce.py`:

1. Update the module docstring to include the hold state machine flow:
```
State machine (tap):  IDLE -> ACTIVATING -> FIRED -> COOLDOWN -> IDLE
State machine (hold): IDLE -> ACTIVATING -> HOLDING -> COOLDOWN -> IDLE
```

2. Add `HOLDING` to `DebounceState` enum:
```python
class DebounceState(Enum):
    IDLE = "IDLE"
    ACTIVATING = "ACTIVATING"
    FIRED = "FIRED"
    COOLDOWN = "COOLDOWN"
    HOLDING = "HOLDING"
```

2. Add `gesture_modes` and `hold_release_delay` to `__init__`:
```python
def __init__(
    self,
    activation_delay: float = 0.15,
    cooldown_duration: float = 0.3,
    gesture_cooldowns: dict[str, float] | None = None,
    gesture_modes: dict[str, str] | None = None,
    hold_release_delay: float = 0.1,
) -> None:
    self._activation_delay = activation_delay
    self._cooldown_duration = cooldown_duration
    self._gesture_cooldowns = gesture_cooldowns or {}
    self._gesture_modes = gesture_modes or {}
    self._hold_release_delay = hold_release_delay
    self._cooldown_duration_active = cooldown_duration
    self._state = DebounceState.IDLE
    self._activating_gesture: Optional[Gesture] = None
    self._activation_start: float = 0.0
    self._cooldown_start: float = 0.0
    self._cooldown_gesture: Optional[Gesture] = None
    self._holding_gesture: Optional[Gesture] = None
    self._release_delay_start: Optional[float] = None
```

3. Add `HOLDING` dispatch to `update()`:
```python
def update(
    self, gesture: Optional[Gesture], timestamp: float
) -> Optional[DebounceSignal]:
    if self._state == DebounceState.IDLE:
        return self._handle_idle(gesture, timestamp)
    elif self._state == DebounceState.ACTIVATING:
        return self._handle_activating(gesture, timestamp)
    elif self._state == DebounceState.FIRED:
        return self._handle_fired(gesture, timestamp)
    elif self._state == DebounceState.COOLDOWN:
        return self._handle_cooldown(gesture, timestamp)
    elif self._state == DebounceState.HOLDING:
        return self._handle_holding(gesture, timestamp)
    return None
```

4. Modify `_handle_activating` to branch on mode:
```python
def _handle_activating(
    self, gesture: Optional[Gesture], timestamp: float
) -> Optional[DebounceSignal]:
    if gesture is None:
        self._state = DebounceState.IDLE
        self._activating_gesture = None
        logger.debug("ACTIVATING -> IDLE: gesture released")
        return None

    if gesture != self._activating_gesture:
        self._activating_gesture = gesture
        self._activation_start = timestamp
        logger.debug("ACTIVATING reset: switched to %s", gesture.value)
        return None

    if timestamp - self._activation_start >= self._activation_delay:
        mode = self._gesture_modes.get(gesture.value, "tap")
        if mode == "hold":
            self._state = DebounceState.HOLDING
            self._holding_gesture = gesture
            self._release_delay_start = None
            self._activating_gesture = None
            logger.debug("ACTIVATING -> HOLDING: %s", gesture.value)
            return DebounceSignal(DebounceAction.HOLD_START, gesture)
        else:
            self._state = DebounceState.FIRED
            logger.debug("ACTIVATING -> FIRED: %s", gesture.value)
            return DebounceSignal(DebounceAction.FIRE, gesture)

    return None
```

5. Add `_handle_holding`:
```python
def _handle_holding(
    self, gesture: Optional[Gesture], timestamp: float
) -> Optional[DebounceSignal]:
    held = self._holding_gesture

    # Same gesture still active -> stay holding, cancel any release delay
    if gesture == held:
        self._release_delay_start = None
        return None

    # Different gesture -> release current, start activating new
    if gesture is not None and gesture != held:
        self._state = DebounceState.ACTIVATING
        self._activating_gesture = gesture
        self._activation_start = timestamp
        self._holding_gesture = None
        self._release_delay_start = None
        logger.debug(
            "HOLDING -> ACTIVATING: %s released, switching to %s",
            held.value, gesture.value,
        )
        return DebounceSignal(DebounceAction.HOLD_END, held)

    # Gesture lost (None) -> manage release delay
    if self._release_delay_start is None:
        # Start release delay timer
        self._release_delay_start = timestamp
        logger.debug("HOLDING: release delay started")
        return None

    # Release delay not yet expired
    if timestamp - self._release_delay_start < self._hold_release_delay:
        return None

    # Release delay expired -> release and cooldown
    self._state = DebounceState.COOLDOWN
    self._cooldown_start = timestamp
    self._cooldown_duration_active = self._gesture_cooldowns.get(
        held.value, self._cooldown_duration
    )
    self._cooldown_gesture = held
    self._holding_gesture = None
    self._release_delay_start = None
    logger.debug("HOLDING -> COOLDOWN: %s released", held.value)
    return DebounceSignal(DebounceAction.HOLD_END, held)
```

6. Update `reset()` to clear hold state:
```python
def reset(self) -> None:
    self._state = DebounceState.IDLE
    self._activating_gesture = None
    self._activation_start = 0.0
    self._cooldown_start = 0.0
    self._cooldown_gesture = None
    self._cooldown_duration_active = self._cooldown_duration
    self._holding_gesture = None
    self._release_delay_start = None
```

- [ ] **Step 4: Run ALL debounce tests**

Run: `pytest tests/test_debounce.py -v`
Expected: ALL PASS (old tap tests + new hold tests)

- [ ] **Step 5: Commit**

```bash
git add gesture_keys/debounce.py tests/test_debounce.py
git commit -m "feat: add HOLDING state with release delay to debouncer"
```

---

### Task 6: Update __main__.py for signal-based handling and safety

**Files:**
- Modify: `gesture_keys/__main__.py`

- [ ] **Step 1: Update imports**

Add to imports in `__main__.py`:

```python
from gesture_keys.debounce import DebounceAction, GestureDebouncer
```

(`DebounceAction` is new; `GestureDebouncer` is already imported but make sure `DebounceAction` is there)

- [ ] **Step 2: Pass gesture_modes and hold_release_delay to debouncer constructor**

In `run_preview_mode`, update the debouncer creation (~line 145):

```python
debouncer = GestureDebouncer(
    config.activation_delay, config.cooldown_duration,
    gesture_cooldowns=config.gesture_cooldowns,
    gesture_modes=config.gesture_modes,
    hold_release_delay=config.hold_release_delay,
)
```

- [ ] **Step 3: Replace fire-and-send block with signal handling**

Replace lines ~241-250 (the `fire_gesture` block):

```python
# Debounce and fire keystroke (gated during swiping)
if not swiping:
    debounce_signal = debouncer.update(gesture, current_time)
else:
    debounce_signal = None
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
            sender.release_held()
            logger.info("HOLD END: %s -> %s", gesture_name, key_string)
```

- [ ] **Step 4: Add force-release safety calls**

Add `sender.release_all()` before every `debouncer.reset()` and `smoother.reset()` call:

1. Distance gating reset (~line 207-208):
```python
if not in_range:
    if hand_was_in_range:
        sender.release_all()
        smoother.reset()
        debouncer.reset()
        swipe_detector.reset()
```

2. Swipe enter/exit resets (~lines 220-226):
```python
if swiping and not was_swiping:
    sender.release_all()
    smoother.reset()
    debouncer.reset()
if was_swiping and not swiping:
    sender.release_all()
    smoother.reset()
    debouncer.reset()
```

3. Config reload (~lines 273-276):
```python
if watcher.check(current_time):
    try:
        new_config = load_config(args.config)
        sender.release_all()
        key_mappings = _parse_key_mappings(new_config.gestures)
        debouncer._activation_delay = new_config.activation_delay
        # ... rest of reload ...
        debouncer._gesture_modes = new_config.gesture_modes
        debouncer._hold_release_delay = new_config.hold_release_delay
```

4. Shutdown finally block (~line 321):
```python
finally:
    sender.release_all()
    camera.stop()
    detector.close()
```

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add gesture_keys/__main__.py
git commit -m "feat: update preview mode for hold-key signal handling and safety"
```

---

### Task 7: Update tray.py for signal-based handling and safety

Same changes as Task 6 but in `tray.py`. The detection loop is nearly identical.

**Files:**
- Modify: `gesture_keys/tray.py`

- [ ] **Step 1: Update imports**

Add `DebounceAction` to imports:

```python
from gesture_keys.debounce import DebounceAction, GestureDebouncer
```

- [ ] **Step 2: Pass gesture_modes and hold_release_delay to debouncer**

Update debouncer creation (~line 161):

```python
debouncer = GestureDebouncer(
    config.activation_delay, config.cooldown_duration,
    gesture_cooldowns=config.gesture_cooldowns,
    gesture_modes=config.gesture_modes,
    hold_release_delay=config.hold_release_delay,
)
```

- [ ] **Step 3: Replace fire-and-send block with signal handling**

Replace lines ~234-243 (same pattern as Task 6 Step 3):

```python
if not swiping:
    debounce_signal = debouncer.update(gesture, current_time)
else:
    debounce_signal = None
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
            sender.release_held()
            logger.info("HOLD END: %s -> %s", gesture_name, key_string)
```

- [ ] **Step 4: Add force-release safety calls**

Same locations as Task 6 Step 4:

1. Distance gating reset
2. Swipe enter/exit resets
3. Config reload (add `sender.release_all()` first, also add `debouncer._gesture_modes` and `debouncer._hold_release_delay` updates)
4. Inner loop finally block (~line 288):
```python
finally:
    sender.release_all()
    camera.stop()
    detector.close()
```

5. Toggle inactive — add release before the `while self._active.is_set()` check exits (~line 193). The inner loop's `finally` handles this since it runs when `self._active` goes false.

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add gesture_keys/tray.py
git commit -m "feat: update tray mode for hold-key signal handling and safety"
```

---

### Task 8: Manual smoke test

- [ ] **Step 1: Update config.yaml for testing**

Set one gesture to hold mode for manual testing:

```yaml
gestures:
  fist:
    key: space
    mode: hold
    threshold: 0.7
```

- [ ] **Step 2: Run with preview mode**

Run: `python -m gesture_keys --preview`

Test scenarios:
1. Make fist gesture -> verify "HOLD START: fist -> space" logged
2. Hold fist -> verify space key stays pressed (test in a text editor)
3. Release fist -> verify "HOLD END: fist -> space" logged after ~100ms
4. Brief hand flicker -> verify key doesn't release
5. Switch from fist to peace -> verify hold_end + new gesture activates
6. Test a tap-mode gesture still works normally

- [ ] **Step 3: Revert config if desired**

Revert `config.yaml` to its original state or keep the hold mode config.

- [ ] **Step 4: Final commit with any config changes**

```bash
git add config.yaml
git commit -m "test: smoke test hold-key mode"
```
