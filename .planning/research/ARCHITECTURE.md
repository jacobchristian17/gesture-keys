# Architecture Research: Seamless Gesture Transitions (v1.2)

**Domain:** Real-time gesture-to-keystroke pipeline -- seamless transition support
**Researched:** 2026-03-22
**Confidence:** HIGH (analysis based on full codebase read, no external dependencies)

## Current Pipeline (v1.1)

```
CameraCapture (thread)
    |
HandDetector (MediaPipe, 21 landmarks)
    |
DistanceFilter (gate by palm span)
    |
    +-------> SwipeDetector (wrist velocity, own state machine)
    |              | SwipeDirection | None
    |              v
    |         [fire swipe keystroke immediately]
    |
    +-------> GestureClassifier (rule-based, per-frame)
                   | Gesture | None
                   v
              GestureSmoother (majority vote, window=3)
                   | Gesture | None
                   v
              GestureDebouncer (IDLE->ACTIVATING->FIRED->COOLDOWN)
                   | fire Gesture | None
                   v
              KeystrokeSender
```

### Key Observations About Current Behavior

1. **Debouncer requires None before re-arming.** After COOLDOWN expires, `_handle_cooldown` only transitions to IDLE when `gesture is None` (line 131-132 of debounce.py). If the user holds Gesture A, fires it, then switches to Gesture B without releasing, the debouncer stays stuck in COOLDOWN until the hand is removed entirely.

2. **Swipe-to-static transition has 10 settling frames (~330ms at 30fps).** After swipe COOLDOWN expires, `settling_frames_remaining` blocks the swipe detector from re-arming for 10 frames. Meanwhile, the main loop resets `smoother` and `debouncer` when `swiping` transitions from True to False. The smoother then needs `window_size` frames to refill. Combined latency: ~330ms settling + ~100ms smoother refill + activation_delay.

3. **Static-to-swipe transition resets smoother and debouncer.** When `is_swiping` flips True, the main loop calls `smoother.reset()` and `debouncer.reset()` (tray.py lines 229-232). This is clean but any accumulated ACTIVATING progress is discarded.

4. **Swipe and static paths are mutually exclusive via `is_swiping`.** The main loop feeds `None` to the smoother when swiping (line 237), and skips the debouncer entirely (line 241-242).

## Problem Analysis

### Problem 1: No Direct Gesture-to-Gesture Transition

**Root cause:** `_handle_cooldown` at line 130-133:

```python
def _handle_cooldown(self, gesture, timestamp):
    if timestamp - self._cooldown_start >= self._cooldown_duration:
        if gesture is None:          # <-- BLOCKS transition when gesture held
            self._state = DebounceState.IDLE
    return None
```

The `if gesture is None` guard was intentional -- it prevents re-firing the SAME gesture when held. But it also blocks transitioning to a DIFFERENT gesture. The user must release their hand to "none" before any new gesture can begin activating.

**Impact:** To go from Fist -> Peace, the user must: Fist -> release (None) -> Peace. This adds ~cooldown_duration + activation_delay latency for sequential commands.

### Problem 2: Swipe-to-Static Latency

**Root cause:** Three sequential delays stack up:
1. Swipe cooldown (0.5s default) -- protects against multi-fire
2. Settling frames (10 frames = ~330ms) -- prevents swipe re-arming from hand deceleration
3. Smoother refill (window_size frames = ~100ms at window=3) -- majority vote needs data
4. Activation delay (0.1s current config) -- debouncer hold time

Total: ~1.03s from swipe fire to next static gesture fire. This is perceptible and frustrating.

### Problem 3: Static-to-Swipe Transition

**Root cause:** When the main loop detects `is_swiping` flipping True, it resets smoother and debouncer. But the swipe detector can only arm after its buffer fills (3+ samples). The transition itself is relatively fast (~100ms), but any ACTIVATING progress on a static gesture is lost, which feels like input was "eaten."

## Recommended Architecture Changes

### Change 1: Direct Gesture-to-Gesture Transition in Debouncer

**What:** Modify `_handle_cooldown` to allow transition to a DIFFERENT gesture without requiring None release.

**New state machine:**

```
IDLE --[gesture]--> ACTIVATING --[held >= delay]--> FIRED --[next frame]--> COOLDOWN
  ^                    |                                                      |
  |                    |--[None]--> IDLE                                      |
  |                    |--[different gesture]--> ACTIVATING (restart timer)   |
  |                                                                           |
  +--[None, cooldown expired]--<----------------------------------------------+
  |                                                                           |
  +--[different gesture, cooldown expired]--<-- ACTIVATING (new gesture) <----+
```

**Modified `_handle_cooldown`:**

```python
def _handle_cooldown(self, gesture, timestamp):
    if timestamp - self._cooldown_start >= self._cooldown_duration:
        if gesture is None:
            self._state = DebounceState.IDLE
            logger.debug("COOLDOWN -> IDLE: released")
        elif gesture != self._fired_gesture:
            # Direct transition to new gesture without requiring None
            self._state = DebounceState.ACTIVATING
            self._activating_gesture = gesture
            self._activation_start = timestamp
            logger.debug("COOLDOWN -> ACTIVATING: direct transition to %s", gesture.value)
    return None
```

**New field needed:** `_fired_gesture` -- tracks which gesture was last fired, so cooldown can distinguish "same gesture held" (stay in COOLDOWN) from "different gesture" (allow transition).

**Why track `_fired_gesture`:** Without it, holding Fist after firing Fist would re-enter ACTIVATING and fire again. The current `if gesture is None` guard prevents this but is too aggressive. By comparing against the fired gesture, we block re-fire of the same gesture while allowing new gestures.

**Edge case -- same gesture re-fire:** If user does Fist -> release -> Fist, the existing flow handles this: release causes COOLDOWN -> IDLE, then Fist starts fresh in IDLE -> ACTIVATING. No change needed here.

**Edge case -- rapid gesture switching:** If user does Fist -> Peace -> Fist quickly, each switch resets the activation timer in ACTIVATING (existing behavior at line 105-108). This is correct -- prevents accidental fires during transitional poses.

### Change 2: Reduce Swipe-to-Static Settling Frames

**What:** Reduce `settling_frames` from 10 to 3-4, and compensate with a velocity check.

**Why 10 was chosen originally:** After a swipe fires on deceleration, the hand is still moving slightly. The wrist buffer can contain residual motion that re-arms immediately, causing double-fire. 10 frames gives the hand ~330ms to come to rest.

**Better approach -- velocity gate instead of frame count:**

```python
# In SwipeDetector, after cooldown expires:
if self._settling_frames_remaining > 0:
    self._settling_frames_remaining -= 1
    return None

# NEW: velocity gate -- only re-arm when hand is actually still
if frame_speed > self._min_velocity * 0.3:  # hand still moving
    return None
```

This allows reducing `settling_frames` to 3 (just enough to rebuild a minimal buffer) because the velocity check prevents false re-arming on residual motion. Net improvement: ~230ms saved.

**Alternative considered -- zero settling frames:** Risky. Even with a velocity gate, the first 1-2 frames after cooldown have stale buffer data that could create artifacts. Keep a small settling count (3 frames = ~100ms) as a safety floor.

### Change 3: Reduce Smoother Refill Latency After Swipe

**What:** Reduce `smoothing_window` to 1 for the first N frames after a swipe, then ramp back up.

**Better approach -- use window=1 globally:** The current config already has `smoothing_window: 1`. At window=1, the smoother is a pass-through (returns whatever it receives). This means the smoother refill delay is already zero in the user's current config. The 3-frame default only matters for users who explicitly increase it.

**Recommendation:** Keep smoother as-is. The user's config of `smoothing_window: 1` already eliminates this bottleneck. Document that lower smoothing_window = faster transitions at the cost of more flicker.

### Change 4: Reduce Swipe Cooldown

**What:** Allow configuring swipe cooldown independently from settling behavior.

The current swipe cooldown (0.5s) is reasonable for preventing double-fire but contributes to the total swipe-to-static latency. Since we are adding a velocity gate (Change 2), the settling period is more intelligent. We can safely reduce the default swipe cooldown to 0.3s.

**Config change:**

```yaml
swipe:
  cooldown: 0.3       # reduced from 0.5
  settling_frames: 3   # reduced from 10, velocity gate compensates
```

### Change 5: Preserve ACTIVATING Progress on Swipe Interruption (Optional)

**What:** When a swipe starts (`is_swiping` flips True), instead of resetting the debouncer, snapshot its state. If the swipe detector returns to IDLE without firing (false arm), restore the debouncer state.

**Assessment: Not recommended.** This adds complexity for a rare edge case (static gesture partially activated, then swipe starts but does not fire). The simpler approach of resetting is fine -- the latency cost is one activation_delay period (0.1s in current config), which is not perceptible.

## Integration Points

### Modified Components

| Component | File | Change | Impact |
|-----------|------|--------|--------|
| **GestureDebouncer** | `debounce.py` | Add `_fired_gesture` field, modify `_handle_cooldown` for direct transitions | Core change -- enables gesture-to-gesture |
| **SwipeDetector** | `swipe.py` | Add velocity gate after cooldown, reduce default settling_frames | Reduces swipe-to-static latency |
| **AppConfig** | `config.py` | Add `settling_frames` to swipe config, update defaults | Config surface for tuning |
| **config.yaml** | root | Update defaults for cooldown, settling_frames | User-facing defaults |

### Unchanged Components

| Component | File | Why No Change |
|-----------|------|---------------|
| **GestureSmoother** | `smoother.py` | Works correctly, user config already at window=1 |
| **GestureClassifier** | `classifier.py` | Per-frame classification, no transition logic |
| **DistanceFilter** | `distance.py` | Orthogonal to transition timing |
| **KeystrokeSender** | `keystroke.py` | Fires what it is told, no state |
| **CameraCapture** | `detector.py` | Frame source, unrelated |
| **HandDetector** | `detector.py` | Landmark extraction, unrelated |
| **Pipeline loop** | `tray.py` | No structural changes needed -- debouncer change is internal |

### Internal Boundaries

| Boundary | Communication | Change Required |
|----------|---------------|-----------------|
| Smoother -> Debouncer | `Gesture or None` per frame | None -- same interface |
| Debouncer -> KeystrokeSender | `Gesture or None` (fire signal) | None -- same interface |
| SwipeDetector -> Main loop | `SwipeDirection or None` + `is_swiping` property | None -- same interface |
| Main loop -> Smoother/Debouncer | `reset()` calls on swipe transition | None -- same reset protocol |

## Data Flow: v1.2 Changes Highlighted

```
CameraCapture (thread)
    |
HandDetector (MediaPipe)
    |
DistanceFilter
    |
    +-------> SwipeDetector
    |              | SwipeDirection | None
    |              | is_swiping property
    |              |
    |              | CHANGED: settling_frames reduced 10->3
    |              | NEW: velocity gate after cooldown
    |              v
    |         [fire swipe keystroke]
    |
    +-------> GestureClassifier
                   |
              GestureSmoother (unchanged)
                   |
              GestureDebouncer
                   | CHANGED: _handle_cooldown allows
                   |   different gesture to bypass None requirement
                   | NEW: _fired_gesture tracks last fired gesture
                   v
              KeystrokeSender
```

## Architectural Patterns

### Pattern: State Machine with Transition Guards

**What:** The debouncer state machine uses guards (conditions) on transitions rather than blind state changes. The COOLDOWN -> ACTIVATING transition is guarded by `gesture != self._fired_gesture`.

**When to use:** When a state machine needs to distinguish between "same input repeated" and "new input arrived" to prevent re-triggering.

**Trade-offs:** Adds one field (`_fired_gesture`) and one comparison per frame. Trivial overhead. Makes the state machine slightly more complex to reason about but the behavior is more correct.

```python
# Guard pattern in _handle_cooldown
if cooldown_expired:
    if gesture is None:
        transition_to(IDLE)           # hand removed
    elif gesture != self._fired_gesture:
        transition_to(ACTIVATING)     # new gesture, allow it
    # else: same gesture still held, stay in COOLDOWN
```

### Pattern: Velocity Gate as Anti-Bounce

**What:** After a temporal event (swipe), use instantaneous velocity to gate re-entry into the detection state, rather than a fixed frame count.

**When to use:** When a fixed delay is too conservative for fast interactions but too aggressive for slow recoveries. Velocity adapts to actual hand behavior.

**Trade-offs:** Slightly more complex than frame counting. Requires tuning the velocity threshold fraction (0.3x of min_velocity recommended). But eliminates the one-size-fits-all problem of fixed settling frames.

```python
# Instead of: if self._settling_frames_remaining > 0: return None
# Use: if frame_speed > self._min_velocity * 0.3: return None
```

### Pattern: Track-Last-Fired for Re-fire Prevention

**What:** Store the identity of the last fired gesture to distinguish "same gesture held" from "different gesture arrived" during cooldown.

**When to use:** When a cooldown period should block re-fire of the same action but allow a different action.

**Trade-offs:** One extra field to maintain and clear on reset. Simple and effective.

## Anti-Patterns to Avoid

### Anti-Pattern: Skipping Cooldown for Direct Transitions

**What people do:** Remove the cooldown entirely and let any new gesture immediately begin activating after a fire.
**Why it is wrong:** The activation_delay alone does not prevent double-fire from brief flicker between gestures. A user transitioning from Fist to Peace may briefly show an intermediate pose (half-open hand) that could match Open Palm. Without cooldown, that flicker could fire Open Palm before Peace starts activating.
**Do this instead:** Keep cooldown, but allow COOLDOWN -> ACTIVATING for a *different* gesture after cooldown expires. The cooldown duration still provides a guard period.

### Anti-Pattern: Reducing Activation Delay to Zero

**What people do:** Set `activation_delay: 0` to make static gestures "instant."
**Why it is wrong:** Even with smoothing, single-frame classification noise can produce a false gesture for 1-2 frames. Zero delay means any noise fires immediately.
**Do this instead:** Keep activation_delay at minimum 0.05-0.1s. This is 1-3 frames at 30fps and unperceptible to users, but catches single-frame noise.

### Anti-Pattern: Coupling Swipe and Static State Machines

**What people do:** Make the debouncer aware of swipe state, or make the swipe detector aware of debouncer state.
**Why it is wrong:** The two detectors operate on fundamentally different signal types (pose vs motion). Coupling them makes both harder to test and reason about. The mutual exclusion via `is_swiping` in the main loop is the correct boundary.
**Do this instead:** Keep the main loop as the coordinator. The loop checks `is_swiping` and routes signals appropriately. Each detector remains self-contained.

### Anti-Pattern: Per-Gesture Cooldown Durations

**What people do:** Allow different cooldown times for different gestures in config.
**Why it is wrong for this codebase:** The debouncer is a single state machine with one cooldown timer. Per-gesture cooldowns would require tracking which gesture is in cooldown and applying different timers, significantly complicating the state machine. The benefit is marginal -- most users want uniform behavior.
**Do this instead:** Use a single global cooldown. If a specific gesture needs different timing, that is a sign the gesture threshold or activation delay needs tuning, not the cooldown.

## Build Order

Dependencies drive the order. Changes 1 and 2 are independent of each other.

```
Phase A: Debouncer Direct Transitions (debounce.py)
    |   Add _fired_gesture field
    |   Modify _handle_cooldown to allow different-gesture transition
    |   Modify _handle_fired to store fired gesture (trivial -- one line)
    |   Update tests: new test cases for direct transition scenarios
    |   RISK: Low -- isolated state machine change, thorough unit tests
    |
Phase B: Swipe Settling Reduction (swipe.py)  [independent of Phase A]
    |   Add velocity gate after cooldown expiry
    |   Reduce default settling_frames from 10 to 3
    |   Update tests: verify no double-fire with reduced settling
    |   RISK: Medium -- needs manual testing to confirm no swipe double-fire
    |
Phase C: Config and Defaults Update (config.py, config.yaml)
    |   Depends on: Phase A and B (need to know final parameter names)
    |   Add settling_frames to swipe config parsing
    |   Update default values: cooldown 0.5->0.3, settling 10->3
    |   Update debouncer defaults if needed
    |   RISK: Low -- additive config changes with backwards-compatible defaults
    |
Phase D: Integration Testing
    |   Depends on: Phase A, B, C
    |   Manual test: gesture-to-gesture transition latency
    |   Manual test: swipe-to-static transition latency
    |   Manual test: no regressions in false-fire prevention
    |   Automated: update test_debounce.py, test_swipe.py, test_integration_mutual_exclusion.py
    |
Phase E: Default Tuning
    |   Depends on: Phase D (need test results)
    |   Adjust activation_delay, cooldown_duration, settling_frames based on testing
    |   This is empirical -- cannot be determined from code analysis alone
```

**Phase A and B are independent** -- build in either order or parallel. Phase C is a thin layer on top. Phase D validates everything. Phase E is iterative tuning.

**Recommended sequence: A -> B -> C -> D -> E** because A is the highest-impact change (enables the core feature) and B is moderate impact (latency reduction).

## Latency Budget (Expected After Changes)

| Scenario | Current | After v1.2 | Improvement |
|----------|---------|------------|-------------|
| Gesture A -> Gesture B (direct) | cooldown(0.5) + release + activation(0.1) = ~0.8s+ | cooldown(0.5) + activation(0.1) = 0.6s | ~0.2s+ (no release needed) |
| Swipe -> Static gesture | cooldown(0.5) + settling(0.33) + smoother(0) + activation(0.1) = ~0.93s | cooldown(0.3) + settling(0.1) + activation(0.1) = ~0.5s | ~0.43s |
| Static -> Swipe | smoother_reset + buffer_fill(0.1) = ~0.1s | unchanged ~0.1s | 0 (already fast) |

Note: `smoother(0)` in current because `smoothing_window: 1` in user config. Users with higher window values would see more improvement.

## Sources

- Direct codebase analysis of `debounce.py`, `swipe.py`, `smoother.py`, `tray.py`, `config.py`
- Existing test suites: `test_debounce.py`, `test_integration_mutual_exclusion.py`
- Current `config.yaml` for real-world parameter values
- v1.1 architecture document (`.planning/research/ARCHITECTURE.md` prior version)

---
*Architecture research for: gesture-keys v1.2 seamless gesture transitions*
*Researched: 2026-03-22*
