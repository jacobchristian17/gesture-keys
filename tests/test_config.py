"""Tests for gesture_keys.config module."""

import os
import time

import pytest

from gesture_keys.config import AppConfig, ConfigWatcher, load_config


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
DEFAULT_CONFIG = os.path.join(PROJECT_ROOT, "config.yaml")


class TestLoadConfigDefault:
    """Test loading the default config.yaml."""

    def test_loads_default_config(self):
        config = load_config(DEFAULT_CONFIG)
        assert isinstance(config, AppConfig)

    def test_camera_index_default(self):
        config = load_config(DEFAULT_CONFIG)
        assert config.camera_index == 0

    def test_smoothing_window_default(self):
        config = load_config(DEFAULT_CONFIG)
        assert config.smoothing_window == 2

    def test_has_seven_gestures(self):
        config = load_config(DEFAULT_CONFIG)
        assert len(config.gestures) == 7

    def test_gesture_names(self):
        config = load_config(DEFAULT_CONFIG)
        expected = {"open_palm", "fist", "thumbs_up", "peace", "pointing", "pinch", "scout"}
        assert set(config.gestures.keys()) == expected

    def test_gesture_has_key_and_threshold(self):
        config = load_config(DEFAULT_CONFIG)
        for name, gesture in config.gestures.items():
            assert "key" in gesture, f"{name} missing 'key'"
            assert "threshold" in gesture, f"{name} missing 'threshold'"

    def test_gesture_thresholds_are_floats(self):
        config = load_config(DEFAULT_CONFIG)
        for name, gesture in config.gestures.items():
            assert isinstance(gesture["threshold"], float), (
                f"{name} threshold is not float"
            )

    def test_default_threshold_values(self):
        config = load_config(DEFAULT_CONFIG)
        expected_thresholds = {
            "open_palm": 0.7,
            "fist": 0.7,
            "thumbs_up": 0.9,
            "peace": 0.7,
            "pointing": 0.7,
            "pinch": 0.06,
            "scout": 0.7,
        }
        for name, gesture in config.gestures.items():
            expected = expected_thresholds[name]
            assert gesture["threshold"] == expected, (
                f"{name} threshold should be {expected}"
            )

    def test_key_mappings(self):
        config = load_config(DEFAULT_CONFIG)
        expected_keys = {
            "open_palm": "win+tab",
            "fist": "esc",
            "thumbs_up": "enter",
            "peace": "win+ctrl+left",
            "pointing": "alt+tab",
            "pinch": "win+down",
        }
        for name, expected_key in expected_keys.items():
            assert config.gestures[name]["key"] == expected_key


class TestLoadConfigCustomPath:
    """Test loading config from a custom path."""

    def test_loads_custom_config(self, tmp_path):
        custom = tmp_path / "custom.yaml"
        custom.write_text(
            "camera:\n  index: 1\n"
            "detection:\n  smoothing_window: 5\n"
            "gestures:\n"
            "  open_palm:\n    key: space\n    threshold: 0.8\n"
            "  fist:\n    key: ctrl+z\n    threshold: 0.8\n"
            "  thumbs_up:\n    key: ctrl+s\n    threshold: 0.8\n"
            "  peace:\n    key: ctrl+c\n    threshold: 0.8\n"
            "  pointing:\n    key: enter\n    threshold: 0.8\n"
            "  pinch:\n    key: ctrl+v\n    threshold: 0.8\n"
        )
        config = load_config(str(custom))
        assert config.camera_index == 1
        assert config.smoothing_window == 5
        assert config.gestures["open_palm"]["threshold"] == 0.8


class TestLoadConfigErrors:
    """Test error handling for config loading."""

    def test_missing_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")

    def test_malformed_yaml_raises_value_error(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("camera:\n  index: [invalid\n")
        with pytest.raises((ValueError, Exception)):
            load_config(str(bad))

    def test_missing_camera_section_raises_value_error(self, tmp_path):
        bad = tmp_path / "no_camera.yaml"
        bad.write_text(
            "detection:\n  smoothing_window: 3\n"
            "gestures:\n"
            "  open_palm:\n    key: space\n    threshold: 0.7\n"
            "  fist:\n    key: ctrl+z\n    threshold: 0.7\n"
            "  thumbs_up:\n    key: ctrl+s\n    threshold: 0.7\n"
            "  peace:\n    key: ctrl+c\n    threshold: 0.7\n"
            "  pointing:\n    key: enter\n    threshold: 0.7\n"
            "  pinch:\n    key: ctrl+v\n    threshold: 0.7\n"
        )
        with pytest.raises(ValueError):
            load_config(str(bad))

    def test_missing_gestures_section_raises_value_error(self, tmp_path):
        bad = tmp_path / "no_gestures.yaml"
        bad.write_text(
            "camera:\n  index: 0\n"
            "detection:\n  smoothing_window: 3\n"
        )
        with pytest.raises(ValueError):
            load_config(str(bad))


class TestAppConfigTimingFields:
    """Test activation_delay and cooldown_duration config fields."""

    MINIMAL_YAML = (
        "camera:\n  index: 0\n"
        "detection:\n  smoothing_window: 2\n"
        "gestures:\n"
        "  open_palm:\n    key: space\n    threshold: 0.7\n"
    )

    TIMING_YAML = (
        "camera:\n  index: 0\n"
        "detection:\n"
        "  smoothing_window: 3\n"
        "  activation_delay: 0.6\n"
        "  cooldown_duration: 1.2\n"
        "gestures:\n"
        "  open_palm:\n    key: space\n    threshold: 0.7\n"
    )

    def test_activation_delay_from_config(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(self.TIMING_YAML)
        config = load_config(str(cfg))
        assert config.activation_delay == 0.6

    def test_cooldown_duration_from_config(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(self.TIMING_YAML)
        config = load_config(str(cfg))
        assert config.cooldown_duration == 1.2

    def test_activation_delay_default_when_missing(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(self.MINIMAL_YAML)
        config = load_config(str(cfg))
        assert config.activation_delay == 0.15

    def test_cooldown_duration_default_when_missing(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(self.MINIMAL_YAML)
        config = load_config(str(cfg))
        assert config.cooldown_duration == 0.3

    def test_default_config_has_timing_fields(self):
        config = load_config(DEFAULT_CONFIG)
        assert config.activation_delay == 0.15
        assert config.cooldown_duration == 0.3


class TestDistanceConfig:
    """Test distance gating config parsing."""

    MINIMAL_YAML = (
        "camera:\n  index: 0\n"
        "gestures:\n"
        "  open_palm:\n    key: space\n    threshold: 0.7\n"
    )

    def test_distance_enabled_true_with_min_hand_size(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            self.MINIMAL_YAML
            + "distance:\n  enabled: true\n  min_hand_size: 0.20\n"
        )
        config = load_config(str(cfg))
        assert config.distance_enabled is True
        assert config.min_hand_size == 0.20

    def test_distance_enabled_false_preserves_min_hand_size(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            self.MINIMAL_YAML
            + "distance:\n  enabled: false\n  min_hand_size: 0.20\n"
        )
        config = load_config(str(cfg))
        assert config.distance_enabled is False
        assert config.min_hand_size == 0.20

    def test_missing_distance_section_defaults_disabled(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(self.MINIMAL_YAML)
        config = load_config(str(cfg))
        assert config.distance_enabled is False
        assert config.min_hand_size == 0.15

    def test_default_config_yaml_has_distance_enabled(self):
        config = load_config(DEFAULT_CONFIG)
        assert config.distance_enabled is True
        assert config.min_hand_size == 0.12


class TestConfigWatcher:
    """Test ConfigWatcher file change detection."""

    def test_check_returns_false_when_unchanged(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text("camera:\n  index: 0\n")
        watcher = ConfigWatcher(str(cfg), check_interval=0.0)
        # First check establishes baseline, second should be False
        watcher.check(0.0)
        assert watcher.check(1.0) is False

    def test_check_returns_true_when_file_modified(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text("camera:\n  index: 0\n")
        watcher = ConfigWatcher(str(cfg), check_interval=0.0)
        watcher.check(0.0)
        # Ensure mtime changes (filesystem granularity)
        time.sleep(0.05)
        cfg.write_text("camera:\n  index: 1\n")
        assert watcher.check(1.0) is True

    def test_check_respects_interval(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text("camera:\n  index: 0\n")
        watcher = ConfigWatcher(str(cfg), check_interval=10.0)
        watcher.check(0.0)
        time.sleep(0.05)
        cfg.write_text("camera:\n  index: 1\n")
        # Interval not elapsed, should return False
        assert watcher.check(1.0) is False

    def test_check_handles_missing_file(self, tmp_path):
        missing = tmp_path / "nonexistent.yaml"
        watcher = ConfigWatcher(str(missing), check_interval=0.0)
        assert watcher.check(0.0) is False


class TestSwipeConfig:
    """Test swipe config parsing and defaults."""

    MINIMAL_YAML = (
        "camera:\n  index: 0\n"
        "gestures:\n"
        "  open_palm:\n    key: space\n    threshold: 0.7\n"
    )

    FULL_SWIPE_YAML = (
        "camera:\n  index: 0\n"
        "gestures:\n"
        "  open_palm:\n    key: space\n    threshold: 0.7\n"
        "swipe:\n"
        "  cooldown: 0.8\n"
        "  min_velocity: 0.5\n"
        "  min_displacement: 0.1\n"
        "  axis_ratio: 3.0\n"
        "  swipe_left:\n    key: alt+left\n"
        "  swipe_right:\n    key: alt+right\n"
        "  swipe_up:\n    key: ctrl+up\n"
        "  swipe_down:\n    key: ctrl+down\n"
    )

    def test_default_appconfig_swipe_enabled_false(self):
        config = AppConfig()
        assert config.swipe_enabled is False

    def test_default_appconfig_swipe_cooldown(self):
        config = AppConfig()
        assert config.swipe_cooldown == 0.5

    def test_default_appconfig_swipe_min_velocity(self):
        config = AppConfig()
        assert config.swipe_min_velocity == 0.4

    def test_default_appconfig_swipe_min_displacement(self):
        config = AppConfig()
        assert config.swipe_min_displacement == 0.08

    def test_default_appconfig_swipe_axis_ratio(self):
        config = AppConfig()
        assert config.swipe_axis_ratio == 2.0

    def test_default_appconfig_swipe_mappings_empty(self):
        config = AppConfig()
        assert config.swipe_mappings == {}

    def test_full_swipe_config_parsing(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(self.FULL_SWIPE_YAML)
        config = load_config(str(cfg))
        assert config.swipe_enabled is True
        assert config.swipe_cooldown == 0.8
        assert config.swipe_min_velocity == 0.5
        assert config.swipe_min_displacement == 0.1
        assert config.swipe_axis_ratio == 3.0
        assert config.swipe_mappings == {
            "swipe_left": "alt+left",
            "swipe_right": "alt+right",
            "swipe_up": "ctrl+up",
            "swipe_down": "ctrl+down",
        }

    def test_missing_swipe_section_defaults_disabled(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(self.MINIMAL_YAML)
        config = load_config(str(cfg))
        assert config.swipe_enabled is False
        assert config.swipe_mappings == {}

    def test_swipe_section_no_directions_disabled(self, tmp_path):
        """Swipe section present but no direction mappings = disabled."""
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            self.MINIMAL_YAML
            + "swipe:\n"
            "  cooldown: 0.6\n"
            "  min_velocity: 0.5\n"
        )
        config = load_config(str(cfg))
        assert config.swipe_enabled is False
        assert config.swipe_mappings == {}

    def test_swipe_section_with_one_direction_enabled(self, tmp_path):
        """Swipe section with at least one direction mapping = enabled."""
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            self.MINIMAL_YAML
            + "swipe:\n"
            "  swipe_left:\n    key: alt+left\n"
        )
        config = load_config(str(cfg))
        assert config.swipe_enabled is True
        assert config.swipe_mappings == {"swipe_left": "alt+left"}

    def test_existing_config_unaffected(self, tmp_path):
        """Adding swipe parsing does not break existing config loading."""
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 1\n"
            "detection:\n"
            "  smoothing_window: 5\n"
            "  activation_delay: 0.6\n"
            "  cooldown_duration: 1.0\n"
            "gestures:\n"
            "  open_palm:\n    key: space\n    threshold: 0.8\n"
            "distance:\n  enabled: true\n  min_hand_size: 0.20\n"
        )
        config = load_config(str(cfg))
        assert config.camera_index == 1
        assert config.smoothing_window == 5
        assert config.activation_delay == 0.6
        assert config.cooldown_duration == 1.0
        assert config.distance_enabled is True
        assert config.min_hand_size == 0.20
        assert config.swipe_enabled is False
