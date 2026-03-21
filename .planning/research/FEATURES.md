# Feature Research: Seamless Gesture-to-Gesture Transitions

**Domain:** Hand gesture recognition -- continuous firing, transition latency, default tuning
**Researched:** 2026-03-22
**Confidence:** MEDIUM (patterns derived from analysis of existing codebase state machines + gesture recognition literature; no single authoritative source for "seamless gesture transitions" as a named pattern)

## Feature Landscape

### Table Stakes (Users Expect These)

Features that are non-negotiable for a "seamless gesture commands" milestone.

| Feature | Why Expected | Complexity | Depends On |
|---------|--------------|------------|------------|
| Direct gesture-to-gesture firing | Current system requires returning to "none" between static gestures due to COOLDOWN->IDLE requiring `gesture is None`. Users expect fist->peace to fire peace without dropping hand. | MEDIUM | Debounce state machine rewrite |
| Reduced swipe->static transition latency | After a swipe fires, the settling_frames (10 frames) + cooldown (0.5s) + smoother refill (3 frames) delay is perceptible. Users expect to swipe then immediately hold a static gesture. | MEDIUM | Swipe settling_frames reduction, smoother carry-forward |
| Reduced static->swipe transition latency | After a static gesture fires, the cooldown (0.5s) blocks swipe detection via `was_swiping` mutual exclusion reset. Users expect to fire a static gesture then immediately swipe. | LOW | Cooldown not blocking swipe path |
| Tuned default timing values | Current defaults (0.4s activate, 0.8s cooldown) were conservative first guesses. Real usage shows they can be tightened. | LOW | User testing data from existing config.yaml |

### Differentiators (Competitive Advantage)

Features that improve UX beyond the basics but are not strictly required for v1.2.

| Feature | Value Proposition | Complexity | Depends On |
|---------|-------------------|------------|------------|
| Configurable transition mode | Let users choose between "require none" (current safe behavior) and "direct transition" (new seamless behavior) via config flag | LOW | Direct transition implementation |
| Adaptive activation delay | Shorter activation delay when transitioning between known gestures (user already has hand up) vs. initial gesture from none (hand just appeared) | MEDIUM | Transition-aware debouncer |
| Swipe-during-static | Allow swipe detection to run even while a static gesture is in ACTIVATING state, so the user can abort a slow static hold and swipe instead | MEDIUM | Parallel pipeline changes |
| Transition preview feedback | Show state machine state in preview overlay (IDLE/ACTIVATING/COOLDOWN) so users can see why a gesture has not fired yet | LOW | Preview overlay extension |
| Per-gesture cooldown overrides | Some gestures (e.g., pinch) may need longer cooldown than others (e.g., fist) | LOW | Config schema extension |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Zero-cooldown / instant repeat | "I want to fire the same gesture repeatedly by holding it" | Without cooldown, a held gesture fires every frame (30+ times/sec). This floods the OS with keystrokes and is never what the user wants. | Keep cooldown for same-gesture repeat. Only skip the "require none" gate for different-gesture transitions. |
| Continuous/held key firing | "Hold fist = hold down Esc key" | pynput press/release semantics differ from single-tap. Holding a key requires tracking when the gesture ends to release. Edge cases with OS key repeat, app-specific behavior, and gesture flicker causing key-stuck states. | Stick to one-shot fire per gesture activation. Held-key mode is a separate feature with its own state machine. |
| Predictive gesture firing | "Fire as soon as the gesture starts forming, before it stabilizes" | Dramatically increases false fires. Transitional hand poses (fingers partially curled) match multiple gestures. The activation delay exists to prevent exactly this. | Keep activation delay but tune it down. 0.1-0.2s is fast enough to feel responsive without predicting. |
| No smoother / raw classification | "Remove the smoothing window for instant response" | Single-frame misclassifications cause spurious fires. MediaPipe occasionally outputs incorrect landmarks for 1-2 frames, especially during hand movement. | Reduce smoothing window to 1-2 frames instead of removing entirely. Window of 1 effectively passes through but still provides the pipeline hook. |
| Simultaneous multi-gesture firing | "Fire both fist and swipe_left at the same time" | Mutual exclusion exists because a moving hand changes its pose appearance. Classifying a fist during a swipe is unreliable -- landmarks shift during motion. Firing both creates unpredictable double-keystrokes. | Keep mutual exclusion. Swipe takes priority over static during motion (already implemented). |

## Feature Dependencies

```
[Direct gesture-to-gesture firing]
    |-- requires --> [Modified debounce state machine]
    |                   COOLDOWN state must allow transition to ACTIVATING
    |                   when a DIFFERENT gesture appears (not just None)
    |-- requires --> [Smoother carry-forward on gesture change]
    |                   Smoother should not need to refill from scratch
    |                   when the raw gesture changes
    |-- depends on --> [Existing smoother.py, debounce.py]

[Reduced swipe->static latency]
    |-- requires --> [Lower settling_frames default]
    |                   Currently 10 frames (~330ms at 30fps). Can reduce to 3-5.
    |-- requires --> [Smoother not reset on swipe->static transition]
    |                   Currently smoother.reset() is called when was_swiping changes.
    |                   This forces 3 frames of refill before any gesture output.
    |-- depends on --> [Existing swipe.py settling_frames, __main__.py transition logic]

[Reduced static->swipe latency]
    |-- requires --> [Swipe detection not blocked during static cooldown]
    |                   Currently swipe runs in parallel but mutual exclusion
    |                   resets swipe buffer when static fires. Swipe should
    |                   continue accumulating during static cooldown.
    |-- depends on --> [Existing __main__.py mutual exclusion logic]

[Tuned defaults]
    |-- requires --> [User testing / real usage data]
    |-- independent of --> [All other features]
    |                      (Can be done as a config change at any time)

[Direct firing] -- should be built BEFORE --> [Latency reductions]
    (The direct-firing state machine change is the core behavioral shift.
     Latency reductions are incremental tuning on top of it.)

[Tuned defaults] -- should be done LAST
    (Tune after the state machine changes are in place, since the
     changes themselves alter what "good" defaults look like.)
```

### Dependency Notes

- **Direct gesture-to-gesture firing is the keystone feature.** Everything else is incremental tuning. The debounce state machine change is the only structural code change needed.
- **Swipe<->static latency reductions are mostly parameter changes.** The settling_frames, cooldown duration, and smoother reset behavior are the knobs. No new components needed.
- **Tuned defaults should come last** because the state machine changes will alter the behavior of existing timing parameters. Tuning before the structural change would require re-tuning afterward.

## Detailed Feature Analysis

### 1. Direct Gesture-to-Gesture Firing (Core Feature)

**Current behavior (the problem):**
The debounce state machine has this path: IDLE -> ACTIVATING -> FIRED -> COOLDOWN -> IDLE. The COOLDOWN->IDLE transition (line 130-132 of debounce.py) requires `gesture is None` before returning to IDLE. This means the user must drop all gestures (return hand to neutral or remove hand) before a new gesture can begin activating.

**Desired behavior:**
After firing gesture A, if the user transitions directly to gesture B (without passing through "none"), gesture B should begin activating immediately. The fire sequence should be: fire A -> see B appearing -> activate B -> fire B.

**Implementation approach -- Modified COOLDOWN state:**

The COOLDOWN state needs a new transition path:
- Current: COOLDOWN + time elapsed + gesture is None -> IDLE
- New: COOLDOWN + time elapsed + gesture is None -> IDLE (unchanged)
- New: COOLDOWN + time elapsed + gesture is DIFFERENT from fired gesture -> ACTIVATING (new path)
- Unchanged: COOLDOWN + same gesture still held -> stay in COOLDOWN (prevents re-fire of same gesture without release)

This is a targeted change to `_handle_cooldown` in debounce.py. The key safety constraint is that the SAME gesture cannot re-fire without going through None first -- only a DIFFERENT gesture can trigger the new transition path. This prevents the "held fist fires repeatedly" anti-feature.

**State machine change:**
```
IDLE --(gesture appears)--> ACTIVATING
ACTIVATING --(held long enough)--> FIRED
FIRED --(immediate)--> COOLDOWN
COOLDOWN --(time elapsed + None)--> IDLE          [existing]
COOLDOWN --(time elapsed + different gesture)--> ACTIVATING  [NEW]
COOLDOWN --(time elapsed + same gesture)--> wait for None    [safety]
```

**Risk:** LOW. The change is additive (new transition, no existing transitions removed). The "same gesture blocks" safety rule prevents the most dangerous failure mode. Existing tests for the COOLDOWN->IDLE path remain valid.

**Confidence:** HIGH -- this is a straightforward state machine extension derived directly from reading the existing code.

### 2. Reduced Swipe-to-Static Transition Latency

**Current behavior (the problem):**
After a swipe fires and its cooldown expires, there are multiple sources of delay before a static gesture can fire:
1. `settling_frames = 10` in swipe.py (line 189) -- 10 frames (~330ms at 30fps) of ignored input after swipe cooldown
2. `smoother.reset()` called when `was_swiping` transitions from True to False (__main__.py line 230-231) -- smoother buffer is emptied, requiring 3 frames to refill
3. `debouncer.reset()` called at the same transition -- debouncer returns to IDLE, requiring a full activation_delay before fire

Total worst-case delay: swipe cooldown (0.5s) + settling (0.33s) + smoother refill (0.1s at 30fps) + activation delay (0.4s) = ~1.33s.

**Reduction approach:**
1. Reduce `settling_frames` default from 10 to 3-5 (saves ~170-230ms)
2. Do NOT reset smoother on swipe->static transition -- let it carry forward. The smoother will naturally transition as new static gesture frames fill the buffer. (saves ~100ms)
3. Consider shorter activation_delay for post-swipe transitions (e.g., 0.2s instead of 0.4s) as part of default tuning

**Risk:** MEDIUM. Reducing settling_frames too aggressively causes false re-arming of swipe detection from residual hand motion after a swipe. The settling guard exists because the hand decelerates over several frames after a swipe, and those deceleration frames can look like a new swipe. Testing needed to find the right balance.

### 3. Reduced Static-to-Swipe Transition Latency

**Current behavior (the problem):**
When a static gesture fires, the debouncer enters COOLDOWN. During cooldown, `swiping` is False (swipe detector is not in ARMED/COOLDOWN state), so the main loop continues feeding landmarks to the swipe detector. However, the smoother and debouncer are in cooldown mode, and if the user starts swiping during this cooldown, the `was_swiping` flag transition triggers `smoother.reset()` and `debouncer.reset()`.

The actual latency here is relatively low because swipe detection runs in a parallel path and is not gated by the static gesture cooldown. The main issue is that starting a swipe during static cooldown resets the static pipeline state, which is correct behavior but feels abrupt.

**Reduction approach:**
1. Verify that swipe detection is truly not blocked during static cooldown (it should not be based on code reading, but verify with tests)
2. Ensure the `was_swiping` transition does not add unnecessary delay
3. Consider not resetting debouncer when swiping starts if static is already in COOLDOWN (it is already cooling down, resetting is redundant)

**Risk:** LOW. The swipe path is already designed to be parallel. This is mostly verification and minor cleanup.

### 4. Tuned Defaults

**Current defaults vs. recommended:**

| Parameter | Current Default | Config Override | Recommended | Rationale |
|-----------|----------------|-----------------|-------------|-----------|
| activation_delay | 0.4s | 0.1s | 0.15-0.2s | User already tuned to 0.1s in config.yaml. 0.15s is fast enough to feel instant while still filtering 1-2 frame flickers. |
| cooldown_duration | 0.8s | 0.5s | 0.3-0.4s | User already tuned to 0.5s. With direct gesture-to-gesture firing, cooldown only needs to prevent same-gesture re-fire, not block all input. Can be shorter. |
| smoothing_window | 3 | 1 | 1-2 | User already at 1. With low activation_delay, smoothing is less critical. Window of 1 is effectively passthrough. Window of 2 adds one frame of flicker protection. |
| settling_frames | 10 | N/A (not configurable) | 3-5 | Make configurable in config.yaml. 3 frames (~100ms) is enough to ignore deceleration without adding perceptible delay. |
| swipe cooldown | 0.5s | 0.5s | 0.3-0.4s | Can be tightened slightly. The settling_frames guard handles post-swipe residual motion. |

**Approach:** Update code defaults to match commonly-used overrides, then expose settling_frames in config. The user's existing config.yaml already shows they prefer faster values -- the code defaults should match what works in practice.

**Risk:** LOW. These are parameter changes. The existing config.yaml overrides mean users already have faster values; changing defaults just makes the out-of-box experience match what works.

## MVP Definition

### Launch With (v1.2)

Minimum features to deliver the "seamless and continuous commands" milestone goal.

- [ ] **Direct gesture-to-gesture firing** -- modify COOLDOWN state to allow ACTIVATING a different gesture without passing through None. Core behavioral change.
- [ ] **Reduced swipe settling_frames** -- lower default from 10 to 3-5 frames. Make configurable in config.yaml.
- [ ] **Remove unnecessary smoother/debouncer resets on swipe<->static transition** -- let pipeline state carry forward instead of clearing on mode switch.
- [ ] **Tuned timing defaults** -- update code defaults to: activation_delay=0.2s, cooldown_duration=0.4s, smoothing_window=2, settling_frames=4, swipe_cooldown=0.4s.

### Add After Validation (v1.2.x)

- [ ] **Configurable transition mode** -- config flag to choose "require_none" (legacy) vs "direct_transition" (new) for users who prefer conservative behavior
- [ ] **Transition preview feedback** -- show current debounce state (IDLE/ACTIVATING/COOLDOWN) in preview overlay for debugging
- [ ] **Per-gesture cooldown overrides** -- allow gestures with high false-fire risk (pinch) to have longer cooldown than reliable ones (fist)

### Future Consideration (v2+)

- [ ] **Adaptive activation delay** -- shorter delay for gesture-to-gesture transitions, longer for none-to-gesture (first appearance). Adds state-dependent timing complexity.
- [ ] **Held-key mode** -- hold gesture = hold key down, release gesture = release key. Separate state machine with press/release tracking.
- [ ] **Swipe-during-static** -- allow swipe to interrupt a static gesture that is still in ACTIVATING state. Complex pipeline interaction.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Direct gesture-to-gesture firing | HIGH | MEDIUM | P1 |
| Reduced settling_frames | HIGH | LOW | P1 |
| Remove unnecessary pipeline resets | MEDIUM | LOW | P1 |
| Tuned timing defaults | HIGH | LOW | P1 |
| Configurable transition mode | LOW | LOW | P2 |
| Transition preview feedback | MEDIUM | LOW | P2 |
| Per-gesture cooldown overrides | LOW | LOW | P3 |
| Adaptive activation delay | MEDIUM | MEDIUM | P3 |
| Held-key mode | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for v1.2 launch
- P2: Should have, add when possible within milestone
- P3: Nice to have, future milestone

## Implementation Architecture Notes

### Debounce State Machine Modification

The change to `_handle_cooldown` in debounce.py is the core implementation. The debouncer needs to track which gesture was fired (currently discarded in `_handle_fired`) so that COOLDOWN can distinguish "same gesture still held" from "different gesture appeared."

Required changes to GestureDebouncer:
1. Store `_fired_gesture` in `_handle_fired` before transitioning to COOLDOWN
2. In `_handle_cooldown`, when cooldown time has elapsed:
   - If gesture is None -> IDLE (existing behavior)
   - If gesture == `_fired_gesture` -> stay in COOLDOWN waiting for None (new: prevents same-gesture re-fire)
   - If gesture != `_fired_gesture` and gesture is not None -> ACTIVATING with new gesture (new: enables direct transition)

This is ~10-15 lines of code change in a single method.

### Pipeline Reset Cleanup

In `__main__.py`, the `was_swiping` transition currently calls `smoother.reset()` and `debouncer.reset()`. This should be changed to:
- When swiping starts (not was_swiping, now swiping): reset smoother and debouncer (correct -- hand is moving, static state is invalid)
- When swiping ends (was swiping, not swiping now): do NOT reset smoother. Do NOT reset debouncer. Let them pick up naturally from the next frame of landmarks. The smoother will fill with new data and the debouncer will start from its current state.

### Settling Frames Configuration

Add `settling_frames` to the swipe config section in config.yaml:
```yaml
swipe:
  settling_frames: 4  # frames to ignore after swipe cooldown (prevents re-arming)
```

And wire it through config.py load_config and hot-reload in __main__.py (same pattern as existing swipe params).

## Sources

- Existing codebase analysis: `debounce.py`, `smoother.py`, `swipe.py`, `__main__.py` -- primary source for current behavior and constraints
- [Gestop: Customizable Gesture Control](https://github.com/ofnote/gestop) -- reference implementation using explicit mode switching (Ctrl key) between static and dynamic gestures; confirms that mode-switching latency is a known UX concern in gesture systems
- [vladmandic/human Debounce Discussion](https://github.com/vladmandic/human/discussions/427) -- confirms debounce is universally an app-level concern, not built into detection libraries; recommends temporal consistency windows
- [Gesture Modeling and Recognition Using Finite State Machines (IEEE)](https://ieeexplore.ieee.org/document/840667/) -- foundational work on FSM-based gesture recognition with state transitions
- [React Native Gesture Handler: States & Events](https://docs.swmansion.com/react-native-gesture-handler/docs/fundamentals/states-events/) -- reference for gesture state machine patterns (Possible->Began->Active->End) where transitions between gesture types are handled by state change events rather than requiring return to idle
- [Apple Gesture Recognizer State Machine](https://developer.apple.com/documentation/uikit/about-the-gesture-recognizer-state-machine) -- reference for how platform gesture recognizers handle state transitions; gestures move through Possible->Recognized without requiring explicit "none" states between recognitions
- [MediaPipe Gesture Recognizer Guide](https://ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer) -- confirms that MediaPipe uses tracking to avoid re-detecting hands every frame, reducing latency; video/live-stream modes skip palm detection when tracking is active
- [Continuous Hand Gesture Recognition Benchmarks and Methods](https://www.sciencedirect.com/science/article/pii/S1077314225001584) -- survey of continuous gesture recognition methods; confirms that skeleton-based approaches (like MediaPipe landmarks) are the standard for start/end point detection

---
*Feature research for: gesture-keys v1.2 seamless gesture-to-gesture transitions*
*Researched: 2026-03-22*
