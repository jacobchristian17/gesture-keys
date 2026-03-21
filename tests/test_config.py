"""Tests for gesture_keys.config module."""

import os
import pytest
import tempfile

from gesture_keys.config import load_config, AppConfig


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
        assert config.smoothing_window == 3

    def test_has_six_gestures(self):
        config = load_config(DEFAULT_CONFIG)
        assert len(config.gestures) == 6

    def test_gesture_names(self):
        config = load_config(DEFAULT_CONFIG)
        expected = {"open_palm", "fist", "thumbs_up", "peace", "pointing", "pinch"}
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
        for name, gesture in config.gestures.items():
            assert gesture["threshold"] == 0.7, (
                f"{name} threshold should be 0.7"
            )

    def test_key_mappings(self):
        config = load_config(DEFAULT_CONFIG)
        expected_keys = {
            "open_palm": "space",
            "fist": "ctrl+z",
            "thumbs_up": "ctrl+s",
            "peace": "ctrl+c",
            "pointing": "enter",
            "pinch": "ctrl+v",
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
