"""Unified gesture detection pipeline.

Extracts the shared detection logic from __main__.py and tray.py into a
single Pipeline class with a FrameResult dataclass for per-frame output.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

from gesture_keys.action import ActionDispatcher, ActionResolver
from gesture_keys.activation import ActivationGate
from gesture_keys.classifier import Gesture, GestureClassifier
from gesture_keys.config import (
    ConfigWatcher,
    build_action_maps,
    build_compound_action_maps,
    extract_gesture_swipe_mappings,
    load_config,
    resolve_hand_gestures,
)
from gesture_keys.detector import CameraCapture, HandDetector
from gesture_keys.distance import DistanceFilter
from gesture_keys.keystroke import KeystrokeSender, parse_key_string
from gesture_keys.orchestrator import (
    GestureOrchestrator,
    LifecycleState,
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
    SWIPE_WINDOW = "SWIPE_WINDOW"  # Legacy, no longer produced by orchestrator


def _map_to_debounce_state(result: OrchestratorResult) -> DebounceState:
    """Map OrchestratorResult to legacy DebounceState for backward compat."""
    if result.outer_state == LifecycleState.IDLE:
        return DebounceState.IDLE
    elif result.outer_state == LifecycleState.ACTIVATING:
        return DebounceState.ACTIVATING
    elif result.outer_state == LifecycleState.ACTIVE:
        if result.temporal_state == TemporalState.HOLD:
            return DebounceState.HOLDING
        return DebounceState.FIRED  # CONFIRMED maps to FIRED
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
    activation_armed: bool = False


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

        # Swipe key mapping sets (populated in start())
        self._right_swipe_key_mappings = None
        self._left_swipe_key_mappings = None
        self._swipe_key_mappings = None
        self._swipe_gesture_directions = None

        # Action dispatch (created in start())
        self._resolver = None
        self._dispatcher = None

        # Activation gate (created in start() when config enabled)
        self._activation_gate: ActivationGate | None = None
        self._activation_gestures: set[str] = set()
        self._activation_bypass: set[str] = set()

        # Per-frame state
        self._prev_gesture = None
        self._prev_handedness = None
        self._hand_was_in_range = True

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

        # Build Action maps for both hands (fail fast on invalid config)
        try:
            right_actions = build_action_maps(config.gestures, config.gesture_modes)
            left_gestures_resolved = resolve_hand_gestures("Left", config)
            left_actions = build_action_maps(left_gestures_resolved, config.gesture_modes)

            # Build compound Action maps
            right_compound = build_compound_action_maps(config.gesture_swipe_mappings)
            left_gestures_swipe = extract_gesture_swipe_mappings(left_gestures_resolved, config.gesture_modes)
            left_compound = build_compound_action_maps(left_gestures_swipe)

            self._resolver = ActionResolver(right_actions, left_actions, right_compound, left_compound)
            self._dispatcher = ActionDispatcher(
                self._sender, self._resolver,
                repeat_interval=config.hold_repeat_interval,
            )
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
        self._left_swipe_key_mappings = _parse_swipe_key_mappings(config.swipe_mappings) if config.swipe_enabled else {}
        self._swipe_key_mappings = self._right_swipe_key_mappings

        # Activation gate (None = bypass mode when disabled or no gestures)
        if config.activation_gate_enabled and config.activation_gate_gestures:
            self._activation_gate = ActivationGate(
                gesture=Gesture(config.activation_gate_gestures[0]),
                duration=config.activation_gate_duration,
            )
            self._activation_gestures = set(config.activation_gate_gestures)
            self._activation_bypass = set(config.activation_gate_bypass)
        else:
            self._activation_gate = None
            self._activation_gestures = set()
            self._activation_bypass = set()

        # Config hot-reload watcher
        self._watcher = ConfigWatcher(self._config_path)

    def stop(self) -> None:
        """Release all resources: camera, detector, held keys."""
        if self._dispatcher is not None:
            self._dispatcher.release_all()
        if self._camera is not None:
            self._camera.stop()
        if self._detector is not None:
            self._detector.close()

    def reset_pipeline(self) -> None:
        """Reset smoother, orchestrator, swipe_detector, and release held keys."""
        self._smoother.reset()
        self._orchestrator.reset()
        self._swipe_detector.reset()
        self._dispatcher.release_all()

    def _filter_signals_through_gate(
        self,
        signals: list,
        current_time: float,
    ) -> list:
        """Filter orchestrator signals through the activation gate.

        When gate is None (bypass mode), all signals pass unchanged.
        When gate is active:
          - Activation gesture signals arm/re-arm the gate and are consumed.
          - Non-activation signals pass only when the gate is armed.

        Args:
            signals: List of OrchestratorSignal from the orchestrator.
            current_time: Current frame timestamp.

        Returns:
            Filtered list of signals to dispatch.
        """
        if self._activation_gate is None:
            return signals

        filtered = []
        for signal in signals:
            gesture_value = signal.gesture.value
            if gesture_value in self._activation_bypass:
                # Bypass gesture: always passes through, ignores gate state
                filtered.append(signal)
            elif gesture_value in self._activation_gestures:
                # Activation gesture: arm/re-arm, consume signal
                self._activation_gate.arm(current_time)
            elif self._activation_gate.is_armed():
                # Non-activation signal while armed: pass through and reset idle timer
                self._activation_gate.keep_alive(current_time)
                filtered.append(signal)
            # else: gate not armed, suppress non-activation signal
        return filtered

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
            self._dispatcher.release_all()
            self._smoother.reset()
            self._orchestrator.reset()
            self._swipe_detector.reset()
            self._resolver.set_hand(handedness)
            logger.info("Hand switch: %s -> %s", self._prev_handedness, handedness)
            if handedness == "Left":
                self._swipe_key_mappings = self._left_swipe_key_mappings
            else:
                self._swipe_key_mappings = self._right_swipe_key_mappings

        # Initial hand detection: set mappings on first hand appearance
        if self._prev_handedness is None and handedness is not None:
            self._resolver.set_hand(handedness)
            if handedness == "Left":
                self._swipe_key_mappings = self._left_swipe_key_mappings
            else:
                self._swipe_key_mappings = self._right_swipe_key_mappings

        self._prev_handedness = handedness if handedness is not None else self._prev_handedness

        # Distance gating: suppress gestures when hand is too far
        if landmarks:
            in_range = self._distance_filter.check(landmarks)
            if not in_range:
                if self._hand_was_in_range:
                    self._dispatcher.release_all()
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

        else:
            self._swipe_detector.update(None, current_time)

        # --- Orchestrator update: single call replaces all coordination logic ---
        orch_result = self._orchestrator.update(gesture, current_time)

        # Activation gate: tick, detect expiry, filter signals
        if self._activation_gate is not None:
            was_armed = self._activation_gate.is_armed()
            self._activation_gate.tick(current_time)
            if was_armed and not self._activation_gate.is_armed():
                # Gate expired: release held keys and reset orchestrator
                self._dispatcher.release_all()
                self._orchestrator.reset()

        filtered_signals = self._filter_signals_through_gate(orch_result.signals, current_time)

        # Dispatch filtered orchestrator signals through ActionDispatcher
        for signal in filtered_signals:
            self._dispatcher.dispatch(signal)

        # Tick tap-repeat: sends held keystroke if interval elapsed
        self._dispatcher.tick(current_time)

        # Safety: release held keys when entering swiping state
        if swiping and self._dispatcher._held_action is not None:
            self._dispatcher.release_all()
            self._smoother.reset()

        # Standalone swipe handling (gated by activation gate)
        gate_allows_swipe = self._activation_gate is None or self._activation_gate.is_armed()
        if swipe_result is not None and gate_allows_swipe:
            swipe_name = swipe_result.value
            if swipe_name in self._swipe_key_mappings:
                modifiers, key, key_string = self._swipe_key_mappings[swipe_name]
                self._sender.send(modifiers, key)
                logger.info("SWIPE: %s -> %s", swipe_name, key_string)
                if self._activation_gate is not None:
                    self._activation_gate.keep_alive(current_time)

        # Config hot-reload check
        if self._watcher.check(current_time):
            self.reload_config()

        activation_armed = (
            self._activation_gate.is_armed()
            if self._activation_gate is not None
            else False
        )
        return FrameResult(
            landmarks=landmarks,
            handedness=self._prev_handedness,
            gesture=gesture,
            raw_gesture=raw_gesture,
            debounce_state=_map_to_debounce_state(orch_result),
            swiping=swiping,
            frame_valid=True,
            orchestrator=orch_result,
            activation_armed=activation_armed,
        )

    def reload_config(self) -> None:
        """Hot-reload config, using flush_pending() for fire-before-reset edge case."""
        try:
            new_config = load_config(self._config_path)
            self._dispatcher.release_all()

            # CRITICAL: flush pending gesture before reset (fire-before-reset edge case)
            # Route flush through dispatcher so Action resolution and fire modes apply
            flush_result = self._orchestrator.flush_pending()
            for signal in flush_result.signals:
                self._dispatcher.dispatch(signal)

            # Rebuild ActionResolver with new action maps
            new_left_gestures_resolved = resolve_hand_gestures("Left", new_config)
            right_actions = build_action_maps(new_config.gestures, new_config.gesture_modes)
            left_actions = build_action_maps(new_left_gestures_resolved, new_config.gesture_modes)
            right_compound = build_compound_action_maps(new_config.gesture_swipe_mappings)
            new_left_gestures_swipe = extract_gesture_swipe_mappings(new_left_gestures_resolved, new_config.gesture_modes)
            left_compound = build_compound_action_maps(new_left_gestures_swipe)
            self._resolver = ActionResolver(right_actions, left_actions, right_compound, left_compound)
            self._dispatcher._resolver = self._resolver
            self._dispatcher._repeat_interval = new_config.hold_repeat_interval
            if self._prev_handedness is not None:
                self._resolver.set_hand(self._prev_handedness)

            # Update orchestrator config params
            self._orchestrator._activation_delay = new_config.activation_delay
            self._orchestrator._cooldown_duration = new_config.cooldown_duration

            self._orchestrator._gesture_cooldowns = new_config.gesture_cooldowns
            self._orchestrator._gesture_modes = new_config.gesture_modes
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
            self._left_swipe_key_mappings = _parse_swipe_key_mappings(new_config.swipe_mappings) if new_config.swipe_enabled else {}
            if self._prev_handedness == "Left":
                self._swipe_key_mappings = self._left_swipe_key_mappings
            else:
                self._swipe_key_mappings = self._right_swipe_key_mappings

            # Activation gate hot-reload
            old_gate = self._activation_gate
            if new_config.activation_gate_enabled and new_config.activation_gate_gestures:
                if old_gate is not None:
                    # Update existing gate in-place
                    old_gate.duration = new_config.activation_gate_duration
                    self._activation_gestures = set(new_config.activation_gate_gestures)
                    self._activation_bypass = set(new_config.activation_gate_bypass)
                else:
                    # Enable: create new gate
                    self._activation_gate = ActivationGate(
                        gesture=Gesture(new_config.activation_gate_gestures[0]),
                        duration=new_config.activation_gate_duration,
                    )
                    self._activation_gestures = set(new_config.activation_gate_gestures)
                    self._activation_bypass = set(new_config.activation_gate_bypass)
            else:
                if old_gate is not None:
                    # Disable: destroy gate and release held keys
                    self._dispatcher.release_all()
                self._activation_gate = None
                self._activation_gestures = set()
                self._activation_bypass = set()

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
