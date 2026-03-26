"""Tests for gesture_keys.config module."""

import os
import time

import pytest

from gesture_keys.config import (
    ActionEntry,
    AppConfig,
    ConfigWatcher,
    DerivedConfig,
    derive_from_actions,
    load_config,
    parse_actions,
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
            "actions:\n"
            "  tap_palm:\n"
            "    trigger: 'open_palm:static'\n"
            "    key: space\n"
            "    threshold: 0.8\n"
        )
        config = load_config(str(custom))
        assert config.camera_index == 1
        assert config.smoothing_window == 5
        assert len(config.actions) == 1
        assert config.actions[0].name == "tap_palm"


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
            "actions:\n"
            "  tap_palm:\n"
            "    trigger: 'open_palm:static'\n"
            "    key: space\n"
        )
        with pytest.raises(ValueError):
            load_config(str(bad))

    def test_missing_actions_raises_value_error(self, tmp_path):
        bad = tmp_path / "no_actions.yaml"
        bad.write_text(
            "camera:\n  index: 0\n"
            "detection:\n  smoothing_window: 3\n"
        )
        with pytest.raises(ValueError, match="missing required 'actions' section"):
            load_config(str(bad))


class TestAppConfigTimingFields:
    """Test activation_delay and cooldown_duration config fields."""

    MINIMAL_YAML = (
        "camera:\n  index: 0\n"
        "actions:\n"
        "  tap_palm:\n"
        "    trigger: 'open_palm:static'\n"
        "    key: space\n"
    )

    TIMING_YAML = (
        "camera:\n  index: 0\n"
        "detection:\n"
        "  smoothing_window: 3\n"
        "  activation_delay: 0.6\n"
        "  cooldown_duration: 1.2\n"
        "actions:\n"
        "  tap_palm:\n"
        "    trigger: 'open_palm:static'\n"
        "    key: space\n"
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
        "actions:\n"
        "  tap_palm:\n"
        "    trigger: 'open_palm:static'\n"
        "    key: space\n"
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


class TestPreferredHandConfig:
    """Test preferred_hand config field."""

    MINIMAL_YAML = (
        "camera:\n  index: 0\n"
        "actions:\n"
        "  tap_palm:\n"
        "    trigger: 'open_palm:static'\n"
        "    key: space\n"
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


class TestSequenceWindowConfig:
    """Test sequence_window config field."""

    def test_sequence_window_default(self):
        config = load_config(DEFAULT_CONFIG)
        assert config.sequence_window == 0.5

    def test_sequence_window_from_detection(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "camera:\n  index: 0\n"
            "detection:\n  sequence_window: 0.3\n"
            "actions:\n"
            "  tap_it:\n"
            "    trigger: 'fist:static'\n"
            "    key: space\n"
        )
        config = load_config(str(cfg))
        assert config.sequence_window == 0.3

    def test_appconfig_default_sequence_window(self):
        config = AppConfig()
        assert config.sequence_window == 0.2


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
