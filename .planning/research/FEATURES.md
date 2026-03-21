# Feature Research: Distance Threshold and Swiping Gestures

**Domain:** Hand gesture recognition -- distance gating and dynamic gesture detection
**Researched:** 2026-03-21
**Confidence:** MEDIUM (distance approach verified via MediaPipe docs; swipe algorithms well-documented but implementation details are project-specific)

## Feature Landscape

### Table Stakes (Users Expect These)

Features that are non-negotiable if advertising "distance threshold" and "swipe gestures."

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Distance gating toggle | Users need to turn distance filtering on/off without editing thresholds | LOW | Boolean `enabled` flag in config under a `distance` section |
| Configurable distance threshold | Different webcam setups and arm lengths require tuning | LOW | Single float in config.yaml; uses hand bounding box area ratio as proxy (see notes below) |
| Swipe left/right/up/down detection | The four cardinal directions are the universal swipe vocabulary | MEDIUM | Track wrist position across a frame buffer, compute velocity and displacement, classify direction |
| Swipe gestures in config.yaml | Must follow existing pattern: gesture name -> key mapping | LOW | Add `swipe_left`, `swipe_right`, `swipe_up`, `swipe_down` to gestures section with same `key`/`threshold` structure |
| Swipe visual feedback in preview | Without feedback, users cannot tell if swipe was detected or why it failed | LOW | Draw direction arrow or flash text on preview window when swipe fires |
| Distance indicator in preview | Users need to see current "distance" value to tune their threshold | LOW | Overlay a bar or numeric value on the preview window showing current hand size ratio |

### Differentiators (Competitive Advantage)

Features that improve UX beyond the basics but are not strictly required.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Per-gesture distance thresholds | Some gestures (pinch) need closer range than others (open palm) | LOW | Extend existing per-gesture threshold dict; classifier already supports per-gesture config |
| Swipe sensitivity config | Let users tune how fast/far they need to swipe | LOW | `min_velocity` and `min_displacement` in config under a `swipe` section |
| Swipe + static gesture combos | "Swipe right while pointing" expands vocabulary significantly | HIGH | Requires tracking static gesture state during motion; complex state machine interaction with debouncer |
| Distance-based confidence scaling | Closer hand = higher confidence = faster activation | MEDIUM | Modulate activation_delay based on distance proxy; nice UX but adds coupling between distance and debounce systems |
| Diagonal swipe support | 8 directions instead of 4 | MEDIUM | Adds ambiguity between cardinal and diagonal; angle-based classification with dead zones needed |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Absolute distance in centimeters | "I want to set threshold to 50cm" | MediaPipe normalized landmarks have no absolute depth from a single RGB camera. The z-coordinate is relative to the wrist, not the camera. World landmarks give metric coordinates relative to hand center, not camera distance. Getting real cm requires camera calibration or a depth sensor -- both out of scope. | Use hand bounding box area (ratio of landmark spread to frame size) as a unitless proxy. Bigger hand in frame = closer to camera. Document that threshold is relative, not in cm. |
| Continuous swipe tracking (drag) | "I want to drag-and-hold while swiping" | Requires maintaining a pressed key state during motion, releasing on stop. Interacts badly with cooldown state machine. Edge cases around "when does drag end?" are numerous. | Stick to discrete swipe-fires (one keystroke per swipe). Revisit drag semantics in a future milestone if needed. |
| Swipe with any hand shape | "Any movement should count as swipe" | Detects unintentional hand repositioning as swipes. Every time user adjusts hand position, spurious swipes fire. | Require swipe velocity above a high threshold so casual repositioning is ignored. Optionally gate swipes behind a specific hand pose. |
| Two-hand swipe gestures | "Swipe with both hands" | Already out of scope per PROJECT.md. Current detector filters to right hand only. Adding left hand doubles complexity. | Single right-hand swipes are sufficient for v1.1. |
| ML-based swipe classification | "Train a model on swipe data" | Adds training data requirement, model management, and contradicts the no-custom-ML constraint. | Rule-based velocity + displacement + direction works well for 4 cardinal swipes. No ML needed. |

## Feature Dependencies

```
[Distance proxy calculation]
    |-- requires --> [Access to landmark bounding box from HandDetector]
    |                   (computable from existing landmark x,y -- no API changes)
    |-- enables --> [Distance gating filter in pipeline]
    |                   |-- enables --> [Per-gesture distance thresholds]
    |-- enables --> [Distance indicator in preview]

[Swipe detection]
    |-- requires --> [Wrist/palm position history buffer (N frames)]
    |-- requires --> [Velocity + displacement calculation]
    |-- requires --> [Direction classification (4-way)]
    |-- enables --> [Swipe gesture entries in config.yaml]
    |-- enables --> [Swipe visual feedback in preview]

[Distance gating] -- independent of --> [Swipe detection]
    (No dependency between the two; they can be built in either order)

[Swipe detection] -- interacts with --> [Debounce state machine]
    (Swipes are instantaneous events, not held poses. They need a different
     activation model than static gestures which use hold-to-activate.)
```

### Dependency Notes

- **Distance proxy requires no HandDetector API changes:** The bounding box area can be computed from the existing 21 normalized landmark x,y values (min/max). No need to access `hand_world_landmarks` or modify `detect()` return values. A standalone function `compute_hand_size(landmarks) -> float` is sufficient.
- **Swipe detection requires a new component -- position history buffer:** The current pipeline is stateless per-frame (landmarks -> classify -> smooth -> debounce). Swipe detection needs a ring buffer of wrist positions across frames to compute velocity and displacement. This is a new `SwipeTracker` class, not a modification of an existing one.
- **Swipe interacts with debounce differently than static gestures:** Static gestures use hold-to-activate (IDLE -> ACTIVATING -> FIRED -> COOLDOWN). Swipes are instantaneous -- they should fire immediately when velocity/displacement thresholds are crossed, then enter cooldown to prevent double-fires. Swipes need either a separate debounce path or the existing debouncer needs an "instant fire" mode for swipe-type gestures.
- **Distance gating and swipe detection are independent:** They share no state. Distance gating is simpler and should be implemented first as a warm-up before the more complex swipe tracker.

## MVP Definition

### Launch With (v1.1)

Minimum features to deliver the milestone goal.

- [ ] **Distance proxy from landmark bounding box** -- compute hand area ratio from min/max of landmark x,y coordinates. No new dependencies, no API changes needed.
- [ ] **Distance gating filter** -- reject all gestures (both static and swipe) when hand is outside configured distance range. Single `distance.min_hand_size` config value (unitless ratio 0.0-1.0). Inserted between detector and classifier in pipeline.
- [ ] **Distance indicator in preview** -- numeric overlay showing current hand size ratio so users can determine their threshold value.
- [ ] **4 cardinal swipe gestures** -- swipe_left, swipe_right, swipe_up, swipe_down as new entries in Gesture enum and config.yaml.
- [ ] **Wrist position tracker** -- ring buffer of recent wrist (landmark 0) positions with timestamps. Compute velocity and displacement per frame.
- [ ] **Swipe classifier** -- rule-based: displacement > min_displacement AND velocity > min_velocity AND primary axis ratio > direction_threshold.
- [ ] **Swipe cooldown** -- prevent double-fire after a swipe is detected. Dedicated cooldown for swipes, separate from static gesture debouncer.
- [ ] **Config entries for swipe tuning** -- `swipe.min_velocity`, `swipe.min_displacement`, `swipe.cooldown` under a `swipe` section in config.yaml.

### Add After Validation (v1.x)

- [ ] **Per-gesture distance thresholds** -- once users confirm the global distance gate works, add per-gesture overrides
- [ ] **Swipe sensitivity presets** -- "slow", "normal", "fast" named presets instead of raw numeric tuning
- [ ] **Swipe visual feedback** -- arrow overlays on preview window showing detected swipe direction

### Future Consideration (v2+)

- [ ] **Diagonal swipes** -- 8-direction classification; defer because 4 directions already double the input vocabulary
- [ ] **Swipe + static combos** -- "pointing + swipe right" as a distinct gesture; defer because state machine complexity is high
- [ ] **Distance-based confidence scaling** -- closer hand = faster activation; defer because it couples two independent systems

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Distance gating filter | HIGH | LOW | P1 |
| Distance preview indicator | MEDIUM | LOW | P1 |
| 4 cardinal swipe gestures | HIGH | MEDIUM | P1 |
| Swipe config entries | HIGH | LOW | P1 |
| Swipe cooldown | HIGH | LOW | P1 |
| Per-gesture distance thresholds | LOW | LOW | P2 |
| Swipe visual feedback | MEDIUM | LOW | P2 |
| Swipe sensitivity presets | LOW | LOW | P3 |
| Diagonal swipes | LOW | MEDIUM | P3 |
| Swipe + static combos | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for v1.1 launch
- P2: Should have, add when possible within milestone
- P3: Nice to have, future milestone

## Implementation Architecture Notes

### Distance Proxy: Bounding Box Area Ratio (Recommended)

The best approach for estimating hand distance without a depth sensor is computing the **bounding box area of the hand landmarks as a fraction of frame area**. This works because:

1. MediaPipe normalized landmarks have x,y in [0.0, 1.0] relative to image dimensions
2. A hand closer to the camera occupies more of the frame
3. Computing `(max_x - min_x) * (max_y - min_y)` from the 21 landmarks gives a unitless ratio
4. No camera calibration needed, no new dependencies, no API changes

The alternative -- using `hand_world_landmarks` from MediaPipe -- gives metric coordinates in meters but relative to the hand's geometric center, not the camera. This does NOT help estimate camera-to-hand distance.

**Why not use the z-coordinate?** MediaPipe's z for normalized landmarks is depth relative to the wrist origin, not absolute distance from camera. It tells you finger depth relative to the palm, not how far the hand is from the lens. The bounding box approach is the standard proxy used in webcam-only hand tracking systems.

**Config format:**
```yaml
distance:
  enabled: true
  min_hand_size: 0.04  # minimum bounding box area ratio (0.0-1.0)
```

### Swipe Detection: Velocity + Displacement + Direction

Standard approach for swipe detection from position tracking:

1. **Ring buffer** of (x, y, timestamp) tuples for wrist landmark (index 0), sized to ~10-15 frames (~0.3-0.5s at 30fps)
2. **Displacement** = Euclidean distance from oldest to newest position in buffer
3. **Velocity** = displacement / time_delta
4. **Direction** = angle of displacement vector, classified into 4 quadrants with dead zones (~15 degrees each side of axis boundaries)
5. **Fire condition** = velocity > min_velocity AND displacement > min_displacement
6. **After fire** = clear buffer, enter cooldown

**Key design decision:** Swipes should be detected on the **wrist landmark** (index 0), not fingertips. The wrist is the most stable landmark during hand movement -- fingertips jitter and change position relative to the hand during gestures.

**Config format:**
```yaml
swipe:
  enabled: true
  min_velocity: 1.5      # normalized units per second
  min_displacement: 0.15  # minimum travel distance (normalized)
  cooldown: 0.5           # seconds after swipe before another can fire
  buffer_size: 10         # frames of position history
```

### Pipeline Integration Points

Current pipeline:
```
camera -> detector -> classifier -> smoother -> debouncer -> keystroke
```

New pipeline with both features:
```
camera -> detector -> [distance gate] -> classifier -> smoother -> debouncer -> keystroke
                   \-> [swipe tracker] -----------------------------> keystroke
```

Key observations:
- **Distance gate sits BEFORE classifier** -- rejects far-away hands entirely, affects both static gestures and swipe detection
- **Swipe tracker is a PARALLEL path** from detector output, not sequential with static gesture classification
- **Swipe tracker needs raw landmark positions**, not classified gestures -- it watches wrist movement regardless of what static gesture the hand is making
- **Swipe has its own cooldown**, separate from the static gesture debouncer -- the two systems fire independently
- **Both paths converge at keystroke sender** -- the sender does not care whether the trigger was a static gesture or a swipe

### Existing Pipeline Touch Points

| Component | Changes Needed | Risk |
|-----------|---------------|------|
| `detector.py` (HandDetector) | None -- landmark data already sufficient | NONE |
| `classifier.py` (GestureClassifier) | Add SWIPE_LEFT/RIGHT/UP/DOWN to Gesture enum | LOW |
| `smoother.py` (GestureSmoother) | None -- swipes bypass smoother (they are instantaneous) | NONE |
| `debounce.py` (GestureDebouncer) | None -- swipes use separate cooldown | NONE |
| `config.py` (load_config) | Add `distance` and `swipe` config sections | LOW |
| `preview.py` | Add distance indicator overlay, swipe direction feedback | LOW |
| `__main__.py` | Add distance gate check, swipe tracker in main loop | MEDIUM |
| `tray.py` | Propagate new config to swipe/distance components on reload | LOW |

## Sources

- [MediaPipe Hand Landmarker Guide](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker) -- confirmed normalized vs world landmark coordinate systems, z-depth limitations
- [MediaPipe Hand Landmarker Python Guide](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python) -- confirmed HandLandmarkerResult includes hand_landmarks and hand_world_landmarks fields
- [MediaPipe z-value discussion (Issue #2439)](https://github.com/google-ai-edge/mediapipe/issues/2439) -- confirmed z is relative depth, not absolute camera distance
- [MediaPipe camera distance discussion (Issue #1153)](https://github.com/google/mediapipe/issues/1153) -- confirmed no built-in camera distance estimation from RGB
- [Hand Distance Measurement repo](https://github.com/MohamedAlaouiMhamdi/Hand-Distance-Measurement) -- example of using landmark spread as distance proxy
- [Gestop: Customizable Gesture Control (arXiv:2010.13197)](https://arxiv.org/pdf/2010.13197) -- reference for swipe detection using palm base timediff coordinates and velocity thresholds
- [Implementing a Swipe Gesture (Musing Mortoray)](https://mortoray.com/implementing-a-swipe-gesture/) -- velocity threshold patterns, distance thresholds, direction classification
- [Dynamic Hand Gesture Recognition Using MediaPipe and Transformer](https://www.mdpi.com/2673-4591/108/1/22) -- confirms frame-to-frame landmark delta approach for dynamic gestures

---
*Feature research for: gesture-keys v1.1 distance threshold and swiping gestures*
*Researched: 2026-03-21*
