"""CLI entry point for gesture-keys: python -m gesture_keys."""

import argparse
import logging
import os
import sys
import time

import cv2

from gesture_keys import __version__
from gesture_keys.classifier import GestureClassifier
from gesture_keys.config import ConfigWatcher, load_config
from gesture_keys.debounce import GestureDebouncer
from gesture_keys.detector import CameraCapture, HandDetector
from gesture_keys.keystroke import KeystrokeSender, parse_key_string
from gesture_keys.preview import draw_hand_landmarks, render_preview
from gesture_keys.smoother import GestureSmoother

logger = logging.getLogger("gesture_keys")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="gesture_keys",
        description="Hand gesture to keyboard command mapping",
    )
    parser.add_argument(
        "--preview", action="store_true",
        help="Open camera preview window with landmark overlay",
    )
    parser.add_argument(
        "--config", default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    return parser.parse_args()


def hide_console_window():
    """Hide the console window on Windows (tray mode only)."""
    if sys.platform == 'win32':
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE


def run_tray_mode(args):
    """Run in system tray mode (default, no preview)."""
    hide_console_window()
    from gesture_keys.tray import TrayApp
    app = TrayApp(config_path=args.config)
    app.run()


def print_banner(config, config_path):
    """Print a concise 4-line startup banner.

    Args:
        config: AppConfig instance.
        config_path: Path string used to load the config.
    """
    gesture_count = len(config.gestures)
    print(f"Gesture Keys v{__version__}")
    print(f"Camera: index {config.camera_index}")
    print(f"Config: {config_path} ({gesture_count} gestures loaded)")
    print("Detection started...")


def _parse_key_mappings(gestures: dict) -> dict:
    """Pre-parse key strings from gesture config into pynput objects.

    Args:
        gestures: Gesture config dict {name: {key: str, ...}}.

    Returns:
        Dict mapping gesture_name -> (modifiers, key, original_key_string).

    Raises:
        ValueError: If any key string is invalid (fail fast at startup).
    """
    mappings = {}
    for name, settings in gestures.items():
        if not isinstance(settings, dict) or "key" not in settings:
            continue
        key_string = settings["key"]
        modifiers, key = parse_key_string(key_string)
        mappings[name] = (modifiers, key, key_string)
    return mappings


def run_preview_mode(args):
    """Run the gesture detection loop with camera preview.

    Args:
        args: Parsed argparse namespace with config and preview fields.
    """
    # Load config
    config = load_config(args.config)

    # Print startup banner
    print_banner(config, args.config)

    # Setup logging: [HH:MM:SS] format per CONTEXT.md
    logging.basicConfig(
        format="[%(asctime)s] %(message)s",
        datefmt="%H:%M:%S",
        level=logging.INFO,
    )

    # Create pipeline components
    camera = CameraCapture(config.camera_index).start()
    detector = HandDetector()

    # Extract per-gesture thresholds from nested config structure
    # config.gestures has {name: {key: ..., threshold: ...}} -- classifier needs {name: float}
    thresholds = {
        name: settings.get("threshold", 0.7)
        for name, settings in config.gestures.items()
        if isinstance(settings, dict)
    }
    classifier = GestureClassifier(thresholds)
    smoother = GestureSmoother(config.smoothing_window)

    # Debounce and keystroke components
    debouncer = GestureDebouncer(
        config.activation_delay, config.cooldown_duration
    )
    sender = KeystrokeSender()

    # Pre-parse key mappings (fail fast on invalid config)
    try:
        key_mappings = _parse_key_mappings(config.gestures)
    except ValueError as e:
        logger.error("Invalid key mapping in config: %s", e)
        raise

    # Config hot-reload watcher
    watcher = ConfigWatcher(args.config)

    prev_gesture = None
    prev_time = time.perf_counter()
    fps = 0.0

    try:
        while True:
            ret, frame = camera.read()
            if not ret or frame is None:
                continue

            # Calculate FPS from frame delta
            current_time = time.perf_counter()
            dt = current_time - prev_time
            if dt > 0:
                fps = 1.0 / dt
            prev_time = current_time

            # Detect right-hand landmarks
            timestamp_ms = int(time.time() * 1000)
            landmarks = detector.detect(frame, timestamp_ms)

            # Classify and smooth
            if landmarks:
                raw_gesture = classifier.classify(landmarks)
                gesture = smoother.update(raw_gesture)
            else:
                gesture = smoother.update(None)

            # Log gesture transitions at DEBUG level
            if gesture != prev_gesture:
                gesture_name = gesture.value if gesture else "None"
                logger.debug("Gesture: %s", gesture_name)
                prev_gesture = gesture

            # Debounce and fire keystroke
            fire_gesture = debouncer.update(gesture, current_time)
            if fire_gesture is not None:
                gesture_name = fire_gesture.value
                if gesture_name in key_mappings:
                    modifiers, key, key_string = key_mappings[gesture_name]
                    sender.send(modifiers, key)
                    logger.info("FIRED: %s -> %s", gesture_name, key_string)

            # Config hot-reload check
            if watcher.check(current_time):
                try:
                    new_config = load_config(args.config)
                    key_mappings = _parse_key_mappings(new_config.gestures)
                    debouncer._activation_delay = new_config.activation_delay
                    debouncer._cooldown_duration = new_config.cooldown_duration
                    debouncer.reset()
                    logger.info(
                        "Config reloaded: %d gestures, delay=%.1fs, cooldown=%.1fs",
                        len(new_config.gestures),
                        new_config.activation_delay,
                        new_config.cooldown_duration,
                    )
                except Exception as e:
                    logger.warning("Config reload failed: %s", e)

            # Preview rendering
            if args.preview:
                if landmarks:
                    draw_hand_landmarks(frame, landmarks)
                gesture_label = gesture.value if gesture else None
                render_preview(frame, gesture_label, fps)

                key = cv2.waitKey(1) & 0xFF
                if key == 27:  # ESC
                    break
                # Check if window was closed via X button
                try:
                    if cv2.getWindowProperty("Gesture Keys", cv2.WND_PROP_VISIBLE) < 1:
                        break
                except cv2.error:
                    break

    except KeyboardInterrupt:
        pass
    finally:
        camera.stop()
        detector.close()
        if args.preview:
            cv2.destroyAllWindows()


def main():
    """Run gesture-keys: tray mode by default, preview mode with --preview."""
    args = parse_args()
    # Resolve config path relative to exe directory when frozen (PyInstaller)
    if not os.path.isabs(args.config) and getattr(sys, 'frozen', False):
        base = os.path.dirname(os.path.abspath(sys.argv[0]))
        args.config = os.path.join(base, args.config)
    if args.preview:
        run_preview_mode(args)
    else:
        run_tray_mode(args)


if __name__ == "__main__":
    main()
