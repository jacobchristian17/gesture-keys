"""Gesture orchestrator -- hierarchical FSM for gesture lifecycle management.

Replaces the flat GestureDebouncer with a two-level state machine:
  Outer (LifecycleState): IDLE -> ACTIVATING -> SWIPE_WINDOW -> ACTIVE -> COOLDOWN
  Inner (TemporalState, only in ACTIVE): CONFIRMED, HOLD, SWIPING

Absorbs coordination logic previously scattered across Pipeline.process_frame():
  - Swiping entry/exit transitions
  - Pre-swipe gesture suppression
  - Compound swipe suppression timing
  - Static-first priority gate (via is_activating property)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple, Optional

from gesture_keys.classifier import Gesture
from gesture_keys.swipe import SwipeDirection

logger = logging.getLogger("gesture_keys")


class OrchestratorAction(Enum):
    """Actions emitted by the orchestrator state machine."""

    FIRE = "fire"
    HOLD_START = "hold_start"
    HOLD_END = "hold_end"
    COMPOUND_FIRE = "compound_fire"


class LifecycleState(Enum):
    """Outer FSM states for gesture lifecycle."""

    IDLE = "IDLE"
    ACTIVATING = "ACTIVATING"
    SWIPE_WINDOW = "SWIPE_WINDOW"
    ACTIVE = "ACTIVE"
    COOLDOWN = "COOLDOWN"


class TemporalState(Enum):
    """Inner FSM states within ACTIVE."""

    CONFIRMED = "CONFIRMED"
    HOLD = "HOLD"
    SWIPING = "SWIPING"


class OrchestratorSignal(NamedTuple):
    """Signal emitted by orchestrator update()."""

    action: OrchestratorAction
    gesture: Gesture
    direction: Optional[SwipeDirection] = None


@dataclass
class OrchestratorResult:
    """Per-frame output from the gesture orchestrator."""

    base_gesture: Optional[Gesture] = None
    temporal_state: Optional[TemporalState] = None
    outer_state: LifecycleState = LifecycleState.IDLE
    signals: list[OrchestratorSignal] = field(default_factory=list)
    suppress_standalone_swipe: bool = False


class GestureOrchestrator:
    """Hierarchical FSM for gesture lifecycle management.

    Args:
        activation_delay: Seconds a gesture must be held before firing.
        cooldown_duration: Seconds after firing during which same gesture is blocked.
        gesture_cooldowns: Per-gesture cooldown overrides (gesture name -> seconds).
        gesture_modes: Per-gesture mode overrides (gesture name -> "tap" or "hold_key").
        hold_release_delay: Seconds to wait after gesture loss before releasing hold.
        swipe_gesture_directions: Gesture name -> set of mapped swipe direction strings.
        swipe_window: Seconds to wait for a swipe after a swipe-mapped gesture appears.
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

        # Outer FSM state
        self._outer_state = LifecycleState.IDLE
        # Inner FSM state (only meaningful when outer is ACTIVE)
        self._temporal_state: Optional[TemporalState] = None

        # Activating state
        self._activating_gesture: Optional[Gesture] = None
        self._activation_start: float = 0.0

        # Cooldown state
        self._cooldown_start: float = 0.0
        self._cooldown_gesture: Optional[Gesture] = None
        self._cooldown_duration_active: float = cooldown_duration

        # Hold state (inner FSM)
        self._holding_gesture: Optional[Gesture] = None
        self._release_delay_start: Optional[float] = None

        # Swipe window state
        self._swipe_window_start: float = 0.0

        # Compound swipe suppression
        self._suppress_until: float = 0.0

        # Swiping tracking (for entry/exit detection)
        self._was_swiping: bool = False
        self._pre_swipe_gesture: Optional[Gesture] = None

    @property
    def is_activating(self) -> bool:
        """True when a static gesture is being confirmed (ACTIVATING state)."""
        return self._outer_state == LifecycleState.ACTIVATING

    @property
    def in_swipe_window(self) -> bool:
        """True when orchestrator is in SWIPE_WINDOW state."""
        return self._outer_state == LifecycleState.SWIPE_WINDOW

    @property
    def activating_gesture(self) -> Optional[Gesture]:
        """The gesture currently being activated or in swipe window."""
        return self._activating_gesture

    def reset(self) -> None:
        """Reset to IDLE state. Used for hand switch and config reload."""
        self._outer_state = LifecycleState.IDLE
        self._temporal_state = None
        self._activating_gesture = None
        self._activation_start = 0.0
        self._cooldown_start = 0.0
        self._cooldown_gesture = None
        self._cooldown_duration_active = self._cooldown_duration
        self._holding_gesture = None
        self._release_delay_start = None
        self._swipe_window_start = 0.0
        self._suppress_until = 0.0
        self._was_swiping = False
        self._pre_swipe_gesture = None

    def flush_pending(self) -> OrchestratorResult:
        """Fire pending gesture if in SWIPE_WINDOW. Used before config reload.

        Returns:
            OrchestratorResult with FIRE signal if a gesture was pending, empty otherwise.
        """
        if (
            self._outer_state == LifecycleState.SWIPE_WINDOW
            and self._activating_gesture is not None
        ):
            gesture = self._activating_gesture
            signals = [OrchestratorSignal(OrchestratorAction.FIRE, gesture)]
            self._outer_state = LifecycleState.IDLE
            self._activating_gesture = None
            return OrchestratorResult(
                base_gesture=gesture,
                outer_state=LifecycleState.IDLE,
                signals=signals,
            )
        return OrchestratorResult(outer_state=self._outer_state)

    def update(
        self,
        gesture: Optional[Gesture],
        timestamp: float,
        *,
        swipe_direction: Optional[SwipeDirection] = None,
        swiping: bool = False,
    ) -> OrchestratorResult:
        """Process one frame of gesture input.

        Args:
            gesture: Smoothed gesture from classifier+smoother, or None.
            timestamp: Current time (perf_counter).
            swipe_direction: Swipe direction detected this frame.
            swiping: Whether SwipeDetector.is_swiping is True this frame.

        Returns:
            OrchestratorResult with current state and any signals to act on.
        """
        signals: list[OrchestratorSignal] = []

        # Handle swiping transitions BEFORE outer state dispatch
        swiping_result = self._handle_swiping_transitions(
            gesture, timestamp, swiping, signals
        )
        if swiping_result is not None:
            return swiping_result

        # Outer FSM dispatch
        if self._outer_state == LifecycleState.IDLE:
            self._handle_idle(gesture, timestamp, signals)
        elif self._outer_state == LifecycleState.ACTIVATING:
            self._handle_activating(gesture, timestamp, signals)
        elif self._outer_state == LifecycleState.SWIPE_WINDOW:
            self._handle_swipe_window(gesture, timestamp, swipe_direction, signals)
        elif self._outer_state == LifecycleState.ACTIVE:
            self._handle_active(gesture, timestamp, signals)
        elif self._outer_state == LifecycleState.COOLDOWN:
            self._handle_cooldown(gesture, timestamp, signals)

        # Update swiping tracking
        self._was_swiping = swiping

        # Build result
        return self._build_result(timestamp, signals)

    def _handle_swiping_transitions(
        self,
        gesture: Optional[Gesture],
        timestamp: float,
        swiping: bool,
        signals: list[OrchestratorSignal],
    ) -> Optional[OrchestratorResult]:
        """Handle swiping entry/exit before outer state dispatch.

        Returns OrchestratorResult if swiping transition consumed the frame, None otherwise.
        """
        # Swiping entry: was not swiping, now swiping
        if not self._was_swiping and swiping:
            # Remember the gesture that was active before swiping started
            if self._activating_gesture is not None:
                self._pre_swipe_gesture = self._activating_gesture
            elif self._holding_gesture is not None:
                self._pre_swipe_gesture = self._holding_gesture
            elif gesture is not None:
                self._pre_swipe_gesture = gesture

            # If in ACTIVE(HOLD), emit HOLD_END
            if (
                self._outer_state == LifecycleState.ACTIVE
                and self._temporal_state == TemporalState.HOLD
                and self._holding_gesture is not None
            ):
                signals.append(
                    OrchestratorSignal(OrchestratorAction.HOLD_END, self._holding_gesture)
                )

            # Reset to IDLE on swiping entry
            self._outer_state = LifecycleState.IDLE
            self._temporal_state = None
            self._activating_gesture = None
            self._holding_gesture = None
            self._release_delay_start = None
            self._was_swiping = True
            return self._build_result(timestamp, signals)

        # Swiping exit: was swiping, now not swiping
        if self._was_swiping and not swiping:
            self._was_swiping = False
            # Transition to COOLDOWN with pre-swipe gesture suppression
            self._outer_state = LifecycleState.COOLDOWN
            self._temporal_state = None
            self._cooldown_start = timestamp
            self._cooldown_gesture = self._pre_swipe_gesture
            self._cooldown_duration_active = self._cooldown_duration
            if self._pre_swipe_gesture is not None and self._pre_swipe_gesture.value in self._gesture_cooldowns:
                self._cooldown_duration_active = self._gesture_cooldowns[self._pre_swipe_gesture.value]
            self._activating_gesture = None
            self._holding_gesture = None
            self._pre_swipe_gesture = None
            return self._build_result(timestamp, signals)

        return None

    def _handle_idle(
        self,
        gesture: Optional[Gesture],
        timestamp: float,
        signals: list[OrchestratorSignal],
    ) -> None:
        if gesture is not None:
            if gesture.value in self._swipe_gesture_directions:
                self._outer_state = LifecycleState.SWIPE_WINDOW
                self._activating_gesture = gesture
                self._swipe_window_start = timestamp
                self._suppress_until = timestamp + self._swipe_window
                logger.info("IDLE -> SWIPE_WINDOW: %s", gesture.value)
            else:
                self._outer_state = LifecycleState.ACTIVATING
                self._activating_gesture = gesture
                self._activation_start = timestamp
                logger.debug("IDLE -> ACTIVATING: %s", gesture.value)

    def _handle_activating(
        self,
        gesture: Optional[Gesture],
        timestamp: float,
        signals: list[OrchestratorSignal],
    ) -> None:
        if gesture is None:
            self._outer_state = LifecycleState.IDLE
            self._activating_gesture = None
            logger.debug("ACTIVATING -> IDLE: gesture released")
            return

        if gesture != self._activating_gesture:
            self._activating_gesture = gesture
            self._activation_start = timestamp
            logger.debug("ACTIVATING reset: switched to %s", gesture.value)
            return

        if timestamp - self._activation_start >= self._activation_delay:
            mode = self._gesture_modes.get(gesture.value, "tap")
            if mode == "hold_key":
                # ACTIVATING -> ACTIVE(HOLD) + HOLD_START
                self._outer_state = LifecycleState.ACTIVE
                self._temporal_state = TemporalState.HOLD
                self._holding_gesture = gesture
                self._release_delay_start = None
                self._activating_gesture = None
                logger.debug("ACTIVATING -> ACTIVE(HOLD): %s", gesture.value)
                signals.append(
                    OrchestratorSignal(OrchestratorAction.HOLD_START, gesture)
                )
            else:
                # ACTIVATING -> ACTIVE(CONFIRMED) + FIRE
                # For tap mode, immediately transition to COOLDOWN (1-frame ACTIVE)
                self._outer_state = LifecycleState.COOLDOWN
                self._cooldown_start = timestamp
                fired_gesture = self._activating_gesture
                self._cooldown_duration_active = self._gesture_cooldowns.get(
                    fired_gesture.value, self._cooldown_duration
                )
                self._cooldown_gesture = fired_gesture
                self._activating_gesture = None
                logger.debug("ACTIVATING -> FIRE -> COOLDOWN: %s", gesture.value)
                signals.append(
                    OrchestratorSignal(OrchestratorAction.FIRE, gesture)
                )

    def _handle_swipe_window(
        self,
        gesture: Optional[Gesture],
        timestamp: float,
        swipe_direction: Optional[SwipeDirection],
        signals: list[OrchestratorSignal],
    ) -> None:
        # Update suppress timing
        self._suppress_until = max(self._suppress_until, timestamp + self._swipe_window)

        # Swipe detected and direction is mapped for this gesture -> COMPOUND_FIRE
        if swipe_direction is not None:
            mapped = self._swipe_gesture_directions.get(
                self._activating_gesture.value, set()
            )
            if swipe_direction.value in mapped:
                fired_gesture = self._activating_gesture
                self._outer_state = LifecycleState.COOLDOWN
                self._cooldown_start = timestamp
                self._cooldown_duration_active = self._gesture_cooldowns.get(
                    fired_gesture.value, self._cooldown_duration
                )
                self._cooldown_gesture = fired_gesture
                self._activating_gesture = None
                logger.info(
                    "SWIPE_WINDOW -> COOLDOWN: compound %s + %s",
                    fired_gesture.value, swipe_direction.value,
                )
                signals.append(
                    OrchestratorSignal(
                        OrchestratorAction.COMPOUND_FIRE, fired_gesture, swipe_direction
                    )
                )
                return
            # Unmapped direction: ignore, keep waiting
            return

        # Window expired -> fire static gesture if still held, else go IDLE
        if timestamp - self._swipe_window_start >= self._swipe_window:
            if gesture == self._activating_gesture:
                # Fire static gesture, transition to cooldown (same as tap mode)
                fired_gesture = self._activating_gesture
                self._outer_state = LifecycleState.COOLDOWN
                self._cooldown_start = timestamp
                self._cooldown_duration_active = self._gesture_cooldowns.get(
                    fired_gesture.value, self._cooldown_duration
                )
                self._cooldown_gesture = fired_gesture
                self._activating_gesture = None
                logger.info(
                    "SWIPE_WINDOW -> FIRE -> COOLDOWN: %s (window expired)",
                    fired_gesture.value,
                )
                signals.append(
                    OrchestratorSignal(OrchestratorAction.FIRE, fired_gesture)
                )
            else:
                # Gesture lost or changed during window, no swipe came
                self._outer_state = LifecycleState.IDLE
                self._activating_gesture = None
                logger.info("SWIPE_WINDOW -> IDLE: window expired, gesture gone")

    def _handle_active(
        self,
        gesture: Optional[Gesture],
        timestamp: float,
        signals: list[OrchestratorSignal],
    ) -> None:
        """Dispatch to inner FSM based on temporal_state."""
        if self._temporal_state == TemporalState.HOLD:
            self._handle_hold(gesture, timestamp, signals)
        elif self._temporal_state == TemporalState.CONFIRMED:
            # Tap mode: auto-transition to COOLDOWN (1-frame ACTIVE)
            self._outer_state = LifecycleState.COOLDOWN
            self._temporal_state = None
            self._cooldown_start = timestamp
            logger.debug("ACTIVE(CONFIRMED) -> COOLDOWN")
        elif self._temporal_state == TemporalState.SWIPING:
            # Stay in SWIPING while swiping flag is True
            # Swiping exit is handled before dispatch
            pass

    def _handle_hold(
        self,
        gesture: Optional[Gesture],
        timestamp: float,
        signals: list[OrchestratorSignal],
    ) -> None:
        """Handle ACTIVE(HOLD) inner state -- same logic as GestureDebouncer._handle_holding()."""
        held = self._holding_gesture

        # Same gesture still active -> stay holding, cancel any release delay
        if gesture == held:
            self._release_delay_start = None
            return

        # Different gesture -> release current, start activating new
        if gesture is not None and gesture != held:
            self._outer_state = LifecycleState.ACTIVATING
            self._temporal_state = None
            self._activating_gesture = gesture
            self._activation_start = timestamp
            self._holding_gesture = None
            self._release_delay_start = None
            logger.debug(
                "ACTIVE(HOLD) -> ACTIVATING: %s released, switching to %s",
                held.value, gesture.value,
            )
            signals.append(OrchestratorSignal(OrchestratorAction.HOLD_END, held))
            return

        # Gesture lost (None) -> manage release delay
        if self._release_delay_start is None:
            self._release_delay_start = timestamp
            logger.debug("ACTIVE(HOLD): release delay started")
            return

        # Release delay not yet expired
        if timestamp - self._release_delay_start < self._hold_release_delay:
            return

        # Release delay expired -> release and cooldown
        self._outer_state = LifecycleState.COOLDOWN
        self._temporal_state = None
        self._cooldown_start = timestamp
        self._cooldown_duration_active = self._gesture_cooldowns.get(
            held.value, self._cooldown_duration
        )
        self._cooldown_gesture = held
        self._holding_gesture = None
        self._release_delay_start = None
        logger.debug("ACTIVE(HOLD) -> COOLDOWN: %s released", held.value)
        signals.append(OrchestratorSignal(OrchestratorAction.HOLD_END, held))

    def _handle_cooldown(
        self,
        gesture: Optional[Gesture],
        timestamp: float,
        signals: list[OrchestratorSignal],
    ) -> None:
        # Different gesture during cooldown -> route to SWIPE_WINDOW or ACTIVATING
        if gesture is not None and gesture != self._cooldown_gesture:
            if gesture.value in self._swipe_gesture_directions:
                self._outer_state = LifecycleState.SWIPE_WINDOW
                self._activating_gesture = gesture
                self._swipe_window_start = timestamp
                self._suppress_until = timestamp + self._swipe_window
                self._cooldown_gesture = None
                logger.debug(
                    "COOLDOWN -> SWIPE_WINDOW: %s (direct transition)", gesture.value
                )
            else:
                self._outer_state = LifecycleState.ACTIVATING
                self._activating_gesture = gesture
                self._activation_start = timestamp
                self._cooldown_gesture = None
                logger.debug(
                    "COOLDOWN -> ACTIVATING: %s (direct transition)", gesture.value
                )
            return

        # Cooldown elapsed + hand released -> return to idle
        if (
            timestamp - self._cooldown_start >= self._cooldown_duration_active
            and gesture is None
        ):
            self._outer_state = LifecycleState.IDLE
            self._cooldown_gesture = None
            logger.debug("COOLDOWN -> IDLE: released")

    def _build_result(
        self, timestamp: float, signals: list[OrchestratorSignal]
    ) -> OrchestratorResult:
        """Build the OrchestratorResult from current internal state."""
        # Determine base gesture
        base_gesture: Optional[Gesture] = None
        if self._outer_state == LifecycleState.ACTIVATING:
            base_gesture = self._activating_gesture
        elif self._outer_state == LifecycleState.SWIPE_WINDOW:
            base_gesture = self._activating_gesture
        elif self._outer_state == LifecycleState.ACTIVE:
            base_gesture = self._holding_gesture
        elif self._outer_state == LifecycleState.COOLDOWN:
            base_gesture = self._cooldown_gesture

        # Temporal state is only valid in ACTIVE
        temporal_state = (
            self._temporal_state
            if self._outer_state == LifecycleState.ACTIVE
            else None
        )

        # Compound swipe suppression
        suppress = timestamp < self._suppress_until

        return OrchestratorResult(
            base_gesture=base_gesture,
            temporal_state=temporal_state,
            outer_state=self._outer_state,
            signals=signals,
            suppress_standalone_swipe=suppress,
        )
