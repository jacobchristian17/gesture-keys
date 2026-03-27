"""Configuration loading and hot-reload for gesture-keys."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional, Union

import yaml

from gesture_keys.action import Action, FireMode
from gesture_keys.keystroke import parse_key_string
from gesture_keys.trigger import (
    SequenceTrigger,
    Trigger,
    TriggerState,
    parse_trigger,
)

logger = logging.getLogger("gesture_keys")


_VALID_HANDS = {"left", "right", "both"}


@dataclass(frozen=True)
class ActionEntry:
    """A parsed action entry from the actions: config section.

    Attributes:
        name: User-chosen action name (YAML key).
        trigger: Parsed Trigger or SequenceTrigger.
        key: Keystroke string (e.g. 'ctrl+z', 'up').
        cooldown: Per-action cooldown override, or None for global default.
        bypass_gate: Whether this action bypasses the activation gate.
        hand: Which hand triggers this action ('left', 'right', 'both').
        threshold: Per-action confidence threshold, or None for default.
    """

    name: str
    trigger: Union[Trigger, SequenceTrigger]
    key: str
    cooldown: Optional[float] = None
    bypass_gate: bool = False
    hand: str = "both"
    threshold: Optional[float] = None


def parse_actions(actions_dict: dict) -> list[ActionEntry]:
    """Parse the actions: YAML section into ActionEntry instances.

    Args:
        actions_dict: Dict from YAML actions: section (action_name -> {trigger, key, ...}).

    Returns:
        List of ActionEntry instances.

    Raises:
        ValueError: If required fields are missing, hand is invalid, or triggers collide.
        TriggerParseError: If a trigger string cannot be parsed.
    """
    entries: list[ActionEntry] = []
    # Track (trigger_string, hand_scope) -> action_name for uniqueness
    seen_triggers: dict[tuple[str, str], str] = {}

    for action_name, settings in actions_dict.items():
        if not isinstance(settings, dict):
            raise ValueError(
                f"Action '{action_name}' must be a mapping, "
                f"got {type(settings).__name__}"
            )

        # Validate required fields
        if "trigger" not in settings:
            raise ValueError(
                f"Action '{action_name}' missing required 'trigger' field"
            )
        if "key" not in settings:
            raise ValueError(
                f"Action '{action_name}' missing required 'key' field"
            )

        trigger_string = str(settings["trigger"])
        key_string = str(settings["key"])
        hand = str(settings.get("hand", "both")).lower()

        if hand not in _VALID_HANDS:
            raise ValueError(
                f"Action '{action_name}' has invalid hand '{hand}'. "
                f"Valid values: {sorted(_VALID_HANDS)}"
            )

        # Check trigger uniqueness per hand scope
        _check_trigger_uniqueness(trigger_string, hand, action_name, seen_triggers)

        # Parse the trigger string (may raise TriggerParseError)
        trigger = parse_trigger(trigger_string)

        cooldown = settings.get("cooldown")
        if cooldown is not None:
            cooldown = float(cooldown)

        threshold = settings.get("threshold")
        if threshold is not None:
            threshold = float(threshold)

        entries.append(
            ActionEntry(
                name=action_name,
                trigger=trigger,
                key=key_string,
                cooldown=cooldown,
                bypass_gate=bool(settings.get("bypass_gate", False)),
                hand=hand,
                threshold=threshold,
            )
        )

    return entries


def _check_trigger_uniqueness(
    trigger_string: str,
    hand: str,
    action_name: str,
    seen: dict[tuple[str, str], str],
) -> None:
    """Check that a trigger+hand combination is unique.

    hand='both' conflicts with 'left' and 'right' (and vice versa).

    Args:
        trigger_string: The raw trigger string.
        hand: The hand scope ('left', 'right', 'both').
        action_name: Current action name (for error messages).
        seen: Mutable dict tracking (trigger_string, hand_scope) -> action_name.

    Raises:
        ValueError: If a duplicate trigger is found.
    """
    if hand == "both":
        scopes_to_check = ["both", "left", "right"]
    else:
        scopes_to_check = [hand, "both"]

    for scope in scopes_to_check:
        key = (trigger_string, scope)
        if key in seen:
            raise ValueError(
                f"duplicate trigger '{trigger_string}': action '{action_name}' "
                f"(hand={hand}) conflicts with action '{seen[key]}' (hand={scope})"
            )

    # Register this trigger for all scopes it covers
    if hand == "both":
        seen[(trigger_string, "both")] = action_name
        seen[(trigger_string, "left")] = action_name
        seen[(trigger_string, "right")] = action_name
    else:
        seen[(trigger_string, hand)] = action_name


@dataclass(frozen=True)
class DerivedConfig:
    """Orchestrator inputs derived from parsed ActionEntry list.

    Attributes:
        gesture_modes: Action name -> "tap" or "hold_key" inferred from trigger state.
        gesture_cooldowns: Action name -> cooldown for actions with overrides.
        activation_gate_bypass: Action names with bypass_gate=True.
        right_static: gesture_value -> Action for right hand static triggers.
        left_static: gesture_value -> Action for left hand static triggers.
        right_holding: gesture_value -> Action for right hand holding triggers.
        left_holding: gesture_value -> Action for left hand holding triggers.
        right_moving: (gesture_value, direction_value) -> Action for right hand.
        left_moving: (gesture_value, direction_value) -> Action for left hand.
        right_sequence: (first_gesture_value, second_gesture_value) -> Action for right hand.
        left_sequence: (first_gesture_value, second_gesture_value) -> Action for left hand.
    """

    gesture_modes: dict[str, str]
    gesture_cooldowns: dict[str, float]
    activation_gate_bypass: list[str]
    right_static: dict[str, Action]
    left_static: dict[str, Action]
    right_holding: dict[str, Action]
    left_holding: dict[str, Action]
    right_moving: dict[tuple[str, str], Action]
    left_moving: dict[tuple[str, str], Action]
    right_sequence: dict[tuple[str, str], Action]
    left_sequence: dict[tuple[str, str], Action]


def derive_from_actions(actions: list[ActionEntry]) -> DerivedConfig:
    """Derive orchestrator inputs from parsed ActionEntry list.

    For each ActionEntry:
    - Infers fire_mode from trigger state (static->tap, holding->hold_key,
      moving->tap, sequence->tap).
    - Builds Action objects with pre-parsed key strings.
    - Routes actions into the correct per-hand, per-trigger-type maps.
    - Collects cooldown overrides and bypass_gate flags.

    Args:
        actions: List of ActionEntry from parse_actions().

    Returns:
        DerivedConfig with gesture_modes, cooldowns, bypass list,
        and 8 typed per-hand action maps.
    """
    _trigger_state_to_fire_mode = {
        TriggerState.STATIC: FireMode.TAP,
        TriggerState.HOLDING: FireMode.HOLD_KEY,
        TriggerState.MOVING: FireMode.TAP,
    }

    gesture_modes: dict[str, str] = {}
    gesture_cooldowns: dict[str, float] = {}
    activation_gate_bypass: list[str] = []
    right_static: dict[str, Action] = {}
    left_static: dict[str, Action] = {}
    right_holding: dict[str, Action] = {}
    left_holding: dict[str, Action] = {}
    right_moving: dict[tuple[str, str], Action] = {}
    left_moving: dict[tuple[str, str], Action] = {}
    right_sequence: dict[tuple[str, str], Action] = {}
    left_sequence: dict[tuple[str, str], Action] = {}

    for entry in actions:
        # Infer fire mode from trigger state
        if isinstance(entry.trigger, SequenceTrigger):
            fire_mode = FireMode.TAP
        else:
            fire_mode = _trigger_state_to_fire_mode[entry.trigger.state]

        # Key by gesture value (e.g. "fist") — orchestrator looks up gesture.value
        if isinstance(entry.trigger, SequenceTrigger):
            gesture_key = entry.trigger.first.gesture.value
        else:
            gesture_key = entry.trigger.gesture.value
        gesture_modes[gesture_key] = fire_mode.value

        # Collect cooldown overrides
        if entry.cooldown is not None:
            gesture_cooldowns[entry.name] = entry.cooldown

        # Collect bypass_gate — key by gesture value (gate checks gesture.value)
        if entry.bypass_gate:
            if isinstance(entry.trigger, SequenceTrigger):
                activation_gate_bypass.append(entry.trigger.first.gesture.value)
                activation_gate_bypass.append(entry.trigger.second.gesture.value)
            else:
                activation_gate_bypass.append(entry.trigger.gesture.value)

        # Build Action with pre-parsed key
        modifiers, key = parse_key_string(entry.key)
        action = Action(
            key_string=entry.key,
            fire_mode=fire_mode,
            gesture_name=entry.name,
            modifiers=modifiers,
            key=key,
        )

        # Route to correct map based on trigger type and hand
        if isinstance(entry.trigger, SequenceTrigger):
            map_key = (
                entry.trigger.first.gesture.value,
                entry.trigger.second.gesture.value,
            )
            if entry.hand in ("both", "right"):
                right_sequence[map_key] = action
            if entry.hand in ("both", "left"):
                left_sequence[map_key] = action
        elif entry.trigger.state == TriggerState.STATIC:
            map_key_str = entry.trigger.gesture.value
            if entry.hand in ("both", "right"):
                right_static[map_key_str] = action
            if entry.hand in ("both", "left"):
                left_static[map_key_str] = action
        elif entry.trigger.state == TriggerState.HOLDING:
            map_key_str = entry.trigger.gesture.value
            if entry.hand in ("both", "right"):
                right_holding[map_key_str] = action
            if entry.hand in ("both", "left"):
                left_holding[map_key_str] = action
        elif entry.trigger.state == TriggerState.MOVING:
            map_key = (entry.trigger.gesture.value, entry.trigger.direction.value)
            if entry.hand in ("both", "right"):
                right_moving[map_key] = action
            if entry.hand in ("both", "left"):
                left_moving[map_key] = action

    return DerivedConfig(
        gesture_modes=gesture_modes,
        gesture_cooldowns=gesture_cooldowns,
        activation_gate_bypass=activation_gate_bypass,
        right_static=right_static,
        left_static=left_static,
        right_holding=right_holding,
        left_holding=left_holding,
        right_moving=right_moving,
        left_moving=left_moving,
        right_sequence=right_sequence,
        left_sequence=left_sequence,
    )


@dataclass
class AppConfig:
    """Application configuration loaded from YAML."""

    camera_index: int = 0
    smoothing_window: int = 2
    activation_delay: float = 0.15
    cooldown_duration: float = 0.3
    distance_enabled: bool = False
    min_hand_size: float = 0.15
    max_hand_size: float = 0.0
    gesture_cooldowns: dict[str, float] = field(default_factory=dict)
    gesture_modes: dict[str, str] = field(default_factory=dict)
    hold_release_delay: float = 0.1
    hold_repeat_interval: float = 0.03
    preferred_hand: str = "left"
    sequence_window: float = 0.2
    activation_gate_enabled: bool = False
    activation_gate_gestures: list[str] = field(default_factory=list)
    activation_gate_duration: float = 3.0
    activation_gate_bypass: list[str] = field(default_factory=list)
    actions: list = field(default_factory=list)


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

    if "actions" not in raw:
        raise ValueError(
            f"Config file {path} missing required 'actions' section"
        )

    camera = raw.get("camera", {})
    detection = raw.get("detection", {})
    distance = raw.get("distance", {})

    preferred_hand = str(raw.get("preferred_hand", "left")).lower()
    if preferred_hand not in ("left", "right"):
        raise ValueError(
            f"preferred_hand must be 'left' or 'right', got '{preferred_hand}'"
        )

    # Parse optional activation_gate section
    activation_gate_raw = raw.get("activation_gate", {}) or {}
    activation_gate_enabled = bool(activation_gate_raw.get("enabled", False))
    activation_gate_gestures = list(activation_gate_raw.get("gestures", []) or [])
    activation_gate_duration = float(activation_gate_raw.get("duration", 3.0))
    activation_gate_bypass_cfg = list(activation_gate_raw.get("bypass", []) or [])

    action_entries = parse_actions(raw["actions"])
    derived = derive_from_actions(action_entries)

    # Resolve config-level bypass action names to gesture values
    action_name_to_gesture: dict[str, str] = {}
    for entry in action_entries:
        if isinstance(entry.trigger, SequenceTrigger):
            action_name_to_gesture[entry.name] = entry.trigger.first.gesture.value
        else:
            action_name_to_gesture[entry.name] = entry.trigger.gesture.value
    resolved_bypass_cfg = [
        action_name_to_gesture.get(name, name) for name in activation_gate_bypass_cfg
    ]

    # Merge activation_gate bypass from config + derived bypass_gate flags
    activation_gate_bypass = list(
        set(resolved_bypass_cfg) | set(derived.activation_gate_bypass)
    )

    return AppConfig(
        camera_index=int(camera.get("index", 0)),
        smoothing_window=int(detection.get("smoothing_window", 2)),
        activation_delay=float(detection.get("activation_delay", 0.15)),
        cooldown_duration=float(detection.get("cooldown_duration", 0.3)),
        distance_enabled=bool(distance.get("enabled", False)),
        min_hand_size=float(distance.get("min_hand_size", 0.15)),
        max_hand_size=float(distance.get("max_hand_size", 0.0)),
        hold_release_delay=float(detection.get("hold_release_delay", 0.1)),
        hold_repeat_interval=float(detection.get("hold_repeat_interval", 0.03)),
        preferred_hand=preferred_hand,
        sequence_window=float(detection.get("sequence_window", 0.5)),
        activation_gate_enabled=activation_gate_enabled,
        activation_gate_gestures=activation_gate_gestures,
        activation_gate_duration=activation_gate_duration,
        gesture_modes=derived.gesture_modes,
        gesture_cooldowns=derived.gesture_cooldowns,
        activation_gate_bypass=activation_gate_bypass,
        actions=action_entries,
    )
