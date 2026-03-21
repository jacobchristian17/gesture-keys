# Domain Pitfalls

**Domain:** Seamless gesture transitions for real-time gesture-to-keystroke system
**Researched:** 2026-03-22
**Focus:** Adding direct gesture-to-gesture firing, faster swipe/static transitions, tuning defaults
**Confidence:** HIGH -- all findings from direct analysis of the existing codebase state machines

## Critical Pitfalls

Mistakes that cause double-fires, stuck states, or require rearchitecting the state machine.

### Pitfall 1: Double-Fire on Transitional Poses

**What goes wrong:** When removing the "must return to None" requirement from the debouncer, transitioning from gesture A to gesture B passes through ambiguous intermediate hand shapes. The classifier momentarily reports gesture C (a transitional pose) for 1-3 frames, which -- if the activation delay is too short -- fires an unintended keystroke.

**Why it happens:** The current state machine (IDLE -> ACTIVATING -> FIRED -> COOLDOWN -> IDLE) assumes each gesture cycle starts clean from IDLE. Allowing COOLDOWN to transition directly to ACTIVATING for a *different* gesture means the classifier's transitional noise between poses A and B becomes a firing candidate. For example, transitioning from FIST to PEACE often passes through POINTING (index extends first) for 2-3 frames. With the current config (activation_delay=0.1s, smoothing_window=1), there is essentially zero noise rejection.

**Consequences:** Unintended keystroke fires. In the current config, going from FIST (esc) to PEACE (win+ctrl+left) could momentarily fire POINTING (alt+tab) -- a disruptive false fire that switches windows.

**Prevention:**
- Require the *new* gesture (different from the just-fired one) to meet the full activation_delay before firing. The COOLDOWN->ACTIVATING transition must reset the activation timer completely.
- Add a `_last_fired_gesture` field to the debouncer. When a new gesture appears in COOLDOWN, start ACTIVATING but do NOT carry over any elapsed time.
- Keep the smoother window as a first line of defense -- transitional frames should be absorbed by majority vote before reaching the debouncer. The current window=1 provides no smoothing at all; consider requiring window >= 3 when direct transitions are enabled.
- Consider a minimum "transition gap" (e.g., 2-3 frames of the new gesture after the old one disappears) even if you remove the None requirement.

**Detection:** Log every FIRED event with the previous gesture. If you see A -> C -> B patterns where C was not intended, transitional pose leakage is occurring.

**Phase:** Address in Phase 1 (direct transitions). This is the primary risk of the entire milestone.

---

### Pitfall 2: Cooldown Removal Causes Repeat-Firing on Held Gestures

**What goes wrong:** In pursuit of faster transitions, developers reduce cooldown_duration too aggressively or skip it entirely for same-gesture re-fires. The held gesture re-enters ACTIVATING immediately after FIRED and fires again after another activation_delay, creating rapid-fire keystroke spam.

**Why it happens:** The current design explicitly prevents this -- COOLDOWN requires `gesture is None` before returning to IDLE (debounce.py line 131-132). Modifying COOLDOWN to allow direct transition to ACTIVATING for a *different* gesture can accidentally also allow same-gesture re-activation if the condition check is wrong.

**Consequences:** Holding FIST sends repeated `esc` keystrokes. Holding OPEN_PALM sends repeated `win+tab`. This makes the app unusable.

**Prevention:**
- The COOLDOWN->ACTIVATING transition MUST check `gesture != last_fired_gesture`. Same-gesture still requires None first.
- Add a `_last_fired_gesture` field. In COOLDOWN, only transition to ACTIVATING when: (a) cooldown duration has elapsed AND (b) current gesture is not None AND (c) current gesture differs from `_last_fired_gesture`.
- Keep the existing behavior as the default. The "return to None" path remains for same-gesture; only *different* gestures get the direct transition.
- Write explicit test: hold gesture A for 5 seconds, verify exactly 1 fire event.

**Detection:** Count fire events per gesture per second. More than 1 fire per 2 seconds for any single gesture is a bug.

**Phase:** Address in Phase 1 alongside direct transitions. Must be tested simultaneously.

---

### Pitfall 3: Swipe/Static Mutual Exclusion Race on Transition Back

**What goes wrong:** Reducing settling_frames (currently 10, ~330ms) or swipe cooldown creates a window where the swipe detector has cleared `is_swiping` but the static pipeline's smoother still contains stale gesture data from before the swipe. The stale smoother output causes a false static fire immediately after a swipe.

**Why it happens:** The current code resets smoother and debouncer when `is_swiping` transitions from False to True (__main__.py lines 229-231). But when is_swiping transitions back to False, there is NO corresponding reset -- it lets the smoother and debouncer naturally refill. With 10 settling frames, the smoother has plenty of time to flush stale data. With fewer settling frames, stale data may survive.

**Consequences:** Completing a swipe_left (fires `right` key) immediately followed by a false OPEN_PALM fire (fires `win+tab`). Extremely disruptive.

**Prevention:**
- When `was_swiping` transitions from True to False, reset the smoother AND debouncer. Add this as a mirror of the existing swipe-start reset:
  ```python
  if not swiping and was_swiping:
      smoother.reset()
      debouncer.reset()
  ```
- This is **missing from the current code** and should be added regardless of settling_frames changes. It is a latent bug that only does not manifest because settling_frames=10 provides enough time.
- Settling frames can then be reduced safely because the smoother starts clean.
- Test: complete swipe, immediately present a static gesture, verify no fire until full activation_delay elapses.

**Detection:** Log both swipe fires and static fires with timestamps. Any static fire within 200ms of a swipe fire is suspicious.

**Phase:** Address in Phase 2 (swipe/static transitions). This is the highest-risk item for that phase.

---

### Pitfall 4: Smoother Window and Activation Delay Fight Each Other

**What goes wrong:** The smoother (majority-vote, window_size=1 currently) and activation_delay (0.1s currently) are tuned together as a system. Changing one without adjusting the other creates either: (a) too-slow response (large window + long delay stack additively) or (b) too-sensitive response (small window + short delay = no noise rejection).

**Why it happens:** Total latency from gesture start to fire = smoother fill time + activation delay. With window=3 at 30fps, smoother adds ~100ms. With the current config (window=1, delay=0.1s), total latency is ~130ms -- extremely fast but relies on the classifier being clean on every single frame. When direct transitions are enabled, the classifier WILL produce transitional noise that window=1 cannot absorb.

**Consequences:** Users (or developers tuning defaults) change one parameter and get unexpected behavior changes. Increasing smoother window for "better reliability" makes the system feel sluggish. Decreasing activation delay for "faster response" causes false fires because the smoother was the only noise barrier.

**Prevention:**
- Document the relationship: `perceived_latency = (window_size / fps) + activation_delay`.
- When recommending defaults, specify smoother AND delay together as a pair.
- Consider exposing a single "responsiveness" parameter that adjusts both proportionally, rather than two independent knobs.
- Test default combinations against the full gesture transition matrix (all 7 gestures to all 7 others) to find false-fire rates.
- For direct transitions, a minimum of window=3 + delay=0.15s is likely needed (total ~250ms) to absorb transitional poses.

**Detection:** Measure actual fire latency from gesture start. If it deviates significantly from the formula, something is wrong.

**Phase:** Address in Phase 3 (tuning defaults). Requires the direct transition changes to be stable first.

## Moderate Pitfalls

### Pitfall 5: Classifier Ambiguity Zones Between Adjacent Gestures

**What goes wrong:** Some gesture pairs share transitional hand shapes that the rule-based classifier cannot distinguish cleanly. The worst confusable pairs based on the priority-ordered classifier (classifier.py):
- **PEACE <-> SCOUT**: 2 vs 3 extended fingers. Ring finger partially extended oscillates classification.
- **POINTING <-> PEACE**: 1 vs 2 fingers. Middle finger partially extended oscillates.
- **FIST <-> THUMBS_UP**: Thumb state is the only differentiator. Thumb angle near the threshold oscillates.
- **OPEN_PALM <-> SCOUT**: Pinky state is the only differentiator. Pinky near threshold oscillates.

With direct transitions enabled, these oscillations become firing candidates rather than being absorbed by the "return to None" gate.

**Prevention:**
- Map the confusable pairs and ensure activation_delay absorbs their oscillation period. At 30fps, a 3-frame oscillation is 100ms -- activation_delay must exceed this for gesture-to-gesture transitions.
- Consider adding "transition hysteresis" for known confusable pairs: once gesture A is in ACTIVATING, only allow transition to a *non-adjacent* gesture (not its confusable neighbor) without an extended delay.
- The priority order helps but does not eliminate the problem when the classifier genuinely alternates between two gestures frame-to-frame.

**Phase:** Phase 1 (direct transitions). Test specifically with confusable pairs.

### Pitfall 6: Settling Frames Are Frame-Count Based, Not Time-Based

**What goes wrong:** The swipe detector's `settling_frames` (currently 10) is a frame count, not a time duration. At 30fps this is ~330ms, but if the system drops to 15fps (CPU load, background tasks), it becomes ~660ms. If the system runs at 60fps (faster hardware), it shrinks to ~166ms.

**Prevention:**
- Convert settling_frames to a time-based `settling_duration` (in seconds). Replace the frame counter with a timestamp comparison, matching how cooldown_duration already works in the same class.
- This also makes the config more intuitive: "settling: 0.15" (seconds) is clearer than "settling_frames: 10".
- If keeping frame count for simplicity, document the FPS dependency and note the effective duration range.

**Phase:** Phase 2 (swipe transitions). Natural time to refactor this.

### Pitfall 7: Hot-Reload Desynchronizes State Machines

**What goes wrong:** Config hot-reload (__main__.py lines 258-284) resets the debouncer but NOT the smoother when parameters change. It also does not reset the swipe detector's settling state. If a user changes activation_delay mid-gesture, the debouncer resets to IDLE but the smoother still contains the old gesture data, potentially causing an immediate re-activation with the new (possibly shorter) delay.

**Prevention:**
- On config reload, reset ALL stateful components: smoother, debouncer, swipe detector, and any new transition state.
- Add `smoother.reset()` to the hot-reload block.
- This is already a latent bug in the current code; it becomes more dangerous with direct transitions because the state machine has more paths and a stale smoother can immediately push a gesture into the new COOLDOWN->ACTIVATING path.

**Phase:** Phase 1 or 2. Fix during whichever phase touches the reload logic first.

### Pitfall 8: Insufficient Test Coverage for New State Transitions

**What goes wrong:** The current test suite (test_debounce.py) thoroughly tests IDLE->ACTIVATING->FIRED->COOLDOWN->IDLE but has zero tests for the new COOLDOWN->ACTIVATING path. Developers add the new transition, manually test it "works," ship it, and discover edge cases later.

**Prevention:** Before implementing, write tests for these specific scenarios:
1. COOLDOWN + different gesture -> ACTIVATING -> FIRED (happy path)
2. COOLDOWN + same gesture -> stays in COOLDOWN (no re-fire)
3. COOLDOWN + different gesture + flicker back to original -> no fire
4. Rapid A -> B -> A -> B cycling (stress test: 4 transitions in 3 seconds)
5. A -> None -> B vs A -> B (both should fire B, timing should be comparable)
6. A fires, immediately switch to B, B fires, immediately switch to A (round trip)
7. A fires, switch to confusable neighbor of A (e.g., PEACE -> SCOUT) -> must wait full delay

The test_integration_mutual_exclusion.py pattern is a good template to replicate for debouncer transitions.

**Phase:** Phase 1. Write tests before implementation (TDD).

### Pitfall 9: Swipe Detector Re-Arms from Residual Hand Motion After Cooldown

**What goes wrong:** After a swipe fires and cooldown expires, the hand is still decelerating. If settling_frames is reduced, the residual velocity from the tail end of the swipe immediately re-arms the detector, causing a phantom second swipe.

**Why it happens:** The current code clears the buffer on COOLDOWN->IDLE transition (swipe.py line 187) and sets settling_frames_remaining. But if settling_frames is reduced to, say, 3, only ~100ms of settling occurs -- the hand may still be moving at detectable velocity.

**Prevention:**
- Convert to time-based settling (see Pitfall 6) and set the minimum to at least 150ms regardless of user config.
- On COOLDOWN->IDLE, clear the buffer AND reset `_prev_speed` to 0 (already done, line 188). The settling guard is the last defense -- do not reduce it below the physical hand deceleration time.
- Test: perform a swipe, verify exactly 1 fire event even with settling_frames=3.

**Phase:** Phase 2 (swipe transitions).

## Minor Pitfalls

### Pitfall 10: Activation Delay Too Short for Direct Transitions

**What goes wrong:** The current config has activation_delay=0.1s. This is safe when "return to None" acts as an implicit debounce gate between gestures. Without that gate, 0.1s is dangerously short for direct transitions -- a transitional hand pose lasting 3 frames at 30fps (100ms) will fire.

**Prevention:**
- Consider separate delays: `activation_delay` for first gesture (from None), `transition_delay` for gesture-to-gesture. The transition delay should be slightly longer (e.g., 0.2s) to absorb transitional poses.
- Alternatively, keep a single delay but recommend a minimum of 0.15-0.2s when direct transitions are enabled.
- The architecture decision (one delay vs two) should be made in Phase 1 even if the final values are tuned in Phase 3.

**Phase:** Architecture in Phase 1, final values in Phase 3.

### Pitfall 11: Swipe During Gesture Transition Creates Phantom Swipe

**What goes wrong:** Transitioning from one static gesture to another involves moving the hand. If the movement is fast enough, the swipe detector may interpret it as a swipe, especially with lowered min_velocity/min_displacement thresholds. The current config has low thresholds (min_velocity=0.15, min_displacement=0.03) which are aggressive.

**Prevention:**
- The existing axis_ratio filter (1.5) helps (gesture transitions are rarely perfectly cardinal).
- Consider suppressing swipe detection during the ACTIVATING state of the static debouncer -- if the user is clearly in the process of changing static gestures, they are not swiping.
- Monitor: if swipe false-fires increase after reducing thresholds, this is the likely cause.

**Phase:** Phase 2 (swipe transitions).

### Pitfall 12: Preview Overlay Hides State Machine Bugs

**What goes wrong:** The preview window shows the smoother's output gesture but not the debouncer's state, fire events, or transition type. Developers think a gesture is "detected" because the preview shows it, but the debouncer has not fired. Or the debouncer fires from stale state that the preview does not surface.

**Prevention:**
- Add debouncer state to the preview overlay (e.g., "FIST [ACTIVATING 0.3s]" or "FIRED!" flash).
- Show whether the current transition is "from None" vs "from [previous gesture]" to debug direct transition logic.
- Log every state transition at INFO level during development (currently DEBUG).

**Phase:** Phase 1. Add before implementing transitions so you can see what the state machine is doing.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Direct gesture-to-gesture transitions | Double-fire on transitional poses (Pitfall 1) | Full activation_delay for new gesture after COOLDOWN; test confusable pairs |
| Direct gesture-to-gesture transitions | Same-gesture repeat-fire (Pitfall 2) | COOLDOWN->ACTIVATING ONLY for different gesture; same-gesture still requires None |
| Direct gesture-to-gesture transitions | Insufficient test coverage (Pitfall 8) | Write tests for all new transition paths before implementation |
| Direct gesture-to-gesture transitions | Preview does not show new states (Pitfall 12) | Add debouncer state to preview before implementing |
| Swipe/static transition speed | Stale smoother data after swipe ends (Pitfall 3) | Reset smoother AND debouncer on swipe->static transition (currently missing!) |
| Swipe/static transition speed | Frame-count settling is FPS-dependent (Pitfall 6) | Convert to time-based settling_duration |
| Swipe/static transition speed | Residual velocity re-arms swipe (Pitfall 9) | Minimum settling time floor; test with reduced settling values |
| Swipe/static transition speed | Phantom swipe from gesture change (Pitfall 11) | Monitor swipe false-fire rate; axis_ratio is first defense |
| Tuning defaults | Smoother/delay parameter coupling (Pitfall 4) | Document and test as a pair; test with transition matrix |
| Tuning defaults | Activation delay too short for transitions (Pitfall 10) | Consider separate transition_delay or raise minimum |
| All phases | Hot-reload desync (Pitfall 7) | Reset all stateful components on config reload |

## Integration Risk Map

The highest-risk integration point is where all three changes intersect: **a user performs gesture A, quickly transitions to gesture B, then swipes**. This exercises:
- Direct transition logic (A -> B without None)
- Swipe/static mutual exclusion (B suppressed during swipe)
- Swipe-to-static return (smoother reset on swipe end)
- All timing parameters simultaneously

This compound scenario must be an explicit integration test case. The individual features are moderate risk; the combination is high risk.

## "Looks Done But Isn't" Checklist

- [ ] Hold gesture A for 10 seconds with direct transitions enabled -- verify exactly 1 fire
- [ ] Transition A -> B for all 7x6=42 gesture pairs -- verify no unintended C fires
- [ ] Specifically test confusable pairs: PEACE<->SCOUT, POINTING<->PEACE, FIST<->THUMBS_UP
- [ ] Complete swipe, immediately hold static gesture -- verify no false static fire
- [ ] Rapid swipe -> static -> swipe -> static (4 transitions in 3 seconds) -- verify correct fires only
- [ ] Change activation_delay via hot-reload mid-gesture -- verify no crash or false fire
- [ ] Test with window=1 (current) AND window=3 -- verify both work with direct transitions
- [ ] Measure total perceived latency for gesture-to-gesture transition -- should be < 500ms

## Sources

- Direct analysis of gesture-keys source code: debounce.py (4-state machine, lines 76-134), swipe.py (3-state machine with settling, lines 148-265), smoother.py (majority-vote deque), __main__.py (main loop integration, lines 183-309), classifier.py (7 gestures, priority-ordered)
- State machine transition analysis from test_debounce.py (14 tests covering current paths) and test_integration_mutual_exclusion.py (5 tests for swipe/static exclusion)
- Config analysis: config.yaml production values (activation_delay=0.1s, cooldown=0.5s, smoothing_window=1, settling_frames=10, swipe min_velocity=0.15, min_displacement=0.03)
- Latent bug identified: missing smoother/debouncer reset on swipe->static transition (__main__.py lacks the mirror of lines 229-231)

---
*Pitfalls research for: gesture-keys v1.2 seamless gesture transitions*
*Researched: 2026-03-22*
