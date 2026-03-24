"""System tray integration for gesture-keys using pystray."""

import logging
import os
import threading
import time

import pystray
from PIL import Image, ImageDraw

from gesture_keys.classifier import GestureClassifier
from gesture_keys.config import ConfigWatcher, extract_gesture_swipe_mappings, load_config, resolve_hand_gestures, resolve_hand_swipe_mappings
from gesture_keys.debounce import DebounceAction, DebounceState, GestureDebouncer
from gesture_keys.detector import CameraCapture, HandDetector
from gesture_keys.keystroke import KeystrokeSender, parse_key_string
from gesture_keys.distance import DistanceFilter
from gesture_keys.smoother import GestureSmoother
from gesture_keys.swipe import SwipeDetector

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


def _parse_swipe_key_mappings(swipe_mappings: dict[str, str]) -> dict:
    """Pre-parse swipe direction key strings into pynput objects.

    Args:
        swipe_mappings: Dict mapping direction name -> key string.

    Returns:
        Dict mapping direction_name -> (modifiers, key, original_key_string).
    """
    mappings = {}
    for direction_name, key_string in swipe_mappings.items():
        modifiers, key = parse_key_string(key_string)
        mappings[direction_name] = (modifiers, key, key_string)
    return mappings


def _parse_compound_swipe_key_mappings(gesture_swipe_mappings: dict[str, dict[str, str]]) -> dict:
    """Pre-parse compound gesture swipe key strings into pynput objects."""
    mappings = {}
    for gesture_name, directions in gesture_swipe_mappings.items():
        for direction_name, key_string in directions.items():
            modifiers, key = parse_key_string(key_string)
            mappings[(gesture_name, direction_name)] = (modifiers, key, key_string)
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
            detector = HandDetector(preferred_hand=config.preferred_hand)

            thresholds = {
                name: settings.get("threshold", 0.7)
                for name, settings in config.gestures.items()
                if isinstance(settings, dict)
            }
            classifier = GestureClassifier(thresholds)
            smoother = GestureSmoother(config.smoothing_window)

            # Build swipe direction sets for debouncer
            swipe_gesture_directions = {
                name: set(dirs.keys())
                for name, dirs in config.gesture_swipe_mappings.items()
            }

            debouncer = GestureDebouncer(
                config.activation_delay, config.cooldown_duration,
                gesture_cooldowns=config.gesture_cooldowns,
                gesture_modes=config.gesture_modes,
                hold_release_delay=config.hold_release_delay,
                swipe_gesture_directions=swipe_gesture_directions,
                swipe_window=config.swipe_window,
            )
            sender = KeystrokeSender()
            distance_filter = DistanceFilter(
                min_hand_size=config.min_hand_size,
                enabled=config.distance_enabled,
            )
            swipe_detector = SwipeDetector(
                min_velocity=config.swipe_min_velocity,
                min_displacement=config.swipe_min_displacement,
                axis_ratio=config.swipe_axis_ratio,
                cooldown_duration=config.swipe_cooldown,
                settling_frames=config.swipe_settling_frames,
            )
            swipe_detector.enabled = config.swipe_enabled
            watcher = ConfigWatcher(self._config_path)

            try:
                right_key_mappings = _parse_key_mappings(config.gestures)
                left_gestures_resolved = resolve_hand_gestures("Left", config)
                left_key_mappings = _parse_key_mappings(left_gestures_resolved)
                key_mappings = right_key_mappings  # start with right (or preferred hand)
            except ValueError as e:
                logger.error("Invalid key mapping: %s", e)
                camera.stop()
                detector.close()
                continue

            right_swipe_key_mappings = _parse_swipe_key_mappings(config.swipe_mappings) if config.swipe_enabled else {}
            left_swipe_resolved = resolve_hand_swipe_mappings("Left", config)
            left_swipe_key_mappings = _parse_swipe_key_mappings(left_swipe_resolved) if config.swipe_enabled else {}
            swipe_key_mappings = right_swipe_key_mappings

            # Pre-parse compound swipe key mappings for both hands
            right_compound_mappings = _parse_compound_swipe_key_mappings(config.gesture_swipe_mappings)
            left_gestures_swipe = extract_gesture_swipe_mappings(
                left_gestures_resolved,
                {**config.gesture_modes, **config.left_gesture_modes} if config.left_gesture_modes else config.gesture_modes,
            )
            left_compound_mappings = _parse_compound_swipe_key_mappings(left_gestures_swipe)
            compound_mappings = right_compound_mappings

            hand_was_in_range = True
            was_swiping = False
            pre_swipe_gesture = None
            prev_handedness = None

            # Hold-mode repeat state
            hold_active = False
            hold_modifiers = None
            hold_key = None
            hold_key_string = None
            hold_gesture_name = None
            hold_last_repeat = 0.0

            try:
                while self._active.is_set() and not self._shutdown.is_set():
                    ret, frame = camera.read()
                    if not ret or frame is None:
                        continue

                    current_time = time.perf_counter()
                    timestamp_ms = int(time.time() * 1000)
                    landmarks, handedness = detector.detect(frame, timestamp_ms)

                    # Hand switch detection: reset pipeline on hand change
                    if handedness is not None and prev_handedness is not None and handedness != prev_handedness:
                        # Instant switch: release holds, reset pipeline
                        hold_active = False
                        sender.release_all()
                        smoother.reset()
                        debouncer.reset()
                        swipe_detector.reset()
                        logger.info("Hand switch: %s -> %s", prev_handedness, handedness)
                        # Swap to correct mapping set for new hand
                        if handedness == "Left":
                            key_mappings = left_key_mappings
                            swipe_key_mappings = left_swipe_key_mappings
                            compound_mappings = left_compound_mappings
                        else:
                            key_mappings = right_key_mappings
                            swipe_key_mappings = right_swipe_key_mappings
                            compound_mappings = right_compound_mappings

                    # Initial hand detection: set mappings on first hand appearance
                    if prev_handedness is None and handedness is not None:
                        if handedness == "Left":
                            key_mappings = left_key_mappings
                            swipe_key_mappings = left_swipe_key_mappings
                            compound_mappings = left_compound_mappings
                        else:
                            key_mappings = right_key_mappings
                            swipe_key_mappings = right_swipe_key_mappings
                            compound_mappings = right_compound_mappings

                    prev_handedness = handedness if handedness is not None else prev_handedness

                    # Distance gating: suppress gestures when hand is too far
                    if landmarks:
                        in_range = distance_filter.check(landmarks)
                        if not in_range:
                            if hand_was_in_range:
                                hold_active = False
                                sender.release_all()
                                smoother.reset()
                                debouncer.reset()
                                swipe_detector.reset()
                            hand_was_in_range = False
                            landmarks = None
                        else:
                            hand_was_in_range = True
                    else:
                        hand_was_in_range = True

                    # --- Static gesture classification (runs FIRST for priority) ---
                    # Classify even during swipe cooldown (is_swiping is now ARMED-only)
                    swiping = config.swipe_enabled and swipe_detector.is_swiping
                    if swiping and not was_swiping:
                        pre_swipe_gesture = gesture
                        hold_active = False
                        sender.release_all()
                        smoother.reset()
                        debouncer.reset()
                    if was_swiping and not swiping:
                        hold_active = False
                        sender.release_all()
                        smoother.reset()
                        debouncer.reset()
                        # Suppress the pre-swipe gesture from re-firing after swipe
                        if pre_swipe_gesture is not None:
                            debouncer._state = DebounceState.COOLDOWN
                            debouncer._cooldown_gesture = pre_swipe_gesture
                            debouncer._cooldown_start = current_time
                            logger.debug(
                                "Swipe exit: suppressing %s re-fire",
                                pre_swipe_gesture.value,
                            )
                        pre_swipe_gesture = None
                    was_swiping = swiping
                    if landmarks and not swiping:
                        raw_gesture = classifier.classify(landmarks)
                        gesture = smoother.update(raw_gesture)
                    else:
                        gesture = smoother.update(None)

                    # --- Swipe detection (BEFORE debouncer) ---
                    swipe_result = None
                    if config.swipe_enabled:
                        suppress_swipe = debouncer.is_activating
                        swipe_result = swipe_detector.update(
                            landmarks or None, current_time,
                            suppressed=suppress_swipe,
                        )
                        if debouncer.in_swipe_window and swipe_result is not None:
                            gesture_name = debouncer.activating_gesture.value if debouncer.activating_gesture else None
                            mapped = swipe_gesture_directions.get(gesture_name, set())
                            if swipe_result.value not in mapped:
                                swipe_detector.reset()
                                swipe_result = None
                    else:
                        swipe_detector.update(None, current_time)

                    # --- Debounce and fire keystroke ---
                    if not swiping:
                        swipe_dir_for_debounce = swipe_result if debouncer.in_swipe_window else None
                        debounce_signal = debouncer.update(
                            gesture, current_time, swipe_direction=swipe_dir_for_debounce,
                        )
                    else:
                        debounce_signal = None

                    if debounce_signal is not None:
                        sig_gesture_name = debounce_signal.gesture.value
                        if debounce_signal.action == DebounceAction.COMPOUND_FIRE:
                            direction_name = debounce_signal.direction.value
                            lookup = (sig_gesture_name, direction_name)
                            if lookup in compound_mappings:
                                sig_mods, sig_key, sig_key_string = compound_mappings[lookup]
                                sender.send(sig_mods, sig_key)
                                logger.info("COMPOUND: %s + %s -> %s", sig_gesture_name, direction_name, sig_key_string)
                        elif sig_gesture_name in key_mappings:
                            sig_mods, sig_key, sig_key_string = key_mappings[sig_gesture_name]
                            if debounce_signal.action == DebounceAction.FIRE:
                                sender.send(sig_mods, sig_key)
                                logger.info("FIRED: %s -> %s", sig_gesture_name, sig_key_string)
                            elif debounce_signal.action == DebounceAction.HOLD_START:
                                sender.send(sig_mods, sig_key)
                                hold_active = True
                                hold_modifiers = sig_mods
                                hold_key = sig_key
                                hold_key_string = sig_key_string
                                hold_gesture_name = sig_gesture_name
                                hold_last_repeat = current_time
                                logger.info("HOLD START: %s -> %s", sig_gesture_name, sig_key_string)
                            elif debounce_signal.action == DebounceAction.HOLD_END:
                                hold_active = False
                                logger.info("HOLD END: %s -> %s", sig_gesture_name, sig_key_string)

                    # Standalone swipe
                    if (
                        swipe_result is not None
                        and not debouncer.in_swipe_window
                        and not (debounce_signal and debounce_signal.action == DebounceAction.COMPOUND_FIRE)
                    ):
                        swipe_name = swipe_result.value
                        if swipe_name in swipe_key_mappings:
                            modifiers, key, key_string = swipe_key_mappings[swipe_name]
                            sender.send(modifiers, key)
                            logger.info("SWIPE: %s -> %s", swipe_name, key_string)

                    # Hold-mode key repeat: send key at repeat interval while holding
                    if hold_active and current_time - hold_last_repeat >= config.hold_repeat_interval:
                        sender.send(hold_modifiers, hold_key)
                        hold_last_repeat = current_time

                    # Config hot-reload
                    if watcher.check(current_time):
                        try:
                            new_config = load_config(self._config_path)
                            hold_active = False
                            sender.release_all()
                            # Re-parse both hand mapping sets
                            right_key_mappings = _parse_key_mappings(new_config.gestures)
                            left_gestures_resolved = resolve_hand_gestures("Left", new_config)
                            left_key_mappings = _parse_key_mappings(left_gestures_resolved)
                            if prev_handedness == "Left":
                                key_mappings = left_key_mappings
                            else:
                                key_mappings = right_key_mappings
                            debouncer._activation_delay = new_config.activation_delay
                            debouncer._cooldown_duration = new_config.cooldown_duration
                            # Update debouncer with hand-appropriate cooldowns/modes
                            if prev_handedness == "Left" and new_config.left_gesture_cooldowns:
                                merged_cooldowns = {**new_config.gesture_cooldowns, **new_config.left_gesture_cooldowns}
                                merged_modes = {**new_config.gesture_modes, **new_config.left_gesture_modes}
                            else:
                                merged_cooldowns = new_config.gesture_cooldowns
                                merged_modes = new_config.gesture_modes
                            debouncer._gesture_cooldowns = merged_cooldowns
                            debouncer._gesture_modes = merged_modes
                            debouncer._hold_release_delay = new_config.hold_release_delay
                            # Handle SWIPE_WINDOW -> fire static action before resetting (spec requirement)
                            if debouncer.in_swipe_window and debouncer.activating_gesture is not None:
                                sw_gesture = debouncer.activating_gesture
                                sw_name = sw_gesture.value
                                if sw_name not in new_config.gesture_swipe_mappings:
                                    if sw_name in key_mappings:
                                        sig_mods, sig_key, sig_key_string = key_mappings[sw_name]
                                        sender.send(sig_mods, sig_key)
                                        logger.info("FIRED (reload): %s -> %s", sw_name, sig_key_string)
                            # Update compound swipe config
                            new_gesture_swipe_mappings = new_config.gesture_swipe_mappings
                            new_swipe_gesture_directions = {
                                name: set(dirs.keys())
                                for name, dirs in new_gesture_swipe_mappings.items()
                            }
                            debouncer._swipe_gesture_directions = new_swipe_gesture_directions
                            debouncer._swipe_window = new_config.swipe_window
                            swipe_gesture_directions = new_swipe_gesture_directions
                            # Re-parse compound key mappings for both hands
                            right_compound_mappings = _parse_compound_swipe_key_mappings(new_gesture_swipe_mappings)
                            new_left_gestures_resolved = resolve_hand_gestures("Left", new_config)
                            new_left_modes = {**new_config.gesture_modes, **new_config.left_gesture_modes} if new_config.left_gesture_modes else new_config.gesture_modes
                            new_left_gestures_swipe = extract_gesture_swipe_mappings(new_left_gestures_resolved, new_left_modes)
                            left_compound_mappings = _parse_compound_swipe_key_mappings(new_left_gestures_swipe)
                            if prev_handedness == "Left":
                                compound_mappings = left_compound_mappings
                            else:
                                compound_mappings = right_compound_mappings
                            debouncer.reset()
                            smoother.reset()
                            swipe_detector.settling_frames = new_config.swipe_settling_frames
                            swipe_detector._settling_frames_remaining = 0
                            distance_filter.enabled = new_config.distance_enabled
                            distance_filter.min_hand_size = new_config.min_hand_size
                            # Swipe hot-reload (both hands)
                            swipe_detector.min_velocity = new_config.swipe_min_velocity
                            swipe_detector.min_displacement = new_config.swipe_min_displacement
                            swipe_detector.axis_ratio = new_config.swipe_axis_ratio
                            swipe_detector.cooldown_duration = new_config.swipe_cooldown
                            swipe_detector.enabled = new_config.swipe_enabled
                            right_swipe_key_mappings = _parse_swipe_key_mappings(new_config.swipe_mappings) if new_config.swipe_enabled else {}
                            left_swipe_resolved = resolve_hand_swipe_mappings("Left", new_config)
                            left_swipe_key_mappings = _parse_swipe_key_mappings(left_swipe_resolved) if new_config.swipe_enabled else {}
                            if prev_handedness == "Left":
                                swipe_key_mappings = left_swipe_key_mappings
                            else:
                                swipe_key_mappings = right_swipe_key_mappings
                            logger.info(
                                "Config reloaded: %d gestures, delay=%.1fs, cooldown=%.1fs, distance=%s, swipe=%s",
                                len(new_config.gestures),
                                new_config.activation_delay,
                                new_config.cooldown_duration,
                                "on" if new_config.distance_enabled else "off",
                                "on" if new_config.swipe_enabled else "off",
                            )
                        except Exception as e:
                            logger.warning("Config reload failed: %s", e)
            finally:
                sender.release_all()
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
