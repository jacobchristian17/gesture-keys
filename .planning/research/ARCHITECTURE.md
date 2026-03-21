# Architecture Research

**Domain:** Real-time hand gesture recognition desktop app (webcam to keyboard commands)
**Researched:** 2026-03-21
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Presentation Layer                         │
│  ┌──────────────┐  ┌──────────────────┐                        │
│  │  System Tray  │  │  Preview Window  │                        │
│  │  (pystray)    │  │  (OpenCV, opt.)  │                        │
│  └──────┬───────┘  └────────┬─────────┘                        │
│         │ toggle/quit       │ frame display                    │
├─────────┴───────────────────┴──────────────────────────────────┤
│                      Orchestration Layer                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              App Orchestrator (app.py)                    │   │
│  │  - Detection loop (daemon thread)                        │   │
│  │  - Debounce state machine                                │   │
│  │  - Active/stop event coordination                        │   │
│  └──────┬──────────────┬──────────────┬────────────────────┘   │
│         │ landmarks    │ gesture      │ fire key               │
├─────────┴──────────────┴──────────────┴────────────────────────┤
│                      Processing Layer                           │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │  Detector    │  │  Gestures    │  │  Keyboard Simulator │   │
│  │  (detector)  │  │  (gestures)  │  │  (keyboard_sim)     │   │
│  │  Camera +    │  │  Landmark    │  │  pynput Controller  │   │
│  │  MediaPipe   │  │  classifier  │  │  keys + combos      │   │
│  └──────┬───────┘  └──────────────┘  └─────────────────────┘   │
│         │ frames                                                │
├─────────┴──────────────────────────────────────────────────────┤
│                      Configuration Layer                        │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              Config Loader (config_loader.py)           │    │
│  │              + config.yaml                              │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|----------------|----------------|
| **System Tray** (`tray.py`) | UI presence: active toggle, edit config, quit | pystray with Pillow-generated icon; runs on main thread (Windows requirement) |
| **Preview Window** (in `app.py` or `detector.py`) | Optional camera feed display for debugging | OpenCV `imshow` gated behind `--preview` flag |
| **App Orchestrator** (`app.py`) | Detection loop, debounce state machine, thread coordination | Daemon thread with `threading.Event` for active/stop signals |
| **Detector** (`detector.py`) | Camera capture + MediaPipe hand landmark inference | OpenCV VideoCapture + MediaPipe Hands; GPU-accelerated via onnxruntime-gpu |
| **Gestures** (`gestures.py`) | Classify 21 landmarks into one of 6 named gestures | Geometric rules: finger-tip vs PIP joint comparison, priority ordering |
| **Keyboard Simulator** (`keyboard_sim.py`) | Fire single keys and combos into foreground app | pynput Controller with press/release for combos |
| **Config Loader** (`config_loader.py`) | Parse YAML, convert key strings to pynput Key objects | PyYAML + lookup table for special keys (ctrl, alt, etc.) |

## Recommended Project Structure

```
gesture-keys/
├── main.py                  # Entry point: argparse, wires components, launches threads
├── config.yaml              # User-editable gesture-to-key mappings + settings
├── requirements.txt         # Pinned dependencies
└── gesture_keys/
    ├── __init__.py
    ├── app.py               # Orchestrator: detection loop + debounce state machine
    ├── detector.py          # Camera capture + MediaPipe hand detection
    ├── gestures.py          # Gesture classification from landmarks
    ├── keyboard_sim.py      # pynput keyboard simulation
    ├── config_loader.py     # YAML parsing + key string resolution
    └── tray.py              # System tray icon + menu
```

### Structure Rationale

- **Flat package, no sub-packages.** Seven modules is not enough to warrant deeper nesting. Every module maps 1:1 to a component with a single clear responsibility.
- **`main.py` outside the package.** Entry point wires everything together; the package modules remain independently testable.
- **`config.yaml` at project root.** Users edit it directly; `os.startfile()` opens it from the tray menu.

## Architectural Patterns

### Pattern 1: Producer-Consumer Pipeline

**What:** The detection loop is a linear pipeline: capture frame, detect landmarks, classify gesture, debounce, fire key. Each stage transforms data for the next.

**When to use:** Always -- this is the core runtime pattern. Every frame flows through the same stages in order.

**Trade-offs:** Simple and debuggable. No parallelism between stages (unnecessary at 30fps with GPU inference). If any stage blocks, the whole pipeline stalls, but MediaPipe + OpenCV are designed for frame-rate operation.

**Example:**
```python
# app.py - simplified detection loop
while not stop_event.is_set():
    if not active_event.is_set():
        time.sleep(0.1)
        continue

    frame = detector.capture_frame()
    if frame is None:
        continue

    landmarks = detector.detect_hands(frame)
    gesture = gestures.classify(landmarks)
    action = debounce.update(gesture)  # returns gesture or None

    if action is not None:
        keyboard_sim.fire(config.get_keys(action))

    if show_preview:
        detector.show_frame(frame, landmarks, gesture)
```

### Pattern 2: Debounce State Machine

**What:** A state machine that gates gesture-to-key firing. Prevents false triggers from transitional hand poses and prevents repeated firing from held gestures.

**When to use:** Between classification and keyboard firing. Every recognized gesture passes through debounce before any key is sent.

**Trade-offs:** Adds latency (0.4s activation delay) but eliminates false positives. The 0.4s/0.8s timing values are configurable, letting users tune responsiveness vs reliability.

**States:**
```
IDLE ──(gesture detected)──> PENDING
    start timer

PENDING ──(same gesture held 0.4s)──> FIRED
    fire key, start cooldown

PENDING ──(gesture changed/lost)──> IDLE
    reset

FIRED ──(cooldown 0.8s elapsed)──> IDLE
    ready for next gesture

FIRED ──(gesture still held, cooldown not elapsed)──> FIRED
    do nothing (prevent repeat)
```

**Example:**
```python
class DebounceStateMachine:
    def __init__(self, activation_delay=0.4, cooldown=0.8):
        self.state = "IDLE"
        self.pending_gesture = None
        self.pending_since = 0.0
        self.fired_at = 0.0
        self.activation_delay = activation_delay
        self.cooldown = cooldown

    def update(self, gesture: str | None) -> str | None:
        now = time.monotonic()

        if self.state == "IDLE":
            if gesture is not None:
                self.state = "PENDING"
                self.pending_gesture = gesture
                self.pending_since = now
            return None

        elif self.state == "PENDING":
            if gesture != self.pending_gesture:
                self.state = "IDLE"
                self.pending_gesture = None
                return None
            if now - self.pending_since >= self.activation_delay:
                self.state = "FIRED"
                self.fired_at = now
                return self.pending_gesture
            return None

        elif self.state == "FIRED":
            if now - self.fired_at >= self.cooldown:
                self.state = "IDLE"
                self.pending_gesture = None
            return None
```

### Pattern 3: Thread Coordination via Events

**What:** The main thread runs pystray; a daemon thread runs the detection pipeline. Communication happens through `threading.Event` objects, not shared mutable state.

**When to use:** For the active toggle and graceful shutdown. No locks needed because Events are thread-safe and the only shared state.

**Trade-offs:** Simple and race-condition-free for this use case. Would not scale to complex multi-thread communication, but this app only needs two signals: "is active" and "should stop."

**Example:**
```python
# main.py
active_event = threading.Event()
active_event.set()  # start active
stop_event = threading.Event()

# Detection thread checks these
detection_thread = threading.Thread(
    target=app.run_detection_loop,
    args=(active_event, stop_event, config, show_preview),
    daemon=True
)
detection_thread.start()

# Tray callbacks toggle them
def on_toggle(icon, item):
    if active_event.is_set():
        active_event.clear()
    else:
        active_event.set()

def on_quit(icon, item):
    stop_event.set()
    icon.stop()
```

## Data Flow

### Frame-to-Keystroke Pipeline

```
[Webcam]
    | (BGR frame via OpenCV VideoCapture)
    v
[MediaPipe Hands] ──> (palm detection + landmark regression, GPU-accelerated)
    | (21 3D landmarks: x, y, z normalized)
    v
[Gesture Classifier] ──> (geometric rules: tip vs PIP joint positions)
    | (gesture name: "FIST", "OPEN_PALM", etc. or None)
    v
[Debounce State Machine] ──> (activation delay + cooldown filtering)
    | (gesture name to fire, or None)
    v
[Config Lookup] ──> (gesture name -> key specification from YAML)
    | (key string or key combo list)
    v
[pynput Controller] ──> (keyboard press/release into OS)
    | (keystrokes delivered to foreground app)
    v
[Target Application]
```

### Thread Communication

```
Main Thread (pystray)          Daemon Thread (detection loop)
       |                                |
       |── active_event.set/clear ─────>| (checked each iteration)
       |── stop_event.set ─────────────>| (breaks loop, thread exits)
       |                                |
       |<── icon.stop() on quit ────────|
```

### Key Data Flows

1. **Frame acquisition:** OpenCV reads BGR frames from webcam at device framerate (typically 30fps). This is CPU-bound I/O, not a GPU task.
2. **Landmark inference:** MediaPipe's two-stage pipeline (palm detection then landmark regression) runs per-frame. With onnxruntime-gpu, inference runs on the RTX 3060. Palm detection is skipped when hand tracking is stable between frames.
3. **Gesture classification:** Pure geometry -- comparing y-coordinates of fingertip landmarks vs PIP joint landmarks to determine extension. Thumb uses x-axis comparison accounting for handedness. Priority ordering resolves ambiguity.
4. **Debounce gating:** State machine consumes gesture stream, only emitting when a gesture has been held steadily for 0.4s and cooldown from last fire has elapsed.
5. **Key firing:** pynput Controller sends press/release events at the OS level. For combos like Ctrl+Z, modifier keys are pressed first, then the key, then all released.

## Performance Considerations

| Concern | Approach | Notes |
|---------|----------|-------|
| Inference latency | onnxruntime-gpu on RTX 3060 | MediaPipe hand landmark inference drops from ~15ms CPU to ~5ms GPU |
| Frame rate | Process at camera native rate (30fps) | No need to skip frames with GPU acceleration |
| CPU usage while idle | Sleep 100ms when deactivated via tray toggle | Detection thread yields CPU when not active |
| Memory | Single frame buffer, no history | Landmarks are tiny (21 x 3 floats); no accumulation needed |
| Camera startup | Lazy initialization on first activation | Avoids blocking app startup; camera released on quit |

### First Bottleneck: Camera Capture

OpenCV's `VideoCapture.read()` is synchronous and blocks until a frame is ready. At 30fps this means ~33ms per frame. With GPU inference at ~5ms, the pipeline is I/O-bound on camera capture, not compute-bound. This is fine -- you cannot process frames faster than the camera produces them.

## Anti-Patterns

### Anti-Pattern 1: Polling Gesture State from the Main Thread

**What people do:** Check gesture state from the pystray main thread using shared variables without synchronization.
**Why it is wrong:** Race conditions on shared mutable state. pystray callbacks run on the main thread; detection runs on the daemon thread. Reading partially-updated gesture state leads to phantom triggers.
**Do this instead:** Keep all gesture processing on the daemon thread. Use `threading.Event` for the two cross-thread signals (active, stop). The daemon thread owns all pipeline state exclusively.

### Anti-Pattern 2: Firing Keys Inside MediaPipe Callbacks

**What people do:** Call pynput keyboard actions from within MediaPipe's processing callbacks or OpenCV's frame processing.
**Why it is wrong:** pynput's Controller.press/release interacts with the Windows input system. Calling it from a tight processing loop without debounce fires keys dozens of times per second. Additionally, blocking in a MediaPipe callback stalls the inference pipeline.
**Do this instead:** Separate detection from action. The pipeline classifies the gesture, the debounce state machine gates firing, and only then does the keyboard simulator execute. Each responsibility in its own module.

### Anti-Pattern 3: Running pystray on a Non-Main Thread on macOS (and Cargo-Culting It)

**What people do:** Find macOS examples that run pystray on the main thread and assume Windows requires the same, or vice versa -- run it on a background thread assuming all platforms are the same.
**Why it is wrong:** On Windows, pystray works from any thread, but the project explicitly targets Windows only and uses `pystray.run()` on the main thread for simplicity. The real danger is copying cross-platform threading patterns that add complexity for no benefit on a Windows-only app.
**Do this instead:** Main thread runs `icon.run(setup=start_detection_thread)`. The `setup` callback starts the daemon thread. Simple, correct, no platform abstraction needed.

### Anti-Pattern 4: Holding OpenCV VideoCapture Open When Inactive

**What people do:** Keep the camera open when the user toggles detection off via the tray.
**Why it is wrong:** The camera LED stays on (confusing/alarming to users), and the camera is unavailable to other apps.
**Do this instead:** Release the camera when deactivated, re-acquire when reactivated. Adds ~500ms latency on reactivation but respects user expectations and system resources.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Webcam (OpenCV) | `cv2.VideoCapture(device_index)` | Device index from config; resolution configurable; release on deactivate |
| MediaPipe Hands | `mediapipe.solutions.hands.Hands()` | `max_num_hands=1`, confidence thresholds from config; GPU via onnxruntime-gpu |
| Windows Input System | `pynput.keyboard.Controller()` | Thread-safe for sending; fires into whatever app has focus |
| Windows Shell | `os.startfile(config_path)` | Opens YAML in default editor from tray menu |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| tray <-> app | `threading.Event` (active_event, stop_event) | No direct function calls across threads; events are the only interface |
| app -> detector | Method calls: `capture_frame()`, `detect_hands()` | Detector is owned by the app thread; no cross-thread sharing |
| app -> gestures | Pure function: `classify(landmarks) -> str or None` | Stateless; takes landmarks, returns gesture name |
| app -> keyboard_sim | Method call: `fire(key_spec)` | Called only from daemon thread after debounce approval |
| config_loader -> all | Read at startup, passed as data | Config is loaded once and passed to components; no hot-reload needed (quit and restart after edit) |

## Build Order (Dependencies Between Components)

The pipeline has clear dependency ordering that maps to implementation phases:

```
1. config_loader.py   (no dependencies -- pure YAML parsing)
   |
2. gestures.py        (no dependencies -- pure geometry functions)
   |
3. detector.py        (depends on: mediapipe, opencv -- camera + inference)
   |
4. keyboard_sim.py    (depends on: pynput, config_loader -- key firing)
   |
5. app.py             (depends on: detector, gestures, keyboard_sim, config_loader)
   |                   (implements: detection loop + debounce state machine)
   |
6. tray.py            (depends on: pystray, Pillow -- system tray UI)
   |
7. main.py            (depends on: all above -- wires everything together)
```

**Rationale for this order:**
- Modules 1-2 are pure logic with no hardware dependencies. They can be built and unit-tested immediately.
- Module 3 introduces camera + MediaPipe. Testable independently by displaying landmarks on a preview window.
- Module 4 is small and independent. Can be tested by firing keys in a text editor.
- Module 5 is the integration point. Once modules 1-4 work individually, the orchestrator wires them into the pipeline and adds debounce.
- Modules 6-7 are packaging. The app works from the command line before tray integration is added.

## Sources

- [MediaPipe Hands documentation](https://mediapipe.readthedocs.io/en/latest/solutions/hands.html)
- [Google Research: On-Device, Real-Time Hand Tracking with MediaPipe](https://research.google/blog/on-device-real-time-hand-tracking-with-mediapipe/)
- [MediaPipe Gesture Recognizer task guide](https://developers.google.com/mediapipe/solutions/vision/gesture_recognizer)
- [pystray documentation](https://pythonhosted.org/pystray/)
- [pystray threading issue #94](https://github.com/moses-palmer/pystray/issues/94)
- [pynput keyboard documentation](https://pynput.readthedocs.io/en/latest/keyboard.html)
- [pynput keyboard usage (Controller)](https://pynput.readthedocs.io/en/latest/keyboard-usage.html)

---
*Architecture research for: hand gesture recognition desktop app (webcam to keyboard commands)*
*Researched: 2026-03-21*
