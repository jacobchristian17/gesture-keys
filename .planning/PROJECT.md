# Gesture Keys

## What This Is

A Python desktop app that uses the webcam to detect hand gestures via MediaPipe and translates them into keyboard commands (single keys and combos). Runs as a Windows system tray app with optional camera preview.

## Core Value

Hand gestures reliably trigger the correct keyboard commands in real applications without false fires.

## Requirements

### Validated

- ✓ Detect 6 hand gestures (open palm, fist, thumbs up, peace, pointing, pinch) from webcam via MediaPipe landmarks — v1.0
- ✓ Map each gesture to configurable keyboard commands (single keys and combos) via YAML config — v1.0
- ✓ Debounce gesture detection with activation delay and cooldown to prevent false triggers — v1.0
- ✓ Run as Windows system tray app with Active toggle, Edit Config, and Quit menu items — v1.0
- ✓ Support optional `--preview` flag for camera preview window during development/testing — v1.0
- ✓ Fire keyboard commands that work in any foreground application — v1.0
- ✓ Distance-based gesture gating — only detect gestures when hand is within configurable distance from camera — v1.1
- ✓ Swipe gestures (left, right, up, down) — detect directional hand movement and fire mapped keyboard commands — v1.1
- ✓ Preview overlays for distance value and swipe direction — v1.1

- ✓ Direct gesture-to-gesture firing without returning to "none" state — v1.2
- ✓ Faster swipe↔static transitions (reduced settling/cooldown lag) — v1.2
- ✓ Tuned debounce/cooldown/threshold defaults based on real usage — v1.2

### Active

(None yet — define in next milestone)

### Out of Scope

- Custom gesture training / ML model training — MediaPipe landmarks sufficient for 6 gestures
- Mobile or cross-platform — Windows-only experiment
- GUI configuration — YAML file editing is sufficient
- Multiple camera support — single camera index from config
- Gesture profiles / per-app mappings — single global config for now
- GPU acceleration (onnxruntime-gpu) — MediaPipe Python on Windows is CPU-only; 30+ FPS on CPU is sufficient
- Two-hand gestures — high complexity, defer until 6-gesture ceiling is hit

## Context

Shipped v1.2 with 6,661 LOC Python.
Tech stack: mediapipe, opencv-python, pynput, pystray, Pillow, PyYAML.
Platform: Windows 11, CPU inference (30+ FPS sufficient).
Architecture: camera thread → MediaPipe landmarks → classifier → smoother → debouncer → keystroke sender, all wrapped in pystray tray app.
Detection pipeline: static classification runs before swipe detection; debouncer.is_activating gates swipe arming. Per-gesture cooldowns and settling_frames are configurable via config.yaml.

## Constraints

- **Platform**: Windows only — pystray main thread requirement, `os.startfile()` for config editing
- **No custom ML**: Classification purely from MediaPipe landmark geometry, no training step
- **Python**: Standard Python ecosystem (pip, venv)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| MediaPipe landmarks over custom ML | No training data needed, 21 landmarks sufficient for 6 gestures | ✓ Good — reliable detection, no training overhead |
| pynput for keyboard simulation | Handles single keys and combos, works across apps | ✓ Good — works in all tested foreground apps |
| YAML config over GUI settings | Simpler to build, easy to hand-edit, sufficient for experiment | ✓ Good — hot-reload makes editing fast |
| Debounce state machine (0.4s activate, 0.8s cooldown) | Prevents false fires from transitional poses and held gestures | ✓ Good — configurable per user preference |
| Priority-ordered gesture classification | Resolves ambiguous poses deterministically (e.g., pinch vs pointing) | ✓ Good — no ambiguity in practice |
| Dropped GPU acceleration | MediaPipe Python on Windows is CPU-only, 30+ FPS sufficient | ✓ Good — simplified dependencies |
| RGBA icon + visible=True for pystray | RGB icons invisible on some Windows 11 configs | ✓ Good — fixed tray icon visibility |
| Lazy TrayApp import in __main__.py | Avoid loading pystray/Pillow when using --preview mode | ✓ Good — faster preview startup |
| COOLDOWN→ACTIVATING for different gesture | Enables direct gesture transitions without "none" intermediate | ✓ Good — ~15 LOC change, clean state machine extension |
| Swipe-exit reset (smoother+debouncer) | Fix latent bug where stale state carried over swipe→static | ✓ Good — prerequisite for settling frame reduction |
| Settling frames 10→3 | Reduce post-swipe latency from ~330ms to ~100ms | ✓ Good — safe with exit reset flushing stale state |
| Static-first priority gate | Prevent swipe arming while debouncer is activating a static gesture | ✓ Good — eliminates swipe-preempts-static bug |
| Per-gesture cooldowns via config.yaml | Different gestures need different cooldowns (e.g., pinch longer than fist) | ✓ Good — simple gesture.value string key lookup |

---
*Last updated: 2026-03-24 after v1.2 milestone*
