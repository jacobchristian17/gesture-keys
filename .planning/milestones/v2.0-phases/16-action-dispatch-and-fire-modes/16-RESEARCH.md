# Phase 16: Action Dispatch and Fire Modes - Research

**Researched:** 2026-03-25
**Domain:** Action resolution, key lifecycle management, config schema design
**Confidence:** HIGH

## Summary

Phase 16 bridges the gap between the orchestrator's gesture signals (FIRE, HOLD_START, HOLD_END, COMPOUND_FIRE) and the keyboard actions that get sent. Currently, the signal-to-keystroke mapping is embedded directly in Pipeline.process_frame() as a ~50-line inline block with ad-hoc hold state tracking. This phase extracts that logic into a structured ActionResolver + ActionDispatcher system with explicit fire modes.

The current codebase has two important properties to understand: (1) The v1.x "hold" mode in Pipeline does NOT use true key holding -- it repeatedly sends press+release at 30Hz via `send()`, creating the illusion of a held key. The `press_and_hold()` and `release_held()` methods exist in KeystrokeSender but are currently unused. (2) All hold state tracking (`_hold_active`, `_hold_modifiers`, `_hold_key`, etc.) lives in Pipeline as ad-hoc instance variables rather than in a dedicated class.

**Primary recommendation:** Create an ActionDispatcher class that owns all key lifecycle state and exposes a clean interface: `dispatch(signal)` for new actions and `release_all()` for safety cleanup. The ActionResolver is a pure function mapping (gesture, temporal_state, hand) to (key, fire_mode). The naming collision -- v1.x config uses "hold" for what Phase 16 calls "hold_key" -- must be handled with backward-compatible config parsing.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ACTN-01 | Action resolver maps static gesture x temporal state to configured keyboard command | ActionResolver as pure function; lookup table from config; gesture + temporal_state + handedness as inputs |
| ACTN-02 | Tap fire mode -- press and release key once on action trigger | Already works via KeystrokeSender.send(); just needs routing through ActionDispatcher |
| ACTN-03 | Hold_key fire mode -- key held down while gesture sustained, released on gesture change | Use KeystrokeSender.press_and_hold() + release_held() (already implemented but unused); ActionDispatcher tracks held state |
| ACTN-04 | Centralized key lifecycle management preventing stuck keys across all exit paths | ActionDispatcher.release_all() called on every exit path; Pipeline delegates all key state to ActionDispatcher |
| ACTN-05 | Config schema supporting structured gesture-to-action mappings with fire mode per action | New config schema with fire_mode field; backward-compat parsing of v1.x "mode: hold" as "fire_mode: hold_key" |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pynput | (existing) | Keyboard control | Already used; press/release/press_and_hold all implemented |
| dataclasses | stdlib | Action/Config types | Project convention for all data types |
| enum | stdlib | FireMode enum | Project convention for all state enums |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | (existing) | Testing | TDD for ActionResolver and ActionDispatcher |
| unittest.mock | stdlib | Mock KeystrokeSender | Verify key press/release sequences without real keyboard |

No new dependencies needed. Everything builds on existing pynput + stdlib.

## Architecture Patterns

### Recommended Project Structure
```
gesture_keys/
  action.py          # ActionResolver + ActionDispatcher + FireMode enum + Action dataclass
  keystroke.py        # KeystrokeSender (unchanged)
  orchestrator.py     # GestureOrchestrator (unchanged)
  pipeline.py         # Simplified: delegates to ActionDispatcher
  config.py           # Updated: parse structured gesture-to-action mappings
tests/
  test_action.py      # ActionResolver + ActionDispatcher unit tests
  test_config.py      # Updated: test new config schema parsing
```

### Pattern 1: ActionResolver (Pure Lookup)
**What:** Maps (gesture_name, temporal_state, handedness) to an Action (key_string, fire_mode).
**When to use:** On every orchestrator signal before dispatch.
**Design:**

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class FireMode(Enum):
    TAP = "tap"
    HOLD_KEY = "hold_key"

@dataclass(frozen=True)
class Action:
    """Resolved action from gesture + temporal state."""
    key_string: str
    fire_mode: FireMode
    gesture_name: str
    # Pre-parsed pynput objects (populated at config load time)
    modifiers: list  # list[Key]
    key: object      # Key | str

class ActionResolver:
    """Resolves gesture signals to keyboard actions.

    Holds pre-parsed action maps for both hands. Pure lookup, no state.
    """
    def __init__(self, right_actions: dict, left_actions: dict):
        self._right_actions = right_actions
        self._left_actions = left_actions
        self._active_actions = right_actions

    def set_hand(self, handedness: str) -> None:
        """Switch active action map based on detected hand."""
        self._active_actions = (
            self._left_actions if handedness == "Left"
            else self._right_actions
        )

    def resolve(self, gesture_name: str) -> Optional[Action]:
        """Look up action for a gesture. Returns None if unmapped."""
        return self._active_actions.get(gesture_name)
```

### Pattern 2: ActionDispatcher (Stateful Key Lifecycle)
**What:** Owns all held-key state and routes signals to the correct fire mode handler.
**When to use:** Replaces the inline signal handling block in Pipeline.process_frame().
**Design:**

```python
class ActionDispatcher:
    """Dispatches orchestrator signals to keyboard actions.

    Owns held-key lifecycle state. Guarantees no stuck keys via
    release_all() on every exit path.
    """
    def __init__(self, sender: KeystrokeSender, resolver: ActionResolver):
        self._sender = sender
        self._resolver = resolver
        self._held_action: Optional[Action] = None

    def dispatch(self, signal: OrchestratorSignal) -> None:
        """Route a signal to the appropriate fire mode handler."""
        if signal.action == OrchestratorAction.FIRE:
            self._handle_fire(signal)
        elif signal.action == OrchestratorAction.HOLD_START:
            self._handle_hold_start(signal)
        elif signal.action == OrchestratorAction.HOLD_END:
            self._handle_hold_end(signal)
        elif signal.action == OrchestratorAction.COMPOUND_FIRE:
            self._handle_compound_fire(signal)

    def _handle_fire(self, signal):
        action = self._resolver.resolve(signal.gesture.value)
        if action and action.fire_mode == FireMode.TAP:
            self._sender.send(action.modifiers, action.key)

    def _handle_hold_start(self, signal):
        action = self._resolver.resolve(signal.gesture.value)
        if action and action.fire_mode == FireMode.HOLD_KEY:
            self._sender.press_and_hold(action.modifiers, action.key)
            self._held_action = action

    def _handle_hold_end(self, signal):
        if self._held_action is not None:
            self._sender.release_held()
            self._held_action = None

    def release_all(self) -> None:
        """Release all held keys. Called on every exit path."""
        self._held_action = None
        self._sender.release_all()
```

### Pattern 3: Exhaustive Exit Path Coverage
**What:** Every path that can interrupt a gesture must call `dispatcher.release_all()`.
**Exit paths (6 total):**

| Exit Path | Where It Happens | Current Code Location |
|-----------|-----------------|----------------------|
| Gesture change | Orchestrator emits HOLD_END | `pipeline.py` signal loop |
| Gate expiry | Phase 17 (future) | Will call `dispatcher.release_all()` |
| Hand switch | Pipeline detects handedness change | `pipeline.py` line ~320 |
| Distance out-of-range | DistanceFilter returns False | `pipeline.py` line ~353 |
| App toggle off | TrayApp sets active=False | `tray.py` line ~110, `pipeline.stop()` |
| Config reload | Pipeline.reload_config() | `pipeline.py` line ~476 |

### Anti-Patterns to Avoid
- **Scattered hold state:** Do NOT track `_hold_active`, `_hold_modifiers`, `_hold_key` etc. as separate Pipeline instance variables. All hold state belongs in ActionDispatcher.
- **release_all() in multiple places with different logic:** All exit paths should call a single `dispatcher.release_all()` method. No manual `_sender.release_all()` calls in Pipeline.
- **Fire mode in orchestrator:** The orchestrator manages WHEN signals fire, not HOW they map to keys. Fire mode resolution belongs in the action layer.
- **Tap-repeat as "hold_key":** The v1.x hold mode sends press+release at 30Hz. The v2.0 hold_key mode must use true press_and_hold + release_held. These are different behaviors.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Key press/release | Raw controller.press/release scattered in Pipeline | KeystrokeSender methods (send, press_and_hold, release_held) | Already handles modifier ordering, error recovery |
| Config parsing | Manual YAML dict traversal | Structured parsing in load_config() -> ActionMap | Centralized validation catches errors at startup |
| Held key tracking | Ad-hoc boolean flags | ActionDispatcher with single `_held_action` field | Single source of truth prevents state desync |

**Key insight:** KeystrokeSender already has `press_and_hold()` and `release_held()` fully implemented and tested (test_keystroke.py lines 118-198). They are simply unused by the current Pipeline. Phase 16 just needs to wire them up through ActionDispatcher.

## Common Pitfalls

### Pitfall 1: Stuck Keys from Missed Exit Paths
**What goes wrong:** A hold_key action holds down a key, but an exit path fails to release it. The key stays "stuck" and the user must Alt+F4 or physically restart.
**Why it happens:** Exit paths are scattered across Pipeline and easy to miss (6 paths currently).
**How to avoid:** ActionDispatcher.release_all() is the ONLY way to release keys. Pipeline.stop(), Pipeline.reset_pipeline(), and every exit path call dispatcher.release_all(). Belt-and-suspenders: Pipeline.stop() always calls release_all() regardless of state.
**Warning signs:** Any exit path that resets orchestrator but doesn't call dispatcher.release_all().

### Pitfall 2: Naming Collision -- "hold" vs "hold_key"
**What goes wrong:** v1.x config uses `mode: hold` to mean "send repeated keystrokes while gesture held" (tap-repeat mode). v2.0 temporal state uses "hold" to mean "gesture held past threshold." The Phase 16 fire mode for sustained key press is `hold_key`. Confusing these causes wrong behavior.
**Why it happens:** The word "hold" is overloaded across 3 different meanings.
**How to avoid:** In config: `fire_mode: hold_key` (never `fire_mode: hold`). Internally: FireMode.HOLD_KEY enum value. For backward compat: parse v1.x `mode: hold` as `fire_mode: hold_key` during config migration.
**Warning signs:** Any code using the bare string "hold" for fire mode.

### Pitfall 3: Hold-to-Hold Transition (Gesture Switch While Holding)
**What goes wrong:** User holds fist (key A held), then switches to open_palm (also hold_key mode). If HOLD_END for fist fires after HOLD_START for open_palm, the release_held() releases the NEW key instead of the old one.
**Why it happens:** KeystrokeSender.release_held() releases everything in _held_keys, not a specific key.
**How to avoid:** The orchestrator already handles this correctly: _handle_hold() emits HOLD_END for the old gesture BEFORE transitioning to ACTIVATING for the new gesture (orchestrator.py line 452-462). ActionDispatcher processes signals in order, so HOLD_END releases old keys before HOLD_START presses new ones. Verify this ordering in tests.
**Warning signs:** Tests that don't verify the signal ordering for gesture transitions.

### Pitfall 4: Config Reload While Key Held
**What goes wrong:** User edits config while a key is held. The key mapping changes but the held key reference becomes stale.
**Why it happens:** Config reload replaces the action maps, but the held key was resolved from the OLD config.
**How to avoid:** Pipeline.reload_config() already calls release_all() before updating config (line 476-477). ActionDispatcher.release_all() clears _held_action and releases physical keys. After reload, new actions use new config.

### Pitfall 5: Tap-Repeat Mode Removal
**What goes wrong:** v1.x "hold" mode (tap-repeat at 30Hz) is removed, and users who relied on it lose functionality.
**Why it happens:** Phase 16 replaces the tap-repeat behavior with true key hold.
**How to avoid:** For v2.0 scope, the tap-repeat behavior is intentionally replaced. The `hold_repeat_interval` config field and the repeat loop in Pipeline (line 453-455) should be removed. If backward compat is needed, add a `repeat` fire mode in a future enhancement (ENH-04). Document the behavior change.

### Pitfall 6: Compound Fire With Hold Mode
**What goes wrong:** A gesture configured as hold_key also has swipe mappings. The swipe window waits for a swipe, but the hold gesture should have started holding immediately.
**Why it happens:** Swipe window takes priority in the orchestrator for swipe-mapped gestures. Gestures with swipe blocks cannot be hold mode (config.py line 148-153 already validates this).
**How to avoid:** Config validation already rejects `mode: hold` + `swipe:` block (ValueError). Preserve this validation in the new config schema.

## Code Examples

### Current Signal Handling in Pipeline (to be replaced)
```python
# pipeline.py lines 409-434 -- this inline block becomes ActionDispatcher.dispatch()
for signal in orch_result.signals:
    sig_gesture_name = signal.gesture.value
    if signal.action == OrchestratorAction.COMPOUND_FIRE:
        # compound lookup + sender.send()
    elif sig_gesture_name in self._key_mappings:
        if signal.action == OrchestratorAction.FIRE:
            self._sender.send(sig_mods, sig_key)
        elif signal.action == OrchestratorAction.HOLD_START:
            self._sender.send(sig_mods, sig_key)  # NOTE: uses send(), not press_and_hold()
            self._hold_active = True
            # ... 6 more ad-hoc state assignments
        elif signal.action == OrchestratorAction.HOLD_END:
            self._hold_active = False
```

### KeystrokeSender Hold Methods (already implemented, unused)
```python
# keystroke.py lines 121-152 -- these are ready to use
def press_and_hold(self, modifiers: list[Key], key: Union[Key, str]) -> None:
    """Press modifiers and key without releasing. Tracks held keys."""
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
```

### v1.x Config (current format)
```yaml
gestures:
  fist:
    key: space
    mode: hold          # v1.x: means tap-repeat at hold_repeat_interval
    threshold: 0.7
  open_palm:
    key: win+tab
    threshold: 0.7
    swipe:
      swipe_left:
        key: "1"
```

### v2.0 Config (target format -- backward compatible)
```yaml
gestures:
  fist:
    key: space
    fire_mode: hold_key   # v2.0: true key hold (press_and_hold + release_held)
    threshold: 0.7
  open_palm:
    key: win+tab
    fire_mode: tap        # explicit (default if omitted)
    threshold: 0.7
    swipe:
      swipe_left:
        key: "1"
```

**Backward compatibility approach:** Config parser accepts both `mode:` and `fire_mode:`. If `mode: hold` is found, treat as `fire_mode: hold_key`. If `mode: tap` is found, treat as `fire_mode: tap`. New `fire_mode:` field takes precedence over old `mode:` field.

## State of the Art

| Old Approach (v1.x) | New Approach (v2.0) | Impact |
|---------------------|---------------------|--------|
| `mode: hold` = tap-repeat at 30Hz | `fire_mode: hold_key` = true sustained keypress | Real hold behavior for games/apps expecting held keys |
| Hold state as 6 Pipeline instance vars | ActionDispatcher with single `_held_action` | Single source of truth, no state desync |
| Inline signal handling in process_frame() | ActionDispatcher.dispatch(signal) | Testable, isolated, configurable |
| gesture_name -> key_string flat lookup | ActionResolver with (gesture, hand) -> Action | Per-hand action maps with explicit fire mode |
| `_extract_gesture_modes()` returns mode dict | Fire mode stored directly in Action dataclass | No separate mode lookup step |

## Open Questions

1. **Should tap-repeat mode be preserved as a third fire_mode?**
   - What we know: v1.x "hold" uses press+release at 30Hz. Some users may rely on this for scroll-like behavior.
   - What's unclear: Whether any real use case requires tap-repeat vs true hold.
   - Recommendation: Remove tap-repeat for now (v2.0 clean break). ENH-04 in REQUIREMENTS.md already tracks "Repeat fire mode" as a future enhancement. If needed, add `fire_mode: repeat` later.

2. **Should hold_key mode support modifiers?**
   - What we know: KeystrokeSender.press_and_hold() already supports modifiers (tested in test_keystroke.py line 136-139). Config already supports `ctrl+space` style key strings.
   - Recommendation: YES, it works already. No additional work needed.

3. **Compound swipe actions and ActionDispatcher**
   - What we know: Compound swipe mappings use a (gesture_name, direction) lookup key. They always use tap fire mode (compound fire = press+release).
   - Recommendation: ActionDispatcher handles COMPOUND_FIRE as always-tap. The compound mapping table stays in Pipeline or moves to ActionResolver with a separate lookup method.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_action.py tests/test_config.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q --ignore=tests/test_pipeline.py --ignore=tests/test_preview.py --ignore=tests/test_tray.py --ignore=tests/test_detector.py` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ACTN-01 | Resolver maps gesture x temporal state to action | unit | `python -m pytest tests/test_action.py::TestActionResolver -x` | Wave 0 |
| ACTN-02 | Tap fire mode press+release | unit | `python -m pytest tests/test_action.py::TestTapFireMode -x` | Wave 0 |
| ACTN-03 | Hold_key fire mode sustained press + release on change | unit | `python -m pytest tests/test_action.py::TestHoldKeyFireMode -x` | Wave 0 |
| ACTN-04 | No stuck keys on all 6 exit paths | unit | `python -m pytest tests/test_action.py::TestStuckKeyPrevention -x` | Wave 0 |
| ACTN-05 | Config schema with fire_mode per action | unit | `python -m pytest tests/test_config.py::TestFireModeConfig -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_action.py tests/test_config.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q --ignore=tests/test_pipeline.py --ignore=tests/test_preview.py --ignore=tests/test_tray.py --ignore=tests/test_detector.py`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_action.py` -- covers ACTN-01, ACTN-02, ACTN-03, ACTN-04 (new file)
- [ ] `gesture_keys/action.py` -- ActionResolver + ActionDispatcher + FireMode + Action (new file)
- [ ] Config schema tests for `fire_mode` field in `tests/test_config.py` (extend existing)

## Sources

### Primary (HIGH confidence)
- `gesture_keys/keystroke.py` -- KeystrokeSender already has press_and_hold/release_held fully implemented and tested
- `gesture_keys/orchestrator.py` -- OrchestratorAction enum defines FIRE, HOLD_START, HOLD_END, COMPOUND_FIRE signals
- `gesture_keys/pipeline.py` -- Current inline signal handling (lines 409-455) shows exact behavior to preserve and refactor
- `gesture_keys/config.py` -- _extract_gesture_modes() shows current mode parsing; extract_gesture_swipe_mappings() validates hold+swipe rejection
- `tests/test_keystroke.py` -- TestKeystrokeSenderHold class (lines 118-198) confirms press_and_hold/release_held work correctly

### Secondary (MEDIUM confidence)
- `config.yaml` -- Shows current user-facing config format with `mode: hold` on fist gesture
- `.planning/STATE.md` -- Documents naming collision concern and stuck-key safety requirement

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new dependencies
- Architecture: HIGH -- ActionResolver/ActionDispatcher pattern directly maps to existing signal flow
- Pitfalls: HIGH -- all 6 exit paths identified from reading Pipeline source; stuck key scenarios understood from KeystrokeSender implementation
- Config schema: HIGH -- backward compatibility path clear from existing _extract_gesture_modes() code

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable -- no external dependency changes expected)
