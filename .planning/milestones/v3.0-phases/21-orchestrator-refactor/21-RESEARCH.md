# Phase 21: Orchestrator Refactor - Research

**Researched:** 2026-03-26
**Domain:** Python FSM refactoring -- state removal, signal addition, sequence tracking
**Confidence:** HIGH

## Summary

This phase refactors the GestureOrchestrator FSM to remove all swipe-related states/signals and add two new signal types: MOVING_FIRE (gesture + motion) and SEQUENCE_FIRE (two-gesture sequence). The orchestrator currently has 556 lines with swipe logic deeply woven through constructor params, update() signature, state handlers, and build_result(). The test file has 1002 lines with 94 tests, approximately 30-35 of which are swipe-specific and must be deleted or rewritten.

The core lifecycle (IDLE -> ACTIVATING -> ACTIVE -> COOLDOWN) remains intact. The SWIPE_WINDOW lifecycle state, SWIPING temporal state, and COMPOUND_FIRE action are deleted. Two new OrchestratorAction values (MOVING_FIRE, SEQUENCE_FIRE) are added. The update() method gains a `motion_state: Optional[MotionState]` parameter and loses `swipe_direction` and `swiping` parameters. A new constructor parameter `sequence_definitions` accepts registered sequence pairs.

**Primary recommendation:** Execute as a delete-then-add approach: first strip all swipe code from the orchestrator and its tests, then layer on motion_state consumption and sequence tracking as additive features on top of the simplified FSM.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Gesture A counts as "completed" for a sequence after it emits a FIRE signal (must pass activation delay and fire)
- Sequence window timer starts from gesture A's FIRE moment (not from release)
- Both standalone actions AND the sequence action fire -- sequence is purely additive (A fires its standalone, then when B fires within window, B fires its standalone AND the sequence fires)
- Orchestrator receives registered sequence pairs as a constructor parameter (e.g., set of (gesture_A, gesture_B) tuples), matching the existing pattern of gesture_modes, gesture_cooldowns as constructor params
- Sequence window duration configurable, default 0.5s (ORCH-04)
- Remove all three: SWIPE_WINDOW from LifecycleState, SWIPING from TemporalState, COMPOUND_FIRE from OrchestratorAction
- Remove suppress_standalone_swipe field from OrchestratorResult entirely
- Remove swipe_direction and swiping params from update() method
- Remove _handle_swiping_transitions method and all swiping tracking state (_was_swiping, _pre_swipe_gesture, _suppress_until)
- Remove swipe_gesture_directions constructor parameter and _swipe_gesture_directions field
- Remove swipe_window constructor parameter (repurposed as sequence_window)
- No routing needed for MOVING_FIRE -- orchestrator emits whenever gesture + moving + direction detected, ActionResolver decides if there's a matching action
- OrchestratorSignal.direction changes from Optional[SwipeDirection] to Optional[Direction] (from trigger.py)
- SwipeDirection import removed from orchestrator.py entirely
- Add MOVING_FIRE and SEQUENCE_FIRE to OrchestratorAction enum (total: FIRE, HOLD_START, HOLD_END, MOVING_FIRE, SEQUENCE_FIRE)
- Add optional second_gesture: Optional[Gesture] = None field to OrchestratorSignal (for SEQUENCE_FIRE: gesture = first, second_gesture = second)
- OrchestratorResult keeps same shape minus suppress_standalone_swipe: base_gesture, temporal_state, outer_state, signals

### Claude's Discretion
- MOVING_FIRE emission logic (when exactly to emit during gesture lifecycle -- activation delay interaction, hold mode interaction)
- Internal sequence tracking data structure (deque of recent fires, dict of last fire time per gesture, etc.)
- How motion_state param interacts with existing lifecycle states (IDLE, ACTIVATING, ACTIVE, COOLDOWN)
- Whether flush_pending() needs changes for the new states
- Test strategy and which existing swipe tests to rewrite vs delete

### Deferred Ideas (OUT OF SCOPE)
None

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ORCH-01 | Orchestrator accepts motion_state parameter and emits MOVING_FIRE signal when gesture + moving + direction detected | update() gains MotionState param; MOVING_FIRE added to OrchestratorAction; signal emitted during ACTIVE states when motion_state.moving is True |
| ORCH-02 | Orchestrator emits SEQUENCE_FIRE signal when two gestures match a sequence trigger within time window | Constructor gains sequence_definitions param; internal tracking of recent FIRE timestamps per gesture; SEQUENCE_FIRE signal includes both gestures |
| ORCH-03 | Orchestrator FSM simplified: SWIPE_WINDOW, SWIPING, and COMPOUND_FIRE states/signals removed | Delete 3 enum values, remove _handle_swipe_window and _handle_swiping_transitions, strip swipe params from constructor and update() |
| ORCH-04 | Sequence window is configurable (default 0.5s) | Constructor param sequence_window: float = 0.5, used in sequence completion check |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.x | enum, dataclass, typing, collections.deque | All types already used in orchestrator.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | existing | Test framework | Already configured in project |

No new dependencies needed. This is purely internal refactoring of existing Python code.

## Architecture Patterns

### Current Orchestrator Structure (before refactor)
```
orchestrator.py (556 lines):
  OrchestratorAction: FIRE, HOLD_START, HOLD_END, COMPOUND_FIRE
  LifecycleState: IDLE, ACTIVATING, SWIPE_WINDOW, ACTIVE, COOLDOWN
  TemporalState: CONFIRMED, HOLD, SWIPING
  OrchestratorSignal(action, gesture, direction: Optional[SwipeDirection])
  OrchestratorResult(base_gesture, temporal_state, outer_state, signals, suppress_standalone_swipe)
  GestureOrchestrator.__init__(activation_delay, cooldown_duration, gesture_cooldowns,
                                gesture_modes, hold_release_delay, swipe_gesture_directions, swipe_window)
  GestureOrchestrator.update(gesture, timestamp, swipe_direction, swiping)
```

### Target Orchestrator Structure (after refactor)
```
orchestrator.py:
  OrchestratorAction: FIRE, HOLD_START, HOLD_END, MOVING_FIRE, SEQUENCE_FIRE
  LifecycleState: IDLE, ACTIVATING, ACTIVE, COOLDOWN
  TemporalState: CONFIRMED, HOLD
  OrchestratorSignal(action, gesture, direction: Optional[Direction], second_gesture: Optional[Gesture])
  OrchestratorResult(base_gesture, temporal_state, outer_state, signals)
  GestureOrchestrator.__init__(activation_delay, cooldown_duration, gesture_cooldowns,
                                gesture_modes, hold_release_delay,
                                sequence_definitions, sequence_window)
  GestureOrchestrator.update(gesture, timestamp, motion_state)
```

### Pattern 1: MOVING_FIRE Emission Logic
**What:** Emit MOVING_FIRE whenever a recognized gesture is active AND motion_state.moving is True with a direction
**When to emit:** During ACTIVE(HOLD) and on FIRE transitions -- any time the orchestrator has confirmed a gesture and the hand is moving
**Recommendation:**
- During ACTIVATING: Do NOT emit MOVING_FIRE (gesture not yet confirmed)
- On FIRE (tap mode): Emit MOVING_FIRE alongside FIRE if motion_state.moving at fire moment
- During ACTIVE(HOLD): Emit MOVING_FIRE each frame while motion_state.moving is True (continuous signal, like HOLD_START is continuous presence)
- During COOLDOWN: Do NOT emit MOVING_FIRE (gesture in cooldown)
- Key insight: MOVING_FIRE is purely additive -- it does not replace or suppress FIRE/HOLD_START signals. The ActionResolver (Phase 22) decides if there is a matching moving trigger action.

```python
# In _handle_activating when FIRE is emitted:
signals.append(OrchestratorSignal(OrchestratorAction.FIRE, gesture))
if motion_state is not None and motion_state.moving and motion_state.direction is not None:
    signals.append(OrchestratorSignal(
        OrchestratorAction.MOVING_FIRE, gesture, direction=motion_state.direction
    ))

# In _handle_hold each frame while gesture held:
if motion_state is not None and motion_state.moving and motion_state.direction is not None:
    signals.append(OrchestratorSignal(
        OrchestratorAction.MOVING_FIRE, self._holding_gesture, direction=motion_state.direction
    ))
```

### Pattern 2: Sequence Tracking Data Structure
**What:** Track recent FIRE events per gesture to detect sequence completion
**Recommendation:** Use a dict mapping Gesture -> float (last fire timestamp). Simple and O(1) lookup.
```python
# Constructor
self._sequence_definitions: set[tuple[Gesture, Gesture]] = sequence_definitions or set()
self._sequence_window = sequence_window
self._last_fire_time: dict[Gesture, float] = {}

# After any FIRE signal is emitted:
def _check_sequences(self, fired_gesture: Gesture, timestamp: float, signals: list) -> None:
    """Check if this fire completes any registered sequence."""
    for first, second in self._sequence_definitions:
        if second == fired_gesture and first in self._last_fire_time:
            if timestamp - self._last_fire_time[first] <= self._sequence_window:
                signals.append(OrchestratorSignal(
                    OrchestratorAction.SEQUENCE_FIRE,
                    gesture=first,
                    second_gesture=fired_gesture,
                ))
    self._last_fire_time[fired_gesture] = timestamp
```

### Pattern 3: Swipe Code Removal Checklist
**What:** Systematic removal of all swipe-related code from orchestrator.py
**Items to remove:**
1. `from gesture_keys.swipe import SwipeDirection` -- replace with `from gesture_keys.trigger import Direction`
2. `OrchestratorAction.COMPOUND_FIRE` -- delete enum value
3. `LifecycleState.SWIPE_WINDOW` -- delete enum value
4. `TemporalState.SWIPING` -- delete enum value
5. `OrchestratorSignal.direction: Optional[SwipeDirection]` -- change to `Optional[Direction]`
6. `OrchestratorResult.suppress_standalone_swipe` -- delete field
7. Constructor params: `swipe_gesture_directions`, `swipe_window` -- remove (add `sequence_definitions`, `sequence_window`)
8. Instance vars: `_swipe_gesture_directions`, `_swipe_window`, `_swipe_window_start`, `_suppress_until`, `_was_swiping`, `_pre_swipe_gesture` -- delete
9. Methods: `_handle_swiping_transitions()`, `_handle_swipe_window()` -- delete entirely
10. `_handle_idle()`: remove swipe_gesture_directions check branch
11. `_handle_cooldown()`: remove swipe_gesture_directions routing
12. `_build_result()`: remove SWIPE_WINDOW branch, remove suppress logic
13. `reset()`: remove swipe-related state resets
14. `flush_pending()`: simplify or remove (no SWIPE_WINDOW state to flush)
15. Properties: `in_swipe_window` -- delete

### Anti-Patterns to Avoid
- **Partial swipe removal:** Do not leave any SwipeDirection references or SWIPE_WINDOW handling. A grep for "swipe" (case-insensitive) in orchestrator.py should return zero hits after refactor.
- **Overcomplicating MOVING_FIRE:** The orchestrator just emits the signal -- it does NOT check if a matching action exists. That is Phase 22's job.
- **Sequence tracking in wrong layer:** Sequence tracking belongs in the orchestrator (it needs FIRE timing), not in ActionResolver.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Timestamp tracking | Custom timer class | Simple dict[Gesture, float] | Only need last-fire-per-gesture, dict lookup is O(1) |
| Direction type | New enum | trigger.py:Direction | Already exists, single source of truth |
| Motion state type | New dataclass | motion.py:MotionState | Already exists from Phase 19 |

## Common Pitfalls

### Pitfall 1: Breaking existing FIRE/HOLD lifecycle
**What goes wrong:** Refactoring swipe removal accidentally breaks the IDLE -> ACTIVATING -> ACTIVE -> COOLDOWN flow
**Why it happens:** Swipe logic is interleaved with core lifecycle in _handle_idle and _handle_cooldown
**How to avoid:** After swipe removal, run ALL non-swipe tests to ensure core lifecycle is intact before adding new features
**Warning signs:** Tests for tap mode, hold mode, cooldown transitions failing

### Pitfall 2: Sequence fires on wrong gesture pair order
**What goes wrong:** Sequence (A, B) also fires on (B, A)
**Why it happens:** Not checking directionality of sequence definition
**How to avoid:** The check must be: `second == fired_gesture AND first in last_fire_time` -- the fired gesture is always the SECOND in the pair
**Warning signs:** Sequence tests passing with reversed gesture order

### Pitfall 3: Stale sequence timestamps
**What goes wrong:** A fire from 10 seconds ago still triggers a sequence when B fires
**Why it happens:** Not checking window expiry
**How to avoid:** Always check `timestamp - last_fire_time[first] <= sequence_window` before emitting SEQUENCE_FIRE
**Warning signs:** Sequences firing across long time gaps

### Pitfall 4: flush_pending() becomes dead code
**What goes wrong:** flush_pending() still references SWIPE_WINDOW after removal
**Why it happens:** Forgetting to update flush_pending()
**How to avoid:** flush_pending() purpose was to fire pending gesture in SWIPE_WINDOW before config reload. With SWIPE_WINDOW gone, it should either become a no-op or be simplified. Since pipeline.py calls it, keep the method but simplify: if no pending state, return empty result.

### Pitfall 5: OrchestratorSignal NamedTuple field order
**What goes wrong:** Adding second_gesture field breaks existing tuple unpacking
**Why it happens:** NamedTuple fields are positional -- adding a 4th field changes unpacking behavior
**How to avoid:** The existing code uses `action, gesture, direction = sig` (3-field unpack). With a 4th field, this still works because Python allows unpacking fewer than total fields when using NamedTuple attribute access. BUT direct 3-field unpacking `a, b, c = sig` will FAIL if sig has 4 fields. Check all consumers of OrchestratorSignal for tuple unpacking.
**Warning signs:** `ValueError: too many values to unpack` at runtime

### Pitfall 6: Tests importing deleted symbols
**What goes wrong:** Tests import SwipeDirection, COMPOUND_FIRE, SWIPE_WINDOW -- all deleted
**Why it happens:** Tests not updated in sync with production code
**How to avoid:** Update test imports first, then delete swipe test classes entirely, then verify remaining tests pass

## Code Examples

### Updated OrchestratorAction enum
```python
class OrchestratorAction(Enum):
    FIRE = "fire"
    HOLD_START = "hold_start"
    HOLD_END = "hold_end"
    MOVING_FIRE = "moving_fire"
    SEQUENCE_FIRE = "sequence_fire"
```

### Updated LifecycleState enum
```python
class LifecycleState(Enum):
    IDLE = "IDLE"
    ACTIVATING = "ACTIVATING"
    ACTIVE = "ACTIVE"
    COOLDOWN = "COOLDOWN"
```

### Updated TemporalState enum
```python
class TemporalState(Enum):
    CONFIRMED = "CONFIRMED"
    HOLD = "HOLD"
```

### Updated OrchestratorSignal
```python
class OrchestratorSignal(NamedTuple):
    action: OrchestratorAction
    gesture: Gesture
    direction: Optional[Direction] = None
    second_gesture: Optional[Gesture] = None
```

### Updated OrchestratorResult
```python
@dataclass
class OrchestratorResult:
    base_gesture: Optional[Gesture] = None
    temporal_state: Optional[TemporalState] = None
    outer_state: LifecycleState = LifecycleState.IDLE
    signals: list[OrchestratorSignal] = field(default_factory=list)
```

### Updated update() signature
```python
def update(
    self,
    gesture: Optional[Gesture],
    timestamp: float,
    *,
    motion_state: Optional[MotionState] = None,
) -> OrchestratorResult:
```

### Simplified _handle_idle (no swipe routing)
```python
def _handle_idle(self, gesture, timestamp, signals):
    if gesture is not None:
        self._outer_state = LifecycleState.ACTIVATING
        self._activating_gesture = gesture
        self._activation_start = timestamp
        logger.debug("IDLE -> ACTIVATING: %s", gesture.value)
```

### Simplified _handle_cooldown (no swipe routing)
```python
def _handle_cooldown(self, gesture, timestamp, signals):
    if gesture is not None and gesture != self._cooldown_gesture:
        self._outer_state = LifecycleState.ACTIVATING
        self._activating_gesture = gesture
        self._activation_start = timestamp
        self._cooldown_gesture = None
        logger.debug("COOLDOWN -> ACTIVATING: %s (direct transition)", gesture.value)
        return
    if timestamp - self._cooldown_start >= self._cooldown_duration_active and gesture is None:
        self._outer_state = LifecycleState.IDLE
        self._cooldown_gesture = None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SwipeDirection (swipe_left, swipe_right, etc.) | Direction (left, right, up, down) | Phase 18 | Clean cardinal names |
| SwipeDetector (event-based) | MotionDetector (continuous per-frame) | Phase 19 | Feeds MOVING_FIRE |
| swipe_gesture_directions config | actions: with trigger strings | Phase 20 | Unified action model |
| COMPOUND_FIRE (gesture + swipe direction) | MOVING_FIRE (gesture + motion direction) | This phase | Simpler, more general |

## Test Impact Analysis

### Tests to DELETE entirely (swipe-specific, ~35 tests)
- `TestSwipeWindow` (class, ~12 tests) -- SWIPE_WINDOW state no longer exists
- `TestSwipingTransitions` (class, ~4 tests) -- swiping entry/exit no longer exists
- `TestCompoundSwipeSuppression` (class, ~3 tests) -- suppress_standalone_swipe removed
- Swipe-related tests within `TestProperties` (~4 tests: in_swipe_window, activating_gesture_during_swipe_window)
- Swipe-related tests within `TestFlushPending` (~2 tests referencing SWIPE_WINDOW)
- Swipe-related tests within `TestEdgeCases` (~5 tests: edge_1 swipe_window, edge_3 swipe_exit, edge_4 pre_swipe_suppression, edge_5 flush_pending swipe, edge_8 compound_swipe_suppression)
- Swipe-related tests within `TestTemporalStateInvariants` and `TestBaseGesture` (swipe_window cases)

### Tests to MODIFY (import/assertion changes)
- `TestTypeDefinitions`: Remove COMPOUND_FIRE assertion, remove SWIPE_WINDOW assertion, remove SWIPING assertion, remove SwipeDirection signal test, remove suppress_standalone_swipe assertion. Add MOVING_FIRE and SEQUENCE_FIRE assertions.
- `TestConstructor.test_accepts_all_config_params`: Update constructor params (remove swipe_*, add sequence_*)

### Tests to KEEP unchanged (~50+ tests)
- `TestOrchestratorStateTransitions` (tap lifecycle)
- `TestDirectTransitions` (cooldown direct transitions -- remove swipe branch)
- `TestHoldMode` (all hold mode tests)
- `TestHoldModeGestureChange` (all)
- `TestHoldModeCooldownCycle` (all)
- `TestPerGestureCooldowns` (all)
- `TestReset` (update to not check swipe state)

### Tests to ADD (new features, ~15-20 tests)
- MOVING_FIRE emission during FIRE (tap mode + moving)
- MOVING_FIRE emission during ACTIVE(HOLD) + moving
- MOVING_FIRE NOT emitted during ACTIVATING
- MOVING_FIRE NOT emitted during COOLDOWN
- MOVING_FIRE with correct direction field
- SEQUENCE_FIRE on valid two-gesture sequence within window
- SEQUENCE_FIRE not emitted when outside window
- SEQUENCE_FIRE not emitted for unregistered pairs
- SEQUENCE_FIRE not emitted for reversed pair
- SEQUENCE_FIRE includes correct gesture and second_gesture
- Sequence window configurable (non-default value)
- Both standalone FIRE and SEQUENCE_FIRE emitted on sequence completion
- OrchestratorSignal with second_gesture field
- motion_state=None does not crash

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | pyproject.toml or pytest.ini (existing) |
| Quick run command | `python -m pytest tests/test_orchestrator.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ORCH-01 | MOVING_FIRE emitted when gesture + moving + direction | unit | `python -m pytest tests/test_orchestrator.py -k "moving_fire" -x` | Will be created |
| ORCH-02 | SEQUENCE_FIRE emitted on matching sequence within window | unit | `python -m pytest tests/test_orchestrator.py -k "sequence_fire" -x` | Will be created |
| ORCH-03 | SWIPE_WINDOW, SWIPING, COMPOUND_FIRE removed | unit | `python -m pytest tests/test_orchestrator.py -k "type_def" -x` | Existing, needs update |
| ORCH-04 | Sequence window configurable, default 0.5s | unit | `python -m pytest tests/test_orchestrator.py -k "sequence_window" -x` | Will be created |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_orchestrator.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before /gsd:verify-work

### Wave 0 Gaps
None -- existing test infrastructure covers all phase requirements. New test functions will be added to the existing test_orchestrator.py file.

## Open Questions

1. **MOVING_FIRE during ACTIVE(HOLD) -- continuous or one-shot?**
   - What we know: User wants MOVING_FIRE emitted when gesture is held while moving. MotionState is per-frame continuous.
   - Recommendation: Emit MOVING_FIRE every frame while in ACTIVE(HOLD) and motion_state.moving is True. This matches the continuous nature of MotionState and lets ActionResolver decide what to do with repeated signals. This mirrors how HOLD state is continuous -- the orchestrator reports state, consumers act on it.

2. **flush_pending() after SWIPE_WINDOW removal**
   - What we know: flush_pending() currently fires pending gesture in SWIPE_WINDOW. SWIPE_WINDOW is being removed.
   - Recommendation: Keep flush_pending() as a method but simplify to always return empty OrchestratorResult. It is called by pipeline.py before config reload -- keeping it as a no-op maintains the interface contract while pipeline wiring (Phase 23) can remove the call later.

3. **OrchestratorSignal tuple unpacking compatibility**
   - What we know: Adding second_gesture as 4th field. Existing code uses 3-field unpacking in tests.
   - Recommendation: Since second_gesture defaults to None, attribute access (sig.action, sig.gesture) works fine. Update any 3-field tuple unpacking to use attribute access or 4-field unpacking. Grep for `action, gesture, direction = ` patterns.

## Sources

### Primary (HIGH confidence)
- `gesture_keys/orchestrator.py` -- current FSM implementation (556 lines), all swipe touchpoints identified
- `gesture_keys/trigger.py` -- Direction enum and SequenceTrigger dataclass
- `gesture_keys/motion.py` -- MotionState frozen dataclass
- `tests/test_orchestrator.py` -- 94 existing tests, swipe test classes identified
- `gesture_keys/config.py` -- DerivedConfig pattern for constructor params

### Secondary (MEDIUM confidence)
- `21-CONTEXT.md` -- User decisions and code context from discussion phase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- pure Python refactoring, no new dependencies
- Architecture: HIGH -- existing codebase fully inspected, all swipe touchpoints mapped
- Pitfalls: HIGH -- identified from actual code inspection, not speculation

**Research date:** 2026-03-26
**Valid until:** 2026-04-26 (stable -- internal refactoring, no external dependencies)
