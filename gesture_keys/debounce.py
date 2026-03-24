"""Debounce state machine for gesture activation.

Prevents false fires from flickering gestures and held poses.
State machine (tap):  IDLE -> ACTIVATING -> FIRED -> COOLDOWN -> IDLE
State machine (hold): IDLE -> ACTIVATING -> HOLDING -> COOLDOWN -> IDLE
                                            COOLDOWN -> ACTIVATING (different gesture)

The debouncer sits between the smoother output and keystroke firing.
It requires a gesture to be held continuously for activation_delay
before firing, then enters a cooldown period. During cooldown, a
DIFFERENT gesture can interrupt and begin activating immediately,
enabling fluid gesture-to-gesture transitions. The SAME gesture
remains blocked until released to None.
"""

import logging
from enum import Enum
from typing import NamedTuple, Optional

from gesture_keys.classifier import Gesture
from gesture_keys.swipe import SwipeDirection

logger = logging.getLogger("gesture_keys")


class DebounceAction(Enum):
    """Actions emitted by the debounce state machine."""

    FIRE = "fire"
    HOLD_START = "hold_start"
    HOLD_END = "hold_end"
    COMPOUND_FIRE = "compound_fire"


class DebounceSignal(NamedTuple):
    """Signal emitted by debouncer update()."""

    action: DebounceAction
    gesture: Gesture
    direction: Optional[SwipeDirection] = None


class DebounceState(Enum):
    """States of the debounce state machine."""

    IDLE = "IDLE"
    ACTIVATING = "ACTIVATING"
    FIRED = "FIRED"
    COOLDOWN = "COOLDOWN"
    HOLDING = "HOLDING"
    SWIPE_WINDOW = "SWIPE_WINDOW"


class GestureDebouncer:
    """State machine that debounces gesture input to prevent false fires.

    Args:
        activation_delay: Seconds a gesture must be held before firing.
        cooldown_duration: Seconds after firing during which all gestures
                          are blocked.
        gesture_cooldowns: Per-gesture cooldown overrides (gesture name -> seconds).
        gesture_modes: Per-gesture mode overrides (gesture name -> "tap" or "hold").
        hold_release_delay: Seconds to wait after gesture loss before releasing hold.
    """

    def __init__(
        self,
        activation_delay: float = 0.15,
        cooldown_duration: float = 0.3,
        gesture_cooldowns: dict[str, float] | None = None,
        gesture_modes: dict[str, str] | None = None,
        hold_release_delay: float = 0.1,
        swipe_gesture_directions: dict[str, set[str]] | None = None,
        swipe_window: float = 0.2,
    ) -> None:
        self._activation_delay = activation_delay
        self._cooldown_duration = cooldown_duration
        self._gesture_cooldowns = gesture_cooldowns or {}
        self._gesture_modes = gesture_modes or {}
        self._hold_release_delay = hold_release_delay
        self._swipe_gesture_directions = swipe_gesture_directions or {}
        self._swipe_window = swipe_window
        self._cooldown_duration_active = cooldown_duration
        self._state = DebounceState.IDLE
        self._activating_gesture: Optional[Gesture] = None
        self._activation_start: float = 0.0
        self._cooldown_start: float = 0.0
        self._cooldown_gesture: Optional[Gesture] = None
        self._holding_gesture: Optional[Gesture] = None
        self._release_delay_start: Optional[float] = None
        self._swipe_window_start: float = 0.0

    @property
    def state(self) -> DebounceState:
        """Current state of the debounce machine."""
        return self._state

    @property
    def is_activating(self) -> bool:
        """True when a static gesture is being confirmed (ACTIVATING state).

        Used by main loop to give static gestures priority over swipe arming.
        """
        return self._state == DebounceState.ACTIVATING

    @property
    def in_swipe_window(self) -> bool:
        """True when debouncer is in SWIPE_WINDOW state."""
        return self._state == DebounceState.SWIPE_WINDOW

    @property
    def activating_gesture(self) -> Optional[Gesture]:
        """The gesture currently being activated or in swipe window."""
        return self._activating_gesture

    def reset(self) -> None:
        """Reset to IDLE state. Used for config reload."""
        self._state = DebounceState.IDLE
        self._activating_gesture = None
        self._activation_start = 0.0
        self._cooldown_start = 0.0
        self._cooldown_gesture = None
        self._cooldown_duration_active = self._cooldown_duration
        self._holding_gesture = None
        self._release_delay_start = None
        self._swipe_window_start = 0.0

    def update(
        self, gesture: Optional[Gesture], timestamp: float,
        *, swipe_direction: Optional[SwipeDirection] = None,
    ) -> Optional[DebounceSignal]:
        """Process a smoothed gesture and return fire signal.

        Args:
            gesture: Gesture enum value or None (from smoother).
            timestamp: Current time (e.g. from time.perf_counter()).
            swipe_direction: Optional swipe direction detected this frame.

        Returns:
            DebounceSignal to act on, or None if no signal this frame.
        """
        if self._state == DebounceState.IDLE:
            return self._handle_idle(gesture, timestamp)
        elif self._state == DebounceState.ACTIVATING:
            return self._handle_activating(gesture, timestamp)
        elif self._state == DebounceState.SWIPE_WINDOW:
            return self._handle_swipe_window(gesture, timestamp, swipe_direction)
        elif self._state == DebounceState.FIRED:
            return self._handle_fired(gesture, timestamp)
        elif self._state == DebounceState.COOLDOWN:
            return self._handle_cooldown(gesture, timestamp)
        elif self._state == DebounceState.HOLDING:
            return self._handle_holding(gesture, timestamp)
        return None

    def _handle_idle(
        self, gesture: Optional[Gesture], timestamp: float
    ) -> Optional[DebounceSignal]:
        if gesture is not None:
            if gesture.value in self._swipe_gesture_directions:
                self._state = DebounceState.SWIPE_WINDOW
                self._activating_gesture = gesture
                self._swipe_window_start = timestamp
                logger.debug("IDLE -> SWIPE_WINDOW: %s", gesture.value)
            else:
                self._state = DebounceState.ACTIVATING
                self._activating_gesture = gesture
                self._activation_start = timestamp
                logger.debug("IDLE -> ACTIVATING: %s", gesture.value)
        return None

    def _handle_activating(
        self, gesture: Optional[Gesture], timestamp: float
    ) -> Optional[DebounceSignal]:
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
            mode = self._gesture_modes.get(gesture.value, "tap")
            if mode == "hold":
                self._state = DebounceState.HOLDING
                self._holding_gesture = gesture
                self._release_delay_start = None
                self._activating_gesture = None
                logger.debug("ACTIVATING -> HOLDING: %s", gesture.value)
                return DebounceSignal(DebounceAction.HOLD_START, gesture)
            else:
                self._state = DebounceState.FIRED
                logger.debug("ACTIVATING -> FIRED: %s", gesture.value)
                return DebounceSignal(DebounceAction.FIRE, gesture)

        return None

    def _handle_swipe_window(
        self, gesture: Optional[Gesture], timestamp: float,
        swipe_direction: Optional[SwipeDirection],
    ) -> Optional[DebounceSignal]:
        # Gesture lost -> IDLE
        if gesture is None:
            self._state = DebounceState.IDLE
            self._activating_gesture = None
            logger.debug("SWIPE_WINDOW -> IDLE: gesture released")
            return None

        # Gesture changed -> restart for new gesture
        if gesture != self._activating_gesture:
            self._activating_gesture = gesture
            if gesture.value in self._swipe_gesture_directions:
                self._swipe_window_start = timestamp
                logger.debug("SWIPE_WINDOW reset: switched to %s", gesture.value)
            else:
                self._state = DebounceState.ACTIVATING
                self._activation_start = timestamp
                logger.debug("SWIPE_WINDOW -> ACTIVATING: %s (no swipe mapping)", gesture.value)
            return None

        # Swipe detected and direction is mapped for this gesture -> COMPOUND_FIRE
        if swipe_direction is not None:
            mapped = self._swipe_gesture_directions.get(self._activating_gesture.value, set())
            if swipe_direction.value in mapped:
                fired_gesture = self._activating_gesture
                self._state = DebounceState.COOLDOWN
                self._cooldown_start = timestamp
                self._cooldown_duration_active = self._gesture_cooldowns.get(
                    fired_gesture.value, self._cooldown_duration
                )
                self._cooldown_gesture = fired_gesture
                self._activating_gesture = None
                logger.debug(
                    "SWIPE_WINDOW -> COOLDOWN: compound %s + %s",
                    fired_gesture.value, swipe_direction.value,
                )
                return DebounceSignal(DebounceAction.COMPOUND_FIRE, fired_gesture, swipe_direction)
            # Unmapped direction: ignore, keep waiting
            return None

        # Window expired -> fire static gesture normally
        if timestamp - self._swipe_window_start >= self._swipe_window:
            self._state = DebounceState.FIRED
            logger.debug("SWIPE_WINDOW -> FIRED: %s (window expired)", self._activating_gesture.value)
            return DebounceSignal(DebounceAction.FIRE, self._activating_gesture)

        return None

    def _handle_fired(
        self, gesture: Optional[Gesture], timestamp: float
    ) -> Optional[DebounceSignal]:
        self._state = DebounceState.COOLDOWN
        self._cooldown_start = timestamp
        fired_gesture = self._activating_gesture
        self._cooldown_duration_active = self._gesture_cooldowns.get(
            fired_gesture.value, self._cooldown_duration
        )
        self._cooldown_gesture = fired_gesture
        self._activating_gesture = None
        logger.debug("FIRED -> COOLDOWN")
        return None

    def _handle_cooldown(
        self, gesture: Optional[Gesture], timestamp: float
    ) -> Optional[DebounceSignal]:
        # Different gesture during cooldown -> route to SWIPE_WINDOW or ACTIVATING
        if gesture is not None and gesture != self._cooldown_gesture:
            if gesture.value in self._swipe_gesture_directions:
                self._state = DebounceState.SWIPE_WINDOW
                self._activating_gesture = gesture
                self._swipe_window_start = timestamp
                self._cooldown_gesture = None
                logger.debug("COOLDOWN -> SWIPE_WINDOW: %s (direct transition)", gesture.value)
            else:
                self._state = DebounceState.ACTIVATING
                self._activating_gesture = gesture
                self._activation_start = timestamp
                self._cooldown_gesture = None
                logger.debug(
                    "COOLDOWN -> ACTIVATING: %s (direct transition)", gesture.value
                )
            return None

        # Cooldown elapsed + hand released -> return to idle
        if (
            timestamp - self._cooldown_start >= self._cooldown_duration_active
            and gesture is None
        ):
            self._state = DebounceState.IDLE
            self._cooldown_gesture = None
            logger.debug("COOLDOWN -> IDLE: released")

        return None

    def _handle_holding(
        self, gesture: Optional[Gesture], timestamp: float
    ) -> Optional[DebounceSignal]:
        held = self._holding_gesture

        # Same gesture still active -> stay holding, cancel any release delay
        if gesture == held:
            self._release_delay_start = None
            return None

        # Different gesture -> release current, start activating new
        if gesture is not None and gesture != held:
            self._state = DebounceState.ACTIVATING
            self._activating_gesture = gesture
            self._activation_start = timestamp
            self._holding_gesture = None
            self._release_delay_start = None
            logger.debug(
                "HOLDING -> ACTIVATING: %s released, switching to %s",
                held.value, gesture.value,
            )
            return DebounceSignal(DebounceAction.HOLD_END, held)

        # Gesture lost (None) -> manage release delay
        if self._release_delay_start is None:
            # Start release delay timer
            self._release_delay_start = timestamp
            logger.debug("HOLDING: release delay started")
            return None

        # Release delay not yet expired
        if timestamp - self._release_delay_start < self._hold_release_delay:
            return None

        # Release delay expired -> release and cooldown
        self._state = DebounceState.COOLDOWN
        self._cooldown_start = timestamp
        self._cooldown_duration_active = self._gesture_cooldowns.get(
            held.value, self._cooldown_duration
        )
        self._cooldown_gesture = held
        self._holding_gesture = None
        self._release_delay_start = None
        logger.debug("HOLDING -> COOLDOWN: %s released", held.value)
        return DebounceSignal(DebounceAction.HOLD_END, held)
