# Pitfalls Research

**Domain:** Adding distance-based filtering and swipe/motion gestures to an existing static gesture recognition pipeline (MediaPipe 21 hand landmarks, rule-based classifier, majority-vote smoother, debounce state machine)
**Researched:** 2026-03-21
**Confidence:** HIGH (domain-specific to this codebase architecture, informed by MediaPipe documentation, gesture recognition literature, and codebase analysis)

## Critical Pitfalls

### Pitfall 1: Using MediaPipe Z-coordinate as absolute distance from camera

**What goes wrong:**
Developers assume `landmark.z` gives camera-to-hand distance in real units. It does not. MediaPipe's z-coordinate is relative depth normalized to the wrist, scaled roughly proportional to x. It tells you which finger is closer to the camera relative to the wrist, not how far the hand is from the lens. Using raw z for "distance gating" produces inconsistent behavior that varies with hand size, hand angle, and position in frame.

**Why it happens:**
The MediaPipe docs say z represents "landmark depth" which sounds like camera distance. Developers conflate relative inter-landmark depth with absolute camera proximity. The z values are small floats that seem plausible as distances.

**How to avoid:**
Use **apparent hand size** in normalized image coordinates as a proxy for camera distance. Specifically, compute the Euclidean distance between wrist (landmark 0) and middle finger MCP (landmark 9) in the x,y plane. This is the metacarpal bone length -- it does not change with finger extension and scales inversely with camera distance. A hand closer to the camera produces a larger value. Set a minimum threshold below which gestures are ignored.

**Warning signs:**
- Distance filter seems to work at one hand position but not another
- Users at different physical distances from camera get wildly different behavior
- Threshold values that "work" on your test setup fail for anyone else
- Filter works for one gesture but not another at the same real-world distance

**Phase to address:**
Phase 1 (Distance Threshold) -- this is the foundational design decision for the feature.

---

### Pitfall 2: Distance proxy that varies with hand pose / orientation

**What goes wrong:**
Using hand bounding box area or wrist-to-fingertip span as a distance proxy breaks when the hand changes pose. A fist at 50cm from the camera has a much smaller bounding box than an open palm at the same distance. A hand viewed edge-on (karate chop orientation) has a tiny span. The distance filter incorrectly gates out gestures depending on which gesture the user is making -- effectively breaking certain gestures at certain distances.

**Why it happens:**
The proxy is tested with one gesture (usually open palm, the most visually obvious) and seems to work. Other gestures at the same physical distance produce different proxy values because the measured landmarks move with finger articulation.

**How to avoid:**
Use the distance between landmarks that are structurally stable across all gestures: **wrist (landmark 0) to middle finger MCP (landmark 9)**. This segment is the metacarpal bone and does not change length regardless of finger extension, fist, pinch, or pointing. Alternatively, palm width (index MCP landmark 5 to pinky MCP landmark 17) is also stable. Do NOT use fingertip-based measurements or convex hull area -- both change dramatically with pose.

**Warning signs:**
- Distance filter works for open palm but rejects fist at the same real-world distance
- User must move closer to the camera for some gestures than others
- Threshold must be set very permissive to work across all gestures, defeating the purpose of distance gating

**Phase to address:**
Phase 1 (Distance Threshold) -- choice of distance metric must be validated across all 7 existing gestures.

---

### Pitfall 3: Swipe detection that fights the debounce state machine

**What goes wrong:**
The existing pipeline is: classifier -> smoother (majority vote) -> debouncer (activation delay + cooldown) -> keystroke sender. The debouncer requires a gesture to be held continuously for `activation_delay` before firing, then enters cooldown. Swipe gestures are inherently transient -- a hand sweeps across in 200-400ms. If swipe events are fed through the same debouncer, they either never fire (the classification only appears for a few frames, fewer than the activation delay requires) or fire too late (the hand has stopped moving, the pose may now resemble a static gesture, causing confusion).

**Why it happens:**
It is the path of least resistance to add a new `Gesture.SWIPE_LEFT` enum value and feed it through the same pipeline. The debouncer was designed specifically for static hold-to-activate gestures and its timing model is fundamentally incompatible with transient motion events.

**How to avoid:**
Swipe detection must use a **parallel path** that bypasses both the `GestureSmoother` and `GestureDebouncer`. Build a dedicated `SwipeDetector` component that tracks wrist position over a rolling window, computes displacement and velocity, and fires directly to the keystroke sender. The swipe detector needs its own independent cooldown to prevent double-fires, but must not share the static gesture debouncer. The architecture becomes:

```
landmarks --> classifier --> smoother --> debouncer --> keystroke (static gestures)
landmarks --> swipe_detector ---------------------------------> keystroke (swipe gestures)
```

**Warning signs:**
- Swipes only register when user moves hand unrealistically slowly
- Fast, natural swipes never fire
- Swipe fires but then a static gesture also fires immediately after (or vice versa)
- Reducing activation_delay to accommodate swipes causes static gesture false-fires

**Phase to address:**
Phase 2 (Swipe Gestures) -- this is an architectural decision that must be made before writing any swipe code.

---

### Pitfall 4: Swipe detection on raw per-frame landmark positions (jitter sensitivity)

**What goes wrong:**
MediaPipe landmarks jitter frame-to-frame even when the hand is completely stationary. The wrist landmark can wobble 1-3% of normalized coordinates between consecutive frames. A naive swipe detector that computes displacement between consecutive frames will see phantom micro-movements everywhere, causing false swipe detections. Or, thresholds are raised so high to avoid false positives that real swipes are missed.

**Why it happens:**
Developers test with deliberate, exaggerated swipes and set thresholds to match. In real use, the user's hand at rest produces enough jitter to cross low thresholds, and the user's natural swipes are smaller than the developer's testing swipes.

**How to avoid:**
Track wrist position in a small rolling deque (5-8 frames). Compute displacement as the vector from the oldest buffered position to the newest -- NOT frame-to-frame deltas. This naturally smooths jitter because noise averages out over the window. Additionally, require both: (a) total displacement above a minimum threshold, AND (b) displacement in the primary axis is at least 2-3x the displacement in the perpendicular axis, to distinguish deliberate directional swipes from general hand movement or wobble. Use velocity (displacement / elapsed time) rather than raw displacement so detection is frame-rate independent.

**Warning signs:**
- Swipe events fire when user is holding a static gesture (hand at rest)
- "Ghost swipes" when hand enters or leaves the frame
- Swipe detection works at 30fps but breaks at 15fps (under CPU load) or 60fps (faster camera)
- Swipes fire in random directions when user repositions hand

**Phase to address:**
Phase 2 (Swipe Gestures) -- core detection algorithm design.

---

### Pitfall 5: Swipe and static gesture mutual interference (cross-firing)

**What goes wrong:**
During a swipe, the hand passes through multiple static gesture poses. A leftward swipe might briefly resemble "pointing" as fingers trail, or "open palm" mid-sweep. The static gesture pipeline fires an unintended keystroke mid-swipe. Conversely, transitioning between static gestures (e.g., going from fist to open palm) involves hand movement that the swipe detector interprets as a directional swipe.

**Why it happens:**
Two independent detectors looking at the same landmark stream without coordination will both claim the input. There is no concept of "the hand is currently in motion, ignore static classifications" or "the hand is holding a static pose, ignore displacement."

**How to avoid:**
Implement a **mutual exclusion gate** based on wrist velocity:
1. Compute wrist velocity over the last N frames continuously.
2. When velocity exceeds a "hand is moving" threshold, suppress the static gesture pipeline (classifier output is treated as None, smoother buffer stays frozen or is cleared).
3. When velocity drops below a "hand is still" threshold for M consecutive frames, resume static detection.
4. While the static pipeline has a gesture in ACTIVATING or FIRED state, suppress swipe detection (the hand is intentionally holding a pose, not swiping).

**Warning signs:**
- Random keystrokes fire during swipe motions
- Slow swipes trigger static gesture key mappings
- Quick gesture transitions (fist -> open palm) register as accidental swipes
- The system feels "confused" -- doing one thing triggers two actions

**Phase to address:**
Phase 3 (Integration / Polish) -- after both features work independently, their interaction must be tested and gated.

---

### Pitfall 6: Hardcoded thresholds that break across cameras and users

**What goes wrong:**
Distance thresholds and swipe displacement thresholds tuned on one webcam (e.g., 720p, 70-degree FOV) fail on another webcam (1080p, 90-degree FOV, or a laptop's narrow-angle camera). MediaPipe normalizes landmarks to [0, 1] relative to the image frame. A wider FOV camera means the hand occupies a smaller fraction of normalized coordinate space at the same physical distance. Users with smaller hands also produce smaller landmark spans.

**Why it happens:**
Developers tune thresholds on their own hardware setup and hand, then ship those values as defaults. There is no calibration step.

**How to avoid:**
1. Make ALL thresholds user-configurable in `config.yaml` with documented defaults: `distance_threshold`, `swipe_min_displacement`, `swipe_cooldown`, `swipe_direction_ratio`.
2. In `--preview` mode, overlay the live distance proxy value and wrist velocity on the video frame so users can see what values to set.
3. Document in config comments: "Adjust distance_threshold by running with --preview and noting the value displayed when your hand is at your preferred maximum distance."
4. Consider auto-calibration in a future version: on first detection, record the hand size reference and normalize subsequent readings.

**Warning signs:**
- Feature works on developer's machine, fails on user's laptop webcam
- Bug reports about "gestures not detected" that are actually threshold mismatches
- Thresholds need unintuitive decimal-precision tuning (is 0.08 or 0.12 right?)

**Phase to address:**
Phase 1 for distance config, Phase 2 for swipe config, Phase 3 for preview overlay calibration aids.

---

### Pitfall 7: Hand entry/exit triggering false swipe detections

**What goes wrong:**
When a hand enters the camera frame from the side, the first detected position is at the frame edge. The next frame detects the hand slightly more centered. The swipe detector sees a large positional jump and fires a swipe event. Similarly, when the hand leaves the frame, the last few detections produce erratic landmark positions as MediaPipe loses tracking, which look like rapid movement.

**Why it happens:**
The swipe detector has no concept of "hand just appeared" vs "hand has been continuously tracked." The first frame after hand detection has no prior position to compare against, but developers initialize the position buffer with zeros or the first detection, creating an artificial displacement.

**How to avoid:**
Add a **settling period** after hand detection begins: require N consecutive frames of hand presence (e.g., 5-8 frames, ~200ms at 30fps) before the swipe detector begins tracking. When hand detection is lost (landmarks become empty), clear the swipe position buffer entirely. On re-detection, the settling period restarts.

**Warning signs:**
- Moving hand into camera frame triggers a swipe every time
- Removing hand from frame triggers a swipe in the opposite direction
- Intermittent hand tracking loss (e.g., from poor lighting) causes swipe spam

**Phase to address:**
Phase 2 (Swipe Gestures) -- build the settling period into the SwipeDetector from the start.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Feeding swipes through existing debouncer | No new components needed | Swipes never fire reliably; leads to compromised timing that breaks static gestures too | Never |
| Using landmark z for distance | One-line implementation | Unreliable gating that varies per session, hand size, and angle | Never |
| Single hardcoded swipe threshold | Quick to implement | Different users/cameras cannot use the feature | MVP only -- must be configurable before any release |
| Computing swipe from frame-to-frame deltas | Simpler math, no buffer needed | Jitter-sensitive, frame-rate dependent, false positives | Never -- rolling buffer is nearly as simple and correct |
| No mutual exclusion between swipe and static | Ship both features faster | Constant cross-firing in real use; top user-facing bug | Never |
| No settling period for swipe detector | Simpler state management | Hand entry/exit constantly triggers false swipes | Never -- trivially cheap to implement, expensive to debug without |

## Integration Gotchas

| Integration Point | Common Mistake | Correct Approach |
|-------------------|----------------|------------------|
| SwipeDetector + existing pipeline | Adding swipe as a new `Gesture` enum value processed by same smoother/debouncer | SwipeDetector is a parallel component receiving raw landmarks with its own output path to keystroke sender |
| Distance filter placement | Applying distance filter after classification (rejecting already-classified gestures) | Apply distance filter before classification -- if hand is too far, skip classification entirely; avoids polluting smoother buffer with spurious None values |
| Swipe cooldown + debounce cooldown | Sharing a single cooldown timer between swipe and static paths | Independent cooldowns -- swipe cooldown prevents double-swipe, debounce cooldown prevents static repeat-fire; they must not block each other |
| Config schema for new gesture types | Adding swipe entries alongside static gestures in the same `gestures:` block | Use a separate `swipes:` config section with its own parameters (min_displacement, cooldown, direction_ratio) |
| Preview overlay for new metrics | Not displaying distance proxy or swipe state in preview mode | Show distance proxy value, wrist velocity, and swipe detection indicators on preview frame for calibration |
| Distance filter + swipe detector | Distance filter suppresses landmarks before swipe detector sees them, so hand moving away cancels mid-swipe | Once a swipe is being tracked (motion started), do not apply distance gating until swipe completes or times out |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Storing unbounded landmark history for swipe detection | Memory grows linearly with session time; GC pauses | Use a fixed-size `deque(maxlen=8)` for position buffer; discard old data automatically | After hours of continuous use |
| Computing convex hull every frame for distance bounding box | 1-2ms extra per frame, drops FPS on slow machines | Use simple wrist-to-MCP two-point Euclidean distance (microseconds) | On low-end CPUs already near 30fps limit |
| Running swipe velocity computation when no hand is detected | Wasted cycles, potential errors on empty buffers | Guard swipe computation behind `if landmarks:` check; clear buffer on hand loss | Immediately if hand frequently enters/leaves frame |
| Recomputing distance proxy for both distance filter and swipe detector | Redundant computation of the same landmark distances | Compute distance proxy once per frame, share the value between distance filter and swipe detector | Minor but compounds with other per-frame overhead |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No feedback when hand is "too far" (distance gating silently rejects) | User makes gestures, nothing happens, thinks app is broken | In preview mode, show "TOO FAR" text overlay when hand is detected but below distance threshold |
| Swipe sensitivity too high by default | Casual hand repositioning triggers constant accidental swipes | Default to conservative thresholds (require deliberate motion); let users lower sensitivity in config |
| No visual indicator of swipe detection in preview | User has no idea if swipe was detected or which direction was recognized | In preview mode, draw a directional arrow overlay briefly when a swipe fires |
| Distance gating interrupts mid-swipe | Hand moves further from camera during swipe, distance proxy dips below threshold, swipe is cancelled partway through | Once swipe tracking begins, exempt from distance gating until swipe completes or times out |
| Ambiguous diagonal swipes guess wrong direction | User swipes diagonally, system picks a random axis, wrong keystroke fires | Require dominant axis displacement to be 2-3x the minor axis; reject ambiguous diagonals silently rather than guessing |
| Swipe works but there is no "undo" if wrong direction | User accidentally swipes left instead of right, triggers wrong action | This is inherent to gesture input; keep swipe cooldown long enough to prevent rapid accidental follow-up actions |

## "Looks Done But Isn't" Checklist

- [ ] **Distance threshold:** Works for open palm, but also test with fist, pointing, pinch, and scout at same physical distance -- verify the proxy metric produces consistent values (+/- 20%) across all poses
- [ ] **Swipe detection at varying FPS:** Works at 30fps, but test at 15fps (simulate CPU load) -- verify velocity calculation is time-based, not frame-count-based
- [ ] **Swipe + static mutual exclusion:** Perform a swipe gesture, verify no static keystroke fires during the motion. Perform a quick gesture transition (fist to palm), verify no swipe fires
- [ ] **Hand entry/exit:** Move hand into frame from off-screen -- verify no swipe fires for the first ~200ms after detection begins
- [ ] **Config reload:** Change distance_threshold and swipe settings in config.yaml, verify hot-reload applies new values to both distance filter and swipe detector without restart
- [ ] **Both hands visible:** Verify swipe tracking follows the right hand and does not jump between hands when both are in frame (detector already filters for right hand only)
- [ ] **Swipe during cooldown:** Fire a swipe, immediately swipe again -- verify cooldown prevents double-fire but does not permanently block subsequent swipes
- [ ] **Distance filter + activation gate:** If using the existing ActivationGate, verify distance filter and activation gate work together correctly (distance gating should apply before the gate, not after)

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Used z-coordinate for distance | LOW | Replace distance metric function only; if properly abstracted behind a `compute_distance_proxy(landmarks)` function, swap implementation with no interface change |
| Fed swipes through debouncer | MEDIUM | Extract swipe detection into parallel component, add new output path to keystroke sender, adjust main loop to call both paths |
| No mutual exclusion gate | MEDIUM | Add wrist velocity tracking, insert gating logic between both detection paths; requires touching the main detection loop |
| Hardcoded thresholds | LOW | Extract to config.yaml, add config loading; mechanical refactor |
| Frame-to-frame swipe deltas | LOW | Replace delta computation with rolling buffer approach; localized change within SwipeDetector |
| No settling period on hand entry | LOW | Add frame counter to SwipeDetector, suppress output until counter exceeds threshold; ~10 lines of code |
| Cross-firing between swipe and static | MEDIUM | Requires adding velocity-based gating and testing all combinations; most time is in testing, not coding |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Z-coordinate as distance proxy | Phase 1 (Distance Threshold) | Unit test: `compute_distance_proxy()` uses only x,y of wrist and MCP landmarks, never z |
| Pose-varying distance proxy | Phase 1 (Distance Threshold) | Test distance metric with fist, palm, pointing landmarks at same simulated distance; values within 20% |
| Swipe through debouncer architecture | Phase 2 (Swipe Gestures) | Architecture review: SwipeDetector has independent output path, does not pass through GestureSmoother or GestureDebouncer |
| Jitter-based false swipes | Phase 2 (Swipe Gestures) | Test: feed 60 frames of stationary hand landmarks with realistic jitter, zero swipe events fire |
| Hand entry false swipes | Phase 2 (Swipe Gestures) | Test: simulate hand appearing at frame edge then centering over 10 frames, no swipe fires |
| Swipe/static cross-firing | Phase 3 (Integration) | Integration test: perform swipe, verify no static keystroke during motion; perform quick pose change, verify no swipe fires |
| Hardcoded thresholds | Phase 1 + Phase 2 | Config.yaml has `distance_threshold`, `swipe_min_displacement`, `swipe_cooldown`, `swipe_direction_ratio` keys |
| Camera/FOV variation | Phase 3 (Integration) | Preview mode shows live distance proxy value and swipe velocity/direction indicators |

## Sources

- [MediaPipe Hand Landmark Z-coordinate discussion (Issue #742)](https://github.com/google/mediapipe/issues/742) -- confirms z is relative to wrist, not absolute camera distance
- [MediaPipe distance from camera discussion (Issue #1153)](https://github.com/google/mediapipe/issues/1153) -- confirms bounding box size is the recommended proxy for camera distance
- [MediaPipe Hand Landmarker official guide](https://developers.google.com/mediapipe/solutions/vision/hand_landmarker) -- landmark coordinate specification
- [5 Things I Wish I Knew Before Using MediaPipe for Hand Gesture Recognition](https://dev.to/trojanmocx/5-things-i-wish-i-knew-before-using-mediapipe-for-hand-gesture-recognition-41gb) -- jitter, confidence tuning, lighting sensitivity
- [MediaPipe Hands paper (arXiv:2006.10214)](https://ar5iv.labs.arxiv.org/html/2006.10214) -- landmark model architecture and coordinate normalization
- [Dynamic Hand Gesture Recognition Using MediaPipe and Transformer](https://www.mdpi.com/2673-4591/108/1/22) -- swipe detection accuracy with temporal models
- Codebase analysis: `gesture_keys/classifier.py` (7 static gestures, priority-ordered), `gesture_keys/smoother.py` (majority-vote deque), `gesture_keys/debounce.py` (4-state machine with activation delay + cooldown), `gesture_keys/detector.py` (right-hand only, VIDEO mode)

---
*Pitfalls research for: Adding distance threshold and swipe gestures to gesture-keys v1.1*
*Researched: 2026-03-21*
