"""Unified gesture detection pipeline.

Extracts the shared detection logic from __main__.py and tray.py into a
single Pipeline class with a FrameResult dataclass for per-frame output.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

from gesture_keys.classifier import Gesture, GestureClassifier
from gesture_keys.config import (
    ConfigWatcher,
    extract_gesture_swipe_mappings,
    load_config,
    resolve_hand_gestures,
    resolve_hand_swipe_mappings,
)
from gesture_keys.detector import CameraCapture, HandDetector
from gesture_keys.distance import DistanceFilter
from gesture_keys.keystroke import KeystrokeSender, parse_key_string
from gesture_keys.orchestrator import (
    GestureOrchestrator,
    LifecycleState,
    OrchestratorAction,
    OrchestratorResult,
    TemporalState,
)
from gesture_keys.smoother import GestureSmoother
from gesture_keys.swipe import SwipeDetector

logger = logging.getLogger("gesture_keys")


# Backward-compatible DebounceState enum for FrameResult.debounce_state
class DebounceState(Enum):
    """Legacy debounce states for backward compatibility with preview.py."""

    IDLE = "IDLE"
    ACTIVATING = "ACTIVATING"
    FIRED = "FIRED"
    COOLDOWN = "COOLDOWN"
    HOLDING = "HOLDING"
    SWIPE_WINDOW = "SWIPE_WINDOW"


def _map_to_debounce_state(result: OrchestratorResult) -> DebounceState:
    """Map OrchestratorResult to legacy DebounceState for backward compat."""
    if result.outer_state == LifecycleState.IDLE:
        return DebounceState.IDLE
    elif result.outer_state == LifecycleState.ACTIVATING:
        return DebounceState.ACTIVATING
    elif result.outer_state == LifecycleState.SWIPE_WINDOW:
        return DebounceState.SWIPE_WINDOW
    elif result.outer_state == LifecycleState.ACTIVE:
        if result.temporal_state == TemporalState.HOLD:
            return DebounceState.HOLDING
        return DebounceState.FIRED  # CONFIRMED or SWIPING maps to FIRED
    elif result.outer_state == LifecycleState.COOLDOWN:
        return DebounceState.COOLDOWN
    return DebounceState.IDLE


@dataclass
class FrameResult:
    """Per-frame output from the unified detection pipeline."""

    landmarks: list | None = None
    handedness: str | None = None
    gesture: Gesture | None = None
    raw_gesture: Gesture | None = None
    debounce_state: DebounceState = DebounceState.IDLE
    swiping: bool = False
    frame_valid: bool = True
    orchestrator: OrchestratorResult | None = None


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
    """Pre-parse compound gesture swipe key strings into pynput objects.

    Args:
        gesture_swipe_mappings: Dict of {gesture_name: {direction: key_string}}.

    Returns:
        Dict mapping (gesture_name, direction) -> (modifiers, key, key_string).
    """
    mappings = {}
    for gesture_name, directions in gesture_swipe_mappings.items():
        for direction_name, key_string in directions.items():
            modifiers, key = parse_key_string(key_string)
            mappings[(gesture_name, direction_name)] = (modifiers, key, key_string)
    return mappings


class Pipeline:
    """Unified gesture detection pipeline.

    Owns: camera, detector, classifier, smoother, orchestrator,
          swipe_detector, distance_filter, sender, config_watcher,
          key mappings, and all per-frame state variables.

    Usage:
        pipeline = Pipeline("config.yaml")
        pipeline.start()
        try:
            while True:
                result = pipeline.process_frame()
                if not result.frame_valid:
                    continue
                # Use result for rendering, etc.
        finally:
            pipeline.stop()
    """

    def __init__(self, config_path: str) -> None:
        self._config_path = config_path
        self._config = load_config(config_path)

        # Components (created in start())
        self._camera = None
        self._detector = None
        self._classifier = None
        self._smoother = None
        self._orchestrator = None
        self._sender = None
        self._distance_filter = None
        self._swipe_detector = None
        self._watcher = None

        # Key mapping sets (populated in start())
        self._right_key_mappings = None
        self._left_key_mappings = None
        self._key_mappings = None
        self._right_swipe_key_mappings = None
        self._left_swipe_key_mappings = None
        self._swipe_key_mappings = None
        self._right_compound_mappings = None
        self._left_compound_mappings = None
        self._compound_mappings = None
        self._swipe_gesture_directions = None

        # Per-frame state
        self._prev_gesture = None
        self._prev_handedness = None
        self._hand_was_in_range = True

        # Hold state (repeat timing stays in Pipeline per user decision)
        self._hold_active = False
        self._hold_modifiers = None
        self._hold_key = None
        self._hold_key_string = None
        self._hold_gesture_name = None
        self._hold_last_repeat = 0.0

        # Frame storage for preview access
        self._last_frame = None
        self._current_time = 0.0

    @property
    def last_frame(self):
        """Return the most recent camera frame read by process_frame."""
        return self._last_frame

    def start(self) -> None:
        """Initialize camera, detector, and all pipeline components."""
        config = self._config

        self._camera = CameraCapture(config.camera_index).start()
        self._detector = HandDetector(preferred_hand=config.preferred_hand)

        # Extract per-gesture thresholds from nested config structure
        thresholds = {
            name: settings.get("threshold", 0.7)
            for name, settings in config.gestures.items()
            if isinstance(settings, dict)
        }
        self._classifier = GestureClassifier(thresholds)
        self._smoother = GestureSmoother(config.smoothing_window)

        # Build swipe direction sets for orchestrator
        self._swipe_gesture_directions = {
            name: set(dirs.keys())
            for name, dirs in config.gesture_swipe_mappings.items()
        }

        # Orchestrator and keystroke components
        self._orchestrator = GestureOrchestrator(
            config.activation_delay, config.cooldown_duration,
            gesture_cooldowns=config.gesture_cooldowns,
            gesture_modes=config.gesture_modes,
            hold_release_delay=config.hold_release_delay,
            swipe_gesture_directions=self._swipe_gesture_directions,
            swipe_window=config.swipe_window,
        )
        self._sender = KeystrokeSender()

        # Pre-parse key mappings for both hands (fail fast on invalid config)
        try:
            self._right_key_mappings = _parse_key_mappings(config.gestures)
            left_gestures_resolved = resolve_hand_gestures("Left", config)
            self._left_key_mappings = _parse_key_mappings(left_gestures_resolved)
            self._key_mappings = self._right_key_mappings  # start with right (or preferred hand)
        except ValueError as e:
            logger.error("Invalid key mapping in config: %s", e)
            raise

        # Distance gating filter
        # NOTE: Uses max_hand_size (fixes pre-existing bug in tray.py which was missing it)
        self._distance_filter = DistanceFilter(
            min_hand_size=config.min_hand_size,
            max_hand_size=config.max_hand_size,
            enabled=config.distance_enabled,
        )

        # Swipe detection (parallel path, bypasses smoother/orchestrator)
        self._swipe_detector = SwipeDetector(
            min_velocity=config.swipe_min_velocity,
            min_displacement=config.swipe_min_displacement,
            axis_ratio=config.swipe_axis_ratio,
            cooldown_duration=config.swipe_cooldown,
            settling_frames=config.swipe_settling_frames,
        )
        self._swipe_detector.enabled = config.swipe_enabled
        self._right_swipe_key_mappings = _parse_swipe_key_mappings(config.swipe_mappings) if config.swipe_enabled else {}
        left_swipe_resolved = resolve_hand_swipe_mappings("Left", config)
        self._left_swipe_key_mappings = _parse_swipe_key_mappings(left_swipe_resolved) if config.swipe_enabled else {}
        self._swipe_key_mappings = self._right_swipe_key_mappings

        # Pre-parse compound swipe key mappings for both hands
        self._right_compound_mappings = _parse_compound_swipe_key_mappings(config.gesture_swipe_mappings)
        left_gestures_swipe = extract_gesture_swipe_mappings(
            left_gestures_resolved,
            {**config.gesture_modes, **config.left_gesture_modes} if config.left_gesture_modes else config.gesture_modes,
        )
        self._left_compound_mappings = _parse_compound_swipe_key_mappings(left_gestures_swipe)
        self._compound_mappings = self._right_compound_mappings

        # Config hot-reload watcher
        self._watcher = ConfigWatcher(self._config_path)

    def stop(self) -> None:
        """Release all resources: camera, detector, held keys."""
        if self._sender is not None:
            self._sender.release_all()
        if self._camera is not None:
            self._camera.stop()
        if self._detector is not None:
            self._detector.close()

    def reset_pipeline(self) -> None:
        """Reset smoother, orchestrator, swipe_detector, and hold state."""
        self._smoother.reset()
        self._orchestrator.reset()
        self._swipe_detector.reset()
        self._hold_active = False
        self._sender.release_all()

    def process_frame(self) -> FrameResult:
        """Read camera frame and run the full detection pipeline.

        Returns:
            FrameResult with all computed values for the current frame.
        """
        ret, frame = self._camera.read()
        if not ret or frame is None:
            return FrameResult(frame_valid=False)

        self._last_frame = frame

        current_time = time.perf_counter()
        self._current_time = current_time

        # Detect hand landmarks
        timestamp_ms = int(time.time() * 1000)
        landmarks, handedness = self._detector.detect(frame, timestamp_ms)

        # Hand switch detection: reset pipeline on hand change
        if handedness is not None and self._prev_handedness is not None and handedness != self._prev_handedness:
            self._hold_active = False
            self._sender.release_all()
            self._smoother.reset()
            self._orchestrator.reset()
            self._swipe_detector.reset()
            logger.info("Hand switch: %s -> %s", self._prev_handedness, handedness)
            if handedness == "Left":
                self._key_mappings = self._left_key_mappings
                self._swipe_key_mappings = self._left_swipe_key_mappings
                self._compound_mappings = self._left_compound_mappings
            else:
                self._key_mappings = self._right_key_mappings
                self._swipe_key_mappings = self._right_swipe_key_mappings
                self._compound_mappings = self._right_compound_mappings

        # Initial hand detection: set mappings on first hand appearance
        if self._prev_handedness is None and handedness is not None:
            if handedness == "Left":
                self._key_mappings = self._left_key_mappings
                self._swipe_key_mappings = self._left_swipe_key_mappings
                self._compound_mappings = self._left_compound_mappings
            else:
                self._key_mappings = self._right_key_mappings
                self._swipe_key_mappings = self._right_swipe_key_mappings
                self._compound_mappings = self._right_compound_mappings

        self._prev_handedness = handedness if handedness is not None else self._prev_handedness

        # Distance gating: suppress gestures when hand is too far
        if landmarks:
            in_range = self._distance_filter.check(landmarks)
            if not in_range:
                if self._hand_was_in_range:
                    self._hold_active = False
                    self._sender.release_all()
                    self._smoother.reset()
                    self._orchestrator.reset()
                    self._swipe_detector.reset()
                self._hand_was_in_range = False
                landmarks = None
            else:
                self._hand_was_in_range = True
        else:
            self._hand_was_in_range = True  # No hand = reset tracking for next appearance

        # --- Static gesture classification ---
        swiping = self._config.swipe_enabled and self._swipe_detector.is_swiping
        if landmarks and not swiping:
            raw_gesture = self._classifier.classify(landmarks)
            gesture = self._smoother.update(raw_gesture)
        else:
            raw_gesture = None
            gesture = self._smoother.update(None)

        # Log gesture transitions at DEBUG level
        if gesture != self._prev_gesture:
            gesture_name = gesture.value if gesture else "None"
            logger.debug("Gesture: %s", gesture_name)
            self._prev_gesture = gesture

        # --- Swipe detection (BEFORE orchestrator so result can be passed in) ---
        swipe_result = None
        if self._config.swipe_enabled:
            suppress_swipe = self._orchestrator.is_activating
            swipe_result = self._swipe_detector.update(
                landmarks or None, current_time,
                suppressed=suppress_swipe,
            )

            # If in SWIPE_WINDOW and swipe fired for unmapped direction,
            # reset swipe detector to IDLE so it can detect a subsequent
            # mapped swipe.
            if self._orchestrator.in_swipe_window and swipe_result is not None:
                gesture_name = self._orchestrator.activating_gesture.value if self._orchestrator.activating_gesture else None
                mapped = self._swipe_gesture_directions.get(gesture_name, set())
                if swipe_result.value not in mapped:
                    self._swipe_detector.reset()
                    swipe_result = None
        else:
            self._swipe_detector.update(None, current_time)

        # --- Orchestrator update: single call replaces all coordination logic ---
        orch_result = self._orchestrator.update(
            gesture, current_time,
            swipe_direction=swipe_result,
            swiping=swiping,
        )

        # Process signals from orchestrator
        for signal in orch_result.signals:
            sig_gesture_name = signal.gesture.value
            if signal.action == OrchestratorAction.COMPOUND_FIRE:
                direction_name = signal.direction.value
                lookup = (sig_gesture_name, direction_name)
                if lookup in self._compound_mappings:
                    sig_mods, sig_key, sig_key_string = self._compound_mappings[lookup]
                    self._sender.send(sig_mods, sig_key)
                    logger.info("COMPOUND: %s + %s -> %s", sig_gesture_name, direction_name, sig_key_string)
            elif sig_gesture_name in self._key_mappings:
                sig_mods, sig_key, sig_key_string = self._key_mappings[sig_gesture_name]
                if signal.action == OrchestratorAction.FIRE:
                    self._sender.send(sig_mods, sig_key)
                    logger.info("FIRED: %s -> %s", sig_gesture_name, sig_key_string)
                elif signal.action == OrchestratorAction.HOLD_START:
                    self._sender.send(sig_mods, sig_key)
                    self._hold_active = True
                    self._hold_modifiers = sig_mods
                    self._hold_key = sig_key
                    self._hold_key_string = sig_key_string
                    self._hold_gesture_name = sig_gesture_name
                    self._hold_last_repeat = current_time
                    logger.info("HOLD START: %s -> %s", sig_gesture_name, sig_key_string)
                elif signal.action == OrchestratorAction.HOLD_END:
                    self._hold_active = False
                    logger.info("HOLD END: %s -> %s", sig_gesture_name, sig_key_string)

        # Handle swiping entry/exit hold release (orchestrator emits HOLD_END
        # but Pipeline also needs to release held keys and reset smoother)
        if swiping and self._hold_active:
            # Safety: if orchestrator signaled swiping entry, ensure keys released
            self._hold_active = False
            self._sender.release_all()
            self._smoother.reset()

        # Standalone swipe handling (gated by orchestrator's suppress flag)
        if swipe_result is not None and not orch_result.suppress_standalone_swipe:
            swipe_name = swipe_result.value
            if swipe_name in self._swipe_key_mappings:
                modifiers, key, key_string = self._swipe_key_mappings[swipe_name]
                self._sender.send(modifiers, key)
                logger.info("SWIPE: %s -> %s", swipe_name, key_string)

        # Hold-mode key repeat: send key at repeat interval while holding
        if self._hold_active and current_time - self._hold_last_repeat >= self._config.hold_repeat_interval:
            self._sender.send(self._hold_modifiers, self._hold_key)
            self._hold_last_repeat = current_time

        # Config hot-reload check
        if self._watcher.check(current_time):
            self.reload_config()

        return FrameResult(
            landmarks=landmarks,
            handedness=self._prev_handedness,
            gesture=gesture,
            raw_gesture=raw_gesture,
            debounce_state=_map_to_debounce_state(orch_result),
            swiping=swiping,
            frame_valid=True,
            orchestrator=orch_result,
        )

    def reload_config(self) -> None:
        """Hot-reload config, using flush_pending() for fire-before-reset edge case."""
        try:
            new_config = load_config(self._config_path)
            self._hold_active = False
            self._sender.release_all()

            # Re-parse both hand mapping sets
            self._right_key_mappings = _parse_key_mappings(new_config.gestures)
            left_gestures_resolved = resolve_hand_gestures("Left", new_config)
            self._left_key_mappings = _parse_key_mappings(left_gestures_resolved)
            if self._prev_handedness == "Left":
                self._key_mappings = self._left_key_mappings
            else:
                self._key_mappings = self._right_key_mappings

            # CRITICAL: flush pending gesture before reset (fire-before-reset edge case)
            flush_result = self._orchestrator.flush_pending()
            for signal in flush_result.signals:
                sig_gesture_name = signal.gesture.value
                if sig_gesture_name in self._key_mappings:
                    sig_mods, sig_key, sig_key_string = self._key_mappings[sig_gesture_name]
                    self._sender.send(sig_mods, sig_key)
                    logger.info("FIRED (reload): %s -> %s", sig_gesture_name, sig_key_string)

            # Update orchestrator config params
            self._orchestrator._activation_delay = new_config.activation_delay
            self._orchestrator._cooldown_duration = new_config.cooldown_duration

            if self._prev_handedness == "Left" and new_config.left_gesture_cooldowns:
                merged_cooldowns = {**new_config.gesture_cooldowns, **new_config.left_gesture_cooldowns}
                merged_modes = {**new_config.gesture_modes, **new_config.left_gesture_modes}
            else:
                merged_cooldowns = new_config.gesture_cooldowns
                merged_modes = new_config.gesture_modes
            self._orchestrator._gesture_cooldowns = merged_cooldowns
            self._orchestrator._gesture_modes = merged_modes
            self._orchestrator._hold_release_delay = new_config.hold_release_delay

            # Update compound swipe config
            new_gesture_swipe_mappings = new_config.gesture_swipe_mappings
            new_swipe_gesture_directions = {
                name: set(dirs.keys())
                for name, dirs in new_gesture_swipe_mappings.items()
            }
            self._orchestrator._swipe_gesture_directions = new_swipe_gesture_directions
            self._orchestrator._swipe_window = new_config.swipe_window
            self._swipe_gesture_directions = new_swipe_gesture_directions

            # Re-parse compound key mappings for both hands
            right_compound_mappings = _parse_compound_swipe_key_mappings(new_gesture_swipe_mappings)
            new_left_gestures_resolved = resolve_hand_gestures("Left", new_config)
            new_left_modes = {**new_config.gesture_modes, **new_config.left_gesture_modes} if new_config.left_gesture_modes else new_config.gesture_modes
            new_left_gestures_swipe = extract_gesture_swipe_mappings(new_left_gestures_resolved, new_left_modes)
            left_compound_mappings = _parse_compound_swipe_key_mappings(new_left_gestures_swipe)
            self._right_compound_mappings = right_compound_mappings
            self._left_compound_mappings = left_compound_mappings
            if self._prev_handedness == "Left":
                self._compound_mappings = left_compound_mappings
            else:
                self._compound_mappings = right_compound_mappings

            self._orchestrator.reset()
            self._smoother.reset()
            self._swipe_detector.settling_frames = new_config.swipe_settling_frames
            self._swipe_detector._settling_frames_remaining = 0
            self._distance_filter.enabled = new_config.distance_enabled
            self._distance_filter.min_hand_size = new_config.min_hand_size
            self._distance_filter.max_hand_size = new_config.max_hand_size

            # Swipe hot-reload (both hands)
            self._swipe_detector.min_velocity = new_config.swipe_min_velocity
            self._swipe_detector.min_displacement = new_config.swipe_min_displacement
            self._swipe_detector.axis_ratio = new_config.swipe_axis_ratio
            self._swipe_detector.cooldown_duration = new_config.swipe_cooldown
            self._swipe_detector.enabled = new_config.swipe_enabled
            self._right_swipe_key_mappings = _parse_swipe_key_mappings(new_config.swipe_mappings) if new_config.swipe_enabled else {}
            left_swipe_resolved = resolve_hand_swipe_mappings("Left", new_config)
            self._left_swipe_key_mappings = _parse_swipe_key_mappings(left_swipe_resolved) if new_config.swipe_enabled else {}
            if self._prev_handedness == "Left":
                self._swipe_key_mappings = self._left_swipe_key_mappings
            else:
                self._swipe_key_mappings = self._right_swipe_key_mappings

            self._config = new_config
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
