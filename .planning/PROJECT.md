# Gesture Keys

## What This Is

A Python desktop app that uses the webcam to detect hand gestures via MediaPipe and translates them into keyboard commands via a structured pipeline: activation gate, gesture orchestrator (tri-state model: static/holding/moving), action resolver with 4 trigger types, and key lifecycle management. Runs as a Windows system tray app with optional camera preview.

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
- ✓ Faster swipe-to-static transitions (reduced settling/cooldown lag) — v1.2
- ✓ Tuned debounce/cooldown/threshold defaults based on real usage — v1.2
- ✓ Left-hand detection with same 6 static gestures + 4 swipe directions — v1.3
- ✓ One-hand-at-a-time mode with active hand selection and preferred_hand config — v1.3
- ✓ Left hand mirrors right-hand key mappings by default — v1.3
- ✓ Optional separate left-hand key mappings via left_gestures config section — v1.3
- ✓ Preview overlay hand indicator (L/R) showing active hand in real time — v1.3
- ✓ Unified Pipeline class with shared data types (FrameResult, GestureState) eliminating preview/tray duplication — v2.0
- ✓ Hierarchical GestureOrchestrator FSM managing static/hold/swiping state transitions — v2.0
- ✓ ActionResolver + ActionDispatcher with tap and hold_key fire modes — v2.0
- ✓ Centralized stuck-key prevention across all exit paths — v2.0
- ✓ Activation gate with configurable arm/disarm, bypass mode, and hot-reload — v2.0
- ✓ Tri-state gesture model (static/holding/moving with direction) replacing separate gesture + swipe systems — v3.0
- ✓ Compact trigger string syntax for config (`gesture:state[:direction]`, sequences with `>`) — v3.0
- ✓ MotionDetector replacing SwipeDetector (continuous per-frame signal, no state machine) — v3.0
- ✓ New `actions:` config section replacing `gestures:` and `swipe:` sections — v3.0
- ✓ Orchestrator simplification: remove swipe states, add MOVING_FIRE and SEQUENCE_FIRE signals — v3.0
- ✓ Sequence gesture support (gesture A then B within time window) — v3.0
- ✓ ActionResolver/Dispatcher update for 4 trigger types (static, holding, moving, sequence) — v3.0
- ✓ Pipeline integration: MotionDetector + DerivedConfig end-to-end — v3.0
- ✓ Legacy swipe code and config formats removed, clean tri-state codebase — v3.0

### Active

(None — planning next milestone)

### Out of Scope

- Custom gesture training / ML model training — MediaPipe landmarks sufficient for 6 gestures
- Mobile or cross-platform — Windows-only experiment
- GUI configuration — YAML file editing is sufficient
- Multiple camera support — single camera index from config
- Gesture profiles / per-app mappings — single global config for now
- GPU acceleration (onnxruntime-gpu) — MediaPipe Python on Windows is CPU-only; 30+ FPS on CPU is sufficient
- Simultaneous two-hand detection — one hand at a time; complexity deferred
- MotionDetector config tuning via YAML — motion: section exists but is not parsed (hardcoded defaults sufficient for now)

## Context

Shipped v3.0 with ~9,000 LOC Python (down from v2.0's ~12,000 — cleanup removed ~3,000 lines of legacy swipe code). Architecture: unified Pipeline → ActivationGate → GestureOrchestrator (tri-state FSM) → ActionResolver (4 trigger-type maps) → ActionDispatcher → KeystrokeSender. MotionDetector provides continuous per-frame motion state. Config uses compact trigger string syntax (`gesture:state[:direction]`, sequences with `>`).
Tech stack: mediapipe, opencv-python, pynput, pystray, Pillow, PyYAML.
Platform: Windows 11, CPU inference (30+ FPS sufficient).
405 tests passing with full TDD coverage across pipeline, orchestrator, action dispatch, motion detection, trigger parsing, and activation gate subsystems.

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
| COOLDOWN->ACTIVATING for different gesture | Enables direct gesture transitions without "none" intermediate | ✓ Good — ~15 LOC change, clean state machine extension |
| Static-first priority gate | Prevent swipe arming while debouncer is activating a static gesture | ✓ Good — eliminates swipe-preempts-static bug |
| Per-gesture cooldowns via config.yaml | Different gestures need different cooldowns (e.g., pinch longer than fist) | ✓ Good — simple gesture.value string key lookup |
| Dict-based active hand selection | O(1) lookup from MediaPipe results, sticky during two-hand frames | ✓ Good — prevents hand-switch jitter |
| Classifier hand-agnostic (no changes) | MediaPipe landmarks normalize hand geometry; thumb uses abs() | ✓ Good — zero classifier code changes for left hand |
| Deep-merge for left gestures, full replace for swipes | Gestures benefit from partial override; swipe dirs are atomic | ✓ Good — intuitive config behavior |
| Pre-parse both hand mappings at startup | Avoid per-frame resolution overhead; instant swap on hand switch | ✓ Good — hot-reload re-parses both sets |
| Unified Pipeline class (v2.0) | Eliminated 90% duplication between preview/tray detection loops | ✓ Good — ~70 line preview, ~29 line tray wrapper |
| Hierarchical FSM for orchestrator (v2.0) | Outer lifecycle + inner temporal state cleanly separates concerns | ✓ Good — replaced scattered debouncer + main-loop coordination |
| Resolver-Dispatcher separation (v2.0) | Pure lookup (ActionResolver) separated from stateful dispatch (ActionDispatcher) | ✓ Good — testable, single held-action field prevents state desync |
| App-controlled tap-repeat (v2.0) | Windows SendInput doesn't auto-repeat key-down events | ✓ Good — 33Hz tap-repeat matches real keyboard behavior |
| gate=None as bypass mode (v2.0) | Zero overhead for default config, not a disabled flag | ✓ Good — no conditional checks on hot path when gate unused |
| Tri-state model over separate gesture+swipe (v3.0) | Unified static/holding/moving eliminates dual-system complexity | ✓ Good — single config format, one orchestrator path, ~3k lines removed |
| Compact trigger string syntax (v3.0) | `fist:holding` more readable than nested YAML for action definitions | ✓ Good — parse_trigger() validates at load time, clear error messages |
| MotionDetector with velocity hysteresis (v3.0) | Per-frame signal vs SwipeDetector's event-based approach | ✓ Good — simpler integration, no state machine, continuous updates |
| DerivedConfig for trigger routing (v3.0) | 8 typed maps (4 trigger types × 2 hands) derived once at config load | ✓ Good — O(1) lookup per frame, hot-reload rebuilds maps |
| Sequence gestures via orchestrator (v3.0) | Two-gesture sequences (A then B within 0.5s window) in FSM | ✓ Good — configurable window, clean signal emission |

---
*Last updated: 2026-03-27 after v3.0 milestone complete*
