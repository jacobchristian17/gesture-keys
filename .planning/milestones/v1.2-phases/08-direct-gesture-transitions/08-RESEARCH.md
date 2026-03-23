# Phase 8: Direct Gesture Transitions - Research

**Researched:** 2026-03-22
**Domain:** Debounce state machine modification, OpenCV preview overlay
**Confidence:** HIGH

## Summary

Phase 8 is a focused state machine modification. The core change is adding a COOLDOWN->ACTIVATING transition path in `GestureDebouncer` when a *different* gesture appears during cooldown. The current debouncer blocks ALL gestures during cooldown (lines 127-134 of `debounce.py`), requiring the user to release to None before re-arming. The change is ~15-20 lines in `debounce.py`, with corresponding updates to pass debounce state to the preview overlay, and identical changes in both `__main__.py` and `tray.py` detection loops.

The existing activation delay (0.4s) and smoother majority-vote (window=3) already provide sufficient transitional pose filtering. No new libraries, no architectural changes, no new dependencies. This is purely internal state machine logic plus a UI indicator.

**Primary recommendation:** Modify `_handle_cooldown` to track the fired gesture and allow COOLDOWN->ACTIVATING for different gestures. Add debounce state text to the preview bar. Test exhaustively with the existing pytest suite.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Cooldown is interruptible by a DIFFERENT gesture: when a new gesture appears during COOLDOWN, immediately transition to ACTIVATING for that gesture (COOLDOWN->ACTIVATING)
- Activation timer runs concurrently with remaining cooldown -- no need to wait for cooldown to finish before starting the new gesture's activation delay
- Same gesture held through cooldown stays blocked -- must release to None before same gesture can re-arm (preserves TRANS-02, matches current behavior)
- Keep current 0.4s activation delay -- defer default tuning to Phase 10
- Rely on existing activation delay (0.4s) + smoother majority-vote (window=3) as primary protection against transitional poses firing spuriously
- No special transition logic, smoother reset, or lockout window needed -- transitional poses last ~100-200ms, well under the 0.4s activation threshold
- When activating gesture changes (e.g., POINTING->PEACE during ACTIVATING), reset activation timer fully -- new gesture must be held for full activation_delay from scratch (already the current debouncer behavior at debounce.py lines 105-108)
- No special handling for confusable gesture pairs (PEACE<->POINTING, FIST<->THUMBS_UP) -- trust priority-ordered classifier + smoother + activation delay

### Claude's Discretion
- Debounce state preview (TRANS-03): placement, styling, color-coding, and format of IDLE/ACTIVATING/COOLDOWN indicator in preview overlay
- Internal state tracking for the new COOLDOWN->ACTIVATING transition (e.g., whether to track the fired gesture in cooldown for same-gesture blocking)
- Any additional logging for transition events

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TRANS-01 | User can switch directly from one static gesture to another and the new gesture fires without needing to return hand to neutral/"none" first | Modify `_handle_cooldown` to detect different gesture and transition to ACTIVATING; track `_cooldown_gesture` to distinguish same vs different |
| TRANS-02 | Holding the same gesture through cooldown does NOT re-fire -- only a different gesture triggers direct transition | `_cooldown_gesture` tracking ensures same gesture stays blocked; existing test `test_cooldown_stays_if_gesture_held_after_elapsed` validates this |
| TRANS-03 | Preview window displays current debounce state (IDLE/ACTIVATING/COOLDOWN) so user can see why a gesture hasn't fired yet | Add state text to `render_preview` bottom bar; pass `debouncer.state` from both detection loops |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.13 | Runtime | Project standard |
| pytest | 9.0.2 | Test framework | Already in use, test_debounce.py exists |
| OpenCV (cv2) | existing | Preview rendering | Already used in preview.py |

### Supporting
No new libraries needed. All changes use existing project dependencies.

## Architecture Patterns

### Current Debounce State Machine
```
IDLE -> ACTIVATING -> FIRED -> COOLDOWN -> IDLE (current, requires None release)
```

### New State Machine (Phase 8)
```
IDLE -> ACTIVATING -> FIRED -> COOLDOWN -> IDLE (same gesture held, then released)
                                COOLDOWN -> ACTIVATING (DIFFERENT gesture detected)
```

### Modified File Structure
```
gesture_keys/
  debounce.py          # Core change: _handle_cooldown + _cooldown_gesture tracking
  preview.py           # Add debounce state indicator to render_preview
  __main__.py          # Pass debouncer.state to render_preview
  tray.py              # No preview in tray mode, but detection loop parity
tests/
  test_debounce.py     # New tests for COOLDOWN->ACTIVATING transitions
```

### Pattern 1: Cooldown Gesture Tracking
**What:** Track which gesture caused the fire, so cooldown can distinguish "same gesture still held" from "different gesture appeared"
**When to use:** During COOLDOWN state handling
**Implementation approach:**

The debouncer needs a new instance variable `_cooldown_gesture: Optional[Gesture]` set in `_handle_fired` to remember which gesture triggered the fire. In `_handle_cooldown`:
- If `gesture` is not None AND `gesture != self._cooldown_gesture`: transition to ACTIVATING for the new gesture
- If `gesture == self._cooldown_gesture` or `gesture is None`: keep existing behavior (block same gesture, allow IDLE transition on None after cooldown elapsed)

```python
# In _handle_fired (line 118-125):
def _handle_fired(self, gesture, timestamp):
    self._state = DebounceState.COOLDOWN
    self._cooldown_start = timestamp
    self._cooldown_gesture = self._activating_gesture  # NEW: track fired gesture
    self._activating_gesture = None
    logger.debug("FIRED -> COOLDOWN")
    return None

# In _handle_cooldown (line 127-134), replace entirely:
def _handle_cooldown(self, gesture, timestamp):
    cooldown_elapsed = timestamp - self._cooldown_start >= self._cooldown_duration

    # Different gesture during cooldown -> start activating immediately (TRANS-01)
    if gesture is not None and gesture != self._cooldown_gesture:
        self._state = DebounceState.ACTIVATING
        self._activating_gesture = gesture
        self._activation_start = timestamp
        self._cooldown_gesture = None
        logger.debug("COOLDOWN -> ACTIVATING: %s (direct transition)", gesture.value)
        return None

    # Cooldown elapsed + hand released -> return to idle
    if cooldown_elapsed and gesture is None:
        self._state = DebounceState.IDLE
        self._cooldown_gesture = None
        logger.debug("COOLDOWN -> IDLE: released")

    return None
```

### Pattern 2: Preview State Indicator
**What:** Display debounce state text in the preview bottom bar
**When to use:** Always in preview mode
**Implementation approach:**

Extend `render_preview` signature to accept an optional `debounce_state` string parameter. Display it between the gesture label and FPS counter, color-coded:
- IDLE: gray (dim, not distracting)
- ACTIVATING: yellow (something is happening)
- COOLDOWN: red/orange (blocked)
- FIRED: green flash (momentary, since FIRED->COOLDOWN is immediate)

```python
# In preview.py render_preview:
def render_preview(frame, gesture_name, fps, debounce_state=None):
    # ... existing bar code ...

    # Debounce state indicator (center of bar)
    if debounce_state:
        state_colors = {
            "IDLE": (128, 128, 128),      # Gray
            "ACTIVATING": (0, 255, 255),   # Yellow (BGR)
            "COOLDOWN": (0, 128, 255),     # Orange (BGR)
            "FIRED": (0, 255, 0),          # Green (BGR)
        }
        color = state_colors.get(debounce_state, (255, 255, 255))
        state_text = debounce_state
        text_size = cv2.getTextSize(state_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
        x = (w - text_size[0]) // 2
        cv2.putText(bar, state_text, (x, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
```

### Pattern 3: Detection Loop Updates (Both Files)
**What:** Pass `debouncer.state.value` to `render_preview` in `__main__.py`
**When to use:** Preview rendering section of `run_preview_mode`

In `__main__.py` line 291, update the render_preview call:
```python
render_preview(frame, gesture_label, fps, debounce_state=debouncer.state.value)
```

In `tray.py`: No preview rendering, so no change needed for the state indicator. The debounce logic change in `debounce.py` applies automatically since tray.py uses the same `GestureDebouncer` class.

### Anti-Patterns to Avoid
- **Resetting smoother on transition:** The smoother buffer should NOT be cleared when cooldown is interrupted. The smoother operates independently -- clearing it would cause a gap in gesture detection.
- **Adding transition-specific timers:** No lockout windows, no special transition delays. The 0.4s activation delay is sufficient protection against transitional poses.
- **Modifying tray.py detection logic separately:** The debounce change is in `debounce.py` itself, so both loops benefit automatically. Only `__main__.py` needs a render_preview call update.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Transitional pose filtering | Custom lockout/blacklist logic | Existing 0.4s activation_delay + smoother window=3 | Transitional poses last ~100-200ms, well under threshold |
| State machine complexity | Multiple boolean flags | Single `_cooldown_gesture` field in existing state machine | Enum-based state machine already handles all transitions cleanly |

## Common Pitfalls

### Pitfall 1: Forgetting to Clear _cooldown_gesture
**What goes wrong:** If `_cooldown_gesture` is not cleared when transitioning out of COOLDOWN, it persists and could affect future state transitions.
**Why it happens:** Multiple exit paths from COOLDOWN (to IDLE, to ACTIVATING).
**How to avoid:** Clear `_cooldown_gesture = None` in every transition out of COOLDOWN state, and in `reset()`.
**Warning signs:** Tests pass individually but fail when run in sequence.

### Pitfall 2: FIRED State Duration
**What goes wrong:** The FIRED state is transient -- `_handle_fired` immediately transitions to COOLDOWN on the very next `update()` call. The `_cooldown_gesture` must be set in `_handle_fired`, not in the firing frame's `_handle_activating`.
**Why it happens:** FIRED -> COOLDOWN happens in one frame, so `_activating_gesture` is still set when `_handle_fired` runs.
**How to avoid:** Save `self._cooldown_gesture = self._activating_gesture` in `_handle_fired` before clearing `_activating_gesture`.
**Warning signs:** `_cooldown_gesture` is None during cooldown.

### Pitfall 3: render_preview Signature Change Breaking Tray Tests
**What goes wrong:** Adding a parameter to `render_preview` could break any existing calls that use positional args.
**Why it happens:** Other code or tests calling render_preview without the new parameter.
**How to avoid:** Use keyword argument with default `None` so existing calls work unchanged.
**Warning signs:** Import/call errors in test suite.

### Pitfall 4: Both Detection Loops Must Stay in Sync
**What goes wrong:** `__main__.py` and `tray.py` have duplicated pipeline code. Changes to one without the other creates behavior divergence.
**Why it happens:** No shared detection loop abstraction.
**How to avoid:** For Phase 8, the debounce logic change is in `debounce.py` itself (automatic for both). Only the `render_preview` call in `__main__.py` needs updating. Verify tray.py does not need a parallel change.
**Warning signs:** Different behavior in preview vs tray mode.

## Code Examples

### Current _handle_cooldown (to be replaced)
```python
# Source: gesture_keys/debounce.py lines 127-134
def _handle_cooldown(self, gesture, timestamp):
    if timestamp - self._cooldown_start >= self._cooldown_duration:
        if gesture is None:
            self._state = DebounceState.IDLE
            logger.debug("COOLDOWN -> IDLE: released")
    return None
```

### Current _handle_fired (to be modified)
```python
# Source: gesture_keys/debounce.py lines 118-125
def _handle_fired(self, gesture, timestamp):
    self._state = DebounceState.COOLDOWN
    self._cooldown_start = timestamp
    self._activating_gesture = None
    logger.debug("FIRED -> COOLDOWN")
    return None
```

### Current render_preview Signature
```python
# Source: gesture_keys/preview.py line 78
def render_preview(frame, gesture_name, fps):
```

### Current render_preview Call in __main__.py
```python
# Source: gesture_keys/__main__.py line 291
render_preview(frame, gesture_label, fps)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Cooldown blocks ALL gestures | Cooldown blocks same gesture, allows different | Phase 8 | Direct gesture-to-gesture transitions |
| No debounce state visibility | State shown in preview bar | Phase 8 | User can debug timing issues visually |

## Open Questions

1. **FIRED state in preview display**
   - What we know: FIRED is transient (one frame), so the user will almost never see "FIRED" text
   - What's unclear: Whether to show it at all, or just show IDLE/ACTIVATING/COOLDOWN
   - Recommendation: Include FIRED in the color map for completeness, but it will flash for ~33ms at 30fps. This is actually useful feedback -- a quick green flash confirms the fire happened.

2. **_cooldown_gesture after cooldown-elapsed + different gesture**
   - What we know: If cooldown has elapsed AND a different gesture appears, the current code stays in COOLDOWN (because `gesture is not None`). With the new code, the different-gesture check happens first regardless of elapsed time.
   - What's unclear: Edge case -- should a different gesture after cooldown elapsed go through COOLDOWN->ACTIVATING or COOLDOWN->IDLE->ACTIVATING?
   - Recommendation: COOLDOWN->ACTIVATING directly. The end result is the same (new gesture starts activating), and COOLDOWN->ACTIVATING is simpler. The different-gesture check should be first in `_handle_cooldown`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml (`[tool.pytest.ini_options]`) |
| Quick run command | `python -m pytest tests/test_debounce.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TRANS-01 | Different gesture during cooldown starts activating | unit | `python -m pytest tests/test_debounce.py::TestDirectTransitions -x` | No - Wave 0 |
| TRANS-01 | Different gesture during cooldown eventually fires | unit | `python -m pytest tests/test_debounce.py::TestDirectTransitions -x` | No - Wave 0 |
| TRANS-02 | Same gesture held through cooldown does NOT re-fire | unit | `python -m pytest tests/test_debounce.py::TestDebounceStateTransitions::test_cooldown_stays_if_gesture_held_after_elapsed -x` | Yes |
| TRANS-02 | Same gesture after cooldown elapsed still blocked until None | unit | `python -m pytest tests/test_debounce.py::TestDirectTransitions -x` | No - Wave 0 |
| TRANS-03 | Debounce state accessible via debouncer.state property | unit | `python -m pytest tests/test_debounce.py::TestDebounceStateTransitions::test_starts_in_idle -x` | Yes (property exists) |
| TRANS-03 | render_preview accepts and displays debounce_state | unit | `python -m pytest tests/test_preview_state.py -x` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_debounce.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_debounce.py::TestDirectTransitions` -- new test class covering TRANS-01 and TRANS-02 edge cases (different gesture during cooldown fires, same gesture stays blocked, transitional pose sequence doesn't spuriously fire, rapid gesture switching)
- [ ] Verify `render_preview` accepts optional `debounce_state` kwarg without breaking existing tests

*(Existing test infrastructure covers basic debounce state machine. New tests needed for the COOLDOWN->ACTIVATING path and same-gesture-blocking during cooldown.)*

## Sources

### Primary (HIGH confidence)
- `gesture_keys/debounce.py` - Full source read, state machine lines 64-134
- `gesture_keys/preview.py` - Full source read, render_preview signature and bar layout
- `gesture_keys/__main__.py` - Full source read, detection loop and render_preview call
- `gesture_keys/tray.py` - Full source read, parallel detection loop
- `tests/test_debounce.py` - Full source read, existing test coverage
- `gesture_keys/smoother.py` - Full source read, majority-vote buffer

### Secondary (MEDIUM confidence)
- `.planning/phases/08-direct-gesture-transitions/08-CONTEXT.md` - User decisions and code context
- `.planning/REQUIREMENTS.md` - TRANS-01, TRANS-02, TRANS-03 definitions
- `.planning/STATE.md` - Project history, known blockers

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new dependencies, all changes in existing Python modules
- Architecture: HIGH - State machine modification is well-understood, code is read in full
- Pitfalls: HIGH - All edge cases identified from reading actual source code

**Research date:** 2026-03-22
**Valid until:** 2026-04-22 (stable -- no external dependency changes)
