"""Action resolution and dispatch for gesture-to-keystroke mapping.

ActionResolver: Pure lookup mapping gestures to Actions via four trigger-type
maps (static, holding, moving, sequence) per hand.
ActionDispatcher: Stateful key lifecycle manager routing orchestrator
signals to KeystrokeSender methods.

FireMode determines HOW a resolved action is executed:
  - TAP: press and release once (sender.send)
  - HOLD_KEY: app-controlled tap-repeat via tick() while gesture held
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

from pynput.keyboard import Key

from gesture_keys.classifier import Gesture
from gesture_keys.keystroke import KeystrokeSender
from gesture_keys.orchestrator import OrchestratorAction, OrchestratorSignal
from gesture_keys.trigger import Direction

logger = logging.getLogger("gesture_keys")


class FireMode(Enum):
    """How a resolved action is executed."""

    TAP = "tap"
    HOLD_KEY = "hold_key"


@dataclass(frozen=True)
class Action:
    """Resolved action from gesture + hand configuration.

    Attributes:
        key_string: Original key string from config (e.g. 'ctrl+z').
        fire_mode: How the action should be executed.
        gesture_name: Name of the gesture that triggers this action.
        modifiers: Pre-parsed pynput Key modifier objects.
        key: Pre-parsed pynput Key or single-character string.
    """

    key_string: str
    fire_mode: FireMode
    gesture_name: str
    modifiers: list  # list[Key]
    key: object  # Key | str


class ActionResolver:
    """Resolves gesture signals to keyboard actions using four trigger-type maps.

    Holds pre-parsed action maps for both hands across four trigger types:
    static, holding, moving, and sequence. Pure lookup, no state beyond
    hand selection.

    Supports two construction patterns:
    - New 8-map keyword args (right_static, left_static, etc.)
    - Legacy 4-arg positional (right_actions, left_actions, right_compound,
      left_compound) for backward compatibility with pipeline.py.
    """

    def __init__(
        self,
        right_actions: Optional[dict[str, Action]] = None,
        left_actions: Optional[dict[str, Action]] = None,
        right_compound: Optional[dict[tuple[str, str], Action]] = None,
        left_compound: Optional[dict[tuple[str, str], Action]] = None,
        *,
        right_static: Optional[dict[str, Action]] = None,
        left_static: Optional[dict[str, Action]] = None,
        right_holding: Optional[dict[str, Action]] = None,
        left_holding: Optional[dict[str, Action]] = None,
        right_moving: Optional[dict[tuple[str, str], Action]] = None,
        left_moving: Optional[dict[tuple[str, str], Action]] = None,
        right_sequence: Optional[dict[tuple[str, str], Action]] = None,
        left_sequence: Optional[dict[tuple[str, str], Action]] = None,
    ) -> None:
        if right_static is not None:
            # New 8-map path
            self._right_static = right_static
            self._left_static = left_static or {}
            self._right_holding = right_holding or {}
            self._left_holding = left_holding or {}
            self._right_moving = right_moving or {}
            self._left_moving = left_moving or {}
            self._right_sequence = right_sequence or {}
            self._left_sequence = left_sequence or {}
        else:
            # Legacy 4-arg path: static+holding combined in right_actions/left_actions
            self._right_static = right_actions or {}
            self._left_static = left_actions or {}
            self._right_holding = right_actions or {}
            self._left_holding = left_actions or {}
            self._right_moving = right_compound or {}
            self._left_moving = left_compound or {}
            self._right_sequence = {}
            self._left_sequence = {}

        self._active_static = self._right_static
        self._active_holding = self._right_holding
        self._active_moving = self._right_moving
        self._active_sequence = self._right_sequence

    def set_hand(self, handedness: str) -> None:
        """Switch active action maps based on detected hand.

        Args:
            handedness: 'Left' or 'Right' (from MediaPipe).
        """
        if handedness == "Left":
            self._active_static = self._left_static
            self._active_holding = self._left_holding
            self._active_moving = self._left_moving
            self._active_sequence = self._left_sequence
        else:
            self._active_static = self._right_static
            self._active_holding = self._right_holding
            self._active_moving = self._right_moving
            self._active_sequence = self._right_sequence

    def resolve_static(self, gesture_name: str) -> Optional[Action]:
        """Look up action for a static gesture. Returns None if unmapped."""
        return self._active_static.get(gesture_name)

    def resolve_holding(self, gesture_name: str) -> Optional[Action]:
        """Look up action for a holding gesture. Returns None if unmapped."""
        return self._active_holding.get(gesture_name)

    def resolve_moving(
        self, gesture_name: str, direction: Direction
    ) -> Optional[Action]:
        """Look up action for a moving gesture (gesture + direction).

        Args:
            gesture_name: The gesture value string (e.g. 'open_palm').
            direction: The Direction enum member.

        Returns:
            Action if mapped, None otherwise.
        """
        return self._active_moving.get((gesture_name, direction.value))

    def resolve_sequence(
        self, first: Gesture, second: Gesture
    ) -> Optional[Action]:
        """Look up action for a sequence (first_gesture -> second_gesture).

        Args:
            first: First gesture in the sequence.
            second: Second gesture in the sequence.

        Returns:
            Action if mapped, None otherwise.
        """
        return self._active_sequence.get((first.value, second.value))

    # Legacy resolve() for backward compatibility with pipeline.py dispatcher path
    def resolve(self, gesture_name: str) -> Optional[Action]:
        """Legacy: look up action by gesture name in static map.

        Provided for backward compatibility. New code should use
        resolve_static() or resolve_holding().
        """
        return self._active_static.get(gesture_name)


class ActionDispatcher:
    """Dispatches orchestrator signals to keyboard actions.

    Owns held-key lifecycle state. Routes FIRE/HOLD_START/HOLD_END/
    MOVING_FIRE/SEQUENCE_FIRE signals to the appropriate KeystrokeSender
    methods.

    Hold_key fire mode uses app-controlled tap-repeat: tick() sends repeated
    keystrokes at repeat_interval while _held_action is set. This replaces
    OS key-hold (press_and_hold) which Windows does not auto-repeat for
    programmatic SendInput events.

    Guarantees no stuck keys via release_all() on every exit path.

    Args:
        sender: KeystrokeSender for keyboard control.
        resolver: ActionResolver for gesture -> Action lookup.
        repeat_interval: Seconds between tap-repeat sends (default 30ms).
    """

    def __init__(
        self,
        sender: KeystrokeSender,
        resolver: ActionResolver,
        repeat_interval: float = 0.03,
    ) -> None:
        self._sender = sender
        self._resolver = resolver
        self._held_action: Optional[Action] = None
        self._repeat_interval = repeat_interval
        self._last_repeat_time: float = 0.0

    def dispatch(self, signal: OrchestratorSignal) -> None:
        """Route an orchestrator signal to the appropriate fire mode handler.

        Args:
            signal: OrchestratorSignal with action, gesture, and optional direction.
        """
        if signal.action == OrchestratorAction.FIRE:
            self._handle_fire(signal)
        elif signal.action == OrchestratorAction.HOLD_START:
            self._handle_hold_start(signal)
        elif signal.action == OrchestratorAction.HOLD_END:
            self._handle_hold_end(signal)
        elif signal.action == OrchestratorAction.MOVING_FIRE:
            self._handle_moving_fire(signal)
        elif signal.action == OrchestratorAction.SEQUENCE_FIRE:
            self._handle_sequence_fire(signal)

    def tick(self, current_time: float) -> None:
        """Send repeated keystroke if hold is active and interval elapsed.

        Called every frame by Pipeline.process_frame(). No-op when no
        hold is active.

        Args:
            current_time: Current time in seconds (time.perf_counter()).
        """
        if self._held_action is None:
            return
        if current_time - self._last_repeat_time >= self._repeat_interval:
            self._sender.send(
                self._held_action.modifiers, self._held_action.key
            )
            self._last_repeat_time = current_time

    def _handle_fire(self, signal: OrchestratorSignal) -> None:
        """Handle FIRE signal -- always tap behavior regardless of fire_mode."""
        action = self._resolver.resolve_static(signal.gesture.value)
        if action is not None:
            self._sender.send(action.modifiers, action.key)

    def _handle_hold_start(self, signal: OrchestratorSignal) -> None:
        """Handle HOLD_START -- set held action for tick-based tap-repeat.

        Sets _last_repeat_time to 0.0 so the next tick() fires immediately.
        """
        action = self._resolver.resolve_holding(signal.gesture.value)
        if action is not None and action.fire_mode == FireMode.HOLD_KEY:
            self._held_action = action
            self._last_repeat_time = 0.0  # Next tick() fires immediately

    def _handle_hold_end(self, signal: OrchestratorSignal) -> None:
        """Handle HOLD_END -- clear held action (tick becomes no-op)."""
        self._held_action = None

    def _handle_moving_fire(self, signal: OrchestratorSignal) -> None:
        """Handle MOVING_FIRE -- resolve moving action and send keystroke."""
        action = self._resolver.resolve_moving(
            signal.gesture.value, signal.direction
        )
        if action is not None:
            self._sender.send(action.modifiers, action.key)

    def _handle_sequence_fire(self, signal: OrchestratorSignal) -> None:
        """Handle SEQUENCE_FIRE -- resolve sequence action and send keystroke."""
        action = self._resolver.resolve_sequence(
            signal.gesture, signal.second_gesture
        )
        if action is not None:
            self._sender.send(action.modifiers, action.key)

    def release_all(self) -> None:
        """Release all held keys and clear internal state.

        Called on every exit path (hand switch, distance out-of-range,
        app toggle off, config reload). Idempotent.
        """
        self._held_action = None
        self._sender.release_all()
