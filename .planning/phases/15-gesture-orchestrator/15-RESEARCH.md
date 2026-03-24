# Phase 15: Gesture Orchestrator - Research

**Researched:** 2026-03-25
**Domain:** Hierarchical finite state machine for gesture lifecycle management
**Confidence:** HIGH

## Summary

Phase 15 replaces the flat `GestureDebouncer` (338 lines, 6 states) and ~200 lines of scattered coordination logic in `Pipeline.process_frame()` with a single `GestureOrchestrator` that uses a hierarchical FSM: an outer lifecycle FSM (IDLE, ACTIVATING, SWIPE_WINDOW, ACTIVE, COOLDOWN) containing an inner temporal FSM (CONFIRMED, HOLD, SWIPING) that only exists in the ACTIVE state.

The existing `GestureDebouncer` in `debounce.py` is the reference implementation for all edge-case behaviors. It has 338 lines, handles 6 flat states (IDLE, ACTIVATING, SWIPE_WINDOW, FIRED, COOLDOWN, HOLDING), and emits `DebounceSignal` NamedTuples with actions (FIRE, HOLD_START, HOLD_END, COMPOUND_FIRE). The orchestrator must reproduce identical timing/signal behavior while restructuring the state hierarchy and absorbing the coordination logic currently spread across `Pipeline.process_frame()` (lines 265-465, ~200 lines of swiping transitions, pre-swipe suppression, compound swipe suppression, and hold repeat management).

**Primary recommendation:** Build the orchestrator as a single `orchestrator.py` module with `GestureOrchestrator` class, `OrchestratorResult` dataclass, `OrchestratorSignal` NamedTuple, `LifecycleState` enum, and `TemporalState` enum. Port tests from `test_debounce.py` (675 lines, 50+ tests) to validate identical behavior, then add new tests for the hierarchical structure.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Hierarchical FSM: outer lifecycle FSM + inner temporal FSM
- Outer FSM states: IDLE -> ACTIVATING -> SWIPE_WINDOW -> ACTIVE -> COOLDOWN
  - SWIPE_WINDOW only entered for gestures with mapped swipe directions
  - SWIPE_WINDOW outcomes: swipe detected -> ACTIVE(inner=SWIPING), window expired + gesture held -> ACTIVE(inner=CONFIRMED), gesture lost -> IDLE
- Inner FSM states (only exists in ACTIVE): CONFIRMED -> HOLD, CONFIRMED -> SWIPING
- Inner FSM owns its own timing (hold threshold tracking, hold_start_time)
- ACTIVATING is a distinct outer state, not part of ACTIVE
- Orchestrator absorbs all gesture logic: debounce timing, swipe exit resets, pre-swipe suppression, compound swipe suppression, static-first priority gate
- Pipeline still runs classifier -> smoother and swipe_detector.update(), then passes smoothed gesture + swipe direction to orchestrator.update()
- Orchestrator handles swiping transitions internally (receives swiping flag each frame, detects entry/exit)
- Hold repeat logic stays in Pipeline (keystroke timing, not gesture state)
- Pipeline.process_frame() reduces to: camera read -> detect -> hand switch/distance checks -> orchestrator.update() -> config reload -> return FrameResult (~30 lines)
- orchestrator.update() returns OrchestratorResult dataclass with: base_gesture, temporal_state, outer_state, signals list, suppress_standalone_swipe
- Signals use same actions as current DebounceAction: FIRE, HOLD_START, HOLD_END, COMPOUND_FIRE
- OrchestratorSignal is a NamedTuple with action, gesture, direction
- Orchestrator exposes is_activating property for Pipeline to suppress swipe arming
- FrameResult gets new orchestrator field (OrchestratorResult | None), existing flat fields kept for backward compatibility
- All 10 v1.3 edge cases enumerated and each gets dedicated test coverage
- Old GestureDebouncer (debounce.py) deleted after orchestrator passes all tests

### Claude's Discretion
- Internal data structures and helper methods within the orchestrator
- Exact file organization (single orchestrator.py or split into outer/inner modules)
- Test organization and helper utilities
- How OrchestratorResult fields map to FrameResult during transition period

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ORCH-01 | Unified gesture orchestrator replacing debouncer + main-loop coordination as single state machine | Hierarchical FSM design with outer lifecycle + inner temporal states; absorbs all coordination from Pipeline.process_frame() |
| ORCH-02 | Static gesture as base layer in gesture hierarchy | Static gestures are the base_gesture in OrchestratorResult; ACTIVATING state confirms them before any temporal modifier applies |
| ORCH-03 | Hold temporal state -- sustained static gesture detected over consecutive frames | Inner FSM CONFIRMED -> HOLD transition with configurable threshold; hold_release_delay grace period preserved from existing debouncer |
| ORCH-04 | Swiping temporal state -- directional movement modifier on current static gesture | Inner FSM CONFIRMED -> SWIPING via SWIPE_WINDOW detection; orchestrator receives swiping flag and handles entry/exit internally |
| ORCH-05 | Gesture type prioritization and state transitions managed by orchestrator | Static-first priority gate (is_activating suppresses swipe arming), direct gesture transitions (COOLDOWN + different gesture -> ACTIVATING), per-gesture cooldowns, compound swipe suppression |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `enum` | 3.x | LifecycleState, TemporalState enums | Consistent with existing Gesture, DebounceState, SwipeDirection enums |
| Python stdlib `dataclasses` | 3.x | OrchestratorResult dataclass | Consistent with existing FrameResult pattern |
| Python stdlib `typing.NamedTuple` | 3.x | OrchestratorSignal | Consistent with existing DebounceSignal pattern |
| Python stdlib `logging` | 3.x | State transition logging | Consistent with existing logger pattern |
| pytest | existing | Test framework | Already configured in pyproject.toml |

### Supporting
No additional libraries needed. This is pure Python state machine logic using only stdlib.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled FSM | `python-statemachine` library | Adds dependency for simple FSM; existing codebase uses hand-rolled pattern successfully |
| Single file | Split outer/inner modules | Single file preferred -- orchestrator is ~400-500 lines, manageable in one module |

## Architecture Patterns

### Recommended Project Structure
```
gesture_keys/
    orchestrator.py       # NEW: GestureOrchestrator, OrchestratorResult, OrchestratorSignal, LifecycleState, TemporalState
    pipeline.py           # MODIFIED: imports orchestrator, simplifies process_frame()
    debounce.py           # DELETED after orchestrator passes all tests
tests/
    test_orchestrator.py  # NEW: ported + expanded tests
    test_debounce.py      # DELETED with debounce.py
    test_pipeline.py      # MODIFIED: updated for orchestrator integration
```

### Pattern 1: Hierarchical FSM with Handler Methods
**What:** Outer FSM dispatches to state-specific handler methods (same pattern as existing GestureDebouncer). Inner FSM is a sub-dispatch within the ACTIVE handler.
**When to use:** Always -- this is the locked decision.
**Example:**
```python
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple, Optional

from gesture_keys.classifier import Gesture
from gesture_keys.swipe import SwipeDirection

logger = logging.getLogger("gesture_keys")


class LifecycleState(Enum):
    """Outer FSM states for gesture lifecycle."""
    IDLE = "IDLE"
    ACTIVATING = "ACTIVATING"
    SWIPE_WINDOW = "SWIPE_WINDOW"
    ACTIVE = "ACTIVE"
    COOLDOWN = "COOLDOWN"


class TemporalState(Enum):
    """Inner FSM states within ACTIVE."""
    CONFIRMED = "CONFIRMED"
    HOLD = "HOLD"
    SWIPING = "SWIPING"


class OrchestratorSignal(NamedTuple):
    """Signal emitted by orchestrator update()."""
    action: str  # reuse DebounceAction values: "fire", "hold_start", "hold_end", "compound_fire"
    gesture: Gesture
    direction: Optional[SwipeDirection] = None


@dataclass
class OrchestratorResult:
    """Per-frame output from the gesture orchestrator."""
    base_gesture: Optional[Gesture] = None
    temporal_state: Optional[TemporalState] = None
    outer_state: LifecycleState = LifecycleState.IDLE
    signals: list[OrchestratorSignal] = field(default_factory=list)
    suppress_standalone_swipe: bool = False
```

### Pattern 2: Update Method Signature
**What:** The orchestrator.update() receives smoothed gesture, timestamp, swipe_direction, and swiping flag. It manages entry/exit transitions internally.
**When to use:** Every frame from Pipeline.process_frame().
**Example:**
```python
def update(
    self,
    gesture: Optional[Gesture],
    timestamp: float,
    *,
    swipe_direction: Optional[SwipeDirection] = None,
    swiping: bool = False,
) -> OrchestratorResult:
    """Process one frame of gesture input.

    Args:
        gesture: Smoothed gesture from classifier+smoother, or None.
        timestamp: Current time (perf_counter).
        swipe_direction: Swipe direction detected this frame (from SwipeDetector).
        swiping: Whether SwipeDetector.is_swiping is True this frame.

    Returns:
        OrchestratorResult with current state and any signals to act on.
    """
```

### Pattern 3: Absorbed Coordination Logic
**What:** The orchestrator handles swiping entry/exit, pre-swipe suppression, and compound swipe suppression internally rather than Pipeline doing it.
**When to use:** Replace the ~100 lines of swiping coordination in Pipeline.process_frame() (lines 336-357 and 396-437).
**Key behavior to absorb:**
```python
# Currently in Pipeline.process_frame() -- must move INTO orchestrator:
# 1. Swiping entry: was_swiping=False, swiping=True -> reset internal state
# 2. Swiping exit: was_swiping=True, swiping=False -> suppress pre-swipe gesture re-fire
# 3. Pre-swipe gesture suppression (lines 348-356): set COOLDOWN on swipe exit
# 4. Compound swipe suppression timing (lines 436-441): track suppress_until
```

### Anti-Patterns to Avoid
- **Reaching into private state:** Current Pipeline code injects `_state`, `_cooldown_gesture`, `_cooldown_start` directly on the debouncer (line 349-351). The orchestrator must handle pre-swipe suppression via a proper method, not private state injection.
- **FIRED as a transient state:** The existing debouncer has FIRED as a state that transitions to COOLDOWN on the next frame (always 1-frame). The orchestrator replaces this with ACTIVE(CONFIRMED) which can persist and transition to HOLD or SWIPING.
- **Leaking inner state:** Inner temporal FSM should not exist outside ACTIVE. If outer state is not ACTIVE, temporal_state in OrchestratorResult should be None.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Signal action values | New action enum | Reuse DebounceAction enum values | Downstream consumers (keystroke sender) already handle these string values |
| Config parameter passing | Custom config object | Same constructor params as GestureDebouncer | Identical config surface area; Pipeline already builds these params |

**Key insight:** The orchestrator is a restructuring of existing logic, not new functionality. Every behavior already exists in debounce.py + pipeline.py. The value is in consolidation, not invention.

## Common Pitfalls

### Pitfall 1: SWIPE_WINDOW Fire-Before-Reset on Config Reload
**What goes wrong:** Config reload during SWIPE_WINDOW must fire the pending static gesture before resetting, or the gesture is silently lost.
**Why it happens:** The current `reload_config()` in Pipeline (lines 499-506) handles this explicitly by checking `in_swipe_window` before resetting.
**How to avoid:** Orchestrator needs a `flush_pending()` method that Pipeline calls before `reset()` during config reload. The flush method fires the pending gesture if in SWIPE_WINDOW with a valid activating gesture.
**Warning signs:** Config reload test passes without checking that the pending gesture fires.

### Pitfall 2: Pre-Swipe Gesture Suppression via Private State
**What goes wrong:** Current code (Pipeline lines 348-356) directly injects private state into the debouncer to prevent the pre-swipe gesture from re-firing after a swipe ends.
**Why it happens:** The flat debouncer API didn't have a clean way to express "suppress this specific gesture."
**How to avoid:** The orchestrator handles this internally. When swiping exits (was_swiping=True, swiping=False), the orchestrator transitions to COOLDOWN with the pre-swipe gesture as the cooldown gesture. No private state injection needed.
**Warning signs:** Pipeline still reaches into orchestrator private attributes after refactor.

### Pitfall 3: Hold Release Delay Timer Interaction with State Transitions
**What goes wrong:** The hold release delay timer must be canceled on gesture change but preserved on gesture flicker (None frames during hold).
**Why it happens:** Inner FSM HOLD state tracks `_release_delay_start`. If a different gesture appears during the delay, it must emit HOLD_END and transition. If None appears and returns within the delay, it must stay in HOLD.
**How to avoid:** Exact same logic as current `_handle_holding()` (lines 293-337 of debounce.py). Port directly.
**Warning signs:** Hold release delay test cases fail (test_hold_mode_release_delay_absorbs_flicker, test_multiple_rapid_drops_within_delay).

### Pitfall 4: Compound Swipe Suppression Timing
**What goes wrong:** After a SWIPE_WINDOW is entered, standalone swipes must be suppressed for the window duration + buffer. Without this, a standalone swipe fires simultaneously with a compound gesture attempt.
**Why it happens:** The suppress_until timestamp (currently tracked in Pipeline._compound_swipe_suppress_until) must be set whenever entering or being in SWIPE_WINDOW.
**How to avoid:** Orchestrator tracks suppress_until internally and exposes it via `OrchestratorResult.suppress_standalone_swipe` boolean. Pipeline uses this flag to gate standalone swipe keystroke sending.
**Warning signs:** Standalone swipe fires during a compound gesture window.

### Pitfall 5: Backward Compatibility During Transition
**What goes wrong:** FrameResult.debounce_state is used by preview.py and tests. Removing it breaks the preview overlay.
**Why it happens:** The preview overlay reads `debounce_state` to display state info.
**How to avoid:** Keep existing flat fields on FrameResult for backward compatibility. Add the new `orchestrator` field (OrchestratorResult | None). Map outer_state to debounce_state for backward compatibility (ACTIVE maps to FIRED or HOLDING based on temporal_state).
**Warning signs:** Preview overlay crashes or shows stale state info.

### Pitfall 6: Direct Gesture Transitions from COOLDOWN
**What goes wrong:** During COOLDOWN, a DIFFERENT gesture must immediately transition to ACTIVATING (or SWIPE_WINDOW if it has swipe mappings), bypassing IDLE. The SAME gesture must stay blocked.
**Why it happens:** This is the "fluid gesture-to-gesture transitions" behavior. Without it, users must release their hand to None between gestures.
**How to avoid:** Port the exact logic from `_handle_cooldown()` (lines 261-291). Test with `TestDirectTransitions` class assertions.
**Warning signs:** Direct transition tests fail, or same-gesture re-fire occurs during cooldown.

## Code Examples

### Existing Edge-Case Reference: Pre-Swipe Suppression (Current Pipeline Code)
```python
# Pipeline.process_frame() lines 348-356 -- THIS MUST MOVE INTO ORCHESTRATOR
if self._was_swiping and not swiping:
    self._hold_active = False
    self._sender.release_all()
    self._smoother.reset()
    self._debouncer.reset()
    # Suppress the pre-swipe gesture from re-firing after swipe
    if self._pre_swipe_gesture is not None:
        self._debouncer._state = DebounceState.COOLDOWN
        self._debouncer._cooldown_gesture = self._pre_swipe_gesture
        self._debouncer._cooldown_start = current_time
    self._pre_swipe_gesture = None
```

### Existing Edge-Case Reference: Compound Swipe Suppression (Current Pipeline Code)
```python
# Pipeline.process_frame() lines 436-441 -- THIS MOVES INTO ORCHESTRATOR
if self._debouncer.in_swipe_window or was_in_swipe_window:
    self._compound_swipe_suppress_until = current_time + self._config.swipe_window

compound_suppress = current_time < self._compound_swipe_suppress_until
if swipe_result is not None and not compound_suppress:
    # fire standalone swipe
```

### Existing Edge-Case Reference: Static-First Priority Gate (Current Pipeline Code)
```python
# Pipeline.process_frame() lines 376-380 -- STILL IN PIPELINE (uses orchestrator.is_activating)
suppress_swipe = self._debouncer.is_activating
swipe_result = self._swipe_detector.update(
    landmarks or None, current_time,
    suppressed=suppress_swipe,
)
```

### Orchestrator State Mapping to Backward-Compatible DebounceState
```python
# Map orchestrator states to legacy DebounceState for FrameResult backward compatibility
def _map_to_debounce_state(result: OrchestratorResult) -> DebounceState:
    if result.outer_state == LifecycleState.IDLE:
        return DebounceState.IDLE
    elif result.outer_state == LifecycleState.ACTIVATING:
        return DebounceState.ACTIVATING
    elif result.outer_state == LifecycleState.SWIPE_WINDOW:
        return DebounceState.SWIPE_WINDOW
    elif result.outer_state == LifecycleState.ACTIVE:
        if result.temporal_state == TemporalState.HOLD:
            return DebounceState.HOLDING
        return DebounceState.FIRED  # CONFIRMED or SWIPING maps to FIRED
    elif result.outer_state == LifecycleState.COOLDOWN:
        return DebounceState.COOLDOWN
    return DebounceState.IDLE
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Flat 6-state debouncer + Pipeline coordination (~540 lines combined) | Hierarchical FSM orchestrator (~400-500 lines) | Phase 15 | Single source of truth for all gesture state transitions |
| Private state injection for pre-swipe suppression | Proper orchestrator method | Phase 15 | No more reaching into `_state`, `_cooldown_gesture`, `_cooldown_start` |
| FIRED as 1-frame transient state | ACTIVE with inner CONFIRMED state | Phase 15 | CONFIRMED can persist and transition to HOLD or SWIPING |

**Deprecated/outdated after this phase:**
- `GestureDebouncer` class (debounce.py) -- replaced entirely by GestureOrchestrator
- `DebounceState` enum -- replaced by LifecycleState + TemporalState (but kept for backward compat in FrameResult)
- Pipeline swiping coordination logic (~100 lines) -- absorbed into orchestrator

## Open Questions

1. **Should DebounceAction enum be renamed or duplicated?**
   - What we know: Signals use same action values (FIRE, HOLD_START, HOLD_END, COMPOUND_FIRE)
   - What's unclear: Whether to reuse the DebounceAction enum from debounce.py (which will be deleted) or create a new enum
   - Recommendation: Create a new `OrchestratorAction` enum in orchestrator.py with identical values. This avoids import dependency on soon-to-be-deleted debounce.py. During transition, both can coexist.

2. **Exact ACTIVE state entry point**
   - What we know: ACTIVATING -> ACTIVE(CONFIRMED) when activation_delay elapses. SWIPE_WINDOW -> ACTIVE(CONFIRMED) when window expires with gesture held. SWIPE_WINDOW -> ACTIVE(SWIPING) when mapped swipe detected.
   - What's unclear: Whether the FIRE signal should emit on entry to ACTIVE(CONFIRMED) or as a separate step
   - Recommendation: Emit FIRE signal on entry to ACTIVE(CONFIRMED) from ACTIVATING. Emit COMPOUND_FIRE on entry to ACTIVE(SWIPING). This preserves the existing signal timing.

3. **ACTIVE -> COOLDOWN transition timing**
   - What we know: Current FIRED state is always 1-frame (immediately transitions to COOLDOWN on next update). ACTIVE(CONFIRMED) for tap-mode gestures should behave the same.
   - What's unclear: Whether ACTIVE(CONFIRMED) should auto-transition to COOLDOWN on the next frame for tap-mode gestures
   - Recommendation: Yes, maintain identical 1-frame behavior. For tap-mode: ACTIVE(CONFIRMED) emits FIRE and transitions to COOLDOWN on the same frame or next update. For hold-mode: ACTIVE(CONFIRMED) emits HOLD_START and transitions to ACTIVE(HOLD).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (configured in pyproject.toml) |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `pytest tests/test_orchestrator.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ORCH-01 | Unified orchestrator replaces debouncer + coordination | unit | `pytest tests/test_orchestrator.py -x -k "TestOrchestratorStateTransitions"` | No -- Wave 0 |
| ORCH-01 | Pipeline uses orchestrator instead of debouncer | integration | `pytest tests/test_pipeline.py -x` | Yes (needs update) |
| ORCH-02 | Static gesture as base layer | unit | `pytest tests/test_orchestrator.py -x -k "test_base_gesture"` | No -- Wave 0 |
| ORCH-03 | Hold temporal state | unit | `pytest tests/test_orchestrator.py -x -k "TestHoldMode"` | No -- Wave 0 |
| ORCH-04 | Swiping temporal state | unit | `pytest tests/test_orchestrator.py -x -k "TestSwipeWindow"` | No -- Wave 0 |
| ORCH-05 | Prioritization and transitions | unit | `pytest tests/test_orchestrator.py -x -k "TestDirectTransitions or TestEdgeCases"` | No -- Wave 0 |
| ORCH-05 | All 10 v1.3 edge cases | unit | `pytest tests/test_orchestrator.py -x -k "TestEdgeCases"` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_orchestrator.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_orchestrator.py` -- all orchestrator unit tests (ported from test_debounce.py + new hierarchical tests)
- [ ] No framework install needed -- pytest already configured
- [ ] No shared fixtures needed beyond existing conftest.py

## Sources

### Primary (HIGH confidence)
- `gesture_keys/debounce.py` (338 lines) -- complete reference implementation for all edge cases
- `gesture_keys/pipeline.py` (564 lines) -- coordination logic to absorb, integration points
- `tests/test_debounce.py` (675 lines) -- 50+ tests defining expected behavior
- `tests/test_compound_gesture.py` -- compound swipe test cases
- `tests/test_integration_mutual_exclusion.py` -- swipe/static mutual exclusion tests
- `15-CONTEXT.md` -- locked decisions from discussion phase

### Secondary (MEDIUM confidence)
- State machine patterns from Python stdlib enum + dataclasses -- well-established pattern in this codebase

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- pure Python stdlib, no new dependencies, proven patterns in codebase
- Architecture: HIGH -- hierarchical FSM design locked in CONTEXT.md, all edge cases documented in existing code
- Pitfalls: HIGH -- all pitfalls derived from direct code analysis of existing implementations

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable domain, no external dependencies)
