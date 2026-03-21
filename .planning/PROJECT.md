# Gesture Keys

## What This Is

A Python desktop app that uses the webcam to detect hand gestures via MediaPipe and translates them into keyboard commands (single keys and combos). Runs as a Windows system tray app with optional camera preview, leveraging an NVIDIA RTX 3060 GPU via CUDA for accelerated inference.

## Core Value

Hand gestures reliably trigger the correct keyboard commands in real applications without false fires.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Detect 6 hand gestures (open palm, fist, thumbs up, peace, pointing, pinch) from webcam via MediaPipe landmarks
- [ ] Map each gesture to configurable keyboard commands (single keys and combos) via YAML config
- [ ] Debounce gesture detection with activation delay (0.4s) and cooldown (0.8s) to prevent false triggers
- [ ] Run as Windows system tray app with Active toggle, Edit Config, and Quit menu items
- [ ] Support optional `--preview` flag for camera preview window during development/testing
- [ ] Accelerate inference on RTX 3060 via onnxruntime-gpu / CUDA
- [ ] Fire keyboard commands that work in any foreground application (text editors, browsers, etc.)

### Out of Scope

- Custom gesture training / ML model training — using MediaPipe landmarks only
- Mobile or cross-platform — Windows-only for v1
- GUI configuration — YAML file editing is sufficient
- Multiple camera support — single camera index from config
- Gesture profiles / per-app mappings — single global config

## Context

- Fun experiment to explore MediaPipe hand tracking + keyboard automation
- Target machine: Windows 11 with NVIDIA RTX 3060 (CUDA available)
- MediaPipe provides 21 hand landmarks; gesture classification uses finger tip vs PIP joint comparison
- Priority-ordered classification: PINCH > FIST > THUMBS_UP > POINTING > PEACE > OPEN_PALM > None
- Threading: pystray requires main thread on Windows; detection runs on daemon thread
- Key dependencies: mediapipe, opencv-python, pynput, pystray, Pillow, PyYAML, onnxruntime-gpu

## Constraints

- **Platform**: Windows only — pystray main thread requirement, `os.startfile()` for config editing
- **GPU**: NVIDIA RTX 3060 with CUDA — onnxruntime-gpu for acceleration
- **No custom ML**: Classification purely from MediaPipe landmark geometry, no training step
- **Python**: Standard Python ecosystem (pip, venv)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| MediaPipe landmarks over custom ML | No training data needed, 21 landmarks sufficient for 6 gestures | — Pending |
| pynput for keyboard simulation | Handles single keys and combos, works across apps | — Pending |
| YAML config over GUI settings | Simpler to build, easy to hand-edit, sufficient for experiment | — Pending |
| Debounce state machine (0.4s activate, 0.8s cooldown) | Prevents false fires from transitional poses and held gestures | — Pending |
| Priority-ordered gesture classification | Resolves ambiguous poses deterministically (e.g., pinch vs pointing) | — Pending |

---
*Last updated: 2026-03-21 after initialization*
