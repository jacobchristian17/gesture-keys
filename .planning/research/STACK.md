# Stack Research

**Domain:** Hand gesture recognition desktop app (Windows system tray)
**Researched:** 2026-03-21
**Confidence:** HIGH

## Critical Finding: GPU Acceleration

MediaPipe's Python API on Windows is **CPU-only**. There is no native GPU support for MediaPipe Python on Windows -- GPU acceleration is only available on Linux, Android, iOS, and web. However, MediaPipe hand landmark detection already achieves **30-60+ FPS on CPU**, which is more than sufficient for gesture-to-keystroke mapping at human interaction speeds.

The PROJECT.md mentions `onnxruntime-gpu` for acceleration, but this does not plug into MediaPipe's built-in hand landmarker pipeline on Windows without significant custom work (extracting models, running them manually through ONNX Runtime). **This is not worth the complexity for this project.** CPU inference at 30+ FPS with debounce timings of 0.4s activation is already far faster than the gesture recognition needs to be.

**Recommendation:** Drop `onnxruntime-gpu` from the stack. Use MediaPipe CPU inference. Revisit GPU only if CPU performance is measurably insufficient (unlikely).

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Python | 3.12 | Runtime | Latest stable version supported by MediaPipe. 3.13 has known MediaPipe compatibility issues. | HIGH |
| mediapipe | 0.10.33 | Hand landmark detection | Google's standard solution for hand tracking. 21 landmarks, CPU runs at 30-60 FPS on Windows. No viable alternative with this accuracy-to-simplicity ratio. | HIGH |
| opencv-python | 4.13.0.92 | Webcam capture and frame processing | Industry standard for video capture. MediaPipe expects OpenCV frames (BGR numpy arrays). Use `opencv-python` not `opencv-contrib-python` -- no extra modules needed. | HIGH |
| pynput | 1.8.1 | Keyboard command simulation | Handles single keys and combos via `Controller.press()`/`release()`. Works across foreground apps. Same author as pystray -- consistent API philosophy. | HIGH |
| pystray | 0.19.5 | Windows system tray icon/menu | The only maintained Python system tray library. Requires `icon.run()` on main thread (Windows constraint). In maintenance mode but stable and functional. | HIGH |
| Pillow | 12.1.1 | System tray icon image creation | Required by pystray for icon rendering. Use `Image.new()` + `ImageDraw` to create a simple colored icon programmatically rather than shipping an .ico file. | HIGH |
| PyYAML | 6.0.3 | Configuration file parsing | Standard YAML parser. Simple, well-understood. Always use `yaml.safe_load()` never `yaml.load()`. | HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy | (bundled with mediapipe) | Landmark coordinate math | Comes as mediapipe dependency. Use for distance calculations in gesture classification. |
| logging (stdlib) | -- | Application logging | Built-in. Use for debug output, gesture detection events, error reporting. |
| argparse (stdlib) | -- | CLI argument parsing | Built-in. For `--preview` flag and `--config` path override. |
| threading (stdlib) | -- | Concurrent detection loop | Built-in. Detection loop runs on daemon thread; pystray owns main thread. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| venv | Virtual environment | Use `python -m venv .venv`. Do NOT use conda -- adds unnecessary complexity for a pip-only stack. |
| pip | Package management | Pin exact versions in `requirements.txt`. No need for poetry/pipenv for a project this size. |
| ruff | Linting and formatting | Fast, replaces flake8+black+isort. Single tool, zero config needed. |
| pytest | Testing | For unit testing gesture classification logic (pure math on landmark coords). |

## Installation

```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Core dependencies
pip install mediapipe==0.10.33 opencv-python==4.13.0.92 pynput==1.8.1 pystray==0.19.5 Pillow==12.1.1 PyYAML==6.0.3

# Dev dependencies
pip install ruff pytest

# Freeze
pip freeze > requirements.txt
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| mediapipe (CPU) | mediapipe + onnxruntime-gpu (custom pipeline) | Only if CPU inference proves too slow -- requires extracting .tflite models, converting to ONNX, and managing inference manually. Massive complexity increase for marginal benefit. |
| mediapipe (CPU) | OpenPose | Never for this project. Requires separate installation, heavier models, no pip install. MediaPipe is strictly better for hand landmarks. |
| pynput | pyautogui | Never. pyautogui adds mouse/screen dependencies. pynput is lighter and focused on keyboard/mouse input. |
| pynput | keyboard (library) | Only if pynput has permission issues. The `keyboard` library requires root/admin on some systems but handles some edge cases differently. |
| pystray | infi.systray | Never. Unmaintained since 2019. pystray is the only viable option. |
| PyYAML | toml (tomllib) | If you prefer TOML syntax. YAML is fine for simple key-value gesture mappings. TOML would also work but YAML is more readable for nested combo key definitions. |
| ruff | flake8 + black | Never. ruff replaces both, runs 10-100x faster, single dependency. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| onnxruntime-gpu | MediaPipe Python on Windows is CPU-only. Adding onnxruntime-gpu does NOT accelerate MediaPipe's built-in hand landmarker. You'd need to extract models and build a custom inference pipeline -- massive complexity for a project where CPU already runs at 30-60 FPS. | mediapipe (CPU inference) |
| opencv-contrib-python | Conflicts with opencv-python if both installed. Adds 200+ MB of modules you won't use (CUDA, SIFT, etc). | opencv-python |
| tensorflow | MediaPipe bundles its own TFLite runtime. Installing full TensorFlow adds 500+ MB and provides zero benefit for hand landmark detection. | Nothing -- mediapipe handles inference internally. |
| pyinstaller (premature) | Don't package into .exe until the app works well. PyInstaller + mediapipe has known issues with model file bundling. Cross that bridge later. | Run from venv during development. |
| conda | Adds environment complexity. All dependencies are pip-installable. Conda's mediapipe packages often lag behind PyPI. | python -m venv + pip |
| keyboard (library) | Requires admin/root privileges on some platforms. pynput works without elevation for most use cases. | pynput |

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| mediapipe 0.10.33 | Python 3.9-3.12 | Does NOT support Python 3.13 yet. Stick with 3.12. |
| mediapipe 0.10.33 | opencv-python 4.x | MediaPipe internally uses OpenCV. Ensure only one opencv package is installed. |
| pystray 0.19.5 | Pillow 10+ | pystray uses Pillow for icon creation. Any recent Pillow works. |
| pynput 1.8.1 | Python 3.7+ | No known compatibility issues with other packages in this stack. |
| PyYAML 6.0.3 | Python 3.6+ | Stable, no conflicts expected. |

## Stack Patterns

**For development/testing:**
- Run with `--preview` flag to show OpenCV window with landmark overlay
- Use `cv2.imshow()` for camera preview (only when preview enabled)
- Log gesture detections to console for debugging

**For production/daily use:**
- Run as system tray app (no console, no preview window)
- Use `pythonw.exe` instead of `python.exe` to suppress console window
- Consider `--startup` flag to add to Windows startup via registry or shortcut

**Threading model (pystray constraint):**
- Main thread: `pystray.Icon.run()` -- must be main thread on Windows
- Daemon thread: OpenCV capture loop + MediaPipe inference + gesture classification + keyboard firing
- Communication: Use `threading.Event` for start/stop signals from tray menu

## Sources

- [mediapipe PyPI](https://pypi.org/project/mediapipe/) -- version 0.10.33, Python 3.9-3.12 support (HIGH confidence)
- [opencv-python PyPI](https://pypi.org/project/opencv-python/) -- version 4.13.0.92 (HIGH confidence)
- [pynput PyPI](https://pypi.org/project/pynput/) -- version 1.8.1 (HIGH confidence)
- [pystray PyPI](https://pypi.org/project/pystray/) -- version 0.19.5 (HIGH confidence)
- [Pillow PyPI](https://pypi.org/project/pillow/) -- version 12.1.1 (HIGH confidence)
- [PyYAML PyPI](https://pypi.org/project/PyYAML/) -- version 6.0.3 (HIGH confidence)
- [onnxruntime-gpu PyPI](https://pypi.org/project/onnxruntime-gpu/) -- version 1.24.4, CUDA 12.x required (HIGH confidence)
- [MediaPipe GPU Support docs](https://developers.google.com/mediapipe/framework/getting_started/gpu_support) -- Windows not supported (HIGH confidence)
- [MediaPipe Issue #5742](https://github.com/google-ai-edge/mediapipe/issues/5742) -- Confirms no GPU for Python on Windows (HIGH confidence)
- [ONNX Runtime CUDA EP docs](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html) -- CUDA 12.x + cuDNN 9 required (HIGH confidence)
- [Hand Tracking 30 FPS on CPU](https://medium.com/augmented-startups/hand-tracking-30-fps-on-cpu-in-5-minutes-986a749709d7) -- CPU performance benchmarks (MEDIUM confidence)
- [MediaPipe Hand Landmarker Guide](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker) -- model_complexity settings, Task API (HIGH confidence)

---
*Stack research for: Hand gesture recognition to keyboard commands (Windows desktop)*
*Researched: 2026-03-21*
