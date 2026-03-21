"""Debounce state machine for gesture activation.

Prevents false fires from flickering gestures and held poses.
State machine: IDLE -> ACTIVATING -> FIRED -> COOLDOWN -> IDLE

The debouncer sits between the smoother output and keystroke firing.
It requires a gesture to be held continuously for activation_delay
before firing, then enters a cooldown period that blocks all gestures.
After cooldown, the gesture must be released (None) before a new
activation can begin.
"""

import logging
from enum import Enum
from typing import Optional

from gesture_keys.classifier import Gesture

logger = logging.getLogger("gesture_keys")


class DebounceState(Enum):
    """States of the debounce state machine."""

    IDLE = "IDLE"
    ACTIVATING = "ACTIVATING"
    FIRED = "FIRED"
    COOLDOWN = "COOLDOWN"


class GestureDebouncer:
    """State machine that debounces gesture input to prevent false fires.

    Args:
        activation_delay: Seconds a gesture must be held before firing.
        cooldown_duration: Seconds after firing during which all gestures
                          are blocked.
    """

    def __init__(
        self,
        activation_delay: float = 0.4,
        cooldown_duration: float = 0.8,
    ) -> None:
        self._activation_delay = activation_delay
        self._cooldown_duration = cooldown_duration
        self._state = DebounceState.IDLE
        self._activating_gesture: Optional[Gesture] = None
        self._activation_start: float = 0.0
        self._cooldown_start: float = 0.0

    @property
    def state(self) -> DebounceState:
        """Current state of the debounce machine."""
        return self._state

    def reset(self) -> None:
        """Reset to IDLE state. Used for config reload."""
        self._state = DebounceState.IDLE
        self._activating_gesture = None
        self._activation_start = 0.0
        self._cooldown_start = 0.0

    def update(
        self, gesture: Optional[Gesture], timestamp: float
    ) -> Optional[Gesture]:
        """Process a smoothed gesture and return fire signal.

        Args:
            gesture: Gesture enum value or None (from smoother).
            timestamp: Current time (e.g. from time.perf_counter()).

        Returns:
            Gesture to fire, or None if no fire this frame.
        """
        if self._state == DebounceState.IDLE:
            return self._handle_idle(gesture, timestamp)
        elif self._state == DebounceState.ACTIVATING:
            return self._handle_activating(gesture, timestamp)
        elif self._state == DebounceState.FIRED:
            return self._handle_fired(gesture, timestamp)
        elif self._state == DebounceState.COOLDOWN:
            return self._handle_cooldown(gesture, timestamp)
        return None

    def _handle_idle(
        self, gesture: Optional[Gesture], timestamp: float
    ) -> Optional[Gesture]:
        if gesture is not None:
            self._state = DebounceState.ACTIVATING
            self._activating_gesture = gesture
            self._activation_start = timestamp
            logger.debug("IDLE -> ACTIVATING: %s", gesture.value)
        return None

    def _handle_activating(
        self, gesture: Optional[Gesture], timestamp: float
    ) -> Optional[Gesture]:
        if gesture is None:
            self._state = DebounceState.IDLE
            self._activating_gesture = None
            logger.debug("ACTIVATING -> IDLE: gesture released")
            return None

        if gesture != self._activating_gesture:
            self._activating_gesture = gesture
            self._activation_start = timestamp
            logger.debug("ACTIVATING reset: switched to %s", gesture.value)
            return None

        if timestamp - self._activation_start >= self._activation_delay:
            self._state = DebounceState.FIRED
            logger.debug("ACTIVATING -> FIRED: %s", gesture.value)
            return gesture

        return None

    def _handle_fired(
        self, gesture: Optional[Gesture], timestamp: float
    ) -> Optional[Gesture]:
        self._state = DebounceState.COOLDOWN
        self._cooldown_start = timestamp
        self._activating_gesture = None
        logger.debug("FIRED -> COOLDOWN")
        return None

    def _handle_cooldown(
        self, gesture: Optional[Gesture], timestamp: float
    ) -> Optional[Gesture]:
        if timestamp - self._cooldown_start >= self._cooldown_duration:
            if gesture is None:
                self._state = DebounceState.IDLE
                logger.debug("COOLDOWN -> IDLE: released")
        return None
