# Feature Research

**Domain:** Hand gesture recognition to keyboard commands (desktop utility)
**Researched:** 2026-03-21
**Confidence:** MEDIUM

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Reliable gesture detection (6+ gestures) | Core promise of the app; if gestures misfire or miss, the app is worthless | MEDIUM | MediaPipe landmarks + geometric classification. Priority-ordered resolution handles ambiguous poses |
| Configurable gesture-to-key mappings | Every user has different workflows; hardcoded mappings kill adoption | LOW | YAML config with single keys and combo support. Already planned |
| Debounce / false-trigger prevention | False positives are the #1 complaint in gesture apps. Users abandon immediately if random keys fire | MEDIUM | State machine with activation delay (0.4s) and cooldown (0.8s). Both configurable. Critical for usability |
| System tray with enable/disable toggle | Users need to quickly pause detection (phone call, stretching, etc.) without quitting | LOW | pystray with Active checkbox, already planned |
| Runs in background without visible window | Nobody wants a camera preview window up permanently while working | LOW | Default headless mode with optional --preview flag |
| Works across all foreground apps | Keyboard commands must land in whatever app is focused (editor, browser, game) | LOW | pynput handles this natively via OS-level key injection |
| Startup configuration (camera index, confidence thresholds) | Different webcams, lighting conditions, and setups need tuning | LOW | YAML config section for camera and detection parameters |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| GPU-accelerated inference (CUDA/RTX 3060) | Lower latency, lower CPU load. Most hobby projects run CPU-only and stutter | LOW | onnxruntime-gpu is a pip install; MediaPipe uses ONNX internally. Minimal code, big perf win |
| Confidence-based gesture gating | Only fire when detection confidence exceeds threshold, reducing false positives beyond what debounce alone provides | LOW | MediaPipe already returns confidence scores; just add a threshold check |
| Visual feedback overlay (preview mode) | Shows detected landmarks + current gesture label + debounce state. Essential for debugging and tuning | MEDIUM | OpenCV overlay on camera feed. Only active with --preview flag |
| Per-gesture activation delay tuning | Some gestures (pinch) are harder to hold steady; let users set per-gesture timing | LOW | Extend YAML config to allow per-gesture overrides of global debounce values |
| Gesture sequence support (two gestures = one action) | Enables richer command vocabulary without adding more static gestures. E.g., fist then open palm = "save file" | HIGH | Requires sequence state machine on top of debounce. Defer to v2 |
| On-screen notification on gesture fire | Brief toast/popup confirming which command fired. Builds trust that the right thing happened | MEDIUM | Win32 balloon tip or overlay. Helpful for learning phase |
| Two-hand gesture support | Doubles the gesture vocabulary. Left hand = modifier context, right hand = action | HIGH | MediaPipe supports multi-hand. Complexity is in classification and mapping logic |
| Logging / gesture history | Records what was detected and fired. Essential for debugging false triggers after the fact | LOW | Simple file or console logger with timestamps |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Custom ML model training | "I want to add my own gestures" | Requires training data collection, ML expertise, model management. Massively increases scope and support burden | Stick with MediaPipe landmark geometry. 6 gestures from finger positions covers common needs. Add gestures by coding new geometric rules, not training models |
| Mouse cursor control via hand position | Every demo project does it; looks impressive | Extremely imprecise compared to a real mouse. Jittery, fatiguing, unusable for real work. The "wow demo" that nobody actually uses | Focus on discrete keyboard commands which are reliable. Mouse control is a different product |
| GUI configuration editor | "YAML is scary" | Adds PyQt5/tkinter dependency, massive UI surface area, version sync issues with config file | Open YAML in default text editor via system tray menu. YAML is simple enough for the target audience (developers/power users) |
| Per-application gesture profiles | "Different gestures for different apps" | Requires foreground window detection, profile switching logic, complex config, confusing UX | Single global config. Users who need per-app can use AutoHotkey on top of gesture-keys |
| Continuous/dynamic gestures (swipe, wave) | "Swipe to scroll" | Dynamic gesture recognition is fundamentally harder than static pose detection. Requires temporal modeling (LSTM/DTW), training data, and has much higher false positive rates | Stick with static poses. A held "pointing up" gesture can trigger "scroll up" key repeatedly via the debounce cooldown |
| Multiple camera support | "What if I have two webcams?" | Adds device selection UI, resource management for multiple streams, unclear UX for which camera is active | Single camera index in config. User picks which one |
| Always-on camera preview | "I want to see myself" | Wastes screen real estate, CPU/GPU for rendering, privacy concern if someone walks by | --preview flag for debugging only. Not intended for daily use |

## Feature Dependencies

```
[Camera Capture + MediaPipe Detection]
    +--requires--> [Gesture Classification (landmark geometry)]
                       +--requires--> [Debounce State Machine]
                                          +--requires--> [Keyboard Simulation (pynput)]

[YAML Config Loader]
    +--required-by--> [Gesture-to-Key Mappings]
    +--required-by--> [Camera Settings]
    +--required-by--> [Debounce Timings]

[System Tray (pystray)]
    +--requires--> [Active/Inactive Toggle (threading.Event)]
    +--enhances--> [Edit Config menu item]

[Visual Feedback Overlay]
    +--requires--> [Camera Capture + MediaPipe Detection]
    +--requires--> [Gesture Classification]
    +--optional, gated by--> [--preview flag]

[GPU Acceleration]
    +--enhances--> [Camera Capture + MediaPipe Detection]
    +--independent of--> [all other features]

[Logging]
    +--enhances--> [Debounce State Machine]
    +--enhances--> [Keyboard Simulation]
    +--independent of--> [other features]
```

### Dependency Notes

- **Keyboard Simulation requires Debounce:** Without debounce, gestures fire continuously at frame rate (~30 FPS), making the app unusable. Debounce is not optional.
- **All mappings require Config Loader:** Config must load before detection starts. Validation at load time prevents runtime crashes.
- **Visual Feedback requires Detection pipeline:** Overlay draws on the camera feed with landmark data. Cannot exist without the detection loop.
- **GPU Acceleration is independent:** Swapping onnxruntime-gpu for onnxruntime-cpu changes nothing in app logic. Pure infrastructure concern.

## MVP Definition

### Launch With (v1)

Minimum viable product -- what's needed to validate the concept.

- [x] 6-gesture detection from MediaPipe landmarks -- core value proposition
- [x] YAML-configurable gesture-to-key mappings (single keys + combos) -- without this, app is a tech demo
- [x] Debounce state machine (activation delay + cooldown) -- without this, false triggers make it unusable
- [x] System tray with Active toggle, Edit Config, Quit -- minimum viable UX for a background app
- [x] Optional --preview flag for camera overlay -- needed for setup and debugging
- [x] GPU acceleration via onnxruntime-gpu -- low effort, meaningful performance gain
- [ ] Basic logging (gesture detected, key fired, timestamps) -- needed for debugging false triggers

### Add After Validation (v1.x)

Features to add once core is working and gestures are reliably detected.

- [ ] On-screen toast notification when gesture fires -- builds user trust, aids learning
- [ ] Per-gesture debounce timing overrides -- fine-tune difficult gestures like pinch
- [ ] Confidence threshold gating (in addition to debounce) -- extra false positive prevention
- [ ] Startup with Windows (optional registry entry or shortcut in Startup folder) -- convenience for daily use
- [ ] Config hot-reload (watch config file for changes, reload without restart) -- faster tuning loop

### Future Consideration (v2+)

Features to defer until v1 is proven useful in daily workflows.

- [ ] Gesture sequences (fist then palm = save) -- HIGH complexity, needs careful UX design
- [ ] Two-hand gesture support -- doubles vocabulary but doubles complexity
- [ ] Additional gestures beyond initial 6 -- only if users hit the 6-gesture ceiling
- [ ] Tray icon visual indicator of detection state (green = active, red = paused, yellow = gesture detected) -- polish

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| 6-gesture detection | HIGH | MEDIUM | P1 |
| Gesture-to-key mappings (YAML) | HIGH | LOW | P1 |
| Debounce state machine | HIGH | MEDIUM | P1 |
| System tray (toggle, edit, quit) | HIGH | LOW | P1 |
| GPU acceleration (onnxruntime-gpu) | MEDIUM | LOW | P1 |
| --preview camera overlay | MEDIUM | LOW | P1 |
| Basic logging | MEDIUM | LOW | P1 |
| On-screen notification on fire | MEDIUM | MEDIUM | P2 |
| Per-gesture debounce overrides | LOW | LOW | P2 |
| Confidence threshold gating | MEDIUM | LOW | P2 |
| Config hot-reload | MEDIUM | MEDIUM | P2 |
| Startup with Windows | LOW | LOW | P2 |
| Gesture sequences | MEDIUM | HIGH | P3 |
| Two-hand support | MEDIUM | HIGH | P3 |
| Additional gestures (7+) | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Neural-Hand (GitHub) | AI-Gesture-Control | GestureSign (Windows) | Our Approach |
|---------|---------------------|--------------------|-----------------------|--------------|
| Gesture detection | 10+ gestures, MediaPipe | MediaPipe, volume/brightness focus | Touch/mouse drawn gestures (not camera) | 6 static hand poses via MediaPipe landmarks |
| Output actions | Mouse + keyboard + window mgmt | Volume, brightness, mouse, scroll | Keyboard sim, window control, app launch | Keyboard only (single keys + combos). Focused scope |
| False positive prevention | Not documented | Not documented | N/A (touch-based, different problem) | Debounce state machine + configurable thresholds. Primary design goal |
| Configuration | Hardcoded or minimal | Hardcoded | GUI with per-app profiles | YAML config file. Editable, version-controllable |
| Background operation | Foreground window required | Foreground window | System tray | System tray, headless by default |
| GPU acceleration | CPU only (25-30 FPS) | CPU only | N/A | CUDA via onnxruntime-gpu on RTX 3060 |
| Platform | Cross-platform (Python) | Cross-platform (Python) | Windows only | Windows only (intentional constraint) |

**Key insight from competitor analysis:** Most open-source gesture projects are tech demos that prioritize "wow factor" (mouse control, volume sliders) over reliability. They lack debounce, run in foreground windows, and have no configuration. Our differentiation is reliability-first: debounce state machine, configurable thresholds, background operation, and focused scope (keyboard commands only).

## Sources

- [Neural-Hand - 10+ gestures with MediaPipe](https://github.com/Mo-Abdalkader/Neural-Hand)
- [AI-Gesture-Control-System - Volume/brightness/mouse](https://github.com/VASANI007/AI-Gesture-Control-System)
- [Custom Hand Gesture Recognition and Control](https://github.com/atharvakale31/Custom_Hand_Gesture_Recognition_and_Control)
- [GestureSign - Windows gesture recognition](https://gesturesign.win/)
- [Combating False Positives In Gesture Recognition](https://medium.com/@leeor.langer/combating-false-positives-in-gesture-recognition-e727932b41b1)
- [MAGIC 2.0 - False positive prediction for gesture systems](https://ieeexplore.ieee.org/document/5771412/)
- [MediaPipe Hands GitHub topic](https://github.com/topics/mediapipe-hands)
- [Deloitte - Desktop control via hand gestures](https://medium.com/deloitte-uk-tech-blog/how-to-control-desktop-apps-and-websites-using-hand-gestures-e2605283b3a4)

---
*Feature research for: Hand gesture recognition to keyboard commands*
*Researched: 2026-03-21*
