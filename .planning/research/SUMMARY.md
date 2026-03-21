# Project Research Summary

**Project:** gesture-keys
**Domain:** Real-time hand gesture recognition to keyboard commands (Windows desktop utility)
**Researched:** 2026-03-21
**Confidence:** HIGH

## Executive Summary

Gesture-keys is a Windows system tray application that uses a webcam and MediaPipe hand landmark detection to classify static hand poses and fire configurable keyboard commands. This is a well-trodden domain with mature libraries: MediaPipe provides accurate 21-landmark hand tracking at 30-60 FPS on CPU, pynput handles OS-level keyboard injection, and pystray manages the system tray. The architecture is a straightforward producer-consumer pipeline running on a daemon thread, with pystray owning the main thread (a Windows requirement). The stack is entirely pip-installable with no exotic dependencies.

The recommended approach is CPU-only MediaPipe inference using the new Task API (not the deprecated `mediapipe.solutions` API). A critical finding from stack research is that **MediaPipe Python on Windows has no GPU support** -- `onnxruntime-gpu` cannot accelerate MediaPipe's built-in hand landmarker without extracting models and building a custom inference pipeline, which is not worth the complexity. CPU inference at 30+ FPS is more than sufficient given the 0.4s debounce activation delay. The project's differentiator versus open-source competitors is reliability: a debounce state machine with frame smoothing, configurable thresholds, and headless background operation -- not raw inference speed.

The primary risks are: (1) using the deprecated MediaPipe legacy API that most tutorials reference, (2) gesture classification flickering without frame smoothing, making debounce unreliable, (3) left-hand/right-hand mirroring bugs in thumb detection, and (4) OpenCV camera capture blocking the detection thread on Windows. All four have clear prevention strategies that must be implemented from the start, not deferred.

## Key Findings

### Recommended Stack

The stack is lean and fully pip-installable. All core libraries are mature, well-documented, and have no known compatibility conflicts when pinned to the recommended versions.

**Core technologies:**
- **Python 3.12**: Latest stable version with MediaPipe support. 3.13 has known MediaPipe compatibility issues.
- **mediapipe 0.10.33**: Google's hand landmark detection. 21 landmarks, CPU runs at 30-60 FPS. Use the Task API (`mediapipe.tasks.python.vision.HandLandmarker`), not the deprecated `mediapipe.solutions` API.
- **opencv-python 4.13.0.92**: Webcam capture and frame processing. Use `opencv-python`, not `opencv-contrib-python`.
- **pynput 1.8.1**: Keyboard command simulation via `Controller.press()`/`release()`. Works across foreground apps (with known limitation for elevated/admin apps).
- **pystray 0.19.5**: System tray icon and menu. Must run on main thread on Windows.
- **PyYAML 6.0.3**: Configuration file parsing. Always use `yaml.safe_load()`.
- **Pillow 12.1.1**: Required by pystray for icon rendering.

**Critical stack decision: Drop `onnxruntime-gpu`.** MediaPipe Python on Windows is CPU-only. Adding onnxruntime-gpu does not accelerate MediaPipe's built-in pipeline. CPU performance is already sufficient.

### Expected Features

**Must have (table stakes):**
- 6-gesture detection from MediaPipe landmarks (fist, open palm, thumbs up, pointing up, peace, pinch)
- YAML-configurable gesture-to-key mappings (single keys and combos)
- Debounce state machine with frame smoothing (activation delay + cooldown)
- System tray with active/inactive toggle, edit config, quit
- Background operation without visible window (headless by default)
- Optional `--preview` flag for camera overlay with landmark visualization
- Basic logging (gesture detected, key fired, timestamps)

**Should have (add after core works):**
- Confidence threshold gating (MediaPipe already returns confidence scores)
- Per-gesture debounce timing overrides
- On-screen toast notification when gesture fires
- Config hot-reload or "Reload Config" tray menu item
- Startup with Windows option

**Defer (v2+):**
- Gesture sequences (fist then palm = save) -- HIGH complexity
- Two-hand gesture support -- doubles complexity
- Custom ML model training -- massive scope increase, use geometric rules instead
- Mouse cursor control -- imprecise, fatiguing, different product entirely

### Architecture Approach

The app follows a layered architecture with a linear producer-consumer pipeline. Seven flat modules, each with a single responsibility, connected through an orchestrator (`app.py`) that runs the detection loop and debounce state machine on a daemon thread. The main thread runs pystray. Cross-thread communication uses only `threading.Event` objects (active, stop) -- no shared mutable state, no locks needed.

**Major components:**
1. **config_loader.py** -- Parse YAML, resolve key strings to pynput Key objects
2. **gestures.py** -- Classify 21 landmarks into named gestures via geometric rules
3. **detector.py** -- Camera capture (threaded) + MediaPipe Task API hand detection
4. **keyboard_sim.py** -- Fire single keys and combos via pynput Controller
5. **app.py** -- Orchestrator: detection loop, frame smoothing, debounce state machine
6. **tray.py** -- System tray icon, menu, active toggle
7. **main.py** -- Entry point: argparse, wire components, launch threads

### Critical Pitfalls

1. **Legacy MediaPipe API** -- Most tutorials use the deprecated `mediapipe.solutions.hands` API. Use `mediapipe.tasks.python.vision.HandLandmarker` from day one. Migration later requires rewriting the entire detection loop.

2. **Debounce without frame smoothing** -- Raw landmark classifications flicker frame-to-frame, causing the debounce timer to reset constantly. Add a majority-vote smoothing window (5-7 frames) *before* the debounce state machine, not after. This is core to usability, not polish.

3. **Left/right hand mirroring** -- Thumb extension detection uses x-axis comparison that flips depending on handedness. Always check MediaPipe's `handedness` field. Test all 6 gestures with both hands.

4. **Camera capture blocking** -- `cv2.VideoCapture.read()` blocks and can hang on Windows (especially MSMF backend after sleep/wake). Use a dedicated capture thread and specify `cv2.CAP_DSHOW` backend. Build threaded capture from the start.

5. **pynput blocked by elevated apps** -- Windows UIPI silently drops keystrokes sent to admin-elevated applications. Document this limitation; do not run the app as administrator to "fix" it.

## Implications for Roadmap

Based on combined research, the build order follows the architecture's natural dependency chain. The pipeline must be built bottom-up (config and classification first, then detection, then orchestration, then UI).

### Phase 1: Foundation -- Config, Classification, and Detection

**Rationale:** Config loader and gesture classifier have zero hardware dependencies and are pure logic -- they can be built and unit tested immediately. Detector introduces the camera and MediaPipe but is independently verifiable via preview window. These three modules are prerequisites for everything else.
**Delivers:** Working camera capture with landmark detection, gesture classification from landmarks, and YAML config parsing. Verifiable via command-line preview showing detected gestures overlaid on camera feed.
**Features addressed:** Camera capture, MediaPipe landmark detection, 6-gesture classification, YAML config loading, `--preview` overlay
**Pitfalls to avoid:** Use Task API not legacy API; implement threaded camera capture; handle left/right hand mirroring in gesture classification; use `cv2.CAP_DSHOW` backend

### Phase 2: Core Pipeline -- Debounce, Keyboard Sim, and Orchestration

**Rationale:** With detection and classification working, the debounce state machine and keyboard simulator complete the end-to-end pipeline. Frame smoothing must ship with debounce -- they are inseparable for usability. The orchestrator (app.py) wires everything into the sequential pipeline.
**Delivers:** End-to-end gesture-to-keystroke pipeline. Hold a gesture for 0.4s and the mapped key fires once. Verifiable by opening a text editor and testing all 6 gestures.
**Features addressed:** Debounce state machine with frame smoothing, keyboard simulation (single keys + combos), configurable activation delay and cooldown, basic logging
**Pitfalls to avoid:** Build frame smoothing alongside debounce (not later); test pynput against non-elevated apps; create single Controller instance and reuse; verify key combos send correct press/release sequence

### Phase 3: System Tray and Background Operation

**Rationale:** The app works from command line after Phase 2. Phase 3 wraps it in the system tray for daily-use operation. pystray must own the main thread; detection loop moves to daemon thread coordinated via threading.Event.
**Delivers:** Headless background app with system tray icon, active/inactive toggle, edit config menu item, quit. Launchable via `pythonw.exe` with no console window.
**Features addressed:** System tray (pystray), active toggle, edit config (os.startfile), quit with camera release, headless by default
**Pitfalls to avoid:** Run pystray on main thread; use `icon.run(setup=start_detection_thread)` pattern; release camera when deactivated (LED off); ensure all exit paths release camera

### Phase 4: Polish and Reliability

**Rationale:** With core functionality complete, this phase adds the quality-of-life features that make the difference between a tech demo and a daily-use tool. These are lower-risk features that enhance but don't change the core architecture.
**Delivers:** Confidence gating, per-gesture debounce overrides, status feedback via tray icon, config reload, startup option
**Features addressed:** Confidence threshold gating, per-gesture timing overrides, tray icon status colors, config hot-reload or reload menu item, Windows startup option, on-screen toast notifications
**Pitfalls to avoid:** Do not add admin elevation for startup; test config reload does not break running detection loop

### Phase Ordering Rationale

- **Bottom-up dependency chain:** Config and classification have no dependencies, detector depends on MediaPipe, orchestrator depends on all three. This ordering eliminates integration risk by testing each layer before building on it.
- **Debounce + smoothing together:** Research strongly indicates frame smoothing is essential for debounce reliability. Separating them creates a "works in demo, fails in practice" trap.
- **Tray last, not first:** The app should work end-to-end from the command line before adding tray UI. This keeps the feedback loop tight during development of the hard parts (gesture classification tuning, debounce timing).
- **Polish after function:** Confidence gating, status icons, and config reload are enhancements to a working system, not prerequisites.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** MediaPipe Task API usage patterns -- most tutorials cover the legacy API, so the Task API setup (model download, `HandLandmarker` configuration, `LIVE_STREAM` mode) needs careful reference to official docs.
- **Phase 2:** Debounce + smoothing tuning -- the 0.4s/0.8s timing and 5-7 frame smoothing window are starting points that need empirical testing. Plan for iteration time.

Phases with standard patterns (skip deep research):
- **Phase 3:** pystray + threading is well-documented with clear patterns (main thread tray, daemon thread detection, Event-based coordination).
- **Phase 4:** All features are incremental additions to existing components with no new architectural concerns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All libraries verified on PyPI with version compatibility confirmed. GPU finding is well-documented across multiple sources. |
| Features | MEDIUM | Feature prioritization is sound but competitor analysis is limited to open-source projects. The debounce timing values (0.4s/0.8s) are educated guesses that need empirical validation. |
| Architecture | HIGH | Pipeline pattern is standard for real-time CV applications. Component boundaries are clean and well-motivated. Build order follows natural dependencies. |
| Pitfalls | HIGH | Every pitfall is backed by multiple sources (GitHub issues, official docs, community reports). The legacy API and GPU acceleration pitfalls are particularly well-documented. |

**Overall confidence:** HIGH

### Gaps to Address

- **Debounce timing values:** The 0.4s activation / 0.8s cooldown and 5-7 frame smoothing window are starting estimates. Plan for a tuning phase during Phase 2 development with real hands and real webcams.
- **MediaPipe Task API on Windows specifics:** Most Task API documentation targets Android/iOS. Python desktop usage with `LIVE_STREAM` running mode on Windows needs verification during Phase 1 -- specifically whether the async callback pattern works cleanly with the threaded architecture.
- **Gesture discrimination in practice:** Six gestures from geometric rules may produce overlap in practice (e.g., peace vs pointing up when ring finger is partially extended). Priority ordering helps but may need threshold tuning per gesture.
- **GPU acceleration claim in FEATURES.md conflicts with STACK.md findings:** FEATURES.md lists GPU acceleration as P1 via `onnxruntime-gpu`. STACK.md conclusively shows this does not work with MediaPipe Python on Windows. **Resolution: Drop GPU acceleration from scope. CPU is sufficient.**

## Sources

### Primary (HIGH confidence)
- [MediaPipe PyPI](https://pypi.org/project/mediapipe/) -- version 0.10.33, Python 3.9-3.12
- [MediaPipe Hand Landmarker Task API](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker) -- new API, model download, configuration
- [MediaPipe GPU Support docs](https://developers.google.com/mediapipe/framework/getting_started/gpu_support) -- Windows not supported
- [onnxruntime-gpu CUDA compatibility](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html) -- version matrix
- [pynput documentation](https://pynput.readthedocs.io/en/latest/keyboard.html) -- Controller usage, platform limitations
- [pystray documentation](https://pystray.readthedocs.io/en/latest/usage.html) -- threading requirements

### Secondary (MEDIUM confidence)
- [Threaded OpenCV capture pattern](https://nrsyed.com/2018/07/05/multithreading-with-opencv-python-to-improve-video-processing-performance/) -- threaded capture approach
- [Hand tracking 30 FPS on CPU benchmarks](https://medium.com/@augmented-startups) -- CPU performance reference
- [Combating False Positives in Gesture Recognition](https://medium.com/@leeor.langer/combating-false-positives-in-gesture-recognition-e727932b41b1) -- debounce and smoothing strategies
- [MediaPipe hand landmark mirroring](https://gist.github.com/TheJLifeX/74958cc59db477a91837244ff598ef4a) -- left/right hand issues

### Tertiary (needs validation during implementation)
- Debounce timing values (0.4s/0.8s) -- educated estimates, need empirical tuning
- Frame smoothing window size (5-7 frames) -- starting point, needs testing with real camera jitter
- `cv2.CAP_DSHOW` vs MSMF performance on Windows -- community consensus but hardware-dependent

---
*Research completed: 2026-03-21*
*Ready for roadmap: yes*
