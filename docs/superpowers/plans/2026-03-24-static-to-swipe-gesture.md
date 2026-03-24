# Static-to-Swipe Compound Gesture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add compound static-to-swipe gestures where holding a pose then swiping fires a single configured keystroke, replacing the static gesture's normal action when a swipe follows within a configurable time window.

**Architecture:** Extends the debouncer state machine with a new `SWIPE_WINDOW` state that intercepts gestures with swipe mappings. The swipe window starts at gesture recognition and either fires a compound keystroke (on swipe) or the normal static keystroke (on window expiry). Config parsing and both main loops (preview and tray) are updated to support the new event flow.

**Tech Stack:** Python 3, pytest, pynput, PyYAML

**Spec:** `docs/superpowers/specs/2026-03-24-static-to-swipe-gesture-design.md`

**Key design decisions:**
- The debouncer receives the set of *mapped* directions per gesture (not just gesture names) so it can filter unmapped swipe directions internally, avoiding a race where an unmapped swipe consumes the swipe detector's cooldown and blocks subsequent mapped swipes within the window.
- The main loop is reordered: swipe detection runs BEFORE debouncer update, so the swipe result can be passed into `debouncer.update()` on the same frame.
- Both `run_preview_mode()` in `__main__.py` and `_detection_loop()` in `tray.py` have nearly identical pipelines. Both must be updated.
- During SWIPE_WINDOW, the main loop only passes the swipe result to the swipe detector if the direction is mapped for the active gesture. Unmapped directions are not passed to the swipe detector at all — the swipe is suppressed at the main loop level so the swipe detector doesn't consume it and enter its internal cooldown. This preserves the ability to detect a subsequent mapped swipe.
- Standalone swipes are suppressed during SWIPE_WINDOW — the spec says unmapped swipes are "ignored", not fired as standalone.
- The `_parse_compound_swipe_key_mappings` helper is duplicated in both `__main__.py` and `tray.py` (it's 10 lines). Importing from `__main__` would create a fragile dependency on the entry-point module.
- Hot-reload: the spec says removing swipe config during SWIPE_WINDOW should fire the static action. The hot-reload path already calls `debouncer.reset()`. Before that call, check if debouncer is in SWIPE_WINDOW and fire the static gesture manually if so.

---

### Task 1: Extend DebounceSignal with direction field

**Files:**
- Modify: `gesture_keys/debounce.py:25-37`
- Test: `tests/test_debounce.py`

- [ ] **Step 1: Write failing test — DebounceSignal accepts optional direction**

```python
# In tests/test_debounce.py, add import:
from gesture_keys.swipe import SwipeDirection

class TestDebounceSignalDirection:
    """Test DebounceSignal direction field."""

    def test_signal_without_direction_defaults_to_none(self):
        sig = DebounceSignal(DebounceAction.FIRE, Gesture.FIST)
        assert sig.direction is None

    def test_signal_with_direction(self):
        sig = DebounceSignal(DebounceAction.FIRE, Gesture.FIST, SwipeDirection.SWIPE_LEFT)
        assert sig.direction == SwipeDirection.SWIPE_LEFT

    def test_existing_signals_unaffected(self):
        sig = DebounceSignal(DebounceAction.HOLD_START, Gesture.PEACE)
        assert sig.action == DebounceAction.HOLD_START
        assert sig.gesture == Gesture.PEACE
        assert sig.direction is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_debounce.py::TestDebounceSignalDirection -v`
Expected: FAIL — `DebounceSignal` doesn't accept 3rd arg / no `direction` attribute

- [ ] **Step 3: Add COMPOUND_FIRE action and direction field to DebounceSignal**

In `gesture_keys/debounce.py`:

1. Add import at top:
```python
from gesture_keys.swipe import SwipeDirection
```

2. Add `COMPOUND_FIRE` to `DebounceAction`:
```python
class DebounceAction(Enum):
    FIRE = "fire"
    HOLD_START = "hold_start"
    HOLD_END = "hold_end"
    COMPOUND_FIRE = "compound_fire"
```

3. Change `DebounceSignal` to include direction with default:
```python
class DebounceSignal(NamedTuple):
    """Signal emitted by debouncer update()."""
    action: DebounceAction
    gesture: Gesture
    direction: Optional[SwipeDirection] = None
```

- [ ] **Step 4: Fix existing test for 3-field NamedTuple**

Update `test_debounce_signal_unpacking` in `tests/test_debounce.py` (around line 278-282) — the 2-element unpack will break because NamedTuple now has 3 fields:

```python
def test_debounce_signal_unpacking(self):
    signal = DebounceSignal(DebounceAction.HOLD_START, Gesture.PEACE)
    action, gesture, direction = signal
    assert action == DebounceAction.HOLD_START
    assert gesture == Gesture.PEACE
    assert direction is None
```

- [ ] **Step 5: Run full debounce test suite to check for regressions**

Run: `python -m pytest tests/test_debounce.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add gesture_keys/debounce.py tests/test_debounce.py
git commit -m "feat: add COMPOUND_FIRE action and direction field to DebounceSignal"
```

---

### Task 2: Add SWIPE_WINDOW state and constructor params

**Files:**
- Modify: `gesture_keys/debounce.py:40-106`
- Test: `tests/test_debounce.py`

- [ ] **Step 1: Write failing test**

```python
class TestSwipeWindowState:
    """Test SWIPE_WINDOW state basics."""

    def test_swipe_window_state_exists(self):
        assert hasattr(DebounceState, "SWIPE_WINDOW")

    def test_in_swipe_window_false_by_default(self):
        d = GestureDebouncer()
        assert d.in_swipe_window is False

    def test_constructor_accepts_swipe_params(self):
        d = GestureDebouncer(
            swipe_gesture_directions={"peace": {"swipe_left", "swipe_right"}},
            swipe_window=0.2,
        )
        assert d.in_swipe_window is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_debounce.py::TestSwipeWindowState -v`
Expected: FAIL

- [ ] **Step 3: Add SWIPE_WINDOW state, constructor params, and property**

In `gesture_keys/debounce.py`:

1. Add `SWIPE_WINDOW` to `DebounceState`:
```python
class DebounceState(Enum):
    IDLE = "IDLE"
    ACTIVATING = "ACTIVATING"
    FIRED = "FIRED"
    COOLDOWN = "COOLDOWN"
    HOLDING = "HOLDING"
    SWIPE_WINDOW = "SWIPE_WINDOW"
```

2. Update `__init__` to accept new params:
```python
def __init__(
    self,
    activation_delay: float = 0.15,
    cooldown_duration: float = 0.3,
    gesture_cooldowns: dict[str, float] | None = None,
    gesture_modes: dict[str, str] | None = None,
    hold_release_delay: float = 0.1,
    swipe_gesture_directions: dict[str, set[str]] | None = None,
    swipe_window: float = 0.2,
) -> None:
    # ... existing fields ...
    self._swipe_gesture_directions = swipe_gesture_directions or {}
    self._swipe_window = swipe_window
    self._swipe_window_start: float = 0.0
```

Note: `swipe_gesture_directions` maps gesture name -> set of mapped direction value strings (e.g. `{"peace": {"swipe_left", "swipe_right"}}`). This allows the debouncer to filter unmapped swipe directions internally.

3. Add `in_swipe_window` property:
```python
@property
def in_swipe_window(self) -> bool:
    """True when debouncer is in SWIPE_WINDOW state."""
    return self._state == DebounceState.SWIPE_WINDOW
```

4. Update `reset()` to clear `_swipe_window_start`:
```python
def reset(self) -> None:
    # ... existing resets ...
    self._swipe_window_start = 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_debounce.py::TestSwipeWindowState -v`
Expected: PASS

- [ ] **Step 5: Run full debounce test suite**

Run: `python -m pytest tests/test_debounce.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add gesture_keys/debounce.py tests/test_debounce.py
git commit -m "feat: add SWIPE_WINDOW state and swipe direction params to debouncer"
```

---

### Task 3: Implement SWIPE_WINDOW state machine logic

**Files:**
- Modify: `gesture_keys/debounce.py:108-210`
- Test: `tests/test_debounce.py`

- [ ] **Step 1: Write failing tests — swipe window transitions**

```python
class TestSwipeWindowTransitions:
    """Test SWIPE_WINDOW state machine behavior."""

    def _make_debouncer(self, directions=None, swipe_window=0.2, activation_delay=0.15):
        """Helper: create debouncer with peace having swipe_left and swipe_right mapped."""
        return GestureDebouncer(
            activation_delay=activation_delay,
            swipe_gesture_directions=directions or {"peace": {"swipe_left", "swipe_right"}},
            swipe_window=swipe_window,
        )

    def test_gesture_with_swipe_mapping_enters_swipe_window(self):
        d = self._make_debouncer()
        d.update(Gesture.PEACE, 0.0)
        assert d.state == DebounceState.SWIPE_WINDOW
        assert d.in_swipe_window is True

    def test_gesture_without_swipe_mapping_normal_activating(self):
        d = self._make_debouncer()
        d.update(Gesture.FIST, 0.0)
        assert d.state == DebounceState.ACTIVATING

    def test_compound_fire_on_mapped_swipe(self):
        d = self._make_debouncer()
        d.update(Gesture.PEACE, 0.0)
        result = d.update(Gesture.PEACE, 0.05, swipe_direction=SwipeDirection.SWIPE_LEFT)
        assert result is not None
        assert result.action == DebounceAction.COMPOUND_FIRE
        assert result.gesture == Gesture.PEACE
        assert result.direction == SwipeDirection.SWIPE_LEFT
        assert d.state == DebounceState.COOLDOWN

    def test_unmapped_direction_ignored(self):
        """Swipe in unmapped direction (UP) is ignored, window continues."""
        d = self._make_debouncer()  # only left/right mapped
        d.update(Gesture.PEACE, 0.0)
        result = d.update(Gesture.PEACE, 0.05, swipe_direction=SwipeDirection.SWIPE_UP)
        assert result is None
        assert d.state == DebounceState.SWIPE_WINDOW

    def test_fires_static_on_window_expiry(self):
        d = self._make_debouncer(swipe_window=0.2)
        d.update(Gesture.PEACE, 0.0)
        result = d.update(Gesture.PEACE, 0.1)
        assert result is None
        result = d.update(Gesture.PEACE, 0.25)
        assert result == DebounceSignal(DebounceAction.FIRE, Gesture.PEACE)
        assert d.state == DebounceState.FIRED

    def test_idle_on_gesture_lost(self):
        d = self._make_debouncer()
        d.update(Gesture.PEACE, 0.0)
        result = d.update(None, 0.05)
        assert result is None
        assert d.state == DebounceState.IDLE

    def test_gesture_switch_to_swipe_gesture(self):
        d = self._make_debouncer(directions={"peace": {"swipe_left"}, "fist": {"swipe_right"}})
        d.update(Gesture.PEACE, 0.0)
        assert d.state == DebounceState.SWIPE_WINDOW
        d.update(Gesture.FIST, 0.05)
        assert d.state == DebounceState.SWIPE_WINDOW

    def test_gesture_switch_to_non_swipe(self):
        d = self._make_debouncer()
        d.update(Gesture.PEACE, 0.0)
        assert d.state == DebounceState.SWIPE_WINDOW
        d.update(Gesture.THUMBS_UP, 0.05)
        assert d.state == DebounceState.ACTIVATING

    def test_is_activating_false_during_swipe_window(self):
        d = self._make_debouncer()
        d.update(Gesture.PEACE, 0.0)
        assert d.is_activating is False
        assert d.in_swipe_window is True

    def test_cooldown_to_swipe_window_direct_transition(self):
        """Different gesture with swipe mapping during cooldown -> SWIPE_WINDOW."""
        d = self._make_debouncer(
            directions={"peace": {"swipe_left"}, "fist": {"swipe_right"}},
            activation_delay=0.1,
        )
        # Fire fist normally (no swipe mapping... wait, fist HAS swipe mapping here)
        # Use a gesture without swipe mapping to enter cooldown
        d = GestureDebouncer(
            activation_delay=0.1,
            swipe_gesture_directions={"peace": {"swipe_left"}},
            swipe_window=0.2,
        )
        d.update(Gesture.FIST, 0.0)  # ACTIVATING (no swipe mapping)
        d.update(Gesture.FIST, 0.15)  # FIRED
        d.update(Gesture.FIST, 0.16)  # COOLDOWN
        assert d.state == DebounceState.COOLDOWN
        # Now peace (with swipe mapping) during cooldown
        d.update(Gesture.PEACE, 0.17)
        assert d.state == DebounceState.SWIPE_WINDOW
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_debounce.py::TestSwipeWindowTransitions -v`
Expected: FAIL — `update()` doesn't accept `swipe_direction`, no SWIPE_WINDOW transitions

- [ ] **Step 3: Implement swipe window logic**

In `gesture_keys/debounce.py`:

1. Update `update()` signature:
```python
def update(
    self, gesture: Optional[Gesture], timestamp: float,
    *, swipe_direction: Optional[SwipeDirection] = None,
) -> Optional[DebounceSignal]:
    if self._state == DebounceState.IDLE:
        return self._handle_idle(gesture, timestamp)
    elif self._state == DebounceState.ACTIVATING:
        return self._handle_activating(gesture, timestamp)
    elif self._state == DebounceState.SWIPE_WINDOW:
        return self._handle_swipe_window(gesture, timestamp, swipe_direction)
    elif self._state == DebounceState.FIRED:
        return self._handle_fired(gesture, timestamp)
    elif self._state == DebounceState.COOLDOWN:
        return self._handle_cooldown(gesture, timestamp)
    elif self._state == DebounceState.HOLDING:
        return self._handle_holding(gesture, timestamp)
    return None
```

2. Update `_handle_idle()`:
```python
def _handle_idle(
    self, gesture: Optional[Gesture], timestamp: float
) -> Optional[DebounceSignal]:
    if gesture is not None:
        if gesture.value in self._swipe_gesture_directions:
            self._state = DebounceState.SWIPE_WINDOW
            self._activating_gesture = gesture
            self._swipe_window_start = timestamp
            logger.debug("IDLE -> SWIPE_WINDOW: %s", gesture.value)
        else:
            self._state = DebounceState.ACTIVATING
            self._activating_gesture = gesture
            self._activation_start = timestamp
            logger.debug("IDLE -> ACTIVATING: %s", gesture.value)
    return None
```

3. Add `_handle_swipe_window()`:
```python
def _handle_swipe_window(
    self, gesture: Optional[Gesture], timestamp: float,
    swipe_direction: Optional[SwipeDirection],
) -> Optional[DebounceSignal]:
    # Gesture lost -> IDLE
    if gesture is None:
        self._state = DebounceState.IDLE
        self._activating_gesture = None
        logger.debug("SWIPE_WINDOW -> IDLE: gesture released")
        return None

    # Gesture changed -> restart for new gesture
    if gesture != self._activating_gesture:
        self._activating_gesture = gesture
        if gesture.value in self._swipe_gesture_directions:
            self._swipe_window_start = timestamp
            logger.debug("SWIPE_WINDOW reset: switched to %s", gesture.value)
        else:
            self._state = DebounceState.ACTIVATING
            self._activation_start = timestamp
            logger.debug("SWIPE_WINDOW -> ACTIVATING: %s (no swipe mapping)", gesture.value)
        return None

    # Swipe detected and direction is mapped for this gesture -> COMPOUND_FIRE
    if swipe_direction is not None:
        mapped = self._swipe_gesture_directions.get(self._activating_gesture.value, set())
        if swipe_direction.value in mapped:
            fired_gesture = self._activating_gesture
            self._state = DebounceState.COOLDOWN
            self._cooldown_start = timestamp
            self._cooldown_duration_active = self._gesture_cooldowns.get(
                fired_gesture.value, self._cooldown_duration
            )
            self._cooldown_gesture = fired_gesture
            self._activating_gesture = None
            logger.debug(
                "SWIPE_WINDOW -> COOLDOWN: compound %s + %s",
                fired_gesture.value, swipe_direction.value,
            )
            return DebounceSignal(DebounceAction.COMPOUND_FIRE, fired_gesture, swipe_direction)
        # Unmapped direction: ignore, keep waiting
        return None

    # Window expired -> fire static gesture normally
    if timestamp - self._swipe_window_start >= self._swipe_window:
        self._state = DebounceState.FIRED
        logger.debug("SWIPE_WINDOW -> FIRED: %s (window expired)", self._activating_gesture.value)
        return DebounceSignal(DebounceAction.FIRE, self._activating_gesture)

    return None
```

4. Update `_handle_cooldown()` to route to SWIPE_WINDOW for swipe-mapped gestures:
```python
def _handle_cooldown(
    self, gesture: Optional[Gesture], timestamp: float
) -> Optional[DebounceSignal]:
    if gesture is not None and gesture != self._cooldown_gesture:
        if gesture.value in self._swipe_gesture_directions:
            self._state = DebounceState.SWIPE_WINDOW
            self._activating_gesture = gesture
            self._swipe_window_start = timestamp
            self._cooldown_gesture = None
            logger.debug("COOLDOWN -> SWIPE_WINDOW: %s (direct transition)", gesture.value)
        else:
            self._state = DebounceState.ACTIVATING
            self._activating_gesture = gesture
            self._activation_start = timestamp
            self._cooldown_gesture = None
            logger.debug("COOLDOWN -> ACTIVATING: %s (direct transition)", gesture.value)
        return None

    if (
        timestamp - self._cooldown_start >= self._cooldown_duration_active
        and gesture is None
    ):
        self._state = DebounceState.IDLE
        self._cooldown_gesture = None
        logger.debug("COOLDOWN -> IDLE: released")

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_debounce.py::TestSwipeWindowTransitions -v`
Expected: PASS

- [ ] **Step 5: Run full debounce test suite**

Run: `python -m pytest tests/test_debounce.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add gesture_keys/debounce.py tests/test_debounce.py
git commit -m "feat: implement SWIPE_WINDOW state machine logic in debouncer"
```

---

### Task 4: Config parsing for swipe_window and per-gesture swipe blocks

**Files:**
- Modify: `gesture_keys/config.py:14-41, 175-271`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

```python
class TestSwipeWindowConfig:
    """Test swipe_window and per-gesture swipe block parsing."""

    def test_swipe_window_default(self):
        config = load_config(DEFAULT_CONFIG)
        assert config.swipe_window == 0.2

    def test_swipe_window_from_detection(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
camera:
  index: 0
detection:
  swipe_window: 0.3
gestures:
  peace:
    key: ctrl+z
    threshold: 0.7
""")
        config = load_config(str(cfg))
        assert config.swipe_window == 0.3

    def test_gesture_swipe_mappings_parsed(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
camera:
  index: 0
gestures:
  peace:
    key: ctrl+z
    threshold: 0.7
    swipe:
      swipe_left:
        key: ctrl+shift+left
      swipe_right:
        key: ctrl+shift+right
""")
        config = load_config(str(cfg))
        assert "peace" in config.gesture_swipe_mappings
        assert config.gesture_swipe_mappings["peace"]["swipe_left"] == "ctrl+shift+left"
        assert config.gesture_swipe_mappings["peace"]["swipe_right"] == "ctrl+shift+right"

    def test_gesture_swipe_mappings_empty_when_no_block(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
camera:
  index: 0
gestures:
  peace:
    key: ctrl+z
    threshold: 0.7
""")
        config = load_config(str(cfg))
        assert config.gesture_swipe_mappings == {}

    def test_hold_mode_with_swipe_block_raises(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
camera:
  index: 0
gestures:
  fist:
    key: space
    mode: hold
    threshold: 0.7
    swipe:
      swipe_left:
        key: ctrl+left
""")
        with pytest.raises(ValueError, match="hold.*swipe"):
            load_config(str(cfg))

    def test_partial_directions(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
camera:
  index: 0
gestures:
  peace:
    key: ctrl+z
    threshold: 0.7
    swipe:
      swipe_left:
        key: ctrl+shift+left
""")
        config = load_config(str(cfg))
        assert "swipe_left" in config.gesture_swipe_mappings["peace"]
        assert "swipe_right" not in config.gesture_swipe_mappings["peace"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py::TestSwipeWindowConfig -v`
Expected: FAIL

- [ ] **Step 3: Implement config parsing**

In `gesture_keys/config.py`:

1. Add fields to `AppConfig`:
```python
    swipe_window: float = 0.2
    gesture_swipe_mappings: dict[str, dict[str, str]] = field(default_factory=dict)
```

2. Add extraction function (public, no underscore — used by `__main__.py` and `tray.py`):
```python
def extract_gesture_swipe_mappings(gestures: dict, gesture_modes: dict[str, str]) -> dict[str, dict[str, str]]:
    """Extract per-gesture swipe mappings from gesture config.

    Args:
        gestures: Gesture config dict.
        gesture_modes: Gesture mode dict (to reject hold mode).

    Returns:
        Dict mapping gesture_name -> {direction_name: key_string}.

    Raises:
        ValueError: If a hold-mode gesture has a swipe block.
    """
    swipe_directions = ("swipe_left", "swipe_right", "swipe_up", "swipe_down")
    mappings: dict[str, dict[str, str]] = {}
    for name, settings in gestures.items():
        if not isinstance(settings, dict) or "swipe" not in settings:
            continue
        swipe_block = settings["swipe"]
        if not isinstance(swipe_block, dict):
            continue
        mode = gesture_modes.get(name, "tap")
        if mode == "hold":
            raise ValueError(
                f"Gesture '{name}' uses hold mode and cannot have a swipe block. "
                "Static-to-swipe is only supported for tap mode gestures."
            )
        direction_map: dict[str, str] = {}
        for direction in swipe_directions:
            entry = swipe_block.get(direction)
            if isinstance(entry, dict) and "key" in entry:
                direction_map[direction] = entry["key"]
        if direction_map:
            mappings[name] = direction_map
    return mappings
```

3. Update `load_config()` — call after `gesture_modes`, add to AppConfig return:
```python
    gesture_swipe_mappings = extract_gesture_swipe_mappings(gestures, gesture_modes)
    # ... in return AppConfig(...):
    swipe_window=float(detection.get("swipe_window", 0.2)),
    gesture_swipe_mappings=gesture_swipe_mappings,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py::TestSwipeWindowConfig -v`
Expected: PASS

- [ ] **Step 5: Run full config test suite**

Run: `python -m pytest tests/test_config.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add gesture_keys/config.py tests/test_config.py
git commit -m "feat: parse swipe_window and per-gesture swipe blocks from config"
```

---

### Task 5: Left-hand swipe block merging

**Files:**
- Modify: `gesture_keys/config.py` (possibly no changes needed)
- Test: `tests/test_config.py`

- [ ] **Step 1: Write test — left-hand swipe override**

```python
class TestLeftHandSwipeMerge:
    def test_left_gestures_swipe_override(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
camera:
  index: 0
gestures:
  peace:
    key: ctrl+z
    threshold: 0.7
    swipe:
      swipe_left:
        key: ctrl+shift+left
      swipe_right:
        key: ctrl+shift+right
left_gestures:
  peace:
    swipe:
      swipe_left:
        key: ctrl+shift+right
      swipe_right:
        key: ctrl+shift+left
""")
        config = load_config(str(cfg))
        resolved = resolve_hand_gestures("Left", config)
        # Left-hand update replaces the swipe block entirely
        assert resolved["peace"]["swipe"]["swipe_left"]["key"] == "ctrl+shift+right"

    def test_right_hand_unaffected(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
camera:
  index: 0
gestures:
  peace:
    key: ctrl+z
    threshold: 0.7
    swipe:
      swipe_left:
        key: ctrl+shift+left
left_gestures:
  peace:
    swipe:
      swipe_left:
        key: ctrl+shift+right
""")
        config = load_config(str(cfg))
        resolved = resolve_hand_gestures("Right", config)
        assert resolved["peace"]["swipe"]["swipe_left"]["key"] == "ctrl+shift+left"
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_config.py::TestLeftHandSwipeMerge -v`
Expected: PASS — existing `resolve_hand_gestures` does `deepcopy` + `update`, which replaces the swipe block.

- [ ] **Step 3: Commit**

```bash
git add tests/test_config.py
git commit -m "test: verify left-hand swipe block merging"
```

---

### Task 6: Integrate compound gesture in preview mode main loop

**Files:**
- Modify: `gesture_keys/__main__.py`
- Test: `tests/test_compound_gesture.py`

- [ ] **Step 1: Write integration test**

Create `tests/test_compound_gesture.py`:

```python
"""Tests for static-to-swipe compound gesture integration."""

from gesture_keys.classifier import Gesture
from gesture_keys.debounce import DebounceAction, DebounceState, GestureDebouncer
from gesture_keys.swipe import SwipeDirection


class TestCompoundGestureIntegration:
    def test_full_compound_flow(self):
        d = GestureDebouncer(
            swipe_gesture_directions={"peace": {"swipe_left", "swipe_right"}},
            swipe_window=0.2,
        )
        d.update(Gesture.PEACE, 0.0)
        assert d.state == DebounceState.SWIPE_WINDOW
        result = d.update(Gesture.PEACE, 0.1, swipe_direction=SwipeDirection.SWIPE_LEFT)
        assert result.action == DebounceAction.COMPOUND_FIRE
        assert result.gesture == Gesture.PEACE
        assert result.direction == SwipeDirection.SWIPE_LEFT

    def test_static_fallback(self):
        d = GestureDebouncer(
            swipe_gesture_directions={"peace": {"swipe_left"}},
            swipe_window=0.2,
        )
        d.update(Gesture.PEACE, 0.0)
        result = d.update(Gesture.PEACE, 0.25)
        assert result.action == DebounceAction.FIRE

    def test_non_swipe_gesture_unaffected(self):
        d = GestureDebouncer(
            activation_delay=0.15,
            swipe_gesture_directions={"peace": {"swipe_left"}},
        )
        d.update(Gesture.FIST, 0.0)
        assert d.state == DebounceState.ACTIVATING
        result = d.update(Gesture.FIST, 0.2)
        assert result.action == DebounceAction.FIRE

    def test_swipe_not_double_fired(self):
        """COMPOUND_FIRE consumes the swipe — it should not also be standalone."""
        d = GestureDebouncer(
            swipe_gesture_directions={"peace": {"swipe_left"}},
            swipe_window=0.2,
        )
        d.update(Gesture.PEACE, 0.0)
        result = d.update(Gesture.PEACE, 0.1, swipe_direction=SwipeDirection.SWIPE_LEFT)
        assert result.action == DebounceAction.COMPOUND_FIRE
        # After compound fire, debouncer is in COOLDOWN — no further signals
        result2 = d.update(None, 0.15)
        assert result2 is None
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_compound_gesture.py -v`
Expected: PASS (debouncer logic from Task 3)

- [ ] **Step 3: Add compound swipe key parsing helper**

In `gesture_keys/__main__.py`, add after `_parse_swipe_key_mappings()`:

```python
def _parse_compound_swipe_key_mappings(gesture_swipe_mappings: dict[str, dict[str, str]]) -> dict:
    """Pre-parse compound gesture swipe key strings into pynput objects.

    Args:
        gesture_swipe_mappings: Dict of {gesture_name: {direction: key_string}}.

    Returns:
        Dict mapping (gesture_name, direction) -> (modifiers, key, key_string).
    """
    mappings = {}
    for gesture_name, directions in gesture_swipe_mappings.items():
        for direction_name, key_string in directions.items():
            modifiers, key = parse_key_string(key_string)
            mappings[(gesture_name, direction_name)] = (modifiers, key, key_string)
    return mappings
```

- [ ] **Step 4: Update `run_preview_mode()` — debouncer construction and compound key parsing**

Add import at top of `__main__.py`:
```python
from gesture_keys.config import extract_gesture_swipe_mappings
```

Update debouncer creation (around line 145):
```python
    # Build swipe direction sets for debouncer (gesture_name -> set of direction values)
    swipe_gesture_directions = {
        name: set(dirs.keys())
        for name, dirs in config.gesture_swipe_mappings.items()
    }

    debouncer = GestureDebouncer(
        config.activation_delay, config.cooldown_duration,
        gesture_cooldowns=config.gesture_cooldowns,
        gesture_modes=config.gesture_modes,
        hold_release_delay=config.hold_release_delay,
        swipe_gesture_directions=swipe_gesture_directions,
        swipe_window=config.swipe_window,
    )
```

After existing key mapping parsing, add compound mapping parsing:
```python
    # Pre-parse compound swipe key mappings for both hands
    right_compound_mappings = _parse_compound_swipe_key_mappings(config.gesture_swipe_mappings)
    left_gestures_swipe = extract_gesture_swipe_mappings(
        left_gestures_resolved,
        {**config.gesture_modes, **config.left_gesture_modes} if config.left_gesture_modes else config.gesture_modes,
    )
    left_compound_mappings = _parse_compound_swipe_key_mappings(left_gestures_swipe)
    compound_mappings = right_compound_mappings
```

- [ ] **Step 5: Reorder main loop — swipe detection BEFORE debouncer**

The critical reordering in the main `while True` loop. The final order of the pipeline section must be:

1. Static gesture classification + smoothing (existing, unchanged)
2. **Swipe detection** (moved BEFORE debouncer)
3. **Debouncer update** (now receives swipe_direction)
4. Signal handling (COMPOUND_FIRE branch added)

Replace the debouncer + swipe detection sections (roughly lines 296-345) with:

```python
            # --- Swipe detection (BEFORE debouncer so result can be passed in) ---
            swipe_result = None
            if config.swipe_enabled:
                # Suppress swipes during ACTIVATING (static gesture has priority).
                # During SWIPE_WINDOW, swipes are allowed (we need to detect them).
                suppress_swipe = debouncer.is_activating
                swipe_result = swipe_detector.update(
                    landmarks or None, current_time,
                    suppressed=suppress_swipe,
                )

                # If in SWIPE_WINDOW and swipe fired for unmapped direction,
                # reset swipe detector to IDLE so it can detect a subsequent
                # mapped swipe. This prevents unmapped swipes from consuming
                # the detector's internal cooldown.
                if debouncer.in_swipe_window and swipe_result is not None:
                    gesture_name = debouncer._activating_gesture.value if debouncer._activating_gesture else None
                    mapped = swipe_gesture_directions.get(gesture_name, set())
                    if swipe_result.value not in mapped:
                        swipe_detector.reset()
                        swipe_result = None  # Unmapped: don't pass to debouncer
            else:
                swipe_detector.update(None, current_time)

            # --- Debounce and fire keystroke (gated during swiping) ---
            if not swiping:
                # Pass swipe result to debouncer only when in swipe window
                swipe_dir_for_debounce = swipe_result if debouncer.in_swipe_window else None
                debounce_signal = debouncer.update(
                    gesture, current_time, swipe_direction=swipe_dir_for_debounce,
                )
            else:
                debounce_signal = None

            if debounce_signal is not None:
                sig_gesture_name = debounce_signal.gesture.value
                if debounce_signal.action == DebounceAction.COMPOUND_FIRE:
                    # Compound gesture: look up by (gesture, direction)
                    direction_name = debounce_signal.direction.value
                    lookup = (sig_gesture_name, direction_name)
                    if lookup in compound_mappings:
                        sig_mods, sig_key, sig_key_string = compound_mappings[lookup]
                        sender.send(sig_mods, sig_key)
                        logger.info("COMPOUND: %s + %s -> %s", sig_gesture_name, direction_name, sig_key_string)
                elif sig_gesture_name in key_mappings:
                    sig_mods, sig_key, sig_key_string = key_mappings[sig_gesture_name]
                    if debounce_signal.action == DebounceAction.FIRE:
                        sender.send(sig_mods, sig_key)
                        logger.info("FIRED: %s -> %s", sig_gesture_name, sig_key_string)
                    elif debounce_signal.action == DebounceAction.HOLD_START:
                        sender.send(sig_mods, sig_key)
                        hold_active = True
                        hold_modifiers = sig_mods
                        hold_key = sig_key
                        hold_key_string = sig_key_string
                        hold_gesture_name = sig_gesture_name
                        hold_last_repeat = current_time
                        logger.info("HOLD START: %s -> %s", sig_gesture_name, sig_key_string)
                    elif debounce_signal.action == DebounceAction.HOLD_END:
                        hold_active = False
                        logger.info("HOLD END: %s -> %s", sig_gesture_name, sig_key_string)

            # Standalone swipe handling:
            # - Not during SWIPE_WINDOW (spec: unmapped swipes are "ignored")
            # - Not when COMPOUND_FIRE consumed the swipe
            if (
                swipe_result is not None
                and not debouncer.in_swipe_window
                and not (debounce_signal and debounce_signal.action == DebounceAction.COMPOUND_FIRE)
            ):
                swipe_name = swipe_result.value
                if swipe_name in swipe_key_mappings:
                    modifiers, key, key_string = swipe_key_mappings[swipe_name]
                    sender.send(modifiers, key)
                    logger.info("SWIPE: %s -> %s", swipe_name, key_string)
```

- [ ] **Step 6: Update hand switch and initial hand detection to swap compound_mappings**

In hand switch block (around line 220-235):
```python
    if handedness == "Left":
        key_mappings = left_key_mappings
        swipe_key_mappings = left_swipe_key_mappings
        compound_mappings = left_compound_mappings
    else:
        key_mappings = right_key_mappings
        swipe_key_mappings = right_swipe_key_mappings
        compound_mappings = right_compound_mappings
```

In initial hand detection block (around line 238-244):
```python
    if prev_handedness is None and handedness is not None:
        if handedness == "Left":
            key_mappings = left_key_mappings
            swipe_key_mappings = left_swipe_key_mappings
            compound_mappings = left_compound_mappings
        else:
            key_mappings = right_key_mappings
            swipe_key_mappings = right_swipe_key_mappings
            compound_mappings = right_compound_mappings
```

- [ ] **Step 7: Update hot-reload section**

In config hot-reload (around line 347-402), add compound gesture updates after existing debouncer updates:

```python
    # Handle SWIPE_WINDOW -> fire static action before resetting (spec requirement)
    # If debouncer is in SWIPE_WINDOW and the gesture's swipe config was removed,
    # fire the static action before resetting.
    if debouncer.in_swipe_window and debouncer._activating_gesture is not None:
        sw_gesture = debouncer._activating_gesture
        sw_name = sw_gesture.value
        if sw_name not in new_config.gesture_swipe_mappings:
            # Swipe config removed for this gesture — fire static action
            if sw_name in key_mappings:
                sig_mods, sig_key, sig_key_string = key_mappings[sw_name]
                sender.send(sig_mods, sig_key)
                logger.info("FIRED (reload): %s -> %s", sw_name, sig_key_string)

    # Update compound swipe config
    new_gesture_swipe_mappings = new_config.gesture_swipe_mappings
    new_swipe_gesture_directions = {
        name: set(dirs.keys())
        for name, dirs in new_gesture_swipe_mappings.items()
    }
    debouncer._swipe_gesture_directions = new_swipe_gesture_directions
    debouncer._swipe_window = new_config.swipe_window
    # Also update the local swipe_gesture_directions for main loop unmapped direction check
    swipe_gesture_directions = new_swipe_gesture_directions
    # Re-parse compound key mappings for both hands
    right_compound_mappings = _parse_compound_swipe_key_mappings(new_gesture_swipe_mappings)
    new_left_gestures_resolved = resolve_hand_gestures("Left", new_config)
    new_left_modes = {**new_config.gesture_modes, **new_config.left_gesture_modes} if new_config.left_gesture_modes else new_config.gesture_modes
    new_left_gestures_swipe = extract_gesture_swipe_mappings(new_left_gestures_resolved, new_left_modes)
    left_compound_mappings = _parse_compound_swipe_key_mappings(new_left_gestures_swipe)
    if prev_handedness == "Left":
        compound_mappings = left_compound_mappings
    else:
        compound_mappings = right_compound_mappings
```

**Note:** This code runs BEFORE `debouncer.reset()` which is called by the existing hot-reload code. The check fires the static action only if the gesture's swipe config was removed in the new config.

- [ ] **Step 8: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add gesture_keys/__main__.py tests/test_compound_gesture.py
git commit -m "feat: integrate static-to-swipe compound gesture in preview mode"
```

---

### Task 7: Integrate compound gesture in tray mode

**Files:**
- Modify: `gesture_keys/tray.py:128-394`

The tray mode `_detection_loop()` has a nearly identical pipeline to `run_preview_mode()`. Apply the same changes:

- [ ] **Step 1: Update tray.py imports and add helper**

Add import at top:
```python
from gesture_keys.config import extract_gesture_swipe_mappings
```

Duplicate the `_parse_compound_swipe_key_mappings` helper in `tray.py` (do NOT import from `__main__` — importing from the entry-point module is fragile and can cause circular imports):

```python
def _parse_compound_swipe_key_mappings(gesture_swipe_mappings: dict[str, dict[str, str]]) -> dict:
    """Pre-parse compound gesture swipe key strings into pynput objects."""
    mappings = {}
    for gesture_name, directions in gesture_swipe_mappings.items():
        for direction_name, key_string in directions.items():
            modifiers, key = parse_key_string(key_string)
            mappings[(gesture_name, direction_name)] = (modifiers, key, key_string)
    return mappings
```

- [ ] **Step 2: Update debouncer construction** (around line 161)

Same as Task 6 Step 4: build `swipe_gesture_directions` and pass to `GestureDebouncer`.

- [ ] **Step 3: Add compound mapping parsing** (after line 196)

Same as Task 6 Step 4: parse right/left compound mappings, set initial `compound_mappings`.

- [ ] **Step 4: Reorder pipeline — swipe before debouncer** (around lines 296-338)

Same reordering as Task 6 Step 5.

- [ ] **Step 5: Update hand switch and initial hand detection** (around lines 220-244)

Add `compound_mappings` swaps same as Task 6 Step 6.

- [ ] **Step 6: Update hot-reload** (around lines 340-390)

Same as Task 6 Step 7.

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add gesture_keys/tray.py
git commit -m "feat: integrate static-to-swipe compound gesture in tray mode"
```

---

### Task 8: Update config.yaml with swipe_window setting

**Files:**
- Modify: `config.yaml`

- [ ] **Step 1: Add swipe_window to detection section**

```yaml
detection:
  smoothing_window: 2
  activation_delay: 0.2
  cooldown_duration: 0.1
  swipe_window: 0.2          # seconds to wait for static-to-swipe compound gesture
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add config.yaml
git commit -m "feat: add swipe_window setting to config"
```

---

### Task 9: Manual end-to-end verification

- [ ] **Step 1: Add test compound gesture to config.yaml temporarily**

```yaml
gestures:
  peace:
    key: win+ctrl+left
    threshold: 0.7
    swipe:
      swipe_left:
        key: left
      swipe_right:
        key: right
```

- [ ] **Step 2: Run with preview mode**

Run: `python -m gesture_keys --preview`

- [ ] **Step 3: Test scenarios**

1. Peace sign held still → fires `win+ctrl+left` after swipe_window (0.2s)
2. Peace sign + quick swipe left → fires `left`
3. Peace sign + quick swipe right → fires `right`
4. Peace sign + swipe up (unmapped) → ignored, fires `win+ctrl+left` after window
5. Fist (no swipe mapping) → fires at normal activation_delay
6. Standalone swipe (no pose) → fires normal standalone swipe

- [ ] **Step 4: Revert test config if needed, final commit**

```bash
git add -A
git commit -m "feat: complete static-to-swipe compound gesture implementation"
```
