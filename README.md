# Gesture Keys

Hand gesture to keyboard command mapping via webcam. Detect hand gestures in real time using MediaPipe and fire configurable keyboard shortcuts in any application.

## Download

**[Download GestureKeys.exe (Latest Release)](https://github.com/jacobchristian17/gesture-keys/releases/latest)**

No Python installation required. Extract the zip and run `GestureKeys.exe`.

## Supported Gestures

| Gesture | Description | Default Key |
|---------|-------------|-------------|
| Open Palm | All 5 fingers extended | `win+tab` |
| Fist | All fingers closed | `esc` |
| Thumbs Up | Thumb extended | `enter` |
| Peace | Index + middle fingers | `win+ctrl+left` |
| Pointing | Index finger only | `alt+tab` |
| Pinch | Index + thumb together | `win+down` |
| Scout | Index + middle + ring | `win+ctrl+right` |

All gestures and key mappings are configurable via `config.yaml`.

## Usage

### From the exe (recommended)

1. Download and extract the latest release
2. Run `GestureKeys.exe`
3. A green circle icon appears in the system tray
4. Right-click the tray icon for options:
   - **Active/Inactive** — toggle gesture detection on/off
   - **Edit Config** — open `config.yaml` in your default editor
   - **Quit** — stop and exit

### From source

```bash
# Clone and install dependencies
git clone https://github.com/jacobchristian17/gesture-keys.git
cd gesture-keys
pip install -r requirements.txt

# Run in tray mode (default, no window)
python -m gesture_keys

# Run with camera preview (for testing/debugging)
python -m gesture_keys --preview
```

## Configuration

Edit `config.yaml` to customize gestures, keys, and detection settings. Changes are hot-reloaded without restarting.

```yaml
camera:
  index: 0              # Camera device index

detection:
  smoothing_window: 1   # Majority-vote smoothing frames
  activation_delay: 0.05 # Seconds to hold gesture before firing
  cooldown_duration: 0.5 # Seconds before gesture can re-fire

gestures:
  open_palm:
    key: win+tab         # Key combo to fire
    threshold: 0.7       # Detection confidence threshold
  fist:
    key: esc
    threshold: 0.7
  # Add or modify gestures as needed
```

### Key format

- Single keys: `a`, `enter`, `esc`, `space`, `tab`, `f1`
- Modifiers: `ctrl+c`, `alt+tab`, `win+d`, `shift+a`
- Combos: `ctrl+shift+t`, `win+ctrl+left`

## Building the exe

```bash
pip install pyinstaller
python build_exe.py
```

Output: `dist/GestureKeys/GestureKeys.exe`

## Requirements

- Windows 10/11
- Webcam
- Python 3.10+ (only if running from source)

## How it works

Camera frames → MediaPipe hand landmarks → gesture classification (rule-based, right hand only) → frame smoothing → debounce state machine → keyboard command via pynput.

Detection runs on a background thread. The system tray (pystray) runs on the main thread.

## License

MIT
