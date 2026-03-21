# Phase 2: Gesture-to-Keystroke Pipeline - Research

**Researched:** 2026-03-21
**Domain:** Keyboard simulation, debounce state machines, config hot-reload (Python/Windows)
**Confidence:** HIGH

## Summary

Phase 2 connects the gesture detection pipeline (Phase 1) to keyboard command firing via pynput. The core challenge is a debounce state machine (IDLE -> ACTIVATING -> FIRED -> COOLDOWN -> IDLE) that prevents false fires from flickering gestures and held poses. The secondary challenge is parsing config key strings like `ctrl+z` into pynput Key/KeyCode objects and firing them reliably in any foreground application. A config hot-reload mechanism watches config.yaml for changes and applies new mappings without restart.

pynput is the locked choice for keyboard simulation. It provides `Controller.press()` / `Controller.release()` for individual keys, a `pressed()` context manager for modifier combos, and a `Key` enum for special keys. The library is mature (v1.8.1) and works across Windows applications. For config watching, a simple polling approach (stat mtime check every 1-2 seconds) avoids adding watchdog as a dependency -- appropriate for a single-file watch use case.

**Primary recommendation:** Build three new modules -- `debounce.py` (state machine), `keystroke.py` (key parsing + firing), and extend `config.py` with reload support. Wire into the existing main loop between smoother output and logging.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- State machine: IDLE -> ACTIVATING -> FIRED -> COOLDOWN -> IDLE
- Activation delay: 0.4s (configurable in config.yaml `detection.activation_delay`)
- Cooldown duration: 0.8s (configurable in config.yaml `detection.cooldown_duration`)
- Mid-activation gesture switch: reset timer -- new gesture starts fresh 0.4s hold
- Cooldown is global -- after ANY gesture fires, ALL gestures blocked for cooldown duration
- Release detection: gesture must smooth to None for N frames before new activation can begin (uses existing smoother)
- Brief/flickering gestures under activation delay do not fire
- Config format: `gestures.<name>.key` with values like `ctrl+z`, `space`, `enter`
- pynput handles single keys and key combos
- Default mappings: open_palm=space, fist=ctrl+z, thumbs_up=ctrl+s, peace=ctrl+c, pointing=enter, pinch=ctrl+v
- Invalid config on reload: keep current config, log error at WARNING level
- Successful reload logged at INFO with summary (gesture count, key settings)
- Key fire events at INFO: `[HH:MM:SS] FIRED: fist -> ctrl+z`
- Suppressed events (cooldown blocks, too-short holds) at DEBUG level
- State machine transitions at DEBUG level
- Hot-reload events at INFO with summary
- Continues Phase 1 logging format via Python logging module

### Claude's Discretion
- Hot-reload trigger mechanism (file watcher vs polling vs signal)
- Exact state machine implementation (class vs function, timer approach)
- Key combo parsing strategy (splitting `ctrl+z` into modifier + key for pynput)
- Error handling for failed key sends (e.g., invalid key names in config)
- How many frames of None constitute a "release" for cooldown reset

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| KEY-01 | Map each gesture to configurable keyboard commands (single keys and combos) via YAML config | Key parsing strategy, pynput Key enum mapping, config structure |
| KEY-02 | Debounce state machine with configurable activation delay (0.4s) and cooldown (0.8s) | State machine pattern, time.perf_counter for timing, state enum |
| KEY-03 | Fire keyboard commands that work in any foreground application | pynput Controller API, press/release pattern, pressed() context manager |
| KEY-04 | Log detections and key fires with timestamps for debugging | Python logging module, existing logger pattern, DEBUG vs INFO levels |
| KEY-05 | Hot-reload config.yaml without restarting the app | Polling mtime approach, reload_config function, error handling |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pynput | >=1.7.6 | Keyboard simulation (press/release/combos) | PROJECT.md locked decision; works across all foreground apps on Windows |
| PyYAML | >=6.0 | Config parsing (already installed) | Already in use from Phase 1 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| time (stdlib) | - | `time.perf_counter()` for debounce timing | State machine activation/cooldown timers |
| os (stdlib) | - | `os.path.getmtime()` for config polling | Hot-reload mtime checking |
| enum (stdlib) | - | State enum for debounce machine | IDLE/ACTIVATING/FIRED/COOLDOWN states |
| logging (stdlib) | - | Structured logging (already in use) | Fire events, state transitions, reload events |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Polling mtime for config reload | watchdog library | watchdog adds a dependency for watching ONE file; polling every 1-2s is trivial and sufficient |
| pynput Controller | ctypes SendInput | pynput abstracts platform differences; ctypes is Windows-only and verbose |
| time.perf_counter | time.monotonic | perf_counter has higher resolution; both work, perf_counter is standard for sub-second timing |

**Installation:**
```bash
pip install pynput>=1.7.6
```
Add to requirements.txt: `pynput>=1.7.6`

## Architecture Patterns

### Recommended Project Structure
```
gesture_keys/
  __init__.py          # existing
  __main__.py          # existing -- wire debounce + keystroke into loop
  classifier.py        # existing
  config.py            # extend -- add activation_delay, cooldown_duration, reload support
  debounce.py          # NEW -- state machine
  detector.py          # existing
  keystroke.py         # NEW -- key parsing + firing
  preview.py           # existing
  smoother.py          # existing
tests/
  test_debounce.py     # NEW
  test_keystroke.py    # NEW
  test_config.py       # extend -- test new fields + reload
```

### Pattern 1: Debounce State Machine (Class-Based)
**What:** A class with an `update(gesture, timestamp)` method that tracks state transitions and returns a fire signal.
**When to use:** Every frame in the main loop, after smoother output.
**Example:**
```python
# debounce.py
from enum import Enum
import logging

logger = logging.getLogger("gesture_keys")

class DebounceState(Enum):
    IDLE = "IDLE"
    ACTIVATING = "ACTIVATING"
    FIRED = "FIRED"
    COOLDOWN = "COOLDOWN"

class GestureDebouncer:
    def __init__(self, activation_delay: float = 0.4, cooldown_duration: float = 0.8):
        self._activation_delay = activation_delay
        self._cooldown_duration = cooldown_duration
        self._state = DebounceState.IDLE
        self._activating_gesture = None
        self._activation_start: float = 0.0
        self._cooldown_start: float = 0.0

    @property
    def state(self) -> DebounceState:
        return self._state

    def update(self, gesture, timestamp: float):
        """Process a smoothed gesture. Returns gesture to fire or None.

        Args:
            gesture: Gesture enum value or None (from smoother).
            timestamp: Current time from time.perf_counter().

        Returns:
            Gesture to fire, or None if no fire this frame.
        """
        # Handle based on current state
        if self._state == DebounceState.IDLE:
            if gesture is not None:
                self._state = DebounceState.ACTIVATING
                self._activating_gesture = gesture
                self._activation_start = timestamp
                logger.debug("IDLE -> ACTIVATING: %s", gesture.value)
            return None

        elif self._state == DebounceState.ACTIVATING:
            if gesture is None:
                # Gesture released before activation
                self._state = DebounceState.IDLE
                self._activating_gesture = None
                logger.debug("ACTIVATING -> IDLE: gesture released")
                return None
            if gesture != self._activating_gesture:
                # Gesture switched -- reset timer
                self._activating_gesture = gesture
                self._activation_start = timestamp
                logger.debug("ACTIVATING reset: switched to %s", gesture.value)
                return None
            # Same gesture held -- check if delay elapsed
            if timestamp - self._activation_start >= self._activation_delay:
                self._state = DebounceState.FIRED
                logger.debug("ACTIVATING -> FIRED: %s", gesture.value)
                return gesture  # FIRE!
            return None

        elif self._state == DebounceState.FIRED:
            # Transition to cooldown immediately after fire
            self._state = DebounceState.COOLDOWN
            self._cooldown_start = timestamp
            self._activating_gesture = None
            logger.debug("FIRED -> COOLDOWN")
            return None

        elif self._state == DebounceState.COOLDOWN:
            if timestamp - self._cooldown_start >= self._cooldown_duration:
                # Cooldown elapsed -- require gesture to be None before re-activating
                if gesture is None:
                    self._state = DebounceState.IDLE
                    logger.debug("COOLDOWN -> IDLE: released")
                # If gesture still held after cooldown, stay in cooldown
                # until released (prevents re-fire of held gesture)
            return None
```

### Pattern 2: Key String Parser
**What:** Parse config key strings (e.g., `ctrl+z`, `space`, `enter`) into pynput key objects.
**When to use:** At config load time and on hot-reload, pre-parse all key mappings.
**Example:**
```python
# keystroke.py
from pynput.keyboard import Controller, Key, KeyCode

# Map config string names to pynput Key enum members
SPECIAL_KEYS = {
    "ctrl": Key.ctrl,
    "alt": Key.alt,
    "shift": Key.shift,
    "space": Key.space,
    "enter": Key.enter,
    "tab": Key.tab,
    "esc": Key.esc,
    "backspace": Key.backspace,
    "delete": Key.delete,
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
    "home": Key.home,
    "end": Key.end,
    "page_up": Key.page_up,
    "page_down": Key.page_down,
    "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
    "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
    "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
}

def parse_key_string(key_string: str):
    """Parse a key string like 'ctrl+z' into (modifiers, key).

    Returns:
        Tuple of (list of modifier Key objects, final key Key/KeyCode/str).

    Raises:
        ValueError: If a key name is not recognized.
    """
    parts = [p.strip().lower() for p in key_string.split("+")]
    modifiers = []
    for part in parts[:-1]:  # All but last are modifiers
        if part in SPECIAL_KEYS:
            modifiers.append(SPECIAL_KEYS[part])
        else:
            raise ValueError(f"Unknown modifier: '{part}' in '{key_string}'")

    final = parts[-1]
    if final in SPECIAL_KEYS:
        key = SPECIAL_KEYS[final]
    elif len(final) == 1:
        key = final  # Single character -- pynput accepts str
    else:
        raise ValueError(f"Unknown key: '{final}' in '{key_string}'")

    return modifiers, key


class KeystrokeSender:
    def __init__(self):
        self._controller = Controller()

    def send(self, modifiers, key):
        """Press modifiers, tap key, release modifiers."""
        for mod in modifiers:
            self._controller.press(mod)
        self._controller.press(key)
        self._controller.release(key)
        for mod in reversed(modifiers):
            self._controller.release(mod)
```

### Pattern 3: Config Hot-Reload via Polling
**What:** Check config.yaml mtime periodically; reload if changed.
**When to use:** In the main loop, check every N frames or every 1-2 seconds.
**Example:**
```python
# In config.py or a new reload helper
import os
import time

class ConfigWatcher:
    def __init__(self, path: str, check_interval: float = 2.0):
        self._path = path
        self._check_interval = check_interval
        self._last_mtime = os.path.getmtime(path)
        self._last_check = time.perf_counter()

    def check(self, current_time: float) -> bool:
        """Return True if config file has been modified since last check."""
        if current_time - self._last_check < self._check_interval:
            return False
        self._last_check = current_time
        try:
            mtime = os.path.getmtime(self._path)
            if mtime > self._last_mtime:
                self._last_mtime = mtime
                return True
        except OSError:
            pass
        return False
```

### Anti-Patterns to Avoid
- **Firing on every frame while gesture is held:** The state machine MUST fire exactly once, then enter cooldown. Never check "is gesture present?" without state tracking.
- **Parsing key strings on every fire:** Parse key mappings once at config load and cache the parsed (modifiers, key) tuples. Re-parse only on hot-reload.
- **Using time.time() for debounce:** Use `time.perf_counter()` -- it is monotonic and high-resolution. `time.time()` can jump on clock adjustments.
- **Blocking the main loop for config reload:** Config reload (YAML parse + key re-parse) should be fast (<10ms). Never use a blocking file watcher in the main loop.
- **Creating a new Controller per keystroke:** Create ONE `pynput.keyboard.Controller` instance and reuse it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Keyboard simulation | ctypes Win32 SendInput calls | pynput Controller | Cross-app compatibility, modifier handling, tested on Windows |
| Key combo parsing | Ad-hoc string splitting without validation | Structured parser with SPECIAL_KEYS lookup dict | Edge cases: unknown keys, empty strings, double-plus in key names |
| YAML config parsing | Custom config file format | PyYAML safe_load (already in use) | Established pattern from Phase 1 |

**Key insight:** pynput handles the OS-level complexity of sending keystrokes to arbitrary foreground windows. The `pressed()` context manager / manual press-release correctly sequences modifier keys. Do not attempt direct Win32 API calls.

## Common Pitfalls

### Pitfall 1: Gesture Flicker Causing Multiple Fires
**What goes wrong:** Without proper debounce, a gesture that flickers between detected and None can fire multiple times.
**Why it happens:** The smoother helps but isn't perfect -- the state machine is the second defense layer.
**How to avoid:** The ACTIVATING state requires continuous detection for the full activation_delay. Any drop to None resets to IDLE.
**Warning signs:** Multiple FIRED log entries for a single gesture hold.

### Pitfall 2: Held Gesture Re-Fires After Cooldown
**What goes wrong:** User holds fist for 5 seconds, it fires at 0.4s, then again at 1.2s (after cooldown).
**How to avoid:** After cooldown expires, require gesture to drop to None before allowing IDLE transition. The state machine stays in COOLDOWN until the gesture is released.
**Warning signs:** Repeated FIRED entries without the user re-performing the gesture.

### Pitfall 3: pynput Modifier Keys Not Released on Error
**What goes wrong:** If an exception occurs between pressing Ctrl and pressing Z, Ctrl stays held system-wide.
**Why it happens:** No try/finally around the press/release sequence.
**How to avoid:** Use try/finally to ensure all pressed modifiers are released. Or use pynput's `pressed()` context manager which handles cleanup.
**Warning signs:** After app crash, keys behave strangely (everything is Ctrl+whatever).

### Pitfall 4: Config Reload Breaks Running State
**What goes wrong:** Reloading config while the state machine is in ACTIVATING or COOLDOWN creates inconsistency.
**How to avoid:** On reload, reset the debouncer to IDLE state. The brief interruption is acceptable -- user is editing config, not gesturing.
**Warning signs:** Fire events referencing gestures not in the new config.

### Pitfall 5: Key String Parsing Edge Cases
**What goes wrong:** Config has `ctrl+` (trailing plus), or `CTRL+Z` (uppercase), or unknown key name.
**How to avoid:** Normalize to lowercase, validate each part against SPECIAL_KEYS dict, raise clear ValueError for unknowns.
**Warning signs:** KeyError or AttributeError at runtime instead of clear config error.

## Code Examples

### Wiring Into Main Loop
```python
# In __main__.py main(), after smoother setup:
from gesture_keys.debounce import GestureDebouncer
from gesture_keys.keystroke import KeystrokeSender, parse_key_string

debouncer = GestureDebouncer(
    activation_delay=config.activation_delay,
    cooldown_duration=config.cooldown_duration,
)
sender = KeystrokeSender()

# Pre-parse key mappings from config
key_mappings = {}  # gesture_name -> (modifiers, key)
for name, settings in config.gestures.items():
    key_str = settings.get("key", "")
    if key_str:
        key_mappings[name] = parse_key_string(key_str)

# In the frame loop, after smoother:
current_time = time.perf_counter()
fire_gesture = debouncer.update(gesture, current_time)
if fire_gesture and fire_gesture.value in key_mappings:
    modifiers, key = key_mappings[fire_gesture.value]
    sender.send(modifiers, key)
    key_str = config.gestures[fire_gesture.value]["key"]
    logger.info("FIRED: %s -> %s", fire_gesture.value, key_str)
```

### Config Extension
```python
# Extend AppConfig dataclass:
@dataclass
class AppConfig:
    camera_index: int = 0
    smoothing_window: int = 3
    activation_delay: float = 0.4
    cooldown_duration: float = 0.8
    gestures: dict[str, dict[str, Any]] = field(default_factory=dict)

# In load_config, add:
    activation_delay=float(detection.get("activation_delay", 0.4)),
    cooldown_duration=float(detection.get("cooldown_duration", 0.8)),
```

### Config YAML Extension
```yaml
detection:
  smoothing_window: 3
  activation_delay: 0.4
  cooldown_duration: 0.8
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pynput 1.7.x | pynput 1.8.1 | March 2025 | Added injected event detection; API unchanged |
| watchdog for single file | os.path.getmtime polling | N/A (design choice) | No extra dependency for single-file watch |

**Deprecated/outdated:**
- Nothing relevant -- pynput API has been stable since 1.7.x

## Open Questions

1. **How many frames of None constitute a "release"?**
   - What we know: The smoother already requires majority vote, so one frame of None won't pass through. If smoother returns None, the gesture is genuinely gone.
   - Recommendation: A single None from the smoother (which already represents multiple raw frames) is sufficient for release detection. No additional frame counting needed on top of the smoother.

2. **Should key parsing errors prevent app startup?**
   - What we know: CONTEXT.md specifies invalid config on reload keeps current config with WARNING log.
   - Recommendation: On initial startup, invalid key strings should raise ValueError (fail fast). On hot-reload, log WARNING and keep current mappings.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| KEY-01 | Parse key strings to pynput objects; map gestures to keys | unit | `python -m pytest tests/test_keystroke.py -x` | No - Wave 0 |
| KEY-02 | State machine transitions, timing, cooldown, no re-fire | unit | `python -m pytest tests/test_debounce.py -x` | No - Wave 0 |
| KEY-03 | Controller.press/release fires in foreground app | integration (manual) | Manual -- verify in text editor | N/A |
| KEY-04 | Log messages contain timestamps, gesture names, keys | unit | `python -m pytest tests/test_debounce.py tests/test_keystroke.py -x -k log` | No - Wave 0 |
| KEY-05 | Config reload detects mtime change, applies new mappings | unit | `python -m pytest tests/test_config.py -x -k reload` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_debounce.py` -- covers KEY-02 (state machine logic, timing, cooldown)
- [ ] `tests/test_keystroke.py` -- covers KEY-01, KEY-03 (key parsing, sender with mock controller)
- [ ] `tests/test_config.py` additions -- covers KEY-05 (reload, new fields)
- [ ] `pynput>=1.7.6` in requirements.txt -- dependency for keystroke module

## Sources

### Primary (HIGH confidence)
- [pynput official docs - keyboard usage](https://pynput.readthedocs.io/en/latest/keyboard-usage.html) - Controller API, press/release, pressed() context manager
- [pynput official docs - keyboard reference](https://pynput.readthedocs.io/en/latest/keyboard.html) - Full Key enum members, KeyCode class, HotKey.parse format
- [pynput PyPI](https://pypi.org/project/pynput/) - Current version 1.8.1

### Secondary (MEDIUM confidence)
- [watchdog PyPI](https://pypi.org/project/watchdog/) - Evaluated but rejected for single-file use case
- Existing codebase analysis (config.py, __main__.py, smoother.py, classifier.py) - Integration points verified

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pynput is the locked decision, API verified from official docs
- Architecture: HIGH - state machine pattern is well-defined in CONTEXT.md, integration points verified in existing code
- Pitfalls: HIGH - common debounce and keyboard automation pitfalls are well-documented

**Research date:** 2026-03-21
**Valid until:** 2026-04-21 (stable domain, pynput API unchanged for years)
