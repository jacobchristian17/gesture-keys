# Stack Research

**Domain:** Distance threshold and swipe gesture detection for gesture-keys v1.1
**Researched:** 2026-03-21
**Confidence:** HIGH

## Executive Summary

No new dependencies are needed. Both distance-based gesture gating and swipe detection can be implemented entirely with data already available from MediaPipe's HandLandmarkerResult, combined with simple math (stdlib `math` module) and frame-over-frame position tracking using Python's `collections.deque`. The existing stack (mediapipe, opencv-python, pynput, pystray, PyYAML) is sufficient.

## Recommended Stack Additions

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **None** | -- | -- | No new packages needed. All techniques use existing MediaPipe output + stdlib math. |

### Techniques (Not Libraries)

These are the implementation approaches, not new dependencies.

| Technique | Purpose | Inputs | Why This Approach |
|-----------|---------|--------|-------------------|
| Palm span proxy | Estimate hand distance from camera | `hand_landmarks` (image-space normalized) | Euclidean distance between WRIST(0) and MIDDLE_MCP(9) shrinks as hand moves away. No calibration needed for threshold gating -- just compare against a configurable normalized value. |
| Wrist position delta tracking | Detect swipe direction | `hand_landmarks[0]` (WRIST) x,y across N frames | WRIST is the most stable landmark (least jitter from finger movement). Track position in a ring buffer, compute displacement vector over a time window. |
| Velocity thresholding | Distinguish intentional swipes from drift | Wrist displacement / elapsed time | Require minimum velocity to trigger swipe, preventing slow hand repositioning from firing. |
| Direction classification | Map movement vector to swipe direction | Displacement vector (dx, dy) | Use `atan2(dy, dx)` to get angle, bin into 4 quadrants (left/right/up/down). Require dominant axis magnitude > minor axis to reject diagonal noise. |

## Distance Threshold: Technical Design

### Approach: Palm Span as Distance Proxy

**What:** Measure the Euclidean distance between WRIST (landmark 0) and MIDDLE_MCP (landmark 9) in normalized image coordinates. This span is a proxy for how close the hand is to the camera -- closer hand = larger span, farther hand = smaller span.

**Why WRIST-to-MIDDLE_MCP:**
- These are skeletal joints, not fingertips -- they are stable regardless of which gesture is being made (fist, open palm, pointing all have the same wrist-to-MCP distance in real space)
- The pair spans the palm length, giving a good signal-to-noise ratio
- Both are reliably detected with low jitter

**Why NOT use world_landmarks or z-coordinate:**
- `world_landmarks` are in meters with origin at the hand's geometric center -- they encode hand-relative 3D pose, not distance from camera. The origin moves with the hand, so absolute camera distance is not available from world_landmarks alone.
- The `z` coordinate in image-space landmarks represents depth relative to the wrist, not distance from camera. Per MediaPipe docs: "the depth at the wrist being the origin, and the smaller the value the closer the landmark is to the camera." This is inter-landmark depth, not camera distance.
- Palm span in normalized image coordinates is a direct, reliable proxy that requires zero calibration and works across different cameras and resolutions.

**Formula:**
```python
import math

def palm_span(landmarks) -> float:
    """Euclidean distance between WRIST and MIDDLE_MCP in normalized coords."""
    wrist = landmarks[0]   # WRIST
    mcp = landmarks[9]     # MIDDLE_MCP
    dx = wrist.x - mcp.x
    dy = wrist.y - mcp.y
    return math.sqrt(dx * dx + dy * dy)
```

**Config integration:**
```yaml
detection:
  distance_threshold: 0.15  # minimum palm span (normalized) to accept gestures
```

A palm span below the threshold means the hand is too far away -- skip classification entirely. Typical values: approximately 0.25 at arm's length, approximately 0.10 at 1.5m away, approximately 0.35+ when hand is close to camera. Users tune via config; a default of 0.15 is a sensible starting point (rejects hands roughly >1m away).

**Integration point:** This check goes in the pipeline BEFORE the classifier. If palm span is below threshold, return no gesture (same as no hand detected). This means the smoother, debouncer, and keystroke sender are unaffected.

### Alternative Considered: Bounding Box Area

Could compute the bounding box of all 21 landmarks and use its area as a proxy. Rejected because:
- Bounding box area changes with gesture (open palm is much larger than fist)
- Palm span between skeletal joints is gesture-invariant
- Bounding box requires iterating all 21 landmarks; palm span needs only 2

## Swipe Detection: Technical Design

### Approach: Wrist Velocity in a Sliding Window

**What:** Track the WRIST landmark position across frames in a ring buffer. When displacement over a time window exceeds a velocity threshold and has a clear dominant direction, fire the corresponding swipe gesture.

**Why WRIST landmark:**
- Most stable point on the hand -- fingertip landmarks jitter significantly during finger movement
- Represents whole-hand translation, not finger articulation
- Already indexed as landmark 0 in the existing codebase

**Core algorithm:**
```python
from collections import deque
import math

class SwipeDetector:
    def __init__(self, min_velocity=0.8, window_seconds=0.3, cooldown=0.5):
        self._history = deque(maxlen=30)  # (x, y, timestamp) tuples
        self._min_velocity = min_velocity       # normalized units/second
        self._window_seconds = window_seconds   # look-back window
        self._cooldown = cooldown
        self._last_swipe_time = 0.0

    def update(self, wrist_x, wrist_y, timestamp):
        """Add wrist position. Returns swipe direction string or None."""
        self._history.append((wrist_x, wrist_y, timestamp))

        if timestamp - self._last_swipe_time < self._cooldown:
            return None

        # Find oldest sample within the time window
        oldest = None
        for x, y, t in self._history:
            if timestamp - t <= self._window_seconds:
                oldest = (x, y, t)
                break

        if oldest is None:
            return None

        dx = wrist_x - oldest[0]
        dy = wrist_y - oldest[1]
        dt = timestamp - oldest[2]

        if dt < 0.05:  # need at least ~50ms of data
            return None

        velocity = math.sqrt(dx*dx + dy*dy) / dt

        if velocity < self._min_velocity:
            return None

        # Require dominant axis (reject diagonals)
        if abs(dx) > abs(dy) * 1.5:
            direction = "swipe_right" if dx > 0 else "swipe_left"
        elif abs(dy) > abs(dx) * 1.5:
            direction = "swipe_down" if dy > 0 else "swipe_up"
        else:
            return None  # diagonal -- ignore

        self._last_swipe_time = timestamp
        self._history.clear()  # reset after firing
        return direction
```

**Key design decisions:**

1. **Sliding window, not frame-to-frame delta:** Frame-to-frame is too noisy (single dropped frame causes huge velocity spike). A 0.3s window smooths out jitter while still being responsive.

2. **Velocity threshold, not displacement threshold:** A slow hand repositioning over 2 seconds covers the same distance as a quick swipe. Velocity (displacement/time) distinguishes intentional swipes from drift.

3. **Dominant axis requirement (1.5x ratio):** Rejects diagonal motion that does not clearly map to a single direction. The 1.5x multiplier means horizontal displacement must be at least 1.5x vertical to register as left/right. Tunable.

4. **Cooldown + history clear after fire:** Prevents a single swipe from firing multiple times as the hand decelerates. Clearing the history means the next swipe starts fresh.

5. **Swipe gestures bypass the static gesture pipeline:** Swipes are motion events, not poses. They should not go through the smoother/debouncer (which are designed for held poses). Swipes fire immediately when detected, with their own cooldown.

**Config integration:**
```yaml
gestures:
  swipe_left:
    key: alt+left
  swipe_right:
    key: alt+right
  swipe_up:
    key: ctrl+up
  swipe_down:
    key: ctrl+down

detection:
  swipe_velocity: 0.8      # normalized units/second
  swipe_window: 0.3         # seconds to measure velocity over
  swipe_cooldown: 0.5       # seconds between swipe fires
```

**Integration point:** The SwipeDetector runs in parallel with the static gesture classifier. Each frame, the wrist position is fed to both the SwipeDetector and the classifier. If SwipeDetector fires, it takes priority (suppress static gesture for that frame). The SwipeDetector outputs a string like "swipe_left" that maps directly to config keys.

## Pipeline Integration Summary

```
Camera Frame
    |
    v
HandDetector.detect() -- returns landmarks (or empty)
    |
    v
[NEW] Distance gate -- palm_span(landmarks) >= threshold?
    |                        |
    | YES                    | NO --> treat as no hand
    v                        v
+---+---+              return None
|       |
v       v
SwipeDetector.update(wrist)    GestureClassifier.classify(landmarks)
    |                               |
    | swipe detected?               v
    | YES --> fire swipe key    GestureSmoother.update()
    | NO  --> continue               |
    v                               v
                              GestureDebouncer.update()
                                    |
                                    v
                              KeystrokeSender (if fired)
```

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| Palm span (WRIST-MIDDLE_MCP) for distance | Z-coordinate depth | Z is relative to wrist, not camera distance |
| Palm span for distance | World landmarks | Origin is at hand center, not camera; does not encode camera distance |
| Palm span for distance | Bounding box area | Area changes with gesture shape; palm span is gesture-invariant |
| Wrist position tracking for swipe | Fingertip tracking | Fingertips jitter during gesture transitions; wrist is stable |
| Velocity threshold for swipe | Displacement-only threshold | Slow drift covers same distance as fast swipe; velocity discriminates intent |
| Sliding window velocity | Frame-to-frame delta | Too noisy; dropped frames cause false spikes |
| Separate swipe pipeline | Swipes through smoother/debouncer | Smoother is designed for held poses (majority vote); swipes are instantaneous events with opposite temporal characteristics |
| `collections.deque` for history | numpy arrays | Overkill; deque is stdlib, maxlen handles ring buffer natively, no dependency needed |

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **numpy** for swipe math | Only need Euclidean distance and atan2 on 2-3 points per frame; stdlib `math` is sufficient and avoids adding a direct dependency | `math.sqrt`, `math.atan2` |
| **scipy** for signal filtering | Smoothing is already handled by GestureSmoother; swipe detection uses a time window which is inherently smooth | Sliding window approach |
| **MediaPipe GestureRecognizer** task | Different task than HandLandmarker; would require switching models, losing the existing landmark-based classifier, and adds a heavier model for recognizing only 7 static gestures (no swipe support anyway) | Keep HandLandmarker + custom classifier |
| **OpenCV optical flow** | Operates on pixel-level motion, not semantic hand position; much heavier compute for worse results when landmarks are already available | Landmark position tracking |
| **Machine learning for swipe classification** | 4-direction swipe from a velocity vector is trivially solved with atan2 and axis dominance check; ML adds training data requirements and complexity for no benefit | Rule-based direction classification |
| **Kalman filter for landmark smoothing** | The existing GestureSmoother handles classification noise; wrist position is already stable enough; Kalman filter adds complexity without measurable benefit for this use case | Raw wrist position + time window averaging |

## Version Compatibility

No new packages, so no new compatibility concerns. Existing stack is unchanged:

| Package | Current | Compatible With | Notes |
|---------|---------|-----------------|-------|
| mediapipe | >=0.10.x | HandLandmarkerResult includes hand_world_landmarks since 0.10.0 | Not needed for distance proxy, but available if future features need world-space data |
| opencv-python | >=4.x | mediapipe >=0.10.x | Already in use, no changes |
| collections.deque | stdlib | All Python 3.x | No version concern; used for swipe history ring buffer |

## Sources

- [MediaPipe Hand Landmarker docs (Google AI Edge)](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker) -- confirmed output includes hand_landmarks, hand_world_landmarks, handedness; z-coordinate semantics verified (HIGH confidence)
- [MediaPipe Hands legacy docs](https://mediapipe.readthedocs.io/en/latest/solutions/hands.html) -- confirmed z-coordinate is "depth at wrist being origin", x/y normalized to [0.0, 1.0], z magnitude "uses roughly the same scale as x" (HIGH confidence)
- [MediaPipe Hand Landmarker Python guide](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python) -- confirmed HandLandmarkerResult structure with hand_landmarks and hand_world_landmarks arrays (HIGH confidence)
- [Hand-Distance-Measurement repo](https://github.com/MohamedAlaouiMhamdi/Hand-Distance-Measurement) -- uses landmark-pair distances with polynomial regression for cm conversion; validates landmark distance approach but calibration is unnecessary for threshold gating (MEDIUM confidence)
- Existing codebase (`classifier.py`, `detector.py`, `smoother.py`, `debounce.py`) -- confirmed landmark indices, coordinate access patterns, current pipeline architecture (HIGH confidence)

---
*Stack research for: gesture-keys v1.1 distance threshold and swipe gestures*
*Researched: 2026-03-21*
