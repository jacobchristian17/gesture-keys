"""System tray integration for gesture-keys using pystray."""

import logging
import os
import threading
import time

import pystray
from PIL import Image, ImageDraw

from gesture_keys.classifier import GestureClassifier
from gesture_keys.config import ConfigWatcher, load_config
from gesture_keys.debounce import GestureDebouncer
from gesture_keys.detector import CameraCapture, HandDetector
from gesture_keys.keystroke import KeystrokeSender, parse_key_string
from gesture_keys.smoother import GestureSmoother

logger = logging.getLogger("gesture_keys")


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


class TrayApp:
    """System tray application wrapping the gesture detection pipeline.

    Provides Active/Inactive toggle, Edit Config, and Quit menu items
    via a pystray system tray icon.

    Args:
        config_path: Path to the YAML configuration file.
    """

    def __init__(self, config_path: str) -> None:
        self._config_path = os.path.abspath(config_path)
        self._active = threading.Event()
        self._active.set()  # Start active
        self._shutdown = threading.Event()
        self._icon = None
        self._detection_thread = None

    def _create_icon_image(self) -> Image.Image:
        """Create a 64x64 RGBA icon image with a green circle.

        Returns:
            PIL Image suitable for use as a tray icon.
        """
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([8, 8, 56, 56], fill="#00cc66")
        return img

    def _build_menu(self) -> pystray.Menu:
        """Build the system tray context menu.

        Returns:
            pystray.Menu with Active toggle, Edit Config, and Quit items.
        """
        return pystray.Menu(
            pystray.MenuItem(
                text=lambda item: "Active" if self._active.is_set() else "Inactive",
                action=self._on_toggle,
                checked=lambda item: self._active.is_set(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Edit Config", self._on_edit_config),
            pystray.MenuItem("Quit", self._on_quit),
        )

    def _on_toggle(self, icon, item) -> None:
        """Toggle detection between active and inactive states."""
        if self._active.is_set():
            self._active.clear()
        else:
            self._active.set()

    def _on_edit_config(self, icon, item) -> None:
        """Open the config file in the default editor."""
        os.startfile(self._config_path)

    def _on_quit(self, icon, item) -> None:
        """Shut down the application cleanly.

        Sets shutdown event, unblocks any active.wait() to prevent deadlock,
        and stops the tray icon.
        """
        self._shutdown.set()
        self._active.set()  # Unblock wait to prevent deadlock
        icon.stop()

    def _detection_loop(self) -> None:
        """Run the gesture detection pipeline in a background thread.

        Outer loop checks shutdown/active state. Inner loop runs detection.
        Camera and detector are released when going inactive or shutting down.
        """
        while not self._shutdown.is_set():
            # Wait for active state, checking shutdown periodically
            if not self._active.wait(timeout=0.5):
                continue

            # Double-check shutdown after wait
            if self._shutdown.is_set():
                break

            # Load config and create pipeline components
            try:
                config = load_config(self._config_path)
            except Exception as e:
                logger.error("Failed to load config: %s", e)
                time.sleep(1.0)
                continue

            camera = CameraCapture(config.camera_index).start()
            detector = HandDetector()

            thresholds = {
                name: settings.get("threshold", 0.7)
                for name, settings in config.gestures.items()
                if isinstance(settings, dict)
            }
            classifier = GestureClassifier(thresholds)
            smoother = GestureSmoother(config.smoothing_window)
            debouncer = GestureDebouncer(
                config.activation_delay, config.cooldown_duration
            )
            sender = KeystrokeSender()
            watcher = ConfigWatcher(self._config_path)

            try:
                key_mappings = _parse_key_mappings(config.gestures)
            except ValueError as e:
                logger.error("Invalid key mapping: %s", e)
                camera.stop()
                detector.close()
                continue

            try:
                while self._active.is_set() and not self._shutdown.is_set():
                    ret, frame = camera.read()
                    if not ret or frame is None:
                        continue

                    current_time = time.perf_counter()
                    timestamp_ms = int(time.time() * 1000)
                    landmarks = detector.detect(frame, timestamp_ms)

                    if landmarks:
                        raw_gesture = classifier.classify(landmarks)
                        gesture = smoother.update(raw_gesture)
                    else:
                        gesture = smoother.update(None)

                    fire_gesture = debouncer.update(gesture, current_time)
                    if fire_gesture is not None:
                        gesture_name = fire_gesture.value
                        if gesture_name in key_mappings:
                            modifiers, key, key_string = key_mappings[gesture_name]
                            sender.send(modifiers, key)
                            logger.info("FIRED: %s -> %s", gesture_name, key_string)

                    # Config hot-reload
                    if watcher.check(current_time):
                        try:
                            new_config = load_config(self._config_path)
                            key_mappings = _parse_key_mappings(new_config.gestures)
                            debouncer._activation_delay = new_config.activation_delay
                            debouncer._cooldown_duration = new_config.cooldown_duration
                            debouncer.reset()
                            logger.info(
                                "Config reloaded: %d gestures",
                                len(new_config.gestures),
                            )
                        except Exception as e:
                            logger.warning("Config reload failed: %s", e)
            finally:
                camera.stop()
                detector.close()

    def _start_detection(self) -> None:
        """Start the detection loop in a daemon thread."""
        self._detection_thread = threading.Thread(
            target=self._detection_loop, daemon=True
        )
        self._detection_thread.start()

    def _on_setup(self, icon) -> None:
        """Setup callback after icon is visible. Starts detection and notifies."""
        icon.visible = True
        icon.notify("Gesture Keys is running", "Gesture Keys")
        self._start_detection()

    def run(self) -> None:
        """Run the tray application.

        Creates the pystray icon and starts the detection loop.
        Blocks until the icon is stopped (via Quit menu item).
        """
        self._icon = pystray.Icon(
            "gesture-keys",
            icon=self._create_icon_image(),
            title="Gesture Keys",
            menu=self._build_menu(),
        )
        self._icon.run(setup=self._on_setup)
