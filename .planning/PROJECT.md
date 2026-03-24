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
- ✓ Left-hand detection with same 6 static gestures + 4 swipe directions — v1.3
- ✓ One-hand-at-a-time mode with active hand selection and preferred_hand config — v1.3
- ✓ Left hand mirrors right-hand key mappings by default — v1.3
- ✓ Optional separate left-hand key mappings via left_gestures config section — v1.3
- ✓ Preview overlay hand indicator (L/R) showing active hand in real time — v1.3

### Active

## Current Milestone: v2.0 Structured Gesture Architecture

**Goal:** Clean rewrite of the gesture pipeline with activation gating, gesture hierarchy (static + temporal states), and action-based dispatch with multiple fire modes.

**Target features:**
- Activation gate: gesture-based arm/disarm with configurable bypass (scout/peace default)
- Gesture hierarchy: static gestures as base layer, hold and swiping as temporal state modifiers
- Action dispatch: static gesture × temporal state → mapped keyboard command
- Fire modes: tap (press+release) and hold_key (sustained keypress mirroring gesture state)
- Orchestrator managing gesture type prioritization and state transitions

### Out of Scope

- Custom gesture training / ML model training — MediaPipe landmarks sufficient for 6 gestures
- Mobile or cross-platform — Windows-only experiment
- GUI configuration — YAML file editing is sufficient
- Multiple camera support — single camera index from config
- Gesture profiles / per-app mappings — single global config for now
- GPU acceleration (onnxruntime-gpu) — MediaPipe Python on Windows is CPU-only; 30+ FPS on CPU is sufficient
- Simultaneous two-hand detection — one hand at a time; complexity deferred
- Per-hand debounce/cooldown tuning — same pipeline behavior for both hands
- Mirrored swipe directions for left hand — swipe directions are absolute

## Context

Clean rewrite milestone. Previous v1.0–v1.3 shipped 7,549 LOC Python with incremental gesture pipeline.
Tech stack: mediapipe, opencv-python, pynput, pystray, Pillow, PyYAML.
Platform: Windows 11, CPU inference (30+ FPS sufficient).
Previous architecture (being replaced): camera thread → MediaPipe landmarks → classifier → smoother → debouncer → keystroke sender.
New architecture target: activation gate → gesture orchestrator (static base + temporal modifiers) → action resolver → fire mode executor.
Compound gestures (v1.3) are subsumed by the temporal state model — no separate compound concept needed.

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
| Dict-based active hand selection | O(1) lookup from MediaPipe results, sticky during two-hand frames | ✓ Good — prevents hand-switch jitter |
| Classifier hand-agnostic (no changes) | MediaPipe landmarks normalize hand geometry; thumb uses abs() | ✓ Good — zero classifier code changes for left hand |
| Deep-merge for left gestures, full replace for swipes | Gestures benefit from partial override; swipe dirs are atomic | ✓ Good — intuitive config behavior |
| Pre-parse both hand mappings at startup | Avoid per-frame resolution overhead; instant swap on hand switch | ✓ Good — hot-reload re-parses both sets |

---
*Last updated: 2026-03-24 after v2.0 milestone started*
