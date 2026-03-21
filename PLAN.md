# Gesture Keys - Hand Gesture to Keyboard Command App

## Context
Build a Python app that uses the webcam to detect hand gestures via MediaPipe and translates them into keyboard commands (single keys and combos). Runs as a Windows system tray app with no camera preview by default. Leverages NVIDIA RTX 3060 GPU via CUDA for accelerated inference.

## Project Structure
```
gesture-keys/
├── main.py                  # Entry point with argparse (--preview, --config)
├── config.yaml              # Gesture-to-key mappings
├── requirements.txt
├── PLAN.md
└── gesture_keys/
    ├── __init__.py
    ├── gestures.py          # Gesture classification from MediaPipe landmarks
    ├── detector.py          # Camera capture + MediaPipe hand detection
    ├── keyboard_sim.py      # pynput keyboard simulation (single + combo keys)
    ├── config_loader.py     # YAML config loading, key string -> pynput Key conversion
    ├── tray.py              # pystray system tray (Active toggle, Edit Config, Quit)
    └── app.py               # Orchestrator: threading, debounce state machine
```

## Dependencies
- `mediapipe` - hand landmark detection (uses GPU automatically when available)
- `opencv-python` - camera capture
- `pynput` - keyboard simulation (single keys + combos)
- `pystray` + `Pillow` - system tray icon
- `PyYAML` - config file parsing
- `onnxruntime-gpu` - CUDA-accelerated inference on RTX 3060

## GPU Acceleration (RTX 3060)
- MediaPipe internally uses ONNX Runtime; installing `onnxruntime-gpu` enables CUDA execution
- This offloads hand landmark inference to the GPU, reducing CPU load and latency
- OpenCV camera capture remains CPU-bound (normal - capture is I/O, not compute)

## Supported Gestures (6 default)
| Gesture | Detection | Default Key |
|---|---|---|
| OPEN_PALM | All 5 fingers extended | `space` |
| FIST | All 5 fingers curled | `esc` |
| THUMBS_UP | Only thumb extended + pointing up | `enter` |
| PEACE | Index + middle extended only | `tab` |
| POINTING | Only index extended | `right` arrow |
| PINCH | Thumb tip + index tip close together | `ctrl+z` |

## Key Design Decisions

### Gesture Classification (`gestures.py`)
- Use MediaPipe's 21 hand landmarks (no custom ML training needed)
- Finger extension: compare tip vs PIP joint positions (y-axis for fingers, x-axis for thumb accounting for handedness)
- Priority-ordered classification: PINCH > FIST > THUMBS_UP > POINTING > PEACE > OPEN_PALM > None

### Debounce State Machine (`app.py`)
- **Activation delay**: 0.4s - gesture must be held steady before triggering
- **Cooldown**: 0.8s - minimum gap before same gesture re-triggers
- Prevents rapid-fire from holding a gesture or transitional poses
- Both values configurable in `config.yaml`

### Config (`config.yaml`)
- Camera settings (device index, resolution)
- Detection confidence thresholds
- Debounce timings
- Gesture-to-key mappings: strings for single keys (`"space"`), lists for combos (`["ctrl", "z"]`)

### Threading Model
- **Main thread**: pystray event loop (Windows requirement)
- **Daemon thread**: Camera capture + detection + keyboard firing
- Sync via `threading.Event` for active toggle and stop signal

### System Tray Menu
- **Active** (checkbox): toggle detection on/off
- **Edit Config**: opens `config.yaml` in default editor via `os.startfile()`
- **Quit**: stops camera, exits

## Implementation Order
1. Project skeleton + `requirements.txt`
2. `config_loader.py` + `config.yaml`
3. `gestures.py` - finger extension + gesture classification
4. `detector.py` - camera + MediaPipe integration
5. `keyboard_sim.py` - key execution
6. `app.py` - orchestrator with debounce state machine
7. `tray.py` - system tray with Pillow-generated icon
8. `main.py` - entry point

## Verification
1. `pip install -r requirements.txt`
2. `python main.py --preview` - verify camera opens and gestures are detected (console output)
3. Open a text editor, make gestures, confirm correct keys are sent
4. Test system tray: toggle active/inactive, edit config, quit
5. Test debounce: hold gesture and confirm single trigger, rapid gesture changes produce no false fires
