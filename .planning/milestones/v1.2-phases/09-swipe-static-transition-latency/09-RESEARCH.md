# Phase 9: Swipe/Static Transition Latency - Research

**Researched:** 2026-03-22
**Domain:** Gesture pipeline state management -- swipe-to-static transition reset and settling frame tuning
**Confidence:** HIGH

## Summary

Phase 9 addresses a specific latency bug and tuning issue in the swipe-to-static gesture transition path. The core problem is asymmetric reset handling: when a swipe begins (`swiping and not was_swiping`), both the smoother and debouncer are reset (lines 229-231 in `__main__.py`), but when a swipe ends (`was_swiping and not swiping`), NO reset occurs. This means stale swipe-motion frames persist in the smoother buffer, requiring the full smoothing window to refill before static gesture recognition can begin. Combined with the current 10-frame settling guard in `SwipeDetector`, total transition latency is approximately 1.3 seconds.

The fix is straightforward: add symmetric exit resets in both detection loops (`__main__.py` and `tray.py`), reduce `settling_frames` default from 10 to 3, and fix a latent hot-reload bug where config changes reset the debouncer but not the smoother. With these changes, the settling contribution drops from ~330ms to ~100ms, and the smoother/debouncer start clean immediately after swipe exit.

**Primary recommendation:** Fix the missing swipe-exit reset first (LAT-02), then reduce settling frames to 3 (LAT-03). The reset fix is a hard prerequisite -- without it, reducing settling frames would cause false static fires from stale smoother state.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- When `is_swiping` transitions from true to false, explicitly reset both smoother and debouncer so stale swipe-motion frames don't pollute static gesture recognition
- Fix must be added in both `__main__.py` and `tray.py` detection loops (mirror the entry reset pattern)
- LAT-02 must land before LAT-03 (hard ordering prerequisite)
- Reduce settling_frames from 10 to 3
- Hot-reload must also reset smoother (in addition to existing debouncer reset) and clear `_settling_frames_remaining`
- Latency budget: with current 0.4s activation_delay, total will be ~600ms (Phase 10's tuning to ~0.15s will bring it to ~300ms target)

### Claude's Discretion
- Exact placement and ordering of reset calls in the detection loops
- Whether to add a `swipe_exiting` log message for debugging transitions
- Test approach for verifying the latency improvement

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| LAT-01 | Swipe-to-static transition fires within ~300ms of swipe cooldown ending (down from ~1.3s) | Latency budget analysis shows ~600ms achievable with current activation_delay; ~300ms after Phase 10 tuning. Reset fix + settling reduction are the two levers this phase controls. |
| LAT-02 | Smoother and debouncer are properly reset when transitioning from swipe to static mode | Missing exit reset identified at `__main__.py:228-232` and `tray.py:227-232`. Mirror the entry reset pattern with symmetric exit condition. |
| LAT-03 | Settling frames after swipe cooldown reduced from 10 to 3-5 frames | Default in `SwipeDetector.__init__` is `settling_frames=10`. Change to 3. With LAT-02 fix, stale state is flushed so 3 frames is sufficient. |
</phase_requirements>

## Architecture Patterns

### Current Detection Loop Flow (both __main__.py and tray.py)

```
Frame arrives
  -> Distance gating (filter out-of-range hands)
  -> Swipe detection (runs first, needs raw landmarks)
  -> Mutual exclusion check:
       swiping = config.swipe_enabled and swipe_detector.is_swiping
       if swiping and not was_swiping:   # ENTRY -- resets exist
           smoother.reset()
           debouncer.reset()
       was_swiping = swiping             # Track state
       # EXIT RESET IS MISSING HERE     <-- THE BUG
  -> Classify and smooth (suppressed when swiping)
  -> Debounce and fire keystroke (gated during swiping)
  -> Config hot-reload check
```

### Fix Pattern: Symmetric Exit Reset

The fix mirrors the existing entry reset. Insert between the entry check and the `was_swiping = swiping` assignment:

```python
# Existing entry reset
if swiping and not was_swiping:
    smoother.reset()
    debouncer.reset()
# NEW: Exit reset -- flush stale swipe-motion state
if was_swiping and not swiping:
    smoother.reset()
    debouncer.reset()
was_swiping = swiping
```

**Placement rationale:** The exit reset must happen BEFORE `was_swiping = swiping` so the condition triggers correctly. It must also happen BEFORE the classify/smooth block so the smoother starts fresh on the same frame that swiping ends.

### Settling Frame Default Change

In `swipe.py` `SwipeDetector.__init__`:
```python
# Change from:
settling_frames: int = 10,
# To:
settling_frames: int = 3,
```

This is safe because:
1. The LAT-02 reset fix flushes stale smoother/debouncer state on swipe exit
2. 3 frames at ~30fps = ~100ms -- enough for residual hand motion to dampen
3. `settling_frames` is already configurable via the constructor and has a property setter for hot-reload

### Hot-Reload Fix

In both `__main__.py` (line ~258-284) and `tray.py` (line ~251-272), the config reload block resets `debouncer` but NOT `smoother`. Add:

```python
# In the config reload block, after debouncer.reset():
smoother.reset()
smoother._window_size = new_config.smoothing_window
smoother._buffer = deque(maxlen=new_config.smoothing_window)
```

Note: The smoother's `reset()` clears the buffer, but if `smoothing_window` changed, we also need to update the window size. However, `GestureSmoother` currently stores `_window_size` and creates the deque with `maxlen=window_size` in `__init__`. A full reset means clearing the buffer AND updating the window size if it changed.

Also clear settling state:
```python
swipe_detector._settling_frames_remaining = 0
```

### Anti-Patterns to Avoid
- **Resetting only smoother without debouncer (or vice versa):** Both must reset together. The debouncer references activation timing from the smoother's output, so a stale smoother feeding a fresh debouncer (or vice versa) creates timing mismatches.
- **Reducing settling frames without the exit reset fix:** This would cause false static fires because stale swipe-motion frames in the smoother would achieve majority vote during the shortened settling period.
- **Modifying SwipeDetector.is_swiping logic:** The `is_swiping` property correctly returns True for ARMED and COOLDOWN states. The problem is not in when `is_swiping` becomes False, but in what happens (or fails to happen) at that transition.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Smoother state cleanup | Custom "partial buffer" logic | `smoother.reset()` | Already clears the deque completely; partial clearing would introduce edge cases |
| Debouncer state cleanup | Manual state field setting | `debouncer.reset()` | Resets all 5 internal fields atomically; missing one creates stuck states |
| Settling frame management | New settling mechanism | Existing `_settling_frames_remaining` counter | Already works correctly in swipe.py; just change the default value |

## Common Pitfalls

### Pitfall 1: Forgetting to modify both detection loops
**What goes wrong:** Fix applied to `__main__.py` but not `tray.py` (or vice versa), causing inconsistent behavior between preview mode and tray mode.
**Why it happens:** The detection loops are duplicated across two files with near-identical but not perfectly identical code.
**How to avoid:** Always modify both files. Diff the two detection loops after changes to verify they remain symmetric.
**Warning signs:** Bug reports that only occur in tray mode (no preview window) or only in preview mode.

### Pitfall 2: Reset ordering relative to was_swiping assignment
**What goes wrong:** If `was_swiping = swiping` is moved before the exit reset check, the condition `was_swiping and not swiping` can never be True.
**How to avoid:** Keep the exit reset check between the entry reset check and the `was_swiping = swiping` assignment.

### Pitfall 3: Smoother window_size not updated on hot-reload
**What goes wrong:** `smoother.reset()` clears the buffer but keeps the old `maxlen`. If `smoothing_window` changed in config, the smoother uses the old window size until restart.
**How to avoid:** Update `smoother._buffer` with new maxlen when `smoothing_window` changes during hot-reload.
**Note:** This is a latent issue beyond the scope of the hot-reload fix in this phase, but worth noting. The minimal fix for this phase is to just call `smoother.reset()` -- window size changes during hot-reload are a Phase 10 concern if at all.

### Pitfall 4: Tests with settling_frames=10 may break
**What goes wrong:** Existing tests that hardcode `settling_frames=10` in their assertions (e.g., `test_settling_counter_resets_on_each_cooldown_transition` asserts `== 3` with explicit `settling_frames=3` parameter -- this one is fine). Tests that rely on the DEFAULT value of 10 will break.
**How to avoid:** Audit tests that create `SwipeDetector()` without explicit `settling_frames` parameter and verify they still pass with the new default of 3.

## Code Examples

### Exit Reset in __main__.py (lines 228-232 region)

Current code:
```python
# Line 228-232
swiping = config.swipe_enabled and swipe_detector.is_swiping
if swiping and not was_swiping:
    smoother.reset()
    debouncer.reset()
was_swiping = swiping
```

After fix:
```python
swiping = config.swipe_enabled and swipe_detector.is_swiping
if swiping and not was_swiping:
    smoother.reset()
    debouncer.reset()
if was_swiping and not swiping:
    smoother.reset()
    debouncer.reset()
    logger.debug("Swipe exiting: smoother/debouncer reset")
was_swiping = swiping
```

### Hot-Reload Fix in __main__.py (line ~264 region)

Add after existing `debouncer.reset()`:
```python
smoother.reset()
swipe_detector._settling_frames_remaining = 0
```

### Settling Frame Default in swipe.py (line 61)

```python
# Change default from 10 to 3
settling_frames: int = 3,
```

## Latency Budget Analysis

| Component | Before Fix | After Fix | Notes |
|-----------|-----------|-----------|-------|
| Swipe cooldown | 0.5s | 0.5s | Unchanged (swipe's own cooldown) |
| Settling frames | 10 frames (~330ms) | 3 frames (~100ms) | LAT-03 |
| Smoother refill | 3 frames (~100ms) from stale | 0ms (reset clears it) + 3 frames (~100ms) fresh | LAT-02 - starts clean |
| Activation delay | 0.4s (current default) | 0.4s (Phase 10 reduces to 0.15s) | Not this phase |
| **Total after swipe cooldown** | **~1.3s** | **~600ms** (current defaults) / **~300ms** (Phase 10 defaults) | |

The ~1.3s comes from: stale smoother needing full window refill (~100ms wasted) + 10 settling frames (~330ms) + 3 frames smoother refill (~100ms) + 0.4s activation delay = ~930ms after cooldown. With the additional lag from cooldown itself and frame timing, perceived total is ~1.3s.

After fix: 3 settling frames (~100ms) + 3 frames smoother refill (~100ms) + 0.4s activation delay = ~600ms after cooldown. Phase 10's activation_delay reduction to 0.15s brings this to ~350ms.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pyproject.toml (assumed) or pytest default discovery |
| Quick run command | `python -m pytest tests/test_swipe.py tests/test_debounce.py tests/test_integration_mutual_exclusion.py -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LAT-02 | Exit reset clears smoother+debouncer on swipe->static transition | unit | `python -m pytest tests/test_integration_mutual_exclusion.py -x -q -k "exit_reset"` | No - Wave 0 |
| LAT-02 | Hot-reload resets smoother + clears settling state | unit | `python -m pytest tests/test_swipe.py -x -q -k "hot_reload_reset"` | No - Wave 0 |
| LAT-03 | Settling frames default is 3 (not 10) | unit | `python -m pytest tests/test_swipe.py -x -q -k "default_settling"` | No - Wave 0 |
| LAT-01 | End-to-end latency: static fires within budget after swipe cooldown | integration | `python -m pytest tests/test_integration_mutual_exclusion.py -x -q -k "transition_latency"` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_swipe.py tests/test_debounce.py tests/test_integration_mutual_exclusion.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_integration_mutual_exclusion.py::TestSwipeExitReset` -- covers LAT-02 (exit reset fires smoother.reset + debouncer.reset)
- [ ] `tests/test_integration_mutual_exclusion.py::TestTransitionLatency` -- covers LAT-01 (end-to-end timing from cooldown end to static fire)
- [ ] `tests/test_swipe.py::TestSwipeSettlingGuard::test_default_settling_frames_is_3` -- covers LAT-03 (default value check)
- [ ] Hot-reload smoother reset test in appropriate test file -- covers LAT-02 hot-reload sub-fix

*(Existing test infrastructure covers baseline swipe/debounce behavior; gaps are for the NEW behaviors added in this phase)*

## Files to Modify

| File | Lines | Change | Requirement |
|------|-------|--------|-------------|
| `gesture_keys/__main__.py` | ~228-232 | Add exit reset (`if was_swiping and not swiping`) | LAT-02 |
| `gesture_keys/__main__.py` | ~262-264 | Add `smoother.reset()` and settling clear to hot-reload | LAT-02 |
| `gesture_keys/tray.py` | ~227-232 | Add exit reset (mirror __main__.py) | LAT-02 |
| `gesture_keys/tray.py` | ~251-257 | Add `smoother.reset()` and settling clear to hot-reload | LAT-02 |
| `gesture_keys/swipe.py` | ~61 | Change `settling_frames: int = 10` to `settling_frames: int = 3` | LAT-03 |
| `tests/test_integration_mutual_exclusion.py` | new | Add exit reset tests | LAT-02 |
| `tests/test_swipe.py` | new | Add default settling frames assertion | LAT-03 |

## Open Questions

1. **Smoother window_size hot-reload**
   - What we know: `smoother.reset()` clears the buffer but doesn't update `maxlen` if `smoothing_window` changed
   - What's unclear: Whether this matters in practice (users rarely change smoothing_window at runtime)
   - Recommendation: Minimal fix for this phase -- just call `smoother.reset()`. Full hot-reload of smoother window size can be addressed in Phase 10 if needed.

2. **Debug logging for swipe exit**
   - What we know: Entry resets have no explicit log message; the state machine logs in SwipeDetector handle COOLDOWN->IDLE
   - What's unclear: Whether adding a debug log at the exit reset point provides value vs noise
   - Recommendation: Add a single `logger.debug("Swipe exiting: smoother/debouncer reset")` at the exit reset. It's zero-cost at INFO level and useful for diagnosing transition issues.

## Sources

### Primary (HIGH confidence)
- Direct source code analysis of `gesture_keys/__main__.py`, `gesture_keys/tray.py`, `gesture_keys/swipe.py`, `gesture_keys/smoother.py`, `gesture_keys/debounce.py`
- Existing test suite in `tests/test_swipe.py`, `tests/test_debounce.py`, `tests/test_integration_mutual_exclusion.py`
- Phase 9 CONTEXT.md with user-confirmed implementation decisions

### Secondary (MEDIUM confidence)
- Latency budget calculations based on ~30fps assumption and known timing constants from config defaults

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new libraries; all changes are to existing codebase
- Architecture: HIGH - direct code analysis of exact lines to modify
- Pitfalls: HIGH - identified from actual code structure (dual loops, reset ordering)

**Research date:** 2026-03-22
**Valid until:** Indefinite (no external dependencies; all findings from stable internal code)
