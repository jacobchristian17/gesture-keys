# Pitfalls Research

**Domain:** Hand gesture recognition to keyboard commands (Windows desktop, MediaPipe + pynput)
**Researched:** 2026-03-21
**Confidence:** HIGH (multiple sources verified per pitfall)

## Critical Pitfalls

### Pitfall 1: Using the Legacy MediaPipe API Instead of the Task API

**What goes wrong:**
The legacy `mediapipe.solutions.hands` API was deprecated in March 2023. Tutorials and Stack Overflow answers overwhelmingly reference this legacy API. Code using it will work today but receives no updates, no bug fixes, and no GPU acceleration improvements. The legacy drawing utilities (`mp.solutions.drawing_utils`) are incompatible with the new Task API's Landmark objects (missing `HasField` attribute), so mixing old and new code produces runtime errors.

**Why it happens:**
Most online examples and tutorials still use the legacy API. The new `mediapipe.tasks.python.vision.HandLandmarker` API has a different interface and requires downloading a `.task` model file, which adds setup complexity.

**How to avoid:**
Use `mediapipe.tasks.python.vision.HandLandmarker` from day one. Download the `hand_landmarker.task` model bundle. Write a custom lightweight landmark drawing function instead of relying on legacy `mp.solutions.drawing_utils`. The new API provides the same 21 landmarks but with a cleaner interface and active maintenance.

**Warning signs:**
- Any import from `mediapipe.solutions.hands`
- Using `mp_hands.Hands()` constructor
- Deprecation warnings in console output

**Phase to address:**
Phase 1 (project skeleton / detector setup). Get the API choice right from the start -- migrating later requires rewriting the detection loop and all landmark access code.

---

### Pitfall 2: Left Hand vs Right Hand Landmark Mirroring

**What goes wrong:**
Finger extension detection logic that works perfectly for right hands produces wrong results for left hands. The thumb is the worst offender: its "extended" direction depends on handedness (x-axis comparison flips). A user raising all 5 fingers on their left hand gets classified as 4 fingers, or a left-hand thumbs-up gets misclassified as a fist.

**Why it happens:**
MediaPipe assumes the input image is mirrored (front-facing camera, horizontally flipped). It returns a `handedness` field, but developers often ignore it and hardcode the right-hand x-axis comparison for thumb extension. The y-axis comparisons for other fingers are handedness-agnostic, so the bug only manifests on thumb-dependent gestures, making it easy to miss during testing if you only use your dominant hand.

**How to avoid:**
Always read the `handedness` field from MediaPipe results. For thumb extension, flip the x-axis comparison based on whether the detected hand is left or right. The PLAN.md already mentions "x-axis for thumb accounting for handedness" -- this must actually be implemented, not skipped. Test every gesture with both hands during development.

**Warning signs:**
- THUMBS_UP works with right hand but not left
- PINCH detection is inconsistent
- Only testing with one hand during development

**Phase to address:**
Phase 1 (gesture classification). Must be baked into `gestures.py` from the start. Add explicit left-hand test cases.

---

### Pitfall 3: CUDA / cuDNN / onnxruntime-gpu Version Hell on Windows

**What goes wrong:**
Installing `onnxruntime-gpu` via pip and expecting GPU acceleration "just works" leads to silent CPU fallback or cryptic CUDA errors. The onnxruntime-gpu 1.21.0 Windows package was actually built against CUDA 11 instead of CUDA 12 (a known packaging bug). cuDNN 8.x and 9.x are mutually incompatible. The CUDA toolkit alone does not install cuDNN. Missing DLLs on PATH cause silent fallback to CPU with no error, just slow inference.

**Why it happens:**
The CUDA ecosystem on Windows is a matrix of version dependencies: onnxruntime version x CUDA version x cuDNN version x GPU driver version. pip install gives you a binary built against specific CUDA/cuDNN versions, and if your system libraries do not match, it fails silently or loudly.

**How to avoid:**
1. Pin exact versions in `requirements.txt` (e.g., `onnxruntime-gpu==1.20.1`)
2. Verify GPU is actually being used at startup: check `onnxruntime.get_device()` returns `"GPU"` and log available execution providers
3. Use `onnxruntime.InferenceSession` with explicit `providers=['CUDAExecutionProvider', 'CPUExecutionProvider']` to get errors instead of silent fallback
4. Document required CUDA toolkit version and cuDNN version in README
5. Consider using onnxruntime-gpu's `preload_dlls()` function (available since 1.21.0) for explicit DLL loading
6. Alternatively: MediaPipe's new Task API may handle GPU internally without needing separate onnxruntime-gpu -- verify this before adding the dependency at all

**Warning signs:**
- Inference runs but CPU usage is high and GPU usage is 0%
- `onnxruntime.get_available_providers()` does not include `CUDAExecutionProvider`
- Import succeeds but inference is slower than expected (~30ms+ per frame instead of ~5-10ms)

**Phase to address:**
Phase 1 (environment setup). Verify GPU acceleration works before building anything else. If GPU setup is too painful, confirm CPU-only MediaPipe performance is acceptable (it likely is for a single webcam at 30fps on a modern CPU).

---

### Pitfall 4: pynput Keyboard Events Blocked by Elevated / Admin Applications

**What goes wrong:**
pynput uses Win32 `SendInput` which injects input events with the `LLMHF_INJECTED` flag. When the foreground application is running as Administrator (e.g., Task Manager, some games, IDE running as admin), pynput's simulated keystrokes are silently dropped due to Windows UIPI (User Interface Privilege Isolation). The app appears to work during development but fails when the user switches to certain windows.

**Why it happens:**
Windows security model prevents non-elevated processes from sending input to elevated processes. This is by design (prevents input injection attacks). Developers test with their IDE or text editor in the foreground, which works fine, and never test against elevated apps.

**How to avoid:**
1. Document this limitation clearly -- it is a Windows security feature, not a bug
2. Do NOT run the app as administrator by default (this creates other security issues)
3. Test explicitly against elevated applications and verify graceful behavior
4. Consider adding a startup log message noting that keyboard simulation will not work in elevated/admin applications
5. For v1, accept this limitation and document it rather than fighting Windows security

**Warning signs:**
- "It works in Notepad but not in [other app]"
- Users report intermittent key delivery failures
- Works on developer machine but fails for users who run apps as admin

**Phase to address:**
Phase 2 (keyboard simulation). Document the limitation in the README. Test against common elevated scenarios.

---

### Pitfall 5: Debounce Timing That Feels Broken in Practice

**What goes wrong:**
The planned 0.4s activation delay + 0.8s cooldown (1.2s total cycle) sounds reasonable on paper but feels sluggish or produces phantom triggers in practice. MediaPipe does not return a steady stream of identical classifications -- landmarks jitter frame-to-frame, causing the classified gesture to flicker between the intended gesture and `None` (or a neighboring gesture). A 0.4s activation delay with flickering classification means the gesture may never "hold" for the full 0.4s, making the system feel unresponsive. Conversely, if thresholds are loosened to fix this, false triggers increase.

**Why it happens:**
Gesture classification from raw landmark positions is inherently noisy. The finger tip vs PIP joint comparison produces binary extended/not-extended, but landmarks near the threshold oscillate. The debounce state machine treats each frame independently without smoothing, so a single frame of "wrong" classification resets the activation timer.

**How to avoid:**
1. Add a **smoothing window** (e.g., majority vote over last 5-7 frames) before the debounce state machine, not after. The state machine should receive smoothed gesture labels, not raw per-frame classifications
2. Make activation delay and cooldown independently configurable in YAML (already planned)
3. Start with shorter values (0.3s activate, 0.5s cooldown) and tune based on real testing
4. Add a `--preview` mode that shows the current raw vs smoothed gesture classification on screen so you can see the flickering and tune thresholds visually
5. Consider requiring N consecutive matching frames rather than a pure time-based delay

**Warning signs:**
- Gestures "almost never trigger" even when held clearly
- Gestures trigger when transitioning between poses (false fires)
- Different users need different timing values
- Preview shows gesture label flickering rapidly

**Phase to address:**
Phase 2 (debounce state machine in `app.py`). Build the smoothing window in the same phase as debounce. Do not defer smoothing to a "polish" phase -- it is core to usability.

---

### Pitfall 6: OpenCV Camera Capture Blocking the Detection Thread

**What goes wrong:**
`cv2.VideoCapture.read()` is a blocking call. On Windows, the default MSMF (Media Foundation) backend can have high latency (100-200ms per frame) and occasionally hangs for seconds when the camera is being accessed by another application or after system sleep/wake. If camera capture and gesture classification run on the same thread sequentially, a camera stall freezes the entire detection pipeline with no user feedback.

**Why it happens:**
The simplest camera loop is `while True: ret, frame = cap.read(); process(frame)`. This works in demos but is fragile in production. Windows camera backends (MSMF, DirectShow) have different latency and reliability characteristics. MSMF is the default and can be slow to initialize.

**How to avoid:**
1. Use a dedicated camera capture thread that continuously grabs frames into a shared variable (producer), with the detection thread consuming the latest frame (consumer). This decouples capture latency from processing latency
2. Explicitly specify `cv2.CAP_DSHOW` (DirectShow) backend on Windows -- it is often faster and more reliable for USB webcams than MSMF: `cv2.VideoCapture(index, cv2.CAP_DSHOW)`
3. Set camera resolution explicitly via `cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)` -- lower resolution means faster capture and faster inference
4. Add a timeout/watchdog: if no frame is received for 3 seconds, log a warning and attempt to reinitialize the camera
5. Always call `cap.release()` on shutdown (in a `finally` block or signal handler)

**Warning signs:**
- Detection loop runs at much less than camera FPS
- App hangs after system sleep/wake
- High latency between gesture and key trigger (>500ms)
- Camera stays "in use" after app closes (green light stays on)

**Phase to address:**
Phase 1 (detector.py). Use the threaded capture pattern from the start. Switching from single-threaded to threaded capture later requires restructuring the entire detection loop.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoding gesture thresholds in code | Faster to prototype | Every user has different hand proportions; threshold tuning requires code changes | Never -- put thresholds in config.yaml from day one |
| Using legacy MediaPipe solutions API | More tutorials available | Migration required when legacy stops working entirely; no GPU improvements | Never -- new Task API is available and stable |
| Skipping frame smoothing | Simpler debounce logic | Flickering classifications make debounce unreliable; leads to endless threshold tweaking | Only for initial proof-of-concept (first day) |
| Single-threaded capture + process | Less code, no sync issues | Camera stalls block everything; limits FPS to slower of capture/process | Only for initial proof-of-concept (first day) |
| Not verifying GPU acceleration | Avoids CUDA setup pain | May ship with CPU-only inference unknowingly; higher latency and CPU usage | Acceptable if CPU performance is verified as sufficient |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| MediaPipe + OpenCV | Passing BGR frames to MediaPipe (expects RGB) | Convert with `cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)` before passing to MediaPipe |
| MediaPipe + Camera | Not flipping frame horizontally for front-facing camera | MediaPipe assumes mirrored input; use `cv2.flip(frame, 1)` or configure MediaPipe accordingly |
| pynput + pystray | Both need threading coordination; pystray must be on main thread | Run pystray on main thread, detection loop on daemon thread, communicate via `threading.Event` |
| pynput keyboard controller | Creating controller instance per keypress | Create one `keyboard.Controller()` instance and reuse it; creating per-press adds overhead |
| YAML config + pynput Keys | Mapping string "ctrl" to `pynput.keyboard.Key.ctrl` | Build explicit string-to-Key mapping dict; do not use `getattr(Key, string)` blindly as it fails for regular characters |
| OpenCV + Windows shutdown | Not releasing camera on exit | Use `atexit.register(cap.release)` or try/finally; Windows may keep camera locked |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Processing every frame at full resolution | High CPU/GPU usage, thermal throttling | Resize to 640x480 or smaller before inference; MediaPipe does not need HD input | Immediately on laptops; within minutes on desktops |
| Drawing landmarks on every frame even without preview | Wasted CPU cycles on unused rendering | Only draw when `--preview` flag is active | Always wasteful; ~2-5ms per frame overhead |
| Logging every frame's gesture classification | Disk I/O bottleneck, huge log files | Log only state transitions (gesture detected, gesture lost, key fired) | Within minutes of running |
| Not setting `max_num_hands=1` | MediaPipe searches for multiple hands, doubling inference time | Set `max_num_hands=1` since only one hand is needed for gesture control | Immediately -- 2x inference cost for no benefit |
| Running MediaPipe in VIDEO mode instead of LIVE_STREAM | Higher latency, frame buffering | Use LIVE_STREAM running mode for real-time webcam input | Noticeable latency (100ms+) from first frame |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Running app as Administrator to "fix" pynput issues | App can now inject keys into ALL windows including security dialogs; malware risk if app is compromised | Accept UAC limitation; document it; never elevate by default |
| Webcam feed accessible to other processes | Privacy concern if camera stream is shared or logged | Never write frames to disk; never expose camera over network; clear frame buffer on shutdown |
| YAML config with arbitrary key combos | User could map gestures to dangerous combos (e.g., Alt+F4, Ctrl+Alt+Del) | Document risks in config comments; Ctrl+Alt+Del is blocked by Windows anyway (hardware interrupt) |
| Shipping with debug/preview mode enabled | Camera preview window visible; performance degraded | Default to no preview; require explicit `--preview` flag |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No feedback when gesture is detected but on cooldown | User holds gesture repeatedly, nothing happens, thinks app is broken | Show a subtle system tray notification or change tray icon color during cooldown |
| No way to know if camera is working without preview | User has no idea if detection is running | Change tray icon to indicate status: green = active + detecting, yellow = active + no hand seen, red = camera error |
| Activation delay feels like lag, not intentional | User thinks the app is slow/broken | In preview mode, show a visual progress bar for the activation timer filling up |
| No way to temporarily disable without quitting | User must quit and restart to stop accidental triggers during normal computer use | Already planned: Active toggle in tray menu. Make sure the keyboard shortcut is also available (e.g., global hotkey to toggle) |
| Config changes require app restart | Tedious edit-restart-test cycle during gesture tuning | Watch config file for changes and hot-reload (or add "Reload Config" to tray menu) |
| Gesture fires in wrong application | User gestures while switching windows; key goes to unintended app | Add a short delay after activation before sending key, or provide per-app enable/disable (v2 feature) |

## "Looks Done But Isn't" Checklist

- [ ] **Gesture classification:** Works with left hand, not just right hand -- test all 6 gestures with both hands
- [ ] **GPU acceleration:** Actually running on GPU, not silently falling back to CPU -- check `onnxruntime.get_available_providers()` at startup
- [ ] **Camera release:** Camera LED turns off when app exits (including via tray Quit, Ctrl+C, and crash) -- test all exit paths
- [ ] **Debounce:** Holding a gesture fires exactly once, not zero times (too strict) or multiple times (too loose) -- test with 10-second holds
- [ ] **Key combos:** Ctrl+Z actually sends Ctrl DOWN then Z DOWN then Z UP then Ctrl UP, not Ctrl+Z as a single event -- test in a real text editor
- [ ] **System tray:** Tray icon persists after closing preview window -- preview close should not kill the app
- [ ] **Config reload:** Changing gesture mappings in YAML actually takes effect -- test after editing config
- [ ] **Background operation:** App works when no window is focused (just desktop) -- pynput should still send keys
- [ ] **Startup camera:** App handles "camera not found" or "camera in use by another app" gracefully with a user-visible error, not a Python traceback

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Used legacy MediaPipe API | MEDIUM | Replace `mp.solutions.hands` with Task API; rewrite detection loop; landmark access pattern changes but indices are the same |
| No frame smoothing, debounce is unreliable | LOW | Add smoothing window before debounce state machine; does not require architectural changes |
| Single-threaded camera capture | MEDIUM | Extract capture into a separate thread with a shared frame variable; requires adding thread sync but detection logic stays the same |
| CUDA version mismatch | LOW | Pin correct versions in requirements.txt; add startup GPU verification; no code changes needed |
| Hardcoded gesture thresholds | LOW | Move constants to config.yaml; replace hardcoded values with config lookups |
| Left-hand detection broken | LOW | Add handedness check to gesture classification; flip thumb comparison; no architectural change |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Legacy MediaPipe API | Phase 1: Project setup | Confirm imports use `mediapipe.tasks.python.vision` not `mediapipe.solutions` |
| Left/right hand mirroring | Phase 1: Gesture classification | Test all 6 gestures with both left and right hand; automated test with sample landmark data |
| CUDA version mismatch | Phase 1: Environment setup | Startup log prints GPU provider status; fail-fast if GPU expected but unavailable |
| Camera capture blocking | Phase 1: Detector | Measure FPS in preview mode; should match camera FPS (30), not inference FPS |
| Debounce without smoothing | Phase 2: State machine | Hold gesture for 5 seconds in preview mode; verify exactly 1 trigger with no flickering in the smoothed label |
| pynput blocked by elevated apps | Phase 2: Keyboard sim | Test sending keys to Notepad (works), then to an admin-elevated app (document limitation) |
| Config hot-reload missing | Phase 3: Polish | Edit config.yaml while app runs; verify changes take effect without restart |
| No user feedback on state | Phase 3: Polish | Tray icon changes based on detection state; user can tell at a glance if app is working |

## Sources

- [MediaPipe Legacy Solutions deprecation notice](https://mediapipe.readthedocs.io/en/latest/solutions/hands.html)
- [MediaPipe Hand Landmarker Task API](https://developers.google.com/mediapipe/solutions/vision/gesture_recognizer)
- [onnxruntime-gpu CUDA compatibility docs](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html)
- [onnxruntime-gpu 1.21.0 CUDA version packaging bug](https://github.com/microsoft/onnxruntime/issues/23966)
- [The Hidden Pitfalls of ONNXRuntime GPU Setup](https://dev.to/deskpai/the-hidden-pitfalls-of-onnxruntime-gpu-setup-4kb7)
- [pynput platform limitations documentation](https://pynput.readthedocs.io/en/latest/limitations.html)
- [pynput system-wide input problems (Issue #15)](https://github.com/moses-palmer/pynput/issues/15)
- [pynput input lag with listeners (Issue #438)](https://github.com/moses-palmer/pynput/issues/438)
- [pynput admin privilege requirements (Issue #375)](https://github.com/moses-palmer/pynput/issues/375)
- [pystray threading and main thread requirements](https://pystray.readthedocs.io/en/latest/usage.html)
- [Threaded OpenCV capture for improved FPS](https://nrsyed.com/2018/07/05/multithreading-with-opencv-python-to-improve-video-processing-performance/)
- [MediaPipe hand tracking low-light performance research](https://www.mdpi.com/2079-9292/14/4/704)
- [Hand landmark left/right hand detection issues (GitHub gist)](https://gist.github.com/TheJLifeX/74958cc59db477a91837244ff598ef4a)
- [draw_landmarks fails with new HandLandmarker API (Issue #5361)](https://github.com/google-ai-edge/mediapipe/issues/5361)

---
*Pitfalls research for: Hand gesture recognition to keyboard commands (Windows, MediaPipe, pynput)*
*Researched: 2026-03-21*
