"""Configuration loading and hot-reload for gesture-keys."""

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import yaml

logger = logging.getLogger("gesture_keys")


@dataclass
class AppConfig:
    """Application configuration loaded from YAML."""

    camera_index: int = 0
    smoothing_window: int = 2
    activation_delay: float = 0.15
    cooldown_duration: float = 0.3
    gestures: dict[str, dict[str, Any]] = field(default_factory=dict)
    distance_enabled: bool = False
    min_hand_size: float = 0.15
    max_hand_size: float = 0.0
    swipe_enabled: bool = False
    swipe_cooldown: float = 0.5
    swipe_min_velocity: float = 0.4
    swipe_min_displacement: float = 0.08
    swipe_axis_ratio: float = 2.0
    swipe_mappings: dict[str, str] = field(default_factory=dict)
    swipe_settling_frames: int = 3
    gesture_cooldowns: dict[str, float] = field(default_factory=dict)
    gesture_modes: dict[str, str] = field(default_factory=dict)
    hold_release_delay: float = 0.1
    hold_repeat_interval: float = 0.03
    preferred_hand: str = "left"
    left_gestures: dict[str, dict[str, Any]] = field(default_factory=dict)
    left_swipe_mappings: dict[str, str] = field(default_factory=dict)
    left_gesture_cooldowns: dict[str, float] = field(default_factory=dict)
    left_gesture_modes: dict[str, str] = field(default_factory=dict)
    swipe_window: float = 0.2
    gesture_swipe_mappings: dict[str, dict[str, str]] = field(default_factory=dict)


class ConfigWatcher:
    """Watches a config file for changes using mtime polling.

    Args:
        path: Path to the config file to watch.
        check_interval: Minimum seconds between mtime checks.
    """

    def __init__(self, path: str, check_interval: float = 2.0) -> None:
        self._path = path
        self._check_interval = check_interval
        self._last_check_time: float = -1e9
        self._last_mtime: float = 0.0
        try:
            self._last_mtime = os.path.getmtime(path)
        except OSError:
            self._last_mtime = 0.0

    def check(self, current_time: float) -> bool:
        """Check if the config file has been modified.

        Args:
            current_time: Current timestamp (e.g. time.perf_counter()).

        Returns:
            True if file was modified since last check, False otherwise.
        """
        if current_time - self._last_check_time < self._check_interval:
            return False
        self._last_check_time = current_time
        try:
            mtime = os.path.getmtime(self._path)
        except OSError:
            return False
        if mtime != self._last_mtime:
            self._last_mtime = mtime
            return True
        return False


def _extract_gesture_cooldowns(gestures: dict) -> dict[str, float]:
    """Extract per-gesture cooldown overrides from gesture config entries.

    Args:
        gestures: Gesture config dict {name: {key: ..., cooldown: ...}}.

    Returns:
        Dict mapping gesture_name -> cooldown_duration for gestures with overrides.
    """
    cooldowns: dict[str, float] = {}
    for name, settings in gestures.items():
        if isinstance(settings, dict) and "cooldown" in settings:
            cooldowns[name] = float(settings["cooldown"])
    return cooldowns


def _extract_gesture_modes(gestures: dict) -> dict[str, str]:
    """Extract per-gesture mode from gesture config entries.

    Args:
        gestures: Gesture config dict {name: {key: ..., mode: ...}}.

    Returns:
        Dict mapping gesture_name -> "tap" or "hold" for all gestures.

    Raises:
        ValueError: If a gesture has an invalid mode value.
    """
    valid_modes = {"tap", "hold"}
    modes: dict[str, str] = {}
    for name, settings in gestures.items():
        if isinstance(settings, dict):
            mode = str(settings.get("mode", "tap")).lower()
            if mode not in valid_modes:
                raise ValueError(
                    f"Gesture '{name}' has invalid mode '{mode}'. "
                    f"Valid modes: {valid_modes}"
                )
            modes[name] = mode
    return modes


def extract_gesture_swipe_mappings(gestures: dict, gesture_modes: dict[str, str]) -> dict[str, dict[str, str]]:
    """Extract per-gesture swipe mappings from gesture config.

    Args:
        gestures: Gesture config dict.
        gesture_modes: Gesture mode dict (to reject hold mode).

    Returns:
        Dict mapping gesture_name -> {direction_name: key_string}.

    Raises:
        ValueError: If a hold-mode gesture has a swipe block.
    """
    swipe_directions = ("swipe_left", "swipe_right", "swipe_up", "swipe_down")
    mappings: dict[str, dict[str, str]] = {}
    for name, settings in gestures.items():
        if not isinstance(settings, dict) or "swipe" not in settings:
            continue
        swipe_block = settings["swipe"]
        if not isinstance(swipe_block, dict):
            continue
        mode = gesture_modes.get(name, "tap")
        if mode == "hold":
            raise ValueError(
                f"Gesture '{name}' uses hold mode and cannot have a swipe block. "
                "Static-to-swipe is only supported for tap mode gestures."
            )
        direction_map: dict[str, str] = {}
        for direction in swipe_directions:
            entry = swipe_block.get(direction)
            if isinstance(entry, dict) and "key" in entry:
                direction_map[direction] = entry["key"]
        if direction_map:
            mappings[name] = direction_map
    return mappings


def resolve_hand_gestures(handedness: str, config: AppConfig) -> dict:
    """Return the gesture dict for the given hand.

    When handedness is "Right" or left_gestures is empty, returns
    config.gestures unchanged (mirroring). When "Left" and left_gestures
    has entries, deep-merges left overrides onto right-hand defaults so
    that only explicitly overridden per-gesture settings change.

    Args:
        handedness: "Left" or "Right" (MediaPipe format).
        config: The loaded AppConfig.

    Returns:
        Gesture config dict for the active hand.
    """
    if handedness != "Left" or not config.left_gestures:
        return config.gestures

    import copy

    merged = copy.deepcopy(config.gestures)
    for gesture_name, left_settings in config.left_gestures.items():
        if gesture_name in merged:
            merged[gesture_name].update(left_settings)
        else:
            merged[gesture_name] = dict(left_settings)
    return merged


def resolve_hand_swipe_mappings(
    handedness: str, config: AppConfig
) -> dict[str, str]:
    """Return the swipe mappings for the given hand.

    When handedness is "Right" or left_swipe_mappings is empty, returns
    config.swipe_mappings. When "Left" and left_swipe_mappings has entries,
    returns left_swipe_mappings (full replacement, not merged).

    Args:
        handedness: "Left" or "Right" (MediaPipe format).
        config: The loaded AppConfig.

    Returns:
        Swipe mappings dict for the active hand.
    """
    if handedness != "Left" or not config.left_swipe_mappings:
        return config.swipe_mappings
    return config.left_swipe_mappings


def load_config(path: str = "config.yaml") -> AppConfig:
    """Load configuration from a YAML file.

    Args:
        path: Path to the YAML config file. Defaults to 'config.yaml'.

    Returns:
        AppConfig with camera, detection, and gesture settings.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the YAML is malformed or missing required sections.
    """
    try:
        with open(path, "r") as f:
            raw = yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Config file not found: {path}. "
            "Create a config.yaml or specify a valid path."
        )
    except yaml.YAMLError as e:
        raise ValueError(f"Malformed YAML in {path}: {e}")

    if not isinstance(raw, dict):
        raise ValueError(
            f"Config file {path} must contain a YAML mapping, got {type(raw).__name__}"
        )

    # Validate required sections
    if "camera" not in raw:
        raise ValueError(
            f"Config file {path} missing required 'camera' section"
        )
    if "gestures" not in raw:
        raise ValueError(
            f"Config file {path} missing required 'gestures' section"
        )

    camera = raw.get("camera", {})
    detection = raw.get("detection", {})
    gestures = raw.get("gestures", {})

    distance = raw.get("distance", {})

    swipe = raw.get("swipe", {})
    swipe_directions = ("swipe_left", "swipe_right", "swipe_up", "swipe_down")
    swipe_mappings: dict[str, str] = {}
    for direction in swipe_directions:
        mapping = swipe.get(direction)
        if isinstance(mapping, dict) and "key" in mapping:
            swipe_mappings[direction] = mapping["key"]
    swipe_enabled = bool(swipe) and len(swipe_mappings) > 0

    gesture_modes = _extract_gesture_modes(gestures)
    gesture_swipe_mappings = extract_gesture_swipe_mappings(gestures, gesture_modes)

    preferred_hand = str(raw.get("preferred_hand", "left")).lower()
    if preferred_hand not in ("left", "right"):
        raise ValueError(
            f"preferred_hand must be 'left' or 'right', got '{preferred_hand}'"
        )

    # Parse optional left-hand override sections
    left_gestures = raw.get("left_gestures", {}) or {}
    left_swipe_raw = raw.get("left_swipe", {}) or {}
    left_swipe_mappings: dict[str, str] = {}
    for direction in swipe_directions:
        mapping = left_swipe_raw.get(direction)
        if isinstance(mapping, dict) and "key" in mapping:
            left_swipe_mappings[direction] = mapping["key"]

    return AppConfig(
        camera_index=int(camera.get("index", 0)),
        smoothing_window=int(detection.get("smoothing_window", 2)),
        activation_delay=float(detection.get("activation_delay", 0.15)),
        cooldown_duration=float(detection.get("cooldown_duration", 0.3)),
        gestures=gestures,
        distance_enabled=bool(distance.get("enabled", False)),
        min_hand_size=float(distance.get("min_hand_size", 0.15)),
        max_hand_size=float(distance.get("max_hand_size", 0.0)),
        swipe_enabled=swipe_enabled,
        swipe_cooldown=float(swipe.get("cooldown", 0.5)),
        swipe_min_velocity=float(swipe.get("min_velocity", 0.4)),
        swipe_min_displacement=float(swipe.get("min_displacement", 0.08)),
        swipe_axis_ratio=float(swipe.get("axis_ratio", 2.0)),
        swipe_mappings=swipe_mappings,
        swipe_settling_frames=int(swipe.get("settling_frames", 3)),
        gesture_cooldowns=_extract_gesture_cooldowns(gestures),
        gesture_modes=gesture_modes,
        hold_release_delay=float(detection.get("hold_release_delay", 0.1)),
        hold_repeat_interval=float(detection.get("hold_repeat_interval", 0.03)),
        preferred_hand=preferred_hand,
        left_gestures=left_gestures,
        left_swipe_mappings=left_swipe_mappings,
        left_gesture_cooldowns=_extract_gesture_cooldowns(left_gestures),
        left_gesture_modes=_extract_gesture_modes(left_gestures),
        swipe_window=float(detection.get("swipe_window", 0.2)),
        gesture_swipe_mappings=gesture_swipe_mappings,
    )
