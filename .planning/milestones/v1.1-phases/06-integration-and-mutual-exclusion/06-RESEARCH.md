# Phase 6: Integration and Mutual Exclusion - Research

**Researched:** 2026-03-22
**Domain:** Swipe/static gesture mutual exclusion, distance gating unification, state machine coordination
**Confidence:** HIGH

## Summary

Phase 6 addresses the interaction between the swipe detection pipeline and the static gesture pipeline, ensuring they do not cross-fire. The current codebase runs both pipelines in parallel on every frame with no mutual exclusion -- a swipe motion that passes through recognizable poses mid-motion will trigger static gesture keystrokes, and minor wrist jitter during a held pose could theoretically trigger false swipes.

The core approach is **wrist velocity gating**: use the SwipeDetector's internal velocity computation to determine whether the hand is in "motion mode" (swiping) or "hold mode" (static gesture). When wrist velocity exceeds a threshold, static gestures are suppressed. When velocity is below the threshold (hand is still), swipe detection naturally will not fire (below min_velocity). This creates a clean boundary between the two modes without adding a separate state machine.

Distance gating (INT-02) is already partially implemented -- the distance filter sets `landmarks = None` before both pipelines, which suppresses static gestures and clears the swipe buffer. The gap is that the swipe detector's reset behavior on `None` landmarks should also reset the smoother/debouncer to prevent stale state from the static pipeline.

**Primary recommendation:** Add a velocity-based suppression flag computed from the SwipeDetector's state. When the swipe detector is in ARMED or recently-in-motion state, suppress static gesture processing (feed None to smoother). When SwipeDetector is IDLE with low velocity, allow static gestures. This uses existing SwipeDetector state -- no new velocity computation needed.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INT-01 | Swipe and static gesture detection are mutually exclusive -- swipe motion does not trigger static gestures, and held poses do not trigger false swipes | Velocity-based gating using SwipeDetector state; when ARMED/motion, suppress static pipeline; when IDLE/still, swipe thresholds naturally prevent false fires |
| INT-02 | Distance threshold gates both static gestures and swipe detection -- if hand is too far, neither fires | Already partially implemented: distance filter sets landmarks=None before both pipelines; needs verification that swipe buffer clears and both pipelines reset cleanly |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| No new libraries needed | -- | -- | All integration logic uses existing SwipeDetector state and pipeline flow control |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| collections.deque | stdlib | Already in SwipeDetector buffer | No changes needed |
| enum.Enum | stdlib | Already in SwipeDetector states | Expose state for gating |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Velocity-based gating via SwipeDetector state | Separate GestureArbiter class | Over-engineered for this scope; SwipeDetector already has the velocity/state info |
| Suppressing static pipeline on swipe | Post-fire conflict resolution | Reactive instead of preventive; keystroke already sent, can't un-send |
| Frame-level mutex flag | Time-windowed exclusion zones | Time windows add latency; frame-level is simpler and immediate |

**Installation:**
```bash
# No new packages required
```

## Architecture Patterns

### Current Pipeline Flow (BEFORE Phase 6)
```
landmarks = detector.detect(frame)
    |
    v
distance_filter.check(landmarks) --> if too far: landmarks = None
    |
    +--> [Static path] classifier -> smoother -> debouncer -> fire keystroke
    |
    +--> [Swipe path]  swipe_detector.update(landmarks) -> fire keystroke
```

Both paths run independently every frame. No coordination.

### Recommended Pipeline Flow (AFTER Phase 6)
```
landmarks = detector.detect(frame)
    |
    v
distance_filter.check(landmarks) --> if too far: landmarks = None, reset both
    |
    v
swipe_detector.update(landmarks) --> returns swipe_result + exposes is_swiping
    |
    +--> if swipe fired: send keystroke, skip static path
    |
    +--> if is_swiping (ARMED state): suppress static path (feed None to smoother)
    |
    +--> if not swiping: run static path normally
```

### Pattern 1: Expose SwipeDetector Motion State
**What:** Add a read-only property to SwipeDetector that indicates whether the hand is actively in swipe motion (ARMED state or velocity above threshold). The main loop checks this to suppress the static gesture pipeline.
**When to use:** Every frame after swipe_detector.update() returns.
**Example:**
```python
# In SwipeDetector class - add property
@property
def is_swiping(self) -> bool:
    """True when hand is in active swipe motion (ARMED or just fired)."""
    return self._state in (_SwipeState.ARMED, _SwipeState.COOLDOWN)
```

### Pattern 2: Main Loop Mutual Exclusion
**What:** After calling swipe_detector.update(), check is_swiping to decide whether to run the static gesture pipeline. When swiping, feed None to the smoother to prevent static gesture accumulation.
**When to use:** Both __main__.py and tray.py detection loops.
**Example:**
```python
# Swipe detection FIRST (needs full landmarks)
if config.swipe_enabled:
    swipe_result = swipe_detector.update(landmarks, current_time)
    if swipe_result is not None:
        swipe_name = swipe_result.value
        if swipe_name in swipe_key_mappings:
            modifiers, key, key_string = swipe_key_mappings[swipe_name]
            sender.send(modifiers, key)
            logger.info("SWIPE: %s -> %s", swipe_name, key_string)
else:
    swipe_detector.update(None, current_time)
    swipe_result = None

# Static gesture path -- suppress when swiping
if landmarks and not (config.swipe_enabled and swipe_detector.is_swiping):
    raw_gesture = classifier.classify(landmarks)
    gesture = smoother.update(raw_gesture)
else:
    gesture = smoother.update(None)
```

### Pattern 3: Distance Gating Reset for Both Pipelines
**What:** When distance filter transitions from in-range to out-of-range, reset both the static pipeline (smoother + debouncer) AND the swipe detector buffer/state.
**When to use:** Distance gating section of both loops.
**Example:**
```python
if landmarks:
    in_range = distance_filter.check(landmarks)
    if not in_range:
        if hand_was_in_range:
            smoother.reset()
            debouncer.reset()
            swipe_detector.reset()  # NEW: also reset swipe state
        hand_was_in_range = False
        landmarks = None
    else:
        hand_was_in_range = True
```

### Anti-Patterns to Avoid
- **Post-hoc conflict resolution:** Don't fire both keystrokes then try to cancel one. Suppress BEFORE firing.
- **Separate velocity tracker for gating:** SwipeDetector already tracks velocity and state. Don't duplicate this computation.
- **Bidirectional coupling:** SwipeDetector should not need to know about the static pipeline. The main loop reads SwipeDetector state and decides what to suppress. One-directional dependency only.
- **COOLDOWN state allowing static gestures:** After a swipe fires, the hand is still in motion (decelerating). Static gestures should stay suppressed during COOLDOWN to prevent the stopping hand from triggering a pose.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Velocity computation for gating | Separate velocity tracker | SwipeDetector._state property | Already computed; expose via is_swiping property |
| State arbitration class | GestureArbiter/GestureRouter | Main loop if/else flow | Two pipelines with one gate = simple branching |
| Swipe buffer reset | Custom reset logic | SwipeDetector.reset() method | Need to add this method, but it's trivial (clear buffer, set IDLE) |

**Key insight:** The SwipeDetector already contains all the information needed for mutual exclusion. Its 3-state machine (IDLE/ARMED/COOLDOWN) directly maps to "should static gestures be active?" (yes when IDLE, no when ARMED or COOLDOWN).

## Common Pitfalls

### Pitfall 1: Static Gesture Fires During Swipe Acceleration Phase
**What goes wrong:** Hand starts swiping. During the initial frames before SwipeDetector enters ARMED state (still IDLE, accumulating buffer), the hand passes through a recognizable pose (e.g., open palm during a horizontal swipe). The static pipeline fires a keystroke.
**Why it happens:** SwipeDetector needs 3+ frames and threshold crossing to enter ARMED. During those initial frames, is_swiping is false.
**How to avoid:** Accept this as a minor timing window (2-3 frames at 30fps = ~66-100ms). The static pipeline has a 0.4s activation_delay (configurable), which means the smoother and debouncer already provide ~400ms of protection. A brief pass-through of a pose during a fast swipe will not survive the activation delay. This is a non-issue in practice because swipes are fast (200-500ms total) and the activation delay (400ms) exceeds the entire swipe duration.
**Warning signs:** Static keystrokes fire during swipe motions. If this happens, the activation_delay is set too low.

### Pitfall 2: Swipe Fires During Held Pose (Minor Wrist Jitter)
**What goes wrong:** User holds a static pose but natural hand tremor causes small wrist movements that register as swipe velocity.
**Why it happens:** If min_velocity and min_displacement thresholds are set too low.
**How to avoid:** The existing SwipeDetector thresholds (min_velocity=0.4, min_displacement=0.08) already handle this. Natural tremor produces velocity ~0.01-0.05 normalized/sec and displacement < 0.02. These are well below the default thresholds. No code change needed -- this is handled by SwipeDetector's existing design.
**Warning signs:** False swipe events when hand is held still. Fix by raising thresholds, not by adding code.

### Pitfall 3: Stuck State After Swipe-to-Pose Transition
**What goes wrong:** User swipes, then holds a pose. The static pipeline stays suppressed because is_swiping remains true during COOLDOWN.
**Why it happens:** COOLDOWN duration is 0.5s by default. During this time, static gestures are suppressed. After cooldown ends, SwipeDetector returns to IDLE and is_swiping becomes false, allowing static gestures.
**How to avoid:** This is actually correct behavior -- it prevents the decelerating hand from triggering a static gesture. The 0.5s cooldown is short enough that the user naturally waits before holding a new pose. No stuck state occurs because COOLDOWN always transitions to IDLE after the configured duration.
**Warning signs:** If cooldown is set very high (>2s), users might perceive static gestures as broken after swiping.

### Pitfall 4: Duplicate Loop Drift (CRITICAL)
**What goes wrong:** Changes to mutual exclusion logic in `__main__.py` are not identically applied to `tray.py`.
**Why it happens:** Both files have near-identical detection loops but are maintained separately.
**How to avoid:** Make changes to both files in the same task. The detection logic from lines ~199-243 in __main__.py maps to lines ~199-237 in tray.py. Verify both have identical mutual exclusion code.
**Warning signs:** Swipe/static interaction works in preview mode but not tray mode (or vice versa).

### Pitfall 5: Distance Filter Not Resetting Swipe Detector
**What goes wrong:** Hand moves out of range while a swipe is in progress (ARMED state). Buffer retains stale positions. When hand returns to range, stale buffer data causes immediate false fire.
**Why it happens:** Current code resets smoother and debouncer on distance transition but does NOT reset SwipeDetector.
**How to avoid:** Add `swipe_detector.reset()` call in the distance out-of-range transition block (where smoother.reset() and debouncer.reset() are called). Need to add a reset() method to SwipeDetector if it doesn't exist.
**Warning signs:** False swipe fires when hand re-enters range after being out of range.

## Code Examples

### SwipeDetector.reset() Method
```python
# Add to SwipeDetector class
def reset(self) -> None:
    """Reset detector to clean IDLE state. Used for distance gating transitions."""
    self._buffer.clear()
    if self._state != _SwipeState.COOLDOWN:
        self._state = _SwipeState.IDLE
    self._prev_speed = 0.0
    self._armed_direction = None
```

### SwipeDetector.is_swiping Property
```python
# Add to SwipeDetector class
@property
def is_swiping(self) -> bool:
    """True when hand is in active swipe motion (ARMED or COOLDOWN).

    Used by main loop to suppress static gesture pipeline during swipe activity.
    """
    return self._state in (_SwipeState.ARMED, _SwipeState.COOLDOWN)
```

### Main Loop Reordering (__main__.py and tray.py)
```python
# CURRENT ORDER (broken -- no mutual exclusion):
# 1. Classify -> smooth -> debounce -> fire static
# 2. Swipe detect -> fire swipe

# NEW ORDER (mutual exclusion):
# 1. Swipe detect first (needs raw landmarks)
# 2. Check is_swiping
# 3. If not swiping: classify -> smooth -> debounce -> fire static
# 4. If swiping: feed None to smoother (keep smoother/debouncer cycling)

# Distance gating section -- add swipe reset
if landmarks:
    in_range = distance_filter.check(landmarks)
    if not in_range:
        if hand_was_in_range:
            smoother.reset()
            debouncer.reset()
            swipe_detector.reset()  # NEW
        hand_was_in_range = False
        landmarks = None
    else:
        hand_was_in_range = True
else:
    hand_was_in_range = True

# Swipe detection FIRST
if config.swipe_enabled:
    swipe_result = swipe_detector.update(landmarks, current_time)
    if swipe_result is not None:
        swipe_name = swipe_result.value
        if swipe_name in swipe_key_mappings:
            modifiers, key, key_string = swipe_key_mappings[swipe_name]
            sender.send(modifiers, key)
            logger.info("SWIPE: %s -> %s", swipe_name, key_string)
else:
    swipe_detector.update(None, current_time)
    swipe_result = None

# Suppress static gestures when swiping
swiping = config.swipe_enabled and swipe_detector.is_swiping
if landmarks and not swiping:
    raw_gesture = classifier.classify(landmarks)
    gesture = smoother.update(raw_gesture)
else:
    gesture = smoother.update(None)

# Debounce and fire static gesture (unchanged)
fire_gesture = debouncer.update(gesture, current_time)
if fire_gesture is not None:
    gesture_name = fire_gesture.value
    if gesture_name in key_mappings:
        modifiers, key, key_string = key_mappings[gesture_name]
        sender.send(modifiers, key)
        logger.info("FIRED: %s -> %s", gesture_name, key_string)
```

### Hot-Reload Integration (no changes needed)
The existing hot-reload code in both loops already handles swipe detector parameter updates. No additional hot-reload changes are needed for mutual exclusion since `is_swiping` is computed from existing state.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Run both pipelines independently | Velocity-gated mutual exclusion | Phase 6 | Prevents cross-firing |
| Reset only smoother/debouncer on distance change | Reset all three components (smoother, debouncer, swipe) | Phase 6 | Prevents stale state across distance transitions |

## Open Questions

1. **Should COOLDOWN state suppress static gestures?**
   - What we know: During COOLDOWN (0.5s after swipe fires), the hand is decelerating and may pass through recognizable poses
   - What's unclear: Whether users expect instant static gesture availability after a swipe
   - Recommendation: YES, suppress during COOLDOWN. The 0.5s delay is short and prevents the common case of a stopping hand triggering a static gesture. If users find this too slow, they can reduce swipe cooldown.

2. **Should smoother.reset() be called when entering swiping state?**
   - What we know: When is_swiping becomes true, feeding None to smoother will naturally decay the buffer over window_size frames (default 3 = ~100ms)
   - What's unclear: Whether this gradual decay is fast enough or if an immediate reset is cleaner
   - Recommendation: Feed None (gradual decay) rather than hard reset. Hard reset could cause a brief gesture flash when returning from swipe to static if there's a single misclassified frame. The smoother's natural decay handles this smoothly.

3. **Activation delay as natural protection**
   - What we know: Static gestures require 0.4s activation_delay (configurable) before firing. A fast swipe (200-500ms) will not trigger a static gesture even without explicit suppression because the pose doesn't persist long enough.
   - What's unclear: Whether some users have very low activation_delay settings that could allow cross-firing
   - Recommendation: The mutual exclusion logic should NOT depend on activation_delay being "high enough." Implement explicit suppression via is_swiping regardless.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing infrastructure) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_swipe.py tests/test_integration.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INT-01 | Swipe motion suppresses static gestures; held pose does not trigger swipe | unit | `python -m pytest tests/test_swipe.py::TestSwipeMutualExclusion -x` | No - Wave 0 |
| INT-01 | is_swiping property reflects ARMED/COOLDOWN state | unit | `python -m pytest tests/test_swipe.py::TestSwipeIsSwiping -x` | No - Wave 0 |
| INT-02 | Distance gating resets swipe detector | unit | `python -m pytest tests/test_swipe.py::TestSwipeDistanceReset -x` | No - Wave 0 |
| INT-01+02 | End-to-end: swipe during poses, pose during swipe, distance transitions | integration | `python -m pytest tests/test_integration_mutual_exclusion.py -x` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_swipe.py tests/test_integration.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_swipe.py::TestSwipeIsSwiping` -- test is_swiping property in each state
- [ ] `tests/test_swipe.py::TestSwipeReset` -- test reset() method clears buffer and state
- [ ] `tests/test_swipe.py::TestSwipeMutualExclusion` -- test that static pipeline suppression works when is_swiping is true
- [ ] `tests/test_integration_mutual_exclusion.py` -- end-to-end tests simulating swipe-during-pose and pose-during-swipe sequences

## Sources

### Primary (HIGH confidence)
- Project source code: `gesture_keys/swipe.py` -- SwipeDetector state machine (IDLE/ARMED/COOLDOWN), velocity tracking
- Project source code: `gesture_keys/__main__.py` -- current pipeline integration showing both paths run independently
- Project source code: `gesture_keys/tray.py` -- identical pipeline showing same integration gap
- Project source code: `gesture_keys/debounce.py` -- activation_delay provides natural protection against brief pose flickers
- Project source code: `gesture_keys/distance.py` -- distance gating already sets landmarks=None for both paths

### Secondary (MEDIUM confidence)
- Phase 5 Research (`05-RESEARCH.md`) -- established parallel pipeline architecture and SwipeDetector design decisions
- Phase 5 CONTEXT.md -- locked decisions on cooldown, thresholds, fire timing

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, uses existing SwipeDetector state
- Architecture: HIGH -- simple property exposure + main loop reordering, well-understood patterns
- Pitfalls: HIGH -- identified from direct codebase analysis, timing analysis of activation_delay vs swipe duration
- Mutual exclusion strategy: HIGH -- leverages existing SwipeDetector state machine, no new abstractions

**Research date:** 2026-03-22
**Valid until:** 2026-04-22 (stable -- no external dependencies, internal architecture)
