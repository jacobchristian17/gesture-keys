"""Tests for gesture_keys.config module."""

import os
import time

import pytest

from gesture_keys.config import (
    ActionEntry,
    AppConfig,
    ConfigWatcher,
    DerivedConfig,
    _extract_gesture_modes,
    build_action_maps,
    build_compound_action_maps,
    derive_from_actions,
    extract_gesture_swipe_mappings,
    load_config,
    parse_actions,
    resolve_hand_gestures,
)
from gesture_keys.action import Action, FireMode
from gesture_keys.trigger import (
    Direction,
    SequenceTrigger,
    Trigger,
    TriggerParseError,
    TriggerState,
)
from gesture_keys.classifier import Gesture


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
DEFAULT_CONFIG = os.path.join(PROJECT_ROOT, "config.yaml")


class TestLoadConfigDefault:
    """Test loading the default config.yaml (actions: format)."""

    def test_loads_default_config(self):
        config = load_config(DEFAULT_CONFIG)
        assert isinstance(config, AppConfig)

    def test_camera_index_default(self):
        config = load_config(DEFAULT_CONFIG)
        assert config.camera_index == 0

    def test_smoothing_window_default(self):
        config = load_config(DEFAULT_CONFIG)
        assert config.smoothing_window == 2

    def test_has_eleven_actions(self):
        config = load_config(DEFAULT_CONFIG)
        assert len(config.actions) == 11

    def test_action_names(self):
        config = load_config(DEFAULT_CONFIG)
        names = {a.name for a in config.actions}
        expected = {
            "open_palm_switch", "fist_hold", "thumbs_up_tap",
            "pointing_switch", "peace_desktop_right", "scout_desktop_left",
            "pinch_minimize", "swipe_left", "swipe_right", "swipe_up", "swipe_down",
        }
        assert names == expected

    def test_actions_have_keys(self):
        config = load_config(DEFAULT_CONFIG)
        for action in config.actions:
            assert action.key, f"{action.name} missing 'key'"

    def test_gesture_modes_derived(self):
        config = load_config(DEFAULT_CONFIG)
        assert config.gesture_modes["fist_hold"] == "hold_key"
        assert config.gesture_modes["open_palm_switch"] == "tap"

    def test_bypass_gate_derived(self):
        config = load_config(DEFAULT_CONFIG)
        assert "peace_desktop_right" in config.activation_gate_bypass
        assert "scout_desktop_left" in config.activation_gate_bypass


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

    def test_missing_gestures_and_actions_raises_value_error(self, tmp_path):
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
        assert config.activation_delay == 0.2
        assert config.cooldown_duration == 0.1


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


class TestSettlingFramesConfig:
    """Test swipe_settling_frames config parsing."""

    MINIMAL_YAML = (
        "camera:\n  index: 0\n"
        "gestures:\n"
        "  open_palm:\n    key: space\n    threshold: 0.7\n"
    )

    def test_appconfig_default_settling_frames(self):
        config = AppConfig()
        assert config.swipe_settling_frames == 3

    def test_load_config_settling_frames_default_when_missing(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(self.MINIMAL_YAML)
        config = load_config(str(cfg))
        assert config.swipe_settling_frames == 3

    def test_load_config_parses_settling_frames(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            self.MINIMAL_YAML
            + "swipe:\n"
            "  settling_frames: 5\n"
            "  swipe_left:\n    key: left\n"
        )
        config = load_config(str(cfg))
        assert config.swipe_settling_frames == 5

    def test_load_config_settling_frames_from_default_config(self):
        """Default config uses actions: format -- swipe_settling_frames defaults to 3."""
        config = load_config(DEFAULT_CONFIG)
        assert config.swipe_settling_frames == 3


class TestGestureCooldownsConfig:
    """Test per-gesture cooldown config parsing."""

    MINIMAL_YAML = (
        "camera:\n  index: 0\n"
        "gestures:\n"
        "  open_palm:\n    key: space\n    threshold: 0.7\n"
    )

    def test_appconfig_default_gesture_cooldowns_empty(self):
        config = AppConfig()
        assert config.gesture_cooldowns == {}

    def test_load_config_extracts_per_gesture_cooldown(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "gestures:\n"
            "  pinch:\n    key: win+down\n    threshold: 0.06\n    cooldown: 0.6\n"
        )
        config = load_config(str(cfg))
        assert config.gesture_cooldowns == {"pinch": 0.6}

    def test_load_config_ignores_gestures_without_cooldown(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "gestures:\n"
            "  fist:\n    key: esc\n    threshold: 0.7\n"
            "  pinch:\n    key: win+down\n    threshold: 0.06\n"
        )
        config = load_config(str(cfg))
        assert config.gesture_cooldowns == {}

    def test_load_config_mixed_cooldown_overrides(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "gestures:\n"
            "  fist:\n    key: esc\n    threshold: 0.7\n"
            "  pinch:\n    key: win+down\n    threshold: 0.06\n    cooldown: 0.6\n"
            "  peace:\n    key: ctrl+c\n    threshold: 0.7\n    cooldown: 0.4\n"
        )
        config = load_config(str(cfg))
        assert config.gesture_cooldowns == {"pinch": 0.6, "peace": 0.4}

    def test_default_config_yaml_no_gesture_cooldowns(self):
        """Default config.yaml should have no per-gesture cooldown overrides."""
        config = load_config(DEFAULT_CONFIG)
        # actions: format -- no cooldown overrides specified
        assert config.gesture_cooldowns == {}


class TestPreferredHandConfig:
    """Test preferred_hand config field."""

    MINIMAL_YAML = (
        "camera:\n  index: 0\n"
        "gestures:\n"
        "  open_palm:\n    key: space\n    threshold: 0.7\n"
    )

    def test_appconfig_default_preferred_hand_is_left(self):
        config = AppConfig()
        assert config.preferred_hand == "left"

    def test_preferred_hand_parsed_from_yaml(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            self.MINIMAL_YAML + "preferred_hand: right\n"
        )
        config = load_config(str(cfg))
        assert config.preferred_hand == "right"

    def test_preferred_hand_defaults_to_left_when_missing(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(self.MINIMAL_YAML)
        config = load_config(str(cfg))
        assert config.preferred_hand == "left"

    def test_invalid_preferred_hand_raises_valueerror(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            self.MINIMAL_YAML + "preferred_hand: both\n"
        )
        with pytest.raises(ValueError, match="preferred_hand"):
            load_config(str(cfg))

    def test_default_config_yaml_preferred_hand(self):
        """Default config.yaml should have preferred_hand defaulting to left."""
        config = load_config(DEFAULT_CONFIG)
        assert config.preferred_hand == "left"


class TestGestureModesConfig:
    """Test gesture mode config parsing."""

    MINIMAL_YAML = (
        "camera:\n  index: 0\n"
        "gestures:\n"
        "  open_palm:\n    key: space\n    threshold: 0.7\n"
    )

    def test_appconfig_default_gesture_modes_empty(self):
        config = AppConfig()
        assert config.gesture_modes == {}

    def test_appconfig_default_hold_release_delay(self):
        config = AppConfig()
        assert config.hold_release_delay == 0.1

    def test_mode_hold_parsed(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "gestures:\n"
            "  fist:\n    key: space\n    threshold: 0.7\n    mode: hold\n"
        )
        config = load_config(str(cfg))
        assert config.gesture_modes == {"fist": "hold_key"}

    def test_mode_tap_parsed(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "gestures:\n"
            "  fist:\n    key: space\n    threshold: 0.7\n    mode: tap\n"
        )
        config = load_config(str(cfg))
        assert config.gesture_modes == {"fist": "tap"}

    def test_mode_defaults_to_tap_when_missing(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(self.MINIMAL_YAML)
        config = load_config(str(cfg))
        assert config.gesture_modes == {"open_palm": "tap"}

    def test_invalid_mode_raises_valueerror(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "gestures:\n"
            "  fist:\n    key: space\n    threshold: 0.7\n    mode: toggle\n"
        )
        with pytest.raises(ValueError, match="mode"):
            load_config(str(cfg))

    def test_hold_release_delay_from_config(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "detection:\n  hold_release_delay: 0.2\n"
            "gestures:\n"
            "  open_palm:\n    key: space\n    threshold: 0.7\n"
        )
        config = load_config(str(cfg))
        assert config.hold_release_delay == 0.2

    def test_hold_release_delay_default_when_missing(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(self.MINIMAL_YAML)
        config = load_config(str(cfg))
        assert config.hold_release_delay == 0.1

    def test_mixed_modes(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "gestures:\n"
            "  fist:\n    key: space\n    threshold: 0.7\n    mode: hold\n"
            "  open_palm:\n    key: enter\n    threshold: 0.7\n"
            "  pinch:\n    key: tab\n    threshold: 0.06\n    mode: tap\n"
        )
        config = load_config(str(cfg))
        assert config.gesture_modes == {
            "fist": "hold_key",
            "open_palm": "tap",
            "pinch": "tap",
        }


class TestHandResolution:
    """Tests for resolve_hand_gestures (simplified after left-hand removal)."""

    def test_resolve_right_hand_returns_gestures(self):
        config = AppConfig(gestures={"fist": {"key": "esc", "threshold": 0.7}})
        result = resolve_hand_gestures("Right", config)
        assert result == {"fist": {"key": "esc", "threshold": 0.7}}

    def test_resolve_left_hand_mirrors_right(self):
        """After left-hand removal, Left returns same gestures as Right."""
        config = AppConfig(gestures={"fist": {"key": "esc", "threshold": 0.7}})
        result = resolve_hand_gestures("Left", config)
        assert result == {"fist": {"key": "esc", "threshold": 0.7}}


class TestSwipeWindowConfig:
    """Test swipe_window and per-gesture swipe block parsing."""

    def test_swipe_window_default(self):
        config = load_config(DEFAULT_CONFIG)
        assert config.swipe_window == 0.5

    def test_swipe_window_from_detection(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
camera:
  index: 0
detection:
  swipe_window: 0.3
gestures:
  peace:
    key: ctrl+z
    threshold: 0.7
""")
        config = load_config(str(cfg))
        assert config.swipe_window == 0.3

    def test_gesture_swipe_mappings_parsed(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
camera:
  index: 0
gestures:
  peace:
    key: ctrl+z
    threshold: 0.7
    swipe:
      swipe_left:
        key: ctrl+shift+left
      swipe_right:
        key: ctrl+shift+right
""")
        config = load_config(str(cfg))
        assert "peace" in config.gesture_swipe_mappings
        assert config.gesture_swipe_mappings["peace"]["swipe_left"] == "ctrl+shift+left"
        assert config.gesture_swipe_mappings["peace"]["swipe_right"] == "ctrl+shift+right"

    def test_gesture_swipe_mappings_empty_when_no_block(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
camera:
  index: 0
gestures:
  peace:
    key: ctrl+z
    threshold: 0.7
""")
        config = load_config(str(cfg))
        assert config.gesture_swipe_mappings == {}

    def test_hold_mode_with_swipe_block_raises(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
camera:
  index: 0
gestures:
  fist:
    key: space
    mode: hold
    threshold: 0.7
    swipe:
      swipe_left:
        key: ctrl+left
""")
        with pytest.raises(ValueError, match="hold.*swipe"):
            load_config(str(cfg))

    def test_partial_directions(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
camera:
  index: 0
gestures:
  peace:
    key: ctrl+z
    threshold: 0.7
    swipe:
      swipe_left:
        key: ctrl+shift+left
""")
        config = load_config(str(cfg))
        assert "swipe_left" in config.gesture_swipe_mappings["peace"]
        assert "swipe_right" not in config.gesture_swipe_mappings["peace"]


class TestLoadConfigActions:
    """Tests for actions: path in load_config."""

    def test_actions_path_returns_appconfig(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "actions:\n"
            "  tap_it:\n"
            "    trigger: 'fist:static'\n"
            "    key: space\n"
        )
        config = load_config(str(cfg))
        assert isinstance(config, AppConfig)
        assert len(config.actions) == 1
        assert config.actions[0].name == "tap_it"

    def test_actions_derives_gesture_modes(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "actions:\n"
            "  hold_it:\n"
            "    trigger: 'fist:holding'\n"
            "    key: space\n"
        )
        config = load_config(str(cfg))
        assert config.gesture_modes["hold_it"] == "hold_key"

    def test_actions_derives_cooldowns(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "actions:\n"
            "  slow_tap:\n"
            "    trigger: 'fist:static'\n"
            "    key: up\n"
            "    cooldown: 0.8\n"
        )
        config = load_config(str(cfg))
        assert config.gesture_cooldowns == {"slow_tap": 0.8}

    def test_actions_derives_bypass(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "actions:\n"
            "  bypass_it:\n"
            "    trigger: 'peace:static'\n"
            "    key: win+ctrl+right\n"
            "    bypass_gate: true\n"
        )
        config = load_config(str(cfg))
        assert "bypass_it" in config.activation_gate_bypass

    def test_mutual_exclusion_raises(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "actions:\n"
            "  tap_it:\n"
            "    trigger: 'fist:static'\n"
            "    key: space\n"
            "gestures:\n"
            "  fist:\n    key: space\n    threshold: 0.7\n"
        )
        with pytest.raises(ValueError, match="cannot contain both"):
            load_config(str(cfg))

    def test_mutual_exclusion_with_swipe_raises(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "actions:\n"
            "  tap_it:\n"
            "    trigger: 'fist:static'\n"
            "    key: space\n"
            "swipe:\n"
            "  swipe_left:\n    key: left\n"
        )
        with pytest.raises(ValueError, match="cannot contain both"):
            load_config(str(cfg))

    def test_fallback_to_gestures_when_no_actions(self, tmp_path):
        """Legacy gestures: path still works when actions: absent."""
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "gestures:\n"
            "  open_palm:\n    key: space\n    threshold: 0.7\n"
        )
        config = load_config(str(cfg))
        assert len(config.gestures) == 1
        assert config.actions == []

    def test_actions_path_gestures_empty(self, tmp_path):
        """When using actions: path, config.gestures is empty dict."""
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "actions:\n"
            "  tap_it:\n"
            "    trigger: 'fist:static'\n"
            "    key: space\n"
        )
        config = load_config(str(cfg))
        assert config.gestures == {}


class TestFireModeConfig:
    """Tests for fire_mode config parsing and build_action_maps."""

    def test_fire_mode_hold_key(self):
        """fire_mode: hold_key in config produces gesture_modes['fist'] == 'hold_key'."""
        gestures = {"fist": {"key": "space", "fire_mode": "hold_key"}}
        modes = _extract_gesture_modes(gestures)
        assert modes["fist"] == "hold_key"

    def test_fire_mode_tap(self):
        """fire_mode: tap in config produces gesture_modes['open_palm'] == 'tap'."""
        gestures = {"open_palm": {"key": "win+tab", "fire_mode": "tap"}}
        modes = _extract_gesture_modes(gestures)
        assert modes["open_palm"] == "tap"

    def test_mode_hold_backward_compat(self):
        """mode: hold (v1.x) produces gesture_modes['fist'] == 'hold_key'."""
        gestures = {"fist": {"key": "space", "mode": "hold"}}
        modes = _extract_gesture_modes(gestures)
        assert modes["fist"] == "hold_key"

    def test_mode_tap_backward_compat(self):
        """mode: tap (v1.x) still produces 'tap'."""
        gestures = {"fist": {"key": "space", "mode": "tap"}}
        modes = _extract_gesture_modes(gestures)
        assert modes["fist"] == "tap"

    def test_no_fire_mode_no_mode_defaults_tap(self):
        """No fire_mode and no mode defaults to 'tap'."""
        gestures = {"fist": {"key": "space"}}
        modes = _extract_gesture_modes(gestures)
        assert modes["fist"] == "tap"

    def test_fire_mode_takes_precedence_over_mode(self):
        """fire_mode takes precedence over mode when both present."""
        gestures = {"fist": {"key": "space", "mode": "tap", "fire_mode": "hold_key"}}
        modes = _extract_gesture_modes(gestures)
        assert modes["fist"] == "hold_key"

    def test_invalid_fire_mode_raises(self):
        """Invalid fire_mode raises ValueError."""
        gestures = {"fist": {"key": "space", "fire_mode": "invalid"}}
        with pytest.raises(ValueError, match="invalid"):
            _extract_gesture_modes(gestures)

    def test_invalid_mode_raises(self):
        """Invalid mode raises ValueError."""
        gestures = {"fist": {"key": "space", "mode": "invalid"}}
        with pytest.raises(ValueError, match="invalid"):
            _extract_gesture_modes(gestures)

    def test_build_action_maps_creates_actions(self):
        """build_action_maps() creates dict[str, Action] from gestures config."""
        gestures = {
            "fist": {"key": "space", "threshold": 0.7},
            "open_palm": {"key": "win+tab", "threshold": 0.7},
        }
        modes = {"fist": "tap", "open_palm": "tap"}
        actions = build_action_maps(gestures, modes)
        assert isinstance(actions, dict)
        assert "fist" in actions
        assert "open_palm" in actions
        assert isinstance(actions["fist"], Action)
        assert actions["fist"].key_string == "space"
        assert actions["fist"].fire_mode == FireMode.TAP
        assert actions["fist"].gesture_name == "fist"

    def test_build_action_maps_hold_key_mode(self):
        """build_action_maps() sets FireMode.HOLD_KEY for hold_key gestures."""
        gestures = {"fist": {"key": "space", "threshold": 0.7}}
        modes = {"fist": "hold_key"}
        actions = build_action_maps(gestures, modes)
        assert actions["fist"].fire_mode == FireMode.HOLD_KEY

    def test_build_action_maps_pre_parses_keys(self):
        """build_action_maps() pre-parses key strings via parse_key_string."""
        from pynput.keyboard import Key
        gestures = {"fist": {"key": "ctrl+space", "threshold": 0.7}}
        modes = {"fist": "tap"}
        actions = build_action_maps(gestures, modes)
        assert Key.ctrl in actions["fist"].modifiers
        assert actions["fist"].key == Key.space

    def test_build_action_maps_skips_no_key(self):
        """build_action_maps() skips gestures without a 'key' field."""
        gestures = {"fist": {"threshold": 0.7}}
        modes = {"fist": "tap"}
        actions = build_action_maps(gestures, modes)
        assert "fist" not in actions

    def test_build_compound_action_maps(self):
        """build_compound_action_maps() creates dict from gesture_swipe_mappings."""
        swipe_mappings = {
            "open_palm": {"swipe_left": "1", "swipe_right": "2"},
        }
        actions = build_compound_action_maps(swipe_mappings)
        assert isinstance(actions, dict)
        assert ("open_palm", "swipe_left") in actions
        assert ("open_palm", "swipe_right") in actions
        action = actions[("open_palm", "swipe_left")]
        assert isinstance(action, Action)
        assert action.fire_mode == FireMode.TAP
        assert action.key_string == "1"
        assert action.gesture_name == "open_palm"

    def test_hold_key_with_swipe_raises(self):
        """hold_key gesture with swipe block raises ValueError (existing validation)."""
        gestures = {
            "fist": {"key": "space", "swipe": {"swipe_left": {"key": "1"}}},
        }
        modes = {"fist": "hold_key"}
        with pytest.raises(ValueError, match="hold"):
            extract_gesture_swipe_mappings(gestures, modes)


class TestActionEntry:
    """Tests for the ActionEntry dataclass."""

    def test_action_entry_has_all_fields(self):
        """ActionEntry stores name, trigger, key, cooldown, bypass_gate, hand, threshold."""
        trigger = Trigger(Gesture.FIST, TriggerState.STATIC)
        entry = ActionEntry(
            name="vol_up",
            trigger=trigger,
            key="up",
            cooldown=0.5,
            bypass_gate=True,
            hand="left",
            threshold=0.8,
        )
        assert entry.name == "vol_up"
        assert entry.trigger == trigger
        assert entry.key == "up"
        assert entry.cooldown == 0.5
        assert entry.bypass_gate is True
        assert entry.hand == "left"
        assert entry.threshold == 0.8

    def test_action_entry_defaults(self):
        """ActionEntry defaults: cooldown=None, bypass_gate=False, hand='both', threshold=None."""
        trigger = Trigger(Gesture.FIST, TriggerState.STATIC)
        entry = ActionEntry(name="test", trigger=trigger, key="space")
        assert entry.cooldown is None
        assert entry.bypass_gate is False
        assert entry.hand == "both"
        assert entry.threshold is None

    def test_action_entry_is_frozen(self):
        """ActionEntry is immutable (frozen dataclass)."""
        trigger = Trigger(Gesture.FIST, TriggerState.STATIC)
        entry = ActionEntry(name="test", trigger=trigger, key="space")
        with pytest.raises(AttributeError):
            entry.name = "changed"


class TestParseActions:
    """Tests for parse_actions() function."""

    def test_basic_static_trigger(self):
        """Parse a simple static trigger action."""
        actions_dict = {
            "vol_up": {"trigger": "fist:static", "key": "up"},
        }
        result = parse_actions(actions_dict)
        assert len(result) == 1
        entry = result[0]
        assert entry.name == "vol_up"
        assert entry.trigger == Trigger(Gesture.FIST, TriggerState.STATIC)
        assert entry.key == "up"

    def test_entry_with_cooldown(self):
        """Entry with cooldown: 0.5 -> ActionEntry.cooldown == 0.5."""
        actions_dict = {
            "vol_up": {"trigger": "fist:static", "key": "up", "cooldown": 0.5},
        }
        result = parse_actions(actions_dict)
        assert result[0].cooldown == 0.5

    def test_entry_without_cooldown(self):
        """Entry without cooldown -> ActionEntry.cooldown is None."""
        actions_dict = {
            "vol_up": {"trigger": "fist:static", "key": "up"},
        }
        result = parse_actions(actions_dict)
        assert result[0].cooldown is None

    def test_entry_with_bypass_gate(self):
        """Entry with bypass_gate: true -> ActionEntry.bypass_gate == True."""
        actions_dict = {
            "vol_up": {"trigger": "fist:static", "key": "up", "bypass_gate": True},
        }
        result = parse_actions(actions_dict)
        assert result[0].bypass_gate is True

    def test_entry_without_bypass_gate(self):
        """Entry without bypass_gate -> ActionEntry.bypass_gate == False."""
        actions_dict = {
            "vol_up": {"trigger": "fist:static", "key": "up"},
        }
        result = parse_actions(actions_dict)
        assert result[0].bypass_gate is False

    def test_entry_with_hand_left(self):
        """Entry with hand: left -> ActionEntry.hand == 'left'."""
        actions_dict = {
            "vol_up": {"trigger": "fist:static", "key": "up", "hand": "left"},
        }
        result = parse_actions(actions_dict)
        assert result[0].hand == "left"

    def test_entry_without_hand(self):
        """Entry without hand -> ActionEntry.hand == 'both'."""
        actions_dict = {
            "vol_up": {"trigger": "fist:static", "key": "up"},
        }
        result = parse_actions(actions_dict)
        assert result[0].hand == "both"

    def test_entry_with_threshold(self):
        """Entry with threshold: 0.8 -> ActionEntry.threshold == 0.8."""
        actions_dict = {
            "vol_up": {"trigger": "fist:static", "key": "up", "threshold": 0.8},
        }
        result = parse_actions(actions_dict)
        assert result[0].threshold == 0.8

    def test_invalid_trigger_raises_trigger_parse_error(self):
        """Entry with invalid trigger string -> TriggerParseError raised."""
        actions_dict = {
            "bad": {"trigger": "invalid_gesture:static", "key": "up"},
        }
        with pytest.raises(TriggerParseError):
            parse_actions(actions_dict)

    def test_missing_trigger_field_raises_valueerror(self):
        """Entry missing 'trigger' field -> ValueError with clear message."""
        actions_dict = {
            "bad": {"key": "up"},
        }
        with pytest.raises(ValueError, match="trigger"):
            parse_actions(actions_dict)

    def test_missing_key_field_raises_valueerror(self):
        """Entry missing 'key' field -> ValueError with clear message."""
        actions_dict = {
            "bad": {"trigger": "fist:static"},
        }
        with pytest.raises(ValueError, match="key"):
            parse_actions(actions_dict)

    def test_duplicate_trigger_raises_valueerror(self):
        """Two entries with same trigger string -> ValueError('duplicate trigger')."""
        actions_dict = {
            "vol_up": {"trigger": "fist:static", "key": "up"},
            "vol_down": {"trigger": "fist:static", "key": "down"},
        }
        with pytest.raises(ValueError, match="duplicate trigger"):
            parse_actions(actions_dict)

    def test_invalid_hand_raises_valueerror(self):
        """hand: invalid_value -> ValueError."""
        actions_dict = {
            "vol_up": {"trigger": "fist:static", "key": "up", "hand": "invalid"},
        }
        with pytest.raises(ValueError, match="hand"):
            parse_actions(actions_dict)

    def test_moving_trigger(self):
        """Moving trigger: fist:moving:left -> ActionEntry with direction."""
        actions_dict = {
            "nav_left": {"trigger": "fist:moving:left", "key": "left"},
        }
        result = parse_actions(actions_dict)
        assert result[0].trigger == Trigger(
            Gesture.FIST, TriggerState.MOVING, Direction.LEFT
        )

    def test_sequence_trigger(self):
        """Sequence trigger: fist > open_palm -> ActionEntry with SequenceTrigger."""
        actions_dict = {
            "confirm": {"trigger": "fist > open_palm", "key": "enter"},
        }
        result = parse_actions(actions_dict)
        assert isinstance(result[0].trigger, SequenceTrigger)
        assert result[0].trigger.first.gesture == Gesture.FIST
        assert result[0].trigger.second.gesture == Gesture.OPEN_PALM

    def test_same_trigger_different_hands_allowed(self):
        """Same trigger with hand:left and hand:right is ALLOWED (different scopes)."""
        actions_dict = {
            "left_fist": {"trigger": "fist:static", "key": "left", "hand": "left"},
            "right_fist": {"trigger": "fist:static", "key": "right", "hand": "right"},
        }
        result = parse_actions(actions_dict)
        assert len(result) == 2

    def test_both_overlaps_with_left_raises(self):
        """Same trigger with hand:both and hand:left -> ValueError (both overlaps)."""
        actions_dict = {
            "all_fist": {"trigger": "fist:static", "key": "up", "hand": "both"},
            "left_fist": {"trigger": "fist:static", "key": "left", "hand": "left"},
        }
        with pytest.raises(ValueError, match="duplicate trigger"):
            parse_actions(actions_dict)

    def test_both_overlaps_with_right_raises(self):
        """Same trigger with hand:both and hand:right -> ValueError (both overlaps)."""
        actions_dict = {
            "all_fist": {"trigger": "fist:static", "key": "up", "hand": "both"},
            "right_fist": {"trigger": "fist:static", "key": "right", "hand": "right"},
        }
        with pytest.raises(ValueError, match="duplicate trigger"):
            parse_actions(actions_dict)

    def test_multiple_actions_parsed(self):
        """Multiple valid actions produce correct list."""
        actions_dict = {
            "vol_up": {"trigger": "fist:static", "key": "up"},
            "vol_down": {"trigger": "open_palm:static", "key": "down"},
            "nav_left": {"trigger": "peace:moving:left", "key": "left"},
        }
        result = parse_actions(actions_dict)
        assert len(result) == 3
        names = {e.name for e in result}
        assert names == {"vol_up", "vol_down", "nav_left"}

    def test_hand_right_value(self):
        """hand: right -> ActionEntry.hand == 'right'."""
        actions_dict = {
            "vol_up": {"trigger": "fist:static", "key": "up", "hand": "right"},
        }
        result = parse_actions(actions_dict)
        assert result[0].hand == "right"

    def test_hand_both_value(self):
        """hand: both -> ActionEntry.hand == 'both'."""
        actions_dict = {
            "vol_up": {"trigger": "fist:static", "key": "up", "hand": "both"},
        }
        result = parse_actions(actions_dict)
        assert result[0].hand == "both"


class TestDeriveFromActions:
    """Tests for derive_from_actions() function."""

    def test_gesture_modes_from_trigger_states(self):
        """Static -> tap, holding -> hold_key, moving -> tap."""
        entries = [
            ActionEntry(
                name="tap_action",
                trigger=Trigger(Gesture.OPEN_PALM, TriggerState.STATIC),
                key="win+tab",
            ),
            ActionEntry(
                name="hold_action",
                trigger=Trigger(Gesture.FIST, TriggerState.HOLDING),
                key="space",
            ),
            ActionEntry(
                name="move_action",
                trigger=Trigger(Gesture.PEACE, TriggerState.MOVING, Direction.LEFT),
                key="left",
            ),
        ]
        result = derive_from_actions(entries)
        assert isinstance(result, DerivedConfig)
        assert result.gesture_modes["tap_action"] == "tap"
        assert result.gesture_modes["hold_action"] == "hold_key"
        assert result.gesture_modes["move_action"] == "tap"

    def test_sequence_trigger_defaults_to_tap(self):
        """SequenceTrigger always maps to tap."""
        entries = [
            ActionEntry(
                name="seq_action",
                trigger=SequenceTrigger(
                    first=Trigger(Gesture.FIST, TriggerState.STATIC),
                    second=Trigger(Gesture.OPEN_PALM, TriggerState.STATIC),
                ),
                key="enter",
            ),
        ]
        result = derive_from_actions(entries)
        assert result.gesture_modes["seq_action"] == "tap"

    def test_cooldown_overrides_collected(self):
        """Actions with cooldown populate gesture_cooldowns; without -> not in dict."""
        entries = [
            ActionEntry(
                name="with_cooldown",
                trigger=Trigger(Gesture.FIST, TriggerState.STATIC),
                key="up",
                cooldown=0.6,
            ),
            ActionEntry(
                name="no_cooldown",
                trigger=Trigger(Gesture.OPEN_PALM, TriggerState.STATIC),
                key="down",
            ),
        ]
        result = derive_from_actions(entries)
        assert result.gesture_cooldowns == {"with_cooldown": 0.6}

    def test_bypass_gate_collected(self):
        """Actions with bypass_gate=True appear in activation_gate_bypass list."""
        entries = [
            ActionEntry(
                name="bypass_action",
                trigger=Trigger(Gesture.PEACE, TriggerState.STATIC),
                key="win+ctrl+right",
                bypass_gate=True,
            ),
            ActionEntry(
                name="normal_action",
                trigger=Trigger(Gesture.FIST, TriggerState.STATIC),
                key="space",
            ),
        ]
        result = derive_from_actions(entries)
        assert "bypass_action" in result.activation_gate_bypass
        assert "normal_action" not in result.activation_gate_bypass

    def test_static_entry_in_right_static(self):
        """Static trigger -> appears in right_static keyed by gesture value."""
        entries = [
            ActionEntry(
                name="tap_action",
                trigger=Trigger(Gesture.FIST, TriggerState.STATIC),
                key="space",
            ),
        ]
        result = derive_from_actions(entries)
        assert "fist" in result.right_static
        assert isinstance(result.right_static["fist"], Action)
        assert result.right_static["fist"].key_string == "space"
        assert result.right_static["fist"].fire_mode == FireMode.TAP

    def test_holding_entry_in_right_holding(self):
        """Holding trigger -> appears in right_holding keyed by gesture value."""
        entries = [
            ActionEntry(
                name="hold_action",
                trigger=Trigger(Gesture.FIST, TriggerState.HOLDING),
                key="space",
            ),
        ]
        result = derive_from_actions(entries)
        assert "fist" in result.right_holding
        assert result.right_holding["fist"].fire_mode == FireMode.HOLD_KEY

    def test_moving_entry_in_right_moving(self):
        """Moving trigger -> appears in right_moving keyed by (gesture, direction) tuple."""
        entries = [
            ActionEntry(
                name="move_action",
                trigger=Trigger(Gesture.OPEN_PALM, TriggerState.MOVING, Direction.LEFT),
                key="left",
            ),
        ]
        result = derive_from_actions(entries)
        assert ("open_palm", "left") in result.right_moving
        assert result.right_moving[("open_palm", "left")].key_string == "left"

    def test_sequence_entry_in_right_sequence(self):
        """Sequence trigger -> appears in right_sequence keyed by (first, second) tuple."""
        entries = [
            ActionEntry(
                name="seq_action",
                trigger=SequenceTrigger(
                    first=Trigger(Gesture.FIST, TriggerState.STATIC),
                    second=Trigger(Gesture.OPEN_PALM, TriggerState.STATIC),
                ),
                key="enter",
            ),
        ]
        result = derive_from_actions(entries)
        assert ("fist", "open_palm") in result.right_sequence
        assert result.right_sequence[("fist", "open_palm")].key_string == "enter"

    def test_hand_left_routes_to_left_maps(self):
        """hand='left' routes static action to left_static only."""
        entries = [
            ActionEntry(
                name="left_only",
                trigger=Trigger(Gesture.FIST, TriggerState.STATIC),
                key="ctrl+z",
                hand="left",
            ),
        ]
        result = derive_from_actions(entries)
        assert "fist" in result.left_static
        assert "fist" not in result.right_static

    def test_hand_both_routes_to_both_maps(self):
        """hand='both' routes action to both right and left maps."""
        entries = [
            ActionEntry(
                name="both_action",
                trigger=Trigger(Gesture.FIST, TriggerState.STATIC),
                key="space",
                hand="both",
            ),
        ]
        result = derive_from_actions(entries)
        assert "fist" in result.right_static
        assert "fist" in result.left_static
        assert result.right_static["fist"].key_string == "space"
        assert result.left_static["fist"].key_string == "space"

    def test_hand_right_routes_to_right_only(self):
        """hand='right' routes action to right map only."""
        entries = [
            ActionEntry(
                name="right_only",
                trigger=Trigger(Gesture.FIST, TriggerState.STATIC),
                key="ctrl+y",
                hand="right",
            ),
        ]
        result = derive_from_actions(entries)
        assert "fist" in result.right_static
        assert "fist" not in result.left_static

    def test_hand_both_moving_entry(self):
        """hand='both' routes moving action to both right_moving and left_moving."""
        entries = [
            ActionEntry(
                name="move_both",
                trigger=Trigger(Gesture.OPEN_PALM, TriggerState.MOVING, Direction.UP),
                key="up",
                hand="both",
            ),
        ]
        result = derive_from_actions(entries)
        assert ("open_palm", "up") in result.right_moving
        assert ("open_palm", "up") in result.left_moving

    def test_hand_both_sequence_entry(self):
        """hand='both' routes sequence action to both right_sequence and left_sequence."""
        entries = [
            ActionEntry(
                name="seq_both",
                trigger=SequenceTrigger(
                    first=Trigger(Gesture.FIST, TriggerState.STATIC),
                    second=Trigger(Gesture.PEACE, TriggerState.STATIC),
                ),
                key="enter",
                hand="both",
            ),
        ]
        result = derive_from_actions(entries)
        assert ("fist", "peace") in result.right_sequence
        assert ("fist", "peace") in result.left_sequence

    def test_action_has_parsed_modifiers_and_key(self):
        """Built Action has pre-parsed modifiers and key from parse_key_string."""
        from pynput.keyboard import Key
        entries = [
            ActionEntry(
                name="mod_action",
                trigger=Trigger(Gesture.PEACE, TriggerState.STATIC),
                key="ctrl+space",
            ),
        ]
        result = derive_from_actions(entries)
        action = result.right_static["peace"]
        assert Key.ctrl in action.modifiers
        assert action.key == Key.space

    def test_no_right_actions_or_left_actions_fields(self):
        """DerivedConfig no longer has right_actions/left_actions fields."""
        entries = [
            ActionEntry(
                name="test",
                trigger=Trigger(Gesture.FIST, TriggerState.STATIC),
                key="space",
            ),
        ]
        result = derive_from_actions(entries)
        assert not hasattr(result, "right_actions")
        assert not hasattr(result, "left_actions")

    def test_derived_config_is_frozen(self):
        """DerivedConfig is a frozen dataclass."""
        entries = [
            ActionEntry(
                name="test",
                trigger=Trigger(Gesture.FIST, TriggerState.STATIC),
                key="space",
            ),
        ]
        result = derive_from_actions(entries)
        with pytest.raises(AttributeError):
            result.gesture_modes = {}
