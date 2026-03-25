# Phase 17: Activation Gate - Research

**Researched:** 2026-03-25
**Domain:** Gesture activation gating, state machine integration, config schema extension
**Confidence:** HIGH

## Summary

Phase 17 integrates the existing `ActivationGate` class (already implemented in `gesture_keys/activation.py`) into the Pipeline's frame processing loop. The gate acts as a filter between the orchestrator's signals and the action dispatcher: when enabled, gestures only fire actions while the gate is armed. The activation gesture (configurable, default scout/peace) arms the gate for a timed window and is consumed (not forwarded to the dispatcher).

The existing `ActivationGate` class already handles arm/tick/expiry/reset logic. The main work is: (1) adding config schema fields for activation gate settings, (2) integrating the gate into `Pipeline.process_frame()` between orchestrator output and dispatcher input, (3) implementing bypass mode (default behavior, preserving v1.x passthrough), (4) ensuring gate expiry releases held keys immediately via `dispatcher.release_all()`, and (5) hot-reload support.

**Primary recommendation:** Insert the activation gate as a signal filter in Pipeline between orchestrator signals and dispatcher. When the gate is enabled and not armed, suppress all signals. When the activation gesture fires, arm the gate instead of dispatching. Bypass mode (default) skips the gate entirely.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ACTV-01 | Activation gate arms/disarms gesture detection via configurable activation gestures (scout/peace default) | ActivationGate class exists with arm/tick/expiry. Needs Pipeline integration and config schema for gesture list + duration. |
| ACTV-02 | Bypass mode disables activation gating (all gestures pass through directly) | New `activation_gate.enabled` config field (default: false). Pipeline skips gate logic when disabled. |
| ACTV-03 | Activation gate integrates with gesture orchestrator (consumed gesture doesn't fire actions) | Pipeline filters orchestrator signals through gate. Activation gesture's FIRE/HOLD_START signals are intercepted and converted to gate arm. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| gesture_keys.activation | existing | ActivationGate class with arm/tick/expiry/reset | Already implemented in codebase |
| gesture_keys.pipeline | existing | Pipeline.process_frame() integration point | Central frame processing loop |
| gesture_keys.config | existing | AppConfig dataclass + load_config() | Config schema extension point |
| gesture_keys.action | existing | ActionDispatcher.release_all() | Key lifecycle safety on gate expiry |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| gesture_keys.orchestrator | existing | OrchestratorSignal signals to filter | Gate intercepts signals before dispatch |
| gesture_keys.classifier | existing | Gesture enum for activation gesture matching | Comparing signal.gesture against gate gestures |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Signal filtering in Pipeline | Gate inside Orchestrator | Orchestrator is already complex; Pipeline is the right integration layer since gate is between orchestrator output and dispatcher input |
| Multiple activation gestures list | Single activation gesture | List is more flexible; config `gestures: [scout, peace]` allows either gesture to arm |

## Architecture Patterns

### Integration Point: Pipeline.process_frame()

The gate sits between orchestrator signal emission and dispatcher consumption:

```
Orchestrator.update() -> signals
    |
    v
ActivationGate filter (NEW)
    |
    v
ActionDispatcher.dispatch()
```

**Current code (pipeline.py lines 354-356):**
```python
# Dispatch all orchestrator signals through ActionDispatcher
for signal in orch_result.signals:
    self._dispatcher.dispatch(signal)
```

**New code pattern:**
```python
# Activation gate: tick timer, filter signals
if self._activation_gate is not None:
    self._activation_gate.tick(current_time)
    # Check for gate expiry -> release held keys
    if was_armed and not self._activation_gate.is_armed():
        self._dispatcher.release_all()
    filtered_signals = self._filter_signals_through_gate(orch_result.signals, current_time)
else:
    filtered_signals = orch_result.signals

for signal in filtered_signals:
    self._dispatcher.dispatch(signal)
```

### Signal Filtering Logic

```python
def _filter_signals_through_gate(self, signals, current_time):
    """Filter orchestrator signals through activation gate.

    - If signal's gesture matches activation gesture(s): arm gate, consume signal
    - If gate is armed: pass signal through
    - If gate is not armed: suppress signal
    """
    filtered = []
    for signal in signals:
        if signal.gesture.value in self._activation_gestures:
            # Activation gesture detected - arm the gate, consume the signal
            if not self._activation_gate.is_armed():
                self._activation_gate.arm(current_time)
            # Re-arm on repeated activation gesture (extends window)
            else:
                self._activation_gate.arm(current_time)
            # Do NOT add to filtered - consumed
            continue
        if self._activation_gate.is_armed():
            filtered.append(signal)
        # else: gate not armed, suppress
    return filtered
```

### Config Schema Extension

New top-level `activation_gate` section in config.yaml:

```yaml
activation_gate:
  enabled: false          # Default: bypass mode (v1.x behavior)
  gestures:               # List of gesture names that arm the gate
    - scout
    - peace
  duration: 3.0           # Seconds the gate stays armed after activation
```

**AppConfig additions:**
```python
@dataclass
class AppConfig:
    # ... existing fields ...
    activation_gate_enabled: bool = False
    activation_gate_gestures: list[str] = field(default_factory=list)
    activation_gate_duration: float = 3.0
```

### Bypass Mode (Default)

When `activation_gate.enabled` is `false` (default), Pipeline does NOT create an ActivationGate instance. `self._activation_gate` remains `None`, and all signals pass through directly. This preserves v1.x behavior with zero overhead.

### Anti-Patterns to Avoid
- **Putting gate logic inside Orchestrator:** The orchestrator manages gesture lifecycle (IDLE->ACTIVATING->ACTIVE->COOLDOWN). The activation gate is an application-level concern (should signals reach the dispatcher?). Keep them separate.
- **Not consuming the activation gesture's HOLD signals:** If scout is mapped as hold_key AND is the activation gesture, HOLD_START must be consumed too, not just FIRE. Check `signal.gesture.value in activation_gestures` for ALL signal types.
- **Forgetting to handle gate expiry during active hold:** If a hold_key gesture is active and the gate expires, the held key must be released immediately. This requires checking gate armed state transition (was_armed -> not_armed) each frame.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Arm/disarm timer logic | New timer class | Existing ActivationGate | Already implemented with arm/tick/reset/is_armed |
| Key release on expiry | Manual key tracking | dispatcher.release_all() | Already handles all held key cleanup |
| Config parsing | Custom YAML parsing | Extend existing load_config() | Consistent with all other config sections |

## Common Pitfalls

### Pitfall 1: Stuck Keys on Gate Expiry
**What goes wrong:** Gate expires while a hold_key action is active. The key stays physically held because no HOLD_END signal is emitted.
**Why it happens:** Gate expiry is a timer event, not a gesture change. The orchestrator never sees a gesture loss, so it never emits HOLD_END.
**How to avoid:** In Pipeline.process_frame(), after `activation_gate.tick()`, detect the armed->disarmed transition and call `self._dispatcher.release_all()`. Also reset the orchestrator to prevent stale HOLD state.
**Warning signs:** Keys stuck after gate timeout.

### Pitfall 2: Activation Gesture Still Fires Its Mapped Action
**What goes wrong:** Scout gesture arms the gate AND fires `win+ctrl+right` (its mapped key).
**Why it happens:** Signal filtering runs after orchestrator emits FIRE for scout. If the filter doesn't intercept, the signal reaches the dispatcher.
**How to avoid:** Filter must check `signal.gesture.value in activation_gestures` for ALL signal types (FIRE, HOLD_START, HOLD_END, COMPOUND_FIRE) and consume them.
**Warning signs:** Activation gesture triggers its mapped keystroke.

### Pitfall 3: Re-arming Doesn't Extend Window
**What goes wrong:** User performs activation gesture again while armed, but the timer continues from the original arm time.
**Why it happens:** `arm()` sets `_armed_at = timestamp`, which correctly resets. But if the gate checks `is_armed()` before `arm()`, the re-arm might be skipped.
**How to avoid:** Always call `arm()` when activation gesture is detected, regardless of current armed state. The existing `arm()` implementation already handles this correctly by overwriting `_armed_at`.

### Pitfall 4: Orchestrator HOLD State Persists After Gate Expiry
**What goes wrong:** Gate expires, held key is released, but orchestrator still thinks it's in ACTIVE(HOLD). Next time gate is armed, orchestrator doesn't re-emit HOLD_START.
**Why it happens:** Pipeline releases the key but doesn't reset orchestrator state.
**How to avoid:** On gate expiry, call both `self._dispatcher.release_all()` AND `self._orchestrator.reset()` to ensure clean state.

### Pitfall 5: Hot-Reload Doesn't Update Gate Settings
**What goes wrong:** User changes activation_gate settings in config.yaml but gate keeps old duration/gestures.
**Why it happens:** `reload_config()` doesn't update activation gate parameters.
**How to avoid:** In `reload_config()`, update or recreate `self._activation_gate` from new config. If gate was disabled and is now enabled (or vice versa), handle the transition.

### Pitfall 6: Activation Gesture Consumed Even When Gate Is Bypassed
**What goes wrong:** Scout gesture stops firing its mapped key even though activation_gate is disabled.
**Why it happens:** Signal filter runs even in bypass mode.
**How to avoid:** When `activation_gate.enabled` is false, `self._activation_gate` is `None`, and the filter is completely skipped. The `if self._activation_gate is not None` guard handles this.

## Code Examples

### Existing ActivationGate API (from activation.py)
```python
# Source: gesture_keys/activation.py (existing code)
gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)

# Each frame:
gate.tick(current_time)          # Check expiry
gate.is_armed()                  # Query state
gate.arm(current_time)           # Arm the gate
gate.reset()                     # Force disarm
```

### Config Loading Extension Pattern
```python
# Source: gesture_keys/config.py load_config() pattern
# Follow existing pattern for new config sections:
activation_gate_raw = raw.get("activation_gate", {})
activation_gate_enabled = bool(activation_gate_raw.get("enabled", False))
activation_gate_gestures = list(activation_gate_raw.get("gestures", []))
activation_gate_duration = float(activation_gate_raw.get("duration", 3.0))
```

### Pipeline Start Pattern for Gate Creation
```python
# In Pipeline.start(), after orchestrator creation:
if self._config.activation_gate_enabled and self._config.activation_gate_gestures:
    # Use first gesture for ActivationGate (gate only needs one;
    # Pipeline signal filter checks the full list)
    self._activation_gate = ActivationGate(
        gesture=Gesture(self._config.activation_gate_gestures[0]),
        duration=self._config.activation_gate_duration,
    )
    self._activation_gestures = set(self._config.activation_gate_gestures)
else:
    self._activation_gate = None
    self._activation_gestures = set()
```

Note: The ActivationGate class stores a single gesture, but since we check `signal.gesture.value in self._activation_gestures` in the Pipeline filter, any gesture in the set can arm the gate. The gate's internal `_gesture` field is informational only (used for logging, not for filtering).

### Gate Expiry with Held Key Release
```python
# In Pipeline.process_frame(), before signal dispatch:
if self._activation_gate is not None:
    was_armed = self._activation_gate.is_armed()
    self._activation_gate.tick(current_time)
    if was_armed and not self._activation_gate.is_armed():
        # Gate just expired - release any held keys and reset orchestrator
        logger.info("Activation gate expired - releasing held keys")
        self._dispatcher.release_all()
        self._orchestrator.reset()
```

### FrameResult Extension for Preview Visibility
```python
# Optional: Add activation state to FrameResult for preview display
@dataclass
class FrameResult:
    # ... existing fields ...
    activation_armed: bool = False  # Whether activation gate is currently armed
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No activation gate (v1.x) | Activation gate with bypass default | Phase 17 (v2.0) | Prevents accidental gesture fires when user isn't actively using system |
| ActivationGate stores single gesture | Pipeline filters against gesture set | Phase 17 design | Multiple gestures can arm the gate |

## Open Questions

1. **Should re-arming reset the orchestrator?**
   - What we know: Re-arming extends the armed window. Orchestrator state should remain intact during re-arm.
   - What's unclear: If user performs activation gesture while in ACTIVE(HOLD) for a non-activation gesture, should the hold continue?
   - Recommendation: Yes, keep hold active. Re-arming only resets the timer, not the gesture state.

2. **Should activation gate state be exposed in FrameResult?**
   - What we know: ENH-05 (future) calls for visual feedback for activation state in preview.
   - What's unclear: Whether to add it now or defer.
   - Recommendation: Add `activation_armed: bool` to FrameResult now (trivial, useful for debugging). Full visual rendering is ENH-05 scope.

3. **ActivationGate constructor takes single Gesture but we need multiple**
   - What we know: The gate's `_gesture` field is used only in the constructor and `gesture` property.
   - What's unclear: Whether to modify ActivationGate to accept a list or keep filtering in Pipeline.
   - Recommendation: Keep ActivationGate simple (single gesture for its internal use). Pipeline owns the set-based filtering. The gate's `gesture` property becomes informational.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | None (pytest defaults, collected from tests/) |
| Quick run command | `python -m pytest tests/test_activation.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ACTV-01 | Activation gesture arms gate for configurable duration; gestures fire only while armed | unit | `python -m pytest tests/test_activation.py -x -q` | No - Wave 0 |
| ACTV-01 | Gate expiry disarms; subsequent gestures suppressed | unit | `python -m pytest tests/test_activation.py -x -q` | No - Wave 0 |
| ACTV-01 | Re-arming extends armed window | unit | `python -m pytest tests/test_activation.py -x -q` | No - Wave 0 |
| ACTV-02 | Bypass mode (enabled=false) passes all gestures through | unit | `python -m pytest tests/test_activation.py -x -q` | No - Wave 0 |
| ACTV-02 | Default config has activation_gate disabled | unit | `python -m pytest tests/test_config.py -x -q` | No - Wave 0 |
| ACTV-03 | Activation gesture consumed (doesn't fire mapped action) | unit | `python -m pytest tests/test_activation.py -x -q` | No - Wave 0 |
| ACTV-03 | Gate expiry releases held keys (no stuck keys) | unit | `python -m pytest tests/test_activation.py -x -q` | No - Wave 0 |
| ACTV-03 | Gate expiry resets orchestrator (clean state) | unit | `python -m pytest tests/test_activation.py -x -q` | No - Wave 0 |
| ACTV-03 | Config hot-reload updates gate settings | unit | `python -m pytest tests/test_activation.py -x -q` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_activation.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_activation.py` -- covers ACTV-01, ACTV-02, ACTV-03 (gate unit tests, pipeline integration tests, config tests)
- [ ] Existing `ActivationGate` class has NO tests currently -- needs baseline tests for arm/tick/expiry

## Sources

### Primary (HIGH confidence)
- `gesture_keys/activation.py` -- Existing ActivationGate implementation (arm, tick, reset, is_armed)
- `gesture_keys/pipeline.py` -- Pipeline.process_frame() integration point (lines 354-356 signal dispatch)
- `gesture_keys/action.py` -- ActionDispatcher.release_all() for key safety
- `gesture_keys/config.py` -- AppConfig dataclass and load_config() pattern
- `gesture_keys/orchestrator.py` -- OrchestratorSignal structure and reset() method
- `.planning/REQUIREMENTS.md` -- ACTV-01, ACTV-02, ACTV-03 requirement definitions

### Secondary (MEDIUM confidence)
- `gesture_keys/classifier.py` -- Gesture enum (SCOUT, PEACE are default activation gestures)
- `config.yaml` -- Current config structure showing scout and peace gestures exist

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All components exist in codebase, integration points identified
- Architecture: HIGH - Clear insertion point in Pipeline, existing ActivationGate API matches needs
- Pitfalls: HIGH - Stuck keys pattern well-understood from Phase 16 (ACTN-04), gate expiry is the novel edge case

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable internal architecture)
