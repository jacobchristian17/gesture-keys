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
    smoothing_window: int = 3
    activation_delay: float = 0.4
    cooldown_duration: float = 0.8
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

    return AppConfig(
        camera_index=int(camera.get("index", 0)),
        smoothing_window=int(detection.get("smoothing_window", 3)),
        activation_delay=float(detection.get("activation_delay", 0.4)),
        cooldown_duration=float(detection.get("cooldown_duration", 0.8)),
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
    )
