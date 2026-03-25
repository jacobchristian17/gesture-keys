"""Action resolution and dispatch for gesture-to-keystroke mapping.

ActionResolver: Pure lookup mapping (gesture_name, hand) to Action.
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

from gesture_keys.keystroke import KeystrokeSender
from gesture_keys.orchestrator import OrchestratorAction, OrchestratorSignal

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
    """Resolves gesture signals to keyboard actions.

    Holds pre-parsed action maps for both hands. Pure lookup, no state
    beyond hand selection.

    Args:
        right_actions: Gesture name -> Action map for right hand.
        left_actions: Gesture name -> Action map for left hand.
        right_compound: (gesture_name, direction) -> Action for right hand.
        left_compound: (gesture_name, direction) -> Action for left hand.
    """

    def __init__(
        self,
        right_actions: dict[str, Action],
        left_actions: dict[str, Action],
        right_compound: dict[tuple[str, str], Action],
        left_compound: dict[tuple[str, str], Action],
    ) -> None:
        self._right_actions = right_actions
        self._left_actions = left_actions
        self._right_compound = right_compound
        self._left_compound = left_compound
        self._active_actions = right_actions
        self._active_compound = right_compound

    def set_hand(self, handedness: str) -> None:
        """Switch active action map based on detected hand.

        Args:
            handedness: 'Left' or 'Right' (from MediaPipe).
        """
        if handedness == "Left":
            self._active_actions = self._left_actions
            self._active_compound = self._left_compound
        else:
            self._active_actions = self._right_actions
            self._active_compound = self._right_compound

    def resolve(self, gesture_name: str) -> Optional[Action]:
        """Look up action for a gesture. Returns None if unmapped."""
        return self._active_actions.get(gesture_name)

    def resolve_compound(
        self, gesture_name: str, direction: str
    ) -> Optional[Action]:
        """Look up action for a compound gesture (gesture + swipe direction).

        Args:
            gesture_name: The base gesture name.
            direction: The swipe direction string.

        Returns:
            Action if mapped, None otherwise.
        """
        return self._active_compound.get((gesture_name, direction))


class ActionDispatcher:
    """Dispatches orchestrator signals to keyboard actions.

    Owns held-key lifecycle state. Routes FIRE/HOLD_START/HOLD_END/COMPOUND_FIRE
    signals to the appropriate KeystrokeSender methods.

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
        elif signal.action == OrchestratorAction.COMPOUND_FIRE:
            self._handle_compound_fire(signal)

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
        action = self._resolver.resolve(signal.gesture.value)
        if action is not None:
            self._sender.send(action.modifiers, action.key)

    def _handle_hold_start(self, signal: OrchestratorSignal) -> None:
        """Handle HOLD_START -- set held action for tick-based tap-repeat.

        Sets _last_repeat_time to 0.0 so the next tick() fires immediately.
        """
        action = self._resolver.resolve(signal.gesture.value)
        if action is not None and action.fire_mode == FireMode.HOLD_KEY:
            self._held_action = action
            self._last_repeat_time = 0.0  # Next tick() fires immediately

    def _handle_hold_end(self, signal: OrchestratorSignal) -> None:
        """Handle HOLD_END -- clear held action (tick becomes no-op)."""
        self._held_action = None

    def _handle_compound_fire(self, signal: OrchestratorSignal) -> None:
        """Handle COMPOUND_FIRE -- resolve compound and send."""
        if signal.direction is None:
            return
        action = self._resolver.resolve_compound(
            signal.gesture.value, signal.direction.value
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
