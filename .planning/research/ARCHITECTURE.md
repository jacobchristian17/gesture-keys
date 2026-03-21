# Architecture: Distance Threshold and Swipe Gestures

**Domain:** Extending gesture-keys pipeline with distance gating and swipe detection
**Researched:** 2026-03-21
**Confidence:** HIGH

## Existing Pipeline (Current v1.0)

```
CameraCapture (thread) -> HandDetector (MediaPipe) -> GestureClassifier -> GestureSmoother -> GestureDebouncer -> KeystrokeSender
```

Each frame flows: `frame -> landmarks -> Gesture enum -> smoothed Gesture -> fire-or-None -> keystroke`. The pipeline lives in both `__main__.py` (preview mode) and `tray.py` (tray mode) as duplicated loop code.

## Integration Architecture for v1.1

### New Components

Two new modules, one modified enum, config changes. No existing components need architectural changes -- the new components slot into the existing linear pipeline.

```
CameraCapture -> HandDetector -> [DistanceFilter] -> GestureClassifier -> [SwipeDetector] -> GestureSmoother -> GestureDebouncer -> KeystrokeSender
                                  ^^ NEW                                    ^^ NEW
```

### Component: DistanceFilter (`distance.py`)

**Position in pipeline:** Between HandDetector output and GestureClassifier input.

**Purpose:** Gate out hands that are too far from the camera. When the hand is far away, landmarks are noisy and gestures are unreliable. The filter passes landmarks through when the hand is "close enough" and returns empty list (no hand) when too far.

**Design decision -- hand size as distance proxy:**

MediaPipe's z-coordinate is relative to the wrist, NOT absolute distance from camera. It cannot be used for distance gating. Instead, use the **bounding box diagonal of the 21 landmarks in normalized coordinates** as a proxy for hand proximity. A hand close to the camera occupies a larger fraction of the frame; a distant hand is small.

This is the correct approach because:
- Normalized x,y coordinates are always available (no extra computation)
- Bounding box size correlates directly with distance (bigger = closer)
- No camera calibration required
- Works across different camera resolutions and FOVs

**Interface:**

```python
class DistanceFilter:
    """Filters out hands that are too far from the camera.

    Uses bounding box diagonal of the 21 landmarks as a distance proxy.
    Larger diagonal = closer hand = passes filter.
    """

    def __init__(self, min_size: float = 0.15):
        """
        Args:
            min_size: Minimum bounding box diagonal (normalized 0-1).
                      Default 0.15 means hand must span at least 15%
                      of the frame diagonal. Typical values:
                      - 0.10: permissive (arm's length)
                      - 0.15: moderate (forearm distance)
                      - 0.25: strict (close to camera)
        """

    def check(self, landmarks: list) -> bool:
        """Return True if hand is close enough, False if too far."""

    @property
    def last_size(self) -> float:
        """Last computed hand size, for preview overlay display."""
```

**Implementation detail:** Compute bounding box as `max(x) - min(x)` and `max(y) - min(y)` across all 21 landmarks, then diagonal = `sqrt(dx^2 + dy^2)`. Compare against threshold. This is O(21) per frame -- negligible.

**Config integration:**

```yaml
detection:
  smoothing_window: 1
  activation_delay: 0.05
  cooldown_duration: 0.5
  min_hand_size: 0.15  # NEW -- minimum bounding box diagonal (0.0 to disable)
```

Setting `min_hand_size: 0.0` disables distance filtering entirely (backwards compatible).

### Component: SwipeDetector (`swipe.py`)

**Position in pipeline:** Between GestureClassifier output and GestureSmoother input (parallel path).

**Purpose:** Detect directional hand movement (left/right/up/down) and emit swipe gestures. Swipes are fundamentally different from static gestures -- they are temporal events detected across multiple frames, not single-frame poses.

**Design decision -- wrist trajectory tracking:**

Track the wrist landmark (index 0) position across frames. When wrist moves a sufficient distance in a consistent direction within a time window, emit a swipe gesture. Use wrist because:
- Most stable landmark (not affected by finger pose changes)
- Available whenever any hand is detected
- Movement of wrist = movement of entire hand

**Interface:**

```python
class SwipeDetector:
    """Detects directional swipe gestures from wrist movement over time.

    Tracks wrist position across frames. When wrist moves beyond
    a distance threshold in a consistent direction within a time window,
    emits a swipe gesture.
    """

    def __init__(
        self,
        min_distance: float = 0.15,
        max_duration: float = 0.5,
        min_speed: float = 0.3,
    ):
        """
        Args:
            min_distance: Minimum wrist displacement (normalized coords)
                          to qualify as a swipe.
            max_duration: Maximum seconds for the swipe motion.
                          Prevents slow drifts from triggering.
            min_speed: Minimum speed (distance/second) to qualify.
                       Prevents accidental slow movements.
        """

    def update(self, landmarks: list | None, timestamp: float) -> Gesture | None:
        """Process landmarks for current frame.

        Args:
            landmarks: 21 landmarks or None/empty if no hand detected.
            timestamp: Current time from time.perf_counter().

        Returns:
            Gesture.SWIPE_LEFT/RIGHT/UP/DOWN if swipe detected, else None.
        """

    def reset(self) -> None:
        """Clear tracking state (e.g., on config reload)."""
```

**Swipe detection algorithm:**

1. Each frame: record `(wrist.x, wrist.y, timestamp)` in a small ring buffer (last ~0.5s of frames)
2. Compare current wrist position to position at buffer start
3. Compute displacement vector `(dx, dy)` and elapsed time
4. If `distance >= min_distance` AND `elapsed <= max_duration` AND `speed >= min_speed`:
   - Determine dominant direction: if `|dx| > |dy|` then horizontal (left/right based on sign), else vertical (up/down based on sign)
   - Emit the corresponding swipe gesture
   - Enter cooldown: clear buffer, suppress for ~0.5s to prevent multi-fire
5. If hand disappears (no landmarks): clear buffer

**Critical: camera mirror effect.** Webcam images are typically not mirrored in the raw feed. When the user swipes their hand to the right (from their perspective), the wrist moves LEFT in camera coordinates. The SwipeDetector should work in raw camera coordinates, and the Gesture enum names should match the user's perspective (i.e., `SWIPE_RIGHT` = user moves hand right = wrist.x decreases in normalized coords). This mapping should be documented and potentially configurable.

**Config integration:**

```yaml
detection:
  swipe_min_distance: 0.15  # NEW
  swipe_max_duration: 0.5   # NEW
  swipe_min_speed: 0.3      # NEW

gestures:
  # Static gestures (existing)
  open_palm:
    key: win+tab
    threshold: 0.7
  # Swipe gestures (NEW)
  swipe_left:
    key: alt+left
  swipe_right:
    key: alt+right
  swipe_up:
    key: page_up
  swipe_down:
    key: page_down
```

### Modified: Gesture Enum (`classifier.py`)

Add four new members:

```python
class Gesture(Enum):
    # Existing static gestures
    OPEN_PALM = "open_palm"
    FIST = "fist"
    THUMBS_UP = "thumbs_up"
    PEACE = "peace"
    POINTING = "pointing"
    PINCH = "pinch"
    SCOUT = "scout"
    # New swipe gestures
    SWIPE_LEFT = "swipe_left"
    SWIPE_RIGHT = "swipe_right"
    SWIPE_UP = "swipe_up"
    SWIPE_DOWN = "swipe_down"
```

The Gesture enum is the shared vocabulary between classifier, swipe detector, smoother, debouncer, and keystroke sender. Adding members here is safe -- downstream components already handle `Optional[Gesture]` and look up by `.value` string.

### Modified: AppConfig (`config.py`)

Add new fields with backwards-compatible defaults:

```python
@dataclass
class AppConfig:
    camera_index: int = 0
    smoothing_window: int = 3
    activation_delay: float = 0.4
    cooldown_duration: float = 0.8
    min_hand_size: float = 0.0       # NEW -- 0.0 = disabled
    swipe_min_distance: float = 0.15  # NEW
    swipe_max_duration: float = 0.5   # NEW
    swipe_min_speed: float = 0.3      # NEW
    gestures: dict[str, dict[str, Any]] = field(default_factory=dict)
```

### Modified: Pipeline Loop (`__main__.py` and `tray.py`)

The detection loop gains two new steps. Here is the modified flow:

```python
# Detect landmarks
landmarks = detector.detect(frame, timestamp_ms)

# NEW: Distance filter
if landmarks and not distance_filter.check(landmarks):
    landmarks = []  # Treat as "no hand" if too far

# Classify static gesture
if landmarks:
    raw_gesture = classifier.classify(landmarks)
else:
    raw_gesture = None

# NEW: Check for swipe (runs in parallel with static classification)
swipe = swipe_detector.update(landmarks if landmarks else None, current_time)

# Swipe takes priority over static gesture when detected
if swipe is not None:
    gesture = swipe  # Bypass smoother -- swipes are already temporally validated
else:
    gesture = smoother.update(raw_gesture)

# Debounce and fire (unchanged)
fire_gesture = debouncer.update(gesture, current_time)
```

**Key design decision: swipes bypass the smoother.** The smoother exists to prevent single-frame flicker in static gesture classification. Swipes are inherently multi-frame events -- the SwipeDetector already accumulates evidence across frames before emitting. Passing swipes through the majority-vote smoother would add unnecessary latency and could suppress them (a single swipe event surrounded by None frames would be voted out).

**Key design decision: swipes go through the debouncer.** The debouncer prevents duplicate fires and enforces cooldown. Swipes should still respect cooldown to prevent rapid-fire. However, the activation delay should be minimal for swipes since the SwipeDetector already validates duration. Consider: swipes could bypass the debouncer too and handle their own cooldown internally. Recommendation: let swipes go through debouncer for consistency, but the debouncer's activation delay is already configured low (0.05s) so this adds negligible latency.

## Data Flow Diagram (v1.1)

```
[CameraCapture]
    | BGR frame
    v
[HandDetector]
    | 21 landmarks (or empty)
    v
[DistanceFilter] ---------> too far? -> treat as no hand
    | landmarks (or empty)
    |
    +----> [GestureClassifier]     [SwipeDetector]
    |          | Gesture|None          | Gesture|None
    |          v                       v
    |      [GestureSmoother]      (swipe takes priority)
    |          | Gesture|None          |
    |          v                       |
    |      <--- merge: swipe wins --->
    |          |
    |          v
    |      [GestureDebouncer]
    |          | fire Gesture|None
    |          v
    |      [KeystrokeSender]
    v
[Preview overlay] (optional --preview mode)
    - Hand landmarks skeleton
    - Gesture label
    - Hand size indicator (NEW)
    - FPS counter
```

## Component Boundaries

| Component | Responsibility | Inputs | Outputs | Communicates With |
|-----------|---------------|--------|---------|-------------------|
| **DistanceFilter** | Gate hands by proximity | landmarks list | bool (pass/fail) | Called by pipeline loop |
| **SwipeDetector** | Detect directional movement | landmarks + timestamp | Gesture or None | Called by pipeline loop |
| **GestureClassifier** (existing) | Classify static poses | landmarks | Gesture or None | Called by pipeline loop |
| **GestureSmoother** (existing) | Majority-vote filter | Gesture or None | Gesture or None | Receives static gestures only |
| **GestureDebouncer** (existing) | Gate firing + cooldown | Gesture or None + timestamp | Gesture or None | Receives merged gesture stream |
| **Gesture enum** (modified) | Shared vocabulary | N/A | N/A | Used by all gesture-aware components |
| **AppConfig** (modified) | Configuration values | YAML file | Dataclass fields | Read by pipeline setup |

## Patterns to Follow

### Pattern: Filter-in-Pipeline

**What:** DistanceFilter is a pass-through filter. It does not transform data -- it either passes landmarks through unchanged or replaces them with "no hand." This keeps the downstream pipeline unaware of distance filtering.

**Why:** The classifier, smoother, and debouncer already handle "no hand" (empty landmarks / None gesture). By converting "too far" into "no hand" at the filter level, no downstream code needs to change.

```python
# The filter is invisible to downstream components
if landmarks and not distance_filter.check(landmarks):
    landmarks = []  # Downstream sees "no hand detected"
```

### Pattern: Temporal Event Detector (Swipe)

**What:** SwipeDetector maintains internal state (wrist position history) and emits discrete events. Unlike the classifier which is stateless per-frame, the swipe detector is stateful across frames.

**Why:** Swipes are inherently temporal. A single frame cannot tell you if the hand is swiping or stationary. The detector must accumulate evidence over time.

**Important:** The SwipeDetector must handle:
- Hand disappearing mid-swipe (clear buffer)
- Hand reappearing (start fresh, do not connect to old trajectory)
- Very slow movement (reject via min_speed threshold)
- Diagonal movement (pick dominant axis)

### Pattern: Merge with Priority

**What:** When both the static classifier and swipe detector produce results in the same frame, swipe wins.

**Why:** Swipes are rarer and more intentional. A user physically moving their hand across the frame is clearly swiping, even if mid-swipe the hand briefly resembles "open_palm." Static gestures fire constantly when the hand is visible; swipes fire once per motion. Giving swipe priority prevents static gestures from "stealing" the swipe event.

## Anti-Patterns to Avoid

### Anti-Pattern: Using MediaPipe Z-Coordinate for Distance

**What:** Using `landmark.z` to estimate how far the hand is from the camera.
**Why bad:** MediaPipe z-coordinates are relative to the wrist landmark, not the camera. The wrist itself has z approximately 0. The z values represent depth of fingertips relative to the wrist palm plane, not absolute camera distance. Using z for distance gating would not work.
**Instead:** Use bounding box size of the 21 landmarks in normalized x,y coordinates as the distance proxy.

### Anti-Pattern: Smoothing Swipe Gestures

**What:** Running swipe detector output through the majority-vote GestureSmoother.
**Why bad:** The smoother requires a gesture to be the majority in a window of N frames. A swipe is a single-frame event emission after multi-frame accumulation. The smoother would see `[None, None, SWIPE_LEFT, None, None]` and vote it out.
**Instead:** Swipe gestures bypass the smoother and go directly to the debouncer (or handle their own cooldown).

### Anti-Pattern: Tracking All 21 Landmarks for Swipe

**What:** Computing average position or centroid of all landmarks to track hand movement.
**Why bad:** Finger positions change during a swipe (hand may open/close). Averaging all landmarks introduces noise from finger motion unrelated to the swipe direction.
**Instead:** Track only the wrist landmark (index 0), which is the most stable point during hand translation.

### Anti-Pattern: Duplicate Pipeline Code

**What:** The current codebase has the pipeline loop duplicated in `__main__.py` (preview mode) and `tray.py` (tray mode). Adding distance filter and swipe detector means modifying both.
**Why bad:** Two copies of the pipeline that must stay in sync. Adding v1.1 features to both increases the risk of divergence.
**Mitigation for v1.1:** Accept the duplication for now. Refactoring the pipeline into a shared function/class is a separate concern. For this milestone, modify both loops identically. Flag for future cleanup.

## Build Order (Dependency Chain)

Build order is driven by dependencies between new components:

```
Phase 1: Gesture enum expansion (classifier.py)
    |   Add SWIPE_LEFT/RIGHT/UP/DOWN to Gesture enum
    |   Zero risk -- additive change, nothing breaks
    |
Phase 2: Config expansion (config.py + config.yaml)
    |   Add min_hand_size, swipe_* fields to AppConfig
    |   Add load_config parsing for new fields
    |   Backwards compatible -- new fields have defaults
    |
Phase 3: DistanceFilter (distance.py) -- NEW module
    |   Depends on: landmarks list format (already stable)
    |   Pure logic, easily unit tested
    |   No interaction with other new components
    |
Phase 4: SwipeDetector (swipe.py) -- NEW module
    |   Depends on: Gesture enum (Phase 1), landmarks format
    |   Stateful but self-contained
    |   Unit testable with synthetic landmark sequences
    |
Phase 5: Pipeline integration (__main__.py + tray.py)
    |   Wire DistanceFilter and SwipeDetector into both loops
    |   Depends on: Phases 1-4 complete
    |   Integration testing with camera
    |
Phase 6: Preview overlay updates (preview.py)
    |   Show hand size indicator, swipe direction feedback
    |   Depends on: Phase 5 (needs DistanceFilter.last_size)
    |   Visual polish, not blocking for functionality
```

**Phase 3 and 4 are independent** and can be built in parallel or either order. Phase 5 depends on both. Phase 6 is optional polish.

**Recommended order: 1 -> 2 -> 3 -> 4 -> 5 -> 6** because each phase builds cleanly on the prior one and can be tested before moving forward.

## Scalability Considerations

| Concern | Current (v1.0) | With v1.1 | Notes |
|---------|-----------------|-----------|-------|
| Per-frame computation | ~0.1ms (classify) | ~0.2ms (classify + distance check + swipe tracking) | Negligible -- all pure math on 21 landmarks |
| Memory | Smoother buffer (3 frames) | + swipe wrist buffer (~15 frames at 30fps) | Trivially small |
| Config complexity | 7 gestures | 11 gestures (7 static + 4 swipe) + 4 new detection params | Still manageable in flat YAML |
| Pipeline stages | 4 | 6 | Linear pipeline, no branching complexity at runtime |

## Sources

- [MediaPipe Hand Landmarks Z-value discussion](https://github.com/google/mediapipe/issues/742) -- confirms z is relative to wrist, not camera distance
- [MediaPipe distance from camera discussion](https://github.com/google/mediapipe/issues/1153) -- confirms bounding box size is the practical proxy
- [MediaPipe Hand Landmarker Python guide](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python) -- landmark coordinate system documentation
- [On-Device, Real-Time Hand Tracking with MediaPipe](https://research.google/blog/on-device-real-time-hand-tracking-with-mediapipe/) -- architecture of palm detection + landmark regression pipeline
- [Dynamic Hand Gesture Recognition Using MediaPipe and Transformer](https://www.mdpi.com/2673-4591/108/1/22) -- frame-to-frame landmark tracking for temporal gestures

---
*Architecture research for: gesture-keys v1.1 distance threshold and swipe gestures*
*Researched: 2026-03-21*
