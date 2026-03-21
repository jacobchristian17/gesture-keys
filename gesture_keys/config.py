"""Configuration loading for gesture-keys."""

from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class AppConfig:
    """Application configuration loaded from YAML."""

    camera_index: int = 0
    smoothing_window: int = 3
    gestures: dict[str, dict[str, Any]] = field(default_factory=dict)


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

    return AppConfig(
        camera_index=int(camera.get("index", 0)),
        smoothing_window=int(detection.get("smoothing_window", 3)),
        gestures=gestures,
    )
