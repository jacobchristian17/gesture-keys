# Gesture Keys
![demo gif](https://github.com/user-attachments/assets/81e197c3-6162-426b-9851-63123425559f)

Hand gesture to keyboard command mapping via webcam.

## Installation

**[Download GestureKeys-v3.0-win64.zip](https://github.com/jacobchristian17/gesture-keys/releases/latest)**

Extract the zip and run `GestureKeys.exe`. No Python required.

## Requirements

- Windows 10/11
- Webcam

## Usage

1. Run `GestureKeys.exe` — a green circle appears in the system tray
2. Point your index finger at the camera to arm gesture detection
3. Perform a gesture to fire its mapped key

Right-click the tray icon to toggle on/off, edit config, or quit.

### Gestures

| Gesture | Default Key |
|---------|-------------|
| Open Palm | `win+tab` |
| Fist | `space` (hold) |
| Thumbs Up | `enter` |
| Peace | `win+ctrl+left` |
| Pointing | `alt+tab` |
| Pinch | `win+down` |
| Scout | `win+ctrl+right` |
| Swipe Left/Right/Up/Down | `left` / `right` / `up` / `down` |
| Fist → Open Palm | `esc` |

All gestures and key mappings are configurable in `config.yaml`. Changes hot-reload without restart.

### Running from source

```bash
git clone https://github.com/jacobchristian17/gesture-keys.git
cd gesture-keys
pip install -r requirements.txt
python -m gesture_keys
```

Python 3.10+ required.
