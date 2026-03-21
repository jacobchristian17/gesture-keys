# Phase 1: Detection and Preview - Research

**Researched:** 2026-03-21
**Domain:** MediaPipe hand landmark detection, OpenCV preview, rule-based gesture classification
**Confidence:** HIGH

## Summary

Phase 1 builds the foundation: capture webcam frames, detect hand landmarks via the MediaPipe Task API, classify 6 gestures from landmark geometry, and display results in an OpenCV preview window. The stack is well-established -- MediaPipe 0.10.33 provides the HandLandmarker Task API with built-in handedness detection (left/right), OpenCV handles camera capture and rendering, and gesture classification uses straightforward rule-based finger-state comparisons against landmark positions.

The critical technical nuance is that the Task API's `HandLandmarkerResult` is incompatible with MediaPipe's legacy `drawing_utils.draw_landmarks()` -- the result objects use different data structures than the legacy protobuf format. The workaround is to convert landmarks to `NormalizedLandmarkList` proto format before drawing. This is a well-documented pattern from the official sample notebook.

**Primary recommendation:** Use MediaPipe Task API `HandLandmarker` in VIDEO running mode with `detect_for_video()`, OpenCV `VideoCapture` on a daemon thread for non-blocking capture, and rule-based gesture classification comparing finger tip Y-coordinates against PIP joint Y-coordinates.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Full 21-landmark skeleton with connections drawn on the camera feed (MediaPipe default visualization style)
- Solid bottom bar below the feed: gesture label bottom-left, FPS counter bottom-right
- Window size: 640x480 (standard VGA, matches common webcam resolution)
- Left hand ignored silently -- no overlay, no label, as if it doesn't exist
- 3-frame majority-vote smoothing window (~100ms at 30fps)
- Ambiguous poses fall to None -- conservative approach, only fire on clear matches
- Priority-ordered classification: PINCH > FIST > THUMBS_UP > POINTING > PEACE > OPEN_PALM > None
- Gesture thresholds configurable per-gesture in config.yaml (default 0.7)
- Camera index configurable in config.yaml (default 0)
- Package layout: `gesture_keys/` with separate modules (detector.py, classifier.py, preview.py, config.py)
- Entry point: `python -m gesture_keys --preview`
- Dependencies: requirements.txt with pip/venv
- CLI: argparse for flag parsing (--preview, --help, future --config override)
- Default config.yaml ships with sensible key mappings pre-configured
- Gesture changes only (print on transitions, not every frame)
- None transitions printed (shows gesture start/end lifecycle)
- Brief startup banner: version, camera info, config loaded, gesture count
- Python logging module with levels (INFO for gesture changes/startup, DEBUG for frame-level)
- YAML config with sections: camera, detection, gestures
- Each gesture entry has `key` (mapping) and `threshold` (sensitivity)
- Sensible defaults: open_palm=space, fist=ctrl+z, thumbs_up=ctrl+s, peace=ctrl+c, pointing=enter, pinch=ctrl+v
- Smoothing window size in detection section
- Config.yaml structure follows nested format: camera.index, detection.smoothing_window, gestures.<name>.key/threshold
- Startup banner should be concise (4 lines max): version, camera, config, "Detection started..."
- Console timestamp format: [HH:MM:SS] (no milliseconds for change-only logging)

### Claude's Discretion
- Exact landmark drawing colors and line thickness
- OpenCV window title and close behavior (ESC key, window X button)
- Logging format string and timestamp precision
- Error handling for camera not found / MediaPipe init failure
- Thread architecture for camera capture vs processing
- MediaPipe Task API model download and caching approach

### Deferred Ideas (OUT OF SCOPE)
- Both-hands support (left + right) with per-hand gesture mappings -- deferred to v2 (DET-05)
- Verbose startup mode showing all gesture mappings and thresholds -- could add --verbose flag later
- Continuous frame-by-frame logging mode for debugging -- could add with DEBUG log level
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DET-01 | Detect 6 hand gestures (open palm, fist, thumbs up, peace, pointing, pinch) from webcam via MediaPipe Task API landmarks | HandLandmarker Task API provides 21 landmarks per hand; rule-based classifier compares finger tip vs PIP joint positions |
| DET-02 | Apply frame smoothing (majority-vote window) before debounce to prevent flicker | 3-frame circular buffer with collections.Counter majority vote; ~100ms at 30fps |
| DET-03 | Capture camera frames on a separate thread (non-blocking) | Daemon thread with OpenCV VideoCapture; latest-frame-only pattern avoids queue buildup |
| DET-04 | Right-hand detection only (left hand ignored) | HandLandmarkerResult includes handedness classification per hand; filter by category_name == "Right" |
| DEV-01 | `--preview` flag opens camera preview window | argparse boolean flag; OpenCV imshow loop with waitKey; solid bottom bar overlay |
| DEV-02 | Console output of detected gestures in preview mode | Python logging at INFO level; print on gesture transitions only |
| DEV-03 | FPS display in preview window | Track frame times with time.perf_counter(); render in bottom bar bottom-right |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mediapipe | 0.10.33 | Hand landmark detection via Task API | Official Google library; provides HandLandmarker with built-in handedness, 21-landmark model |
| opencv-python | 4.x (latest) | Camera capture, frame rendering, preview window | De facto standard for Python computer vision; VideoCapture, imshow, drawing primitives |
| PyYAML | 6.x | Config file parsing | Standard YAML parser for Python; simple API |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy | (mediapipe dependency) | Array operations on frames and landmarks | Comes with mediapipe; used for image copying and coordinate math |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| MediaPipe Task API | MediaPipe Solutions (legacy) | Solutions API is deprecated; Task API is the current recommended approach |
| Rule-based classifier | ML classifier (TensorFlow/sklearn) | ML adds training data requirement and complexity; rule-based is sufficient for 6 distinct gestures |
| VIDEO running mode | LIVE_STREAM running mode | LIVE_STREAM is async with callbacks; VIDEO mode is synchronous and simpler for our threaded capture pattern |

**Installation:**
```bash
pip install mediapipe opencv-python PyYAML
```

## Architecture Patterns

### Recommended Project Structure
```
gesture_keys/
    __init__.py          # Package init, version
    __main__.py          # Entry point: argparse, main loop
    detector.py          # HandLandmarker wrapper, camera thread
    classifier.py        # Rule-based gesture classification
    preview.py           # OpenCV window rendering
    config.py            # YAML config loading
config.yaml              # Default configuration
requirements.txt         # Dependencies
```

### Pattern 1: Threaded Camera Capture
**What:** Daemon thread continuously reads frames from VideoCapture; main thread consumes latest frame only.
**When to use:** Always -- camera I/O blocks ~30ms per frame; thread overlap hides this latency.
**Example:**
```python
# Source: Standard OpenCV threading pattern (multiple GitHub refs)
import threading
import cv2

class CameraCapture:
    def __init__(self, camera_index=0):
        self.cap = cv2.VideoCapture(camera_index)
        self.frame = None
        self.ret = False
        self.stopped = False
        self.lock = threading.Lock()

    def start(self):
        thread = threading.Thread(target=self._update, daemon=True)
        thread.start()
        return self

    def _update(self):
        while not self.stopped:
            ret, frame = self.cap.read()
            with self.lock:
                self.ret = ret
                self.frame = frame

    def read(self):
        with self.lock:
            return self.ret, self.frame.copy() if self.frame is not None else None

    def stop(self):
        self.stopped = True
        self.cap.release()
```

### Pattern 2: Task API HandLandmarker with VIDEO Mode
**What:** Create HandLandmarker in VIDEO mode; call detect_for_video() synchronously per frame with monotonic timestamp.
**When to use:** For webcam processing where we control the frame loop.
**Example:**
```python
# Source: https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python
import mediapipe as mp
import time

BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

options = HandLandmarkerOptions(
    base_options=BaseOptions(model_asset_path='hand_landmarker.task'),
    running_mode=VisionRunningMode.VIDEO,
    num_hands=2,  # detect both, filter right-hand in code
    min_hand_detection_confidence=0.5,
    min_hand_presence_confidence=0.5,
    min_tracking_confidence=0.5,
)

with HandLandmarker.create_from_options(options) as landmarker:
    # Per frame:
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    timestamp_ms = int(time.time() * 1000)
    result = landmarker.detect_for_video(mp_image, timestamp_ms)
```

### Pattern 3: Landmark-to-Proto Conversion for Drawing
**What:** Convert Task API landmarks to legacy NormalizedLandmarkList for draw_landmarks compatibility.
**When to use:** Every time you draw landmarks from Task API results.
**Example:**
```python
# Source: https://github.com/google-ai-edge/mediapipe/issues/5361
from mediapipe.framework.formats import landmark_pb2
from mediapipe import solutions

def draw_hand_landmarks(image, hand_landmarks):
    """Convert Task API landmarks to proto and draw."""
    hand_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
    hand_landmarks_proto.landmark.extend([
        landmark_pb2.NormalizedLandmark(
            x=landmark.x, y=landmark.y, z=landmark.z
        )
        for landmark in hand_landmarks
    ])
    solutions.drawing_utils.draw_landmarks(
        image,
        hand_landmarks_proto,
        solutions.hands.HAND_CONNECTIONS,
        solutions.drawing_styles.get_default_hand_landmarks_style(),
        solutions.drawing_styles.get_default_hand_connections_style(),
    )
```

### Pattern 4: Rule-Based Gesture Classification
**What:** Determine finger states (extended/curled) by comparing tip landmark Y to PIP joint Y; classify gesture from finger state combination.
**When to use:** For the 6 target gestures; no ML training needed.
**Example:**
```python
# Source: Composite from multiple community implementations
# MediaPipe Hand Landmark Indices:
# 0=WRIST, 1=THUMB_CMC, 2=THUMB_MCP, 3=THUMB_IP, 4=THUMB_TIP
# 5=INDEX_MCP, 6=INDEX_PIP, 7=INDEX_DIP, 8=INDEX_TIP
# 9=MIDDLE_MCP, 10=MIDDLE_PIP, 11=MIDDLE_DIP, 12=MIDDLE_TIP
# 13=RING_MCP, 14=RING_PIP, 15=RING_DIP, 16=RING_TIP
# 17=PINKY_MCP, 18=PINKY_PIP, 19=PINKY_DIP, 20=PINKY_TIP

FINGER_TIPS = [8, 12, 16, 20]       # Index, Middle, Ring, Pinky tips
FINGER_PIPS = [6, 10, 14, 18]       # Corresponding PIP joints

def is_finger_extended(landmarks, tip_idx, pip_idx):
    """Finger is extended if tip is above (lower Y) PIP joint."""
    return landmarks[tip_idx].y < landmarks[pip_idx].y

def is_thumb_extended(landmarks):
    """Thumb extended if tip is further from palm than IP joint.
    Compare x-distance from wrist for right hand."""
    return abs(landmarks[4].x - landmarks[0].x) > abs(landmarks[3].x - landmarks[0].x)

def thumb_index_pinch(landmarks, threshold=0.05):
    """Pinch: thumb tip close to index tip."""
    dx = landmarks[4].x - landmarks[8].x
    dy = landmarks[4].y - landmarks[8].y
    return (dx*dx + dy*dy) ** 0.5 < threshold
```

### Pattern 5: Majority-Vote Smoothing
**What:** Buffer last N gesture classifications; output the most common one.
**When to use:** Before reporting gesture to prevent flicker from single-frame misclassifications.
**Example:**
```python
from collections import deque, Counter

class GestureSmoother:
    def __init__(self, window_size=3):
        self.buffer = deque(maxlen=window_size)

    def update(self, gesture):
        self.buffer.append(gesture)
        if len(self.buffer) < self.buffer.maxlen:
            return None
        counts = Counter(self.buffer)
        most_common, count = counts.most_common(1)[0]
        return most_common
```

### Anti-Patterns to Avoid
- **Using LIVE_STREAM mode with manual frame loop:** LIVE_STREAM uses async callbacks which add complexity; VIDEO mode is simpler and provides the same result when you control the frame timing.
- **Drawing landmarks directly from Task API result:** Will crash with `AttributeError: 'Landmark' object has no attribute 'HasField'`. Always convert to proto first.
- **Reading camera on main thread:** Blocks ~30ms per read; UI becomes sluggish. Always use a separate capture thread.
- **Using mediapipe.solutions.hands (legacy):** This is the deprecated Solutions API. Use `mediapipe.tasks.vision.HandLandmarker` (Task API) instead.
- **Polling cv2.waitKey(0):** Blocks forever. Use `cv2.waitKey(1)` for ~1ms poll in the render loop.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Hand landmark detection | Custom ML model | MediaPipe HandLandmarker Task API | Pre-trained, 21-landmark model, handles palm detection + tracking |
| Landmark drawing on frames | Custom OpenCV circle/line calls for 21 points | `solutions.drawing_utils.draw_landmarks()` with proto conversion | Handles all 21 points, connections, proper styling |
| Drawing styles | Custom color schemes | `solutions.drawing_styles.get_default_hand_landmarks_style()` | Consistent, tested, finger-group color coding |
| YAML config parsing | Custom file parser | PyYAML `yaml.safe_load()` | Handles nested structures, type coercion, error messages |
| CLI argument parsing | Manual sys.argv parsing | argparse | Standard library, --help generation, type validation |

**Key insight:** MediaPipe handles the hard ML/vision work. Our code is glue: capture frames, pass to MediaPipe, classify from landmarks, render results.

## Common Pitfalls

### Pitfall 1: Task API vs Legacy API Confusion
**What goes wrong:** Using `mediapipe.solutions.hands.Hands()` (legacy) instead of `mediapipe.tasks.vision.HandLandmarker` (Task API). Legacy API works but is deprecated and has different result formats.
**Why it happens:** Most tutorials and StackOverflow answers still reference the legacy API.
**How to avoid:** Always import from `mediapipe.tasks.python.vision`. Use `HandLandmarker.create_from_options()`.
**Warning signs:** Import path contains `mediapipe.solutions.hands` for detection (drawing utils from solutions is fine).

### Pitfall 2: draw_landmarks Incompatibility
**What goes wrong:** Passing Task API `hand_landmarks` list directly to `draw_landmarks()` causes `AttributeError`.
**Why it happens:** Task API returns plain objects; legacy draw expects protobuf objects with `HasField()`.
**How to avoid:** Convert landmarks to `landmark_pb2.NormalizedLandmarkList` before drawing (see Pattern 3).
**Warning signs:** `AttributeError: 'Landmark' object has no attribute 'HasField'` or `'list' object has no attribute 'landmark'`.

### Pitfall 3: Monotonic Timestamp Requirement
**What goes wrong:** `detect_for_video()` fails or produces wrong results if timestamps are not strictly increasing.
**Why it happens:** VIDEO mode expects sequential timestamps like a video file.
**How to avoid:** Use `int(time.time() * 1000)` or a monotonic counter. Never pass the same timestamp twice.
**Warning signs:** RuntimeError about non-monotonic timestamps.

### Pitfall 4: BGR vs RGB Color Space
**What goes wrong:** MediaPipe expects RGB input; OpenCV captures in BGR. Results are wrong or detection fails silently.
**Why it happens:** OpenCV's default is BGR; MediaPipe's default is RGB.
**How to avoid:** `cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)` before creating `mp.Image`. Convert back to BGR for OpenCV display.
**Warning signs:** Poor detection accuracy, landmarks in wrong positions.

### Pitfall 5: Handedness Label is Mirrored
**What goes wrong:** MediaPipe reports handedness as if looking at the person (mirror image). A right hand may be labeled "Left" in a selfie-style webcam feed.
**Why it happens:** MediaPipe uses a non-mirrored convention by default.
**How to avoid:** Test with your actual webcam. The `handedness[0].category_name` field indicates the hand from the model's perspective. With a front-facing webcam, your right hand will typically be labeled "Right" (MediaPipe corrects for this in recent versions). Verify empirically and adjust the filter if needed.
**Warning signs:** Right hand gestures being ignored, left hand gestures being detected.

### Pitfall 6: Thumb Extended Check is Different from Other Fingers
**What goes wrong:** Using Y-coordinate comparison for thumb like other fingers gives wrong results.
**Why it happens:** Thumb moves laterally (X-axis) not vertically. Tip-above-PIP logic fails.
**How to avoid:** Compare thumb tip X-distance from wrist vs thumb IP X-distance from wrist. Or use distance from thumb tip to index MCP.
**Warning signs:** Thumb always detected as extended or always curled regardless of actual position.

### Pitfall 7: Model File Not Found
**What goes wrong:** HandLandmarker creation fails because `hand_landmarker.task` model file is missing.
**Why it happens:** The model must be downloaded separately; it is not bundled with the mediapipe pip package.
**How to avoid:** Download at build/install time or on first run. Cache in a known location. URL: `https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task`
**Warning signs:** FileNotFoundError or RuntimeError on HandLandmarker creation.

## Code Examples

### Complete Main Loop Pattern
```python
# Source: Composite from official docs + community patterns
import cv2
import mediapipe as mp
import time

def main_loop(camera_capture, landmarker, classifier, smoother, preview=False):
    """Main detection loop."""
    prev_gesture = None

    while True:
        ret, frame = camera_capture.read()
        if not ret or frame is None:
            continue

        # BGR -> RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        timestamp_ms = int(time.time() * 1000)

        result = landmarker.detect_for_video(mp_image, timestamp_ms)

        # Filter to right hand only
        gesture = None
        for i, handedness in enumerate(result.handedness):
            if handedness[0].category_name == "Right":
                landmarks = result.hand_landmarks[i]
                raw_gesture = classifier.classify(landmarks)
                gesture = smoother.update(raw_gesture)
                if preview:
                    draw_hand_landmarks(frame, landmarks)
                break  # Only process first right hand

        # Log transitions
        if gesture != prev_gesture:
            logging.info(f"Gesture: {gesture}")
            prev_gesture = gesture

        if preview:
            render_preview(frame, gesture)
            if cv2.waitKey(1) & 0xFF == 27:  # ESC
                break
```

### Config.yaml Structure
```yaml
# Source: User decision from CONTEXT.md
camera:
  index: 0

detection:
  smoothing_window: 3

gestures:
  open_palm:
    key: space
    threshold: 0.7
  fist:
    key: ctrl+z
    threshold: 0.7
  thumbs_up:
    key: ctrl+s
    threshold: 0.7
  peace:
    key: ctrl+c
    threshold: 0.7
  pointing:
    key: enter
    threshold: 0.7
  pinch:
    key: ctrl+v
    threshold: 0.7
```

### Bottom Bar Rendering
```python
# Source: Standard OpenCV rendering pattern
import cv2
import numpy as np

BAR_HEIGHT = 40

def render_preview(frame, gesture_name, fps):
    """Render frame with solid bottom bar showing gesture and FPS."""
    h, w = frame.shape[:2]
    # Create bottom bar
    bar = np.zeros((BAR_HEIGHT, w, 3), dtype=np.uint8)
    bar[:] = (50, 50, 50)  # Dark gray

    # Gesture label bottom-left
    label = gesture_name if gesture_name else "None"
    cv2.putText(bar, label, (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # FPS counter bottom-right
    fps_text = f"FPS: {fps:.0f}"
    text_size = cv2.getTextSize(fps_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
    cv2.putText(bar, fps_text, (w - text_size[0] - 10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)

    # Stack frame + bar
    display = np.vstack([frame, bar])
    cv2.imshow("Gesture Keys", display)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `mediapipe.solutions.hands.Hands()` | `mediapipe.tasks.vision.HandLandmarker` | MediaPipe 0.10.x (2023+) | Task API is recommended; Solutions API deprecated |
| Protobuf result objects | Plain Python objects in Task API | MediaPipe 0.10.x | Must convert back to proto for draw_landmarks |
| Manual palm detection + landmark | Single bundled `.task` model | MediaPipe Tasks | Download one file, handles both stages |

**Deprecated/outdated:**
- `mediapipe.solutions.hands` (Solutions API): Still functional but deprecated. All new code should use Task API.
- `mp.solutions.drawing_utils` for direct Task API results: Requires proto conversion wrapper.

## Open Questions

1. **Handedness mirroring behavior on Windows webcam**
   - What we know: MediaPipe has historically had mirrored handedness labels with front-facing cameras. Recent versions (0.10.x) may have corrected this.
   - What's unclear: Whether the "Right" label in `handedness[0].category_name` corresponds to the user's actual right hand on Windows with a standard USB webcam.
   - Recommendation: Build with "Right" filter. Add a debug log that prints all detected handedness labels. If mirrored, swap to "Left" filter. This should be validated in the very first integration test.

2. **Model download and caching strategy**
   - What we know: The `.task` model file (float16, ~10MB) must be downloaded separately from `storage.googleapis.com`.
   - What's unclear: Best location to cache (project root? appdata? package data?).
   - Recommendation: Ship the model file in the project repo (it is small enough). Alternatively, download on first run to a `models/` directory with a progress indicator. For Phase 1, bundling in repo is simplest.

3. **Pinch detection threshold tuning**
   - What we know: Pinch = thumb tip close to index tip. Euclidean distance threshold needed.
   - What's unclear: Optimal threshold value (depends on hand distance from camera, normalization).
   - Recommendation: Start with 0.05 normalized distance. Make configurable via config.yaml threshold. Test empirically.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | none -- see Wave 0 |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DET-01 | 6 gestures classified from landmarks | unit | `python -m pytest tests/test_classifier.py -x` | -- Wave 0 |
| DET-02 | 3-frame majority-vote smoothing | unit | `python -m pytest tests/test_smoother.py -x` | -- Wave 0 |
| DET-03 | Camera capture on separate thread | unit | `python -m pytest tests/test_detector.py::test_threaded_capture -x` | -- Wave 0 |
| DET-04 | Right-hand only filtering | unit | `python -m pytest tests/test_detector.py::test_right_hand_filter -x` | -- Wave 0 |
| DEV-01 | --preview flag opens window | manual-only | Manual: run `python -m gesture_keys --preview` and verify window opens | N/A |
| DEV-02 | Console output of gesture changes | integration | `python -m pytest tests/test_integration.py::test_console_output -x` | -- Wave 0 |
| DEV-03 | FPS display in preview | manual-only | Manual: verify FPS counter visible in preview window | N/A |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/__init__.py` -- test package init
- [ ] `tests/test_classifier.py` -- covers DET-01 (6 gesture classification from mock landmarks)
- [ ] `tests/test_smoother.py` -- covers DET-02 (majority-vote smoothing logic)
- [ ] `tests/test_detector.py` -- covers DET-03, DET-04 (threaded capture, right-hand filter)
- [ ] `tests/test_config.py` -- covers config loading and defaults
- [ ] `tests/conftest.py` -- shared fixtures (mock landmarks for each gesture, mock config)
- [ ] `pytest.ini` or `pyproject.toml` -- pytest configuration
- [ ] Framework install: `pip install pytest` added to requirements.txt

## Sources

### Primary (HIGH confidence)
- [MediaPipe Hand Landmarker Python Guide](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python) -- Task API setup, options, running modes, result structure
- [MediaPipe HandLandmarker API Reference](https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/HandLandmarker) -- Full API reference
- [MediaPipe Official Sample Notebook](https://github.com/googlesamples/mediapipe/blob/main/examples/hand_landmarker/python/hand_landmarker.ipynb) -- draw_landmarks_on_image function, model URL
- [mediapipe PyPI](https://pypi.org/project/mediapipe/) -- Version 0.10.33, Python 3.9-3.12, Windows x86-64 wheel
- [GitHub Issue #5361](https://github.com/google-ai-edge/mediapipe/issues/5361) -- draw_landmarks incompatibility with Task API, proto conversion workaround

### Secondary (MEDIUM confidence)
- [Simple Hand Gesture Recognition Gist](https://gist.github.com/TheJLifeX/74958cc59db477a91837244ff598ef4a) -- Finger state detection logic, landmark indices, gesture classification rules
- [OpenCV Threading Pattern](https://gist.github.com/allskyee/7749b9318e914ca45eb0a1000a81bf56) -- Threaded VideoCapture with lock pattern
- [Multithreaded Camera Capture](https://nrsyed.com/2018/07/05/multithreading-with-opencv-python-to-improve-video-processing-performance/) -- Threading architecture for camera I/O

### Tertiary (LOW confidence)
- Handedness mirroring behavior -- conflicting reports across MediaPipe versions; needs empirical validation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- MediaPipe Task API, OpenCV, PyYAML are well-documented and verified via official sources
- Architecture: HIGH -- Threaded capture + VIDEO mode + rule-based classifier is a proven community pattern
- Pitfalls: HIGH -- draw_landmarks incompatibility confirmed via GitHub issue; BGR/RGB and timestamp issues documented in official guides
- Gesture classification rules: MEDIUM -- Finger tip vs PIP comparison is standard but pinch detection threshold needs empirical tuning
- Handedness filtering: MEDIUM -- Recent MediaPipe versions should work correctly but needs validation on target hardware

**Research date:** 2026-03-21
**Valid until:** 2026-04-21 (stable domain, MediaPipe Task API unlikely to change significantly)
