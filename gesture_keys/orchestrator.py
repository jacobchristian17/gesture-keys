"""Gesture orchestrator -- hierarchical FSM for gesture lifecycle management.

Replaces the flat GestureDebouncer with a two-level state machine:
  Outer (LifecycleState): IDLE -> ACTIVATING -> ACTIVE -> COOLDOWN
  Inner (TemporalState, only in ACTIVE): CONFIRMED, HOLD

Absorbs coordination logic previously scattered across Pipeline.process_frame():
  - Static-first priority gate (via is_activating property)
  - Per-gesture cooldown durations
  - Hold release delay (flicker absorption)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple, Optional

from gesture_keys.classifier import Gesture
from gesture_keys.motion import MotionState
from gesture_keys.trigger import Direction

logger = logging.getLogger("gesture_keys")


class OrchestratorAction(Enum):
    """Actions emitted by the orchestrator state machine."""

    FIRE = "fire"
    HOLD_START = "hold_start"
    HOLD_END = "hold_end"
    MOVING_FIRE = "moving_fire"


class LifecycleState(Enum):
    """Outer FSM states for gesture lifecycle."""

    IDLE = "IDLE"
    ACTIVATING = "ACTIVATING"
    ACTIVE = "ACTIVE"
    COOLDOWN = "COOLDOWN"


class TemporalState(Enum):
    """Inner FSM states within ACTIVE."""

    CONFIRMED = "CONFIRMED"
    HOLD = "HOLD"


class OrchestratorSignal(NamedTuple):
    """Signal emitted by orchestrator update()."""

    action: OrchestratorAction
    gesture: Gesture
    direction: Optional[Direction] = None
    second_gesture: Optional[Gesture] = None


@dataclass
class OrchestratorResult:
    """Per-frame output from the gesture orchestrator."""

    base_gesture: Optional[Gesture] = None
    temporal_state: Optional[TemporalState] = None
    outer_state: LifecycleState = LifecycleState.IDLE
    signals: list[OrchestratorSignal] = field(default_factory=list)


class GestureOrchestrator:
    """Hierarchical FSM for gesture lifecycle management.

    Args:
        activation_delay: Seconds a gesture must be held before firing.
        cooldown_duration: Seconds after firing during which same gesture is blocked.
        gesture_cooldowns: Per-gesture cooldown overrides (gesture name -> seconds).
        gesture_modes: Per-gesture mode overrides (gesture name -> "tap" or "hold_key").
        hold_release_delay: Seconds to wait after gesture loss before releasing hold.
    """

    def __init__(
        self,
        activation_delay: float = 0.15,
        cooldown_duration: float = 0.3,
        gesture_cooldowns: dict[str, float] | None = None,
        gesture_modes: dict[str, str] | None = None,
        hold_release_delay: float = 0.1,
    ) -> None:
        self._activation_delay = activation_delay
        self._cooldown_duration = cooldown_duration
        self._gesture_cooldowns = gesture_cooldowns or {}
        self._gesture_modes = gesture_modes or {}
        self._hold_release_delay = hold_release_delay

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

    @property
    def is_activating(self) -> bool:
        """True when a static gesture is being confirmed (ACTIVATING state)."""
        return self._outer_state == LifecycleState.ACTIVATING

    @property
    def activating_gesture(self) -> Optional[Gesture]:
        """The gesture currently being activated."""
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

    def flush_pending(self) -> OrchestratorResult:
        """Flush any pending state. Used before config reload.

        Returns:
            OrchestratorResult with current outer state (always empty signals).
        """
        return OrchestratorResult(outer_state=self._outer_state)

    def update(
        self,
        gesture: Optional[Gesture],
        timestamp: float,
        *,
        motion_state: Optional[MotionState] = None,
    ) -> OrchestratorResult:
        """Process one frame of gesture input.

        Args:
            gesture: Smoothed gesture from classifier+smoother, or None.
            timestamp: Current time (perf_counter).
            motion_state: Per-frame motion report, or None if unavailable.

        Returns:
            OrchestratorResult with current state and any signals to act on.
        """
        signals: list[OrchestratorSignal] = []

        # Outer FSM dispatch
        if self._outer_state == LifecycleState.IDLE:
            self._handle_idle(gesture, timestamp, signals)
        elif self._outer_state == LifecycleState.ACTIVATING:
            self._handle_activating(gesture, timestamp, signals, motion_state)
        elif self._outer_state == LifecycleState.ACTIVE:
            self._handle_active(gesture, timestamp, signals, motion_state)
        elif self._outer_state == LifecycleState.COOLDOWN:
            self._handle_cooldown(gesture, timestamp, signals)

        # Build result
        return self._build_result(signals)

    def _handle_idle(
        self,
        gesture: Optional[Gesture],
        timestamp: float,
        signals: list[OrchestratorSignal],
    ) -> None:
        if gesture is not None:
            self._outer_state = LifecycleState.ACTIVATING
            self._activating_gesture = gesture
            self._activation_start = timestamp
            logger.debug("IDLE -> ACTIVATING: %s", gesture.value)

    def _handle_activating(
        self,
        gesture: Optional[Gesture],
        timestamp: float,
        signals: list[OrchestratorSignal],
        motion_state: Optional[MotionState] = None,
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
                # Emit MOVING_FIRE alongside FIRE if moving with direction
                self._maybe_emit_moving_fire(
                    gesture, motion_state, signals
                )

    def _handle_active(
        self,
        gesture: Optional[Gesture],
        timestamp: float,
        signals: list[OrchestratorSignal],
        motion_state: Optional[MotionState] = None,
    ) -> None:
        """Dispatch to inner FSM based on temporal_state."""
        if self._temporal_state == TemporalState.HOLD:
            self._handle_hold(gesture, timestamp, signals, motion_state)
        elif self._temporal_state == TemporalState.CONFIRMED:
            # Tap mode: auto-transition to COOLDOWN (1-frame ACTIVE)
            self._outer_state = LifecycleState.COOLDOWN
            self._temporal_state = None
            self._cooldown_start = timestamp
            logger.debug("ACTIVE(CONFIRMED) -> COOLDOWN")

    def _handle_hold(
        self,
        gesture: Optional[Gesture],
        timestamp: float,
        signals: list[OrchestratorSignal],
        motion_state: Optional[MotionState] = None,
    ) -> None:
        """Handle ACTIVE(HOLD) inner state -- same logic as GestureDebouncer._handle_holding()."""
        held = self._holding_gesture

        # Same gesture still active -> stay holding, cancel any release delay
        if gesture == held:
            self._release_delay_start = None
            # Emit MOVING_FIRE each frame while holding and moving
            self._maybe_emit_moving_fire(held, motion_state, signals)
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
        # Different gesture during cooldown -> start ACTIVATING
        if gesture is not None and gesture != self._cooldown_gesture:
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

    def _maybe_emit_moving_fire(
        self,
        gesture: Gesture,
        motion_state: Optional[MotionState],
        signals: list[OrchestratorSignal],
    ) -> None:
        """Append MOVING_FIRE signal if motion_state indicates movement with direction."""
        if (
            motion_state is not None
            and motion_state.moving
            and motion_state.direction is not None
        ):
            signals.append(
                OrchestratorSignal(
                    OrchestratorAction.MOVING_FIRE,
                    gesture,
                    direction=motion_state.direction,
                )
            )

    def _build_result(
        self, signals: list[OrchestratorSignal]
    ) -> OrchestratorResult:
        """Build the OrchestratorResult from current internal state."""
        # Determine base gesture
        base_gesture: Optional[Gesture] = None
        if self._outer_state == LifecycleState.ACTIVATING:
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

        return OrchestratorResult(
            base_gesture=base_gesture,
            temporal_state=temporal_state,
            outer_state=self._outer_state,
            signals=signals,
        )
