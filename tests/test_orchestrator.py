"""Tests for the gesture orchestrator hierarchical FSM.

Ported from test_debounce.py with adaptations for hierarchical state model:
- DebounceState.FIRED -> LifecycleState.ACTIVE with TemporalState.CONFIRMED (or COOLDOWN after 1-frame)
- DebounceState.HOLDING -> LifecycleState.ACTIVE with TemporalState.HOLD
- DebounceSignal -> OrchestratorSignal in result.signals list
"""

import pytest

from gesture_keys.classifier import Gesture
from gesture_keys.motion import MotionState
from gesture_keys.orchestrator import (
    GestureOrchestrator,
    LifecycleState,
    OrchestratorAction,
    OrchestratorResult,
    OrchestratorSignal,
    TemporalState,
)
from gesture_keys.trigger import Direction


# ─── Type Definitions ───


class TestTypeDefinitions:
    """Test that type definitions exist and have correct values."""

    def test_orchestrator_action_values(self):
        assert OrchestratorAction.FIRE.value == "fire"
        assert OrchestratorAction.HOLD_START.value == "hold_start"
        assert OrchestratorAction.HOLD_END.value == "hold_end"
        assert OrchestratorAction.MOVING_FIRE.value == "moving_fire"

    def test_lifecycle_state_values(self):
        assert LifecycleState.IDLE.value == "IDLE"
        assert LifecycleState.ACTIVATING.value == "ACTIVATING"
        assert LifecycleState.ACTIVE.value == "ACTIVE"
        assert LifecycleState.COOLDOWN.value == "COOLDOWN"

    def test_temporal_state_values(self):
        assert TemporalState.CONFIRMED.value == "CONFIRMED"
        assert TemporalState.HOLD.value == "HOLD"

    def test_orchestrator_signal_creation(self):
        sig = OrchestratorSignal(OrchestratorAction.FIRE, Gesture.FIST)
        assert sig.action == OrchestratorAction.FIRE
        assert sig.gesture == Gesture.FIST
        assert sig.direction is None
        assert sig.second_gesture is None

    def test_orchestrator_signal_with_direction(self):
        sig = OrchestratorSignal(
            OrchestratorAction.MOVING_FIRE, Gesture.FIST, direction=Direction.LEFT
        )
        assert sig.action == OrchestratorAction.MOVING_FIRE
        assert sig.gesture == Gesture.FIST
        assert sig.direction == Direction.LEFT
        assert sig.second_gesture is None

    def test_orchestrator_signal_with_second_gesture(self):
        sig = OrchestratorSignal(
            OrchestratorAction.SEQUENCE_FIRE, Gesture.FIST,
            second_gesture=Gesture.PEACE,
        )
        assert sig.gesture == Gesture.FIST
        assert sig.second_gesture == Gesture.PEACE

    def test_orchestrator_result_defaults(self):
        result = OrchestratorResult()
        assert result.base_gesture is None
        assert result.temporal_state is None
        assert result.outer_state == LifecycleState.IDLE
        assert result.signals == []


# ─── Constructor ───


class TestConstructor:
    """Test GestureOrchestrator constructor."""

    def test_starts_in_idle(self):
        o = GestureOrchestrator()
        result = o.update(None, 0.0)
        assert result.outer_state == LifecycleState.IDLE

    def test_accepts_all_config_params(self):
        o = GestureOrchestrator(
            activation_delay=0.2,
            cooldown_duration=0.5,
            gesture_cooldowns={"fist": 0.6},
            gesture_modes={"fist": "hold_key"},
            hold_release_delay=0.15,
            sequence_definitions={(Gesture.FIST, Gesture.PEACE)},
            sequence_window=1.0,
        )
        # Should not raise
        result = o.update(None, 0.0)
        assert result.outer_state == LifecycleState.IDLE


# ─── Core State Transitions (ported from TestDebounceStateTransitions) ───


class TestOrchestratorStateTransitions:
    """Test basic state machine transitions."""

    def test_idle_to_activating_on_gesture(self):
        o = GestureOrchestrator()
        result = o.update(Gesture.FIST, 0.0)
        assert result.outer_state == LifecycleState.ACTIVATING
        assert result.signals == []

    def test_idle_stays_idle_on_none(self):
        o = GestureOrchestrator()
        result = o.update(None, 0.0)
        assert result.outer_state == LifecycleState.IDLE
        assert result.signals == []

    def test_activating_to_fire_after_delay(self):
        o = GestureOrchestrator(activation_delay=0.4)
        o.update(Gesture.FIST, 0.0)
        result = o.update(Gesture.FIST, 0.5)
        # Should emit FIRE signal
        assert len(result.signals) == 1
        assert result.signals[0] == OrchestratorSignal(
            OrchestratorAction.FIRE, Gesture.FIST
        )

    def test_activating_no_fire_before_delay(self):
        o = GestureOrchestrator(activation_delay=0.4)
        o.update(Gesture.FIST, 0.0)
        result = o.update(Gesture.FIST, 0.3)
        assert result.outer_state == LifecycleState.ACTIVATING
        assert result.signals == []

    def test_activating_resets_on_gesture_switch(self):
        o = GestureOrchestrator(activation_delay=0.4)
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.PEACE, 0.3)
        # Should need fresh 0.4s from the switch
        result = o.update(Gesture.PEACE, 0.6)
        assert result.signals == []
        assert result.outer_state == LifecycleState.ACTIVATING
        # Now it should fire (0.3 + 0.4 = 0.7)
        result = o.update(Gesture.PEACE, 0.8)
        assert len(result.signals) == 1
        assert result.signals[0] == OrchestratorSignal(
            OrchestratorAction.FIRE, Gesture.PEACE
        )

    def test_activating_to_idle_on_none(self):
        o = GestureOrchestrator()
        o.update(Gesture.FIST, 0.0)
        result = o.update(None, 0.1)
        assert result.outer_state == LifecycleState.IDLE
        assert result.signals == []

    def test_tap_mode_active_confirmed_to_cooldown_on_next_update(self):
        """Tap mode: ACTIVE(CONFIRMED) auto-transitions to COOLDOWN on next update."""
        o = GestureOrchestrator(activation_delay=0.4)
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # fires -> ACTIVE(CONFIRMED) or directly COOLDOWN
        result = o.update(Gesture.FIST, 0.6)
        assert result.outer_state == LifecycleState.COOLDOWN

    def test_cooldown_blocks_same_gesture(self):
        o = GestureOrchestrator(activation_delay=0.4, cooldown_duration=0.8)
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # fires
        o.update(Gesture.FIST, 0.6)  # -> cooldown
        result = o.update(Gesture.FIST, 0.7)
        assert result.outer_state == LifecycleState.COOLDOWN
        assert result.signals == []

    def test_cooldown_to_idle_after_elapsed_and_release(self):
        o = GestureOrchestrator(activation_delay=0.4, cooldown_duration=0.8)
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # fires
        o.update(Gesture.FIST, 0.6)  # -> cooldown at t=0.6
        result = o.update(None, 1.5)
        assert result.outer_state == LifecycleState.IDLE

    def test_cooldown_stays_if_gesture_held_after_elapsed(self):
        o = GestureOrchestrator(activation_delay=0.4, cooldown_duration=0.8)
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # fires
        o.update(Gesture.FIST, 0.6)  # -> cooldown at t=0.6
        result = o.update(Gesture.FIST, 1.5)
        assert result.outer_state == LifecycleState.COOLDOWN

    def test_brief_gesture_never_fires(self):
        o = GestureOrchestrator(activation_delay=0.4)
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.2)
        o.update(None, 0.3)  # released early
        result = o.update(Gesture.FIST, 0.5)
        assert result.outer_state == LifecycleState.ACTIVATING

    def test_fires_exactly_once_per_hold(self):
        o = GestureOrchestrator(activation_delay=0.4, cooldown_duration=0.8)
        o.update(Gesture.FIST, 0.0)
        r1 = o.update(Gesture.FIST, 0.5)  # fires
        assert len(r1.signals) == 1
        r2 = o.update(Gesture.FIST, 0.6)
        r3 = o.update(Gesture.FIST, 0.7)
        r4 = o.update(Gesture.FIST, 0.8)
        assert r2.signals == []
        assert r3.signals == []
        assert r4.signals == []


# ─── Direct Transitions (ported from TestDirectTransitions) ───


class TestDirectTransitions:
    """Test COOLDOWN->ACTIVATING transitions for different gestures."""

    def _fire_fist(self, o):
        """Helper: fire FIST and enter cooldown."""
        o.update(Gesture.FIST, 0.0)  # IDLE -> ACTIVATING
        o.update(Gesture.FIST, 0.5)  # ACTIVATING -> ACTIVE(CONFIRMED) + FIRE
        o.update(Gesture.FIST, 0.6)  # ACTIVE -> COOLDOWN (tap mode 1-frame)
        # Verify cooldown
        result = o.update(Gesture.FIST, 0.65)
        assert result.outer_state == LifecycleState.COOLDOWN

    def test_different_gesture_during_cooldown_starts_activating(self):
        o = GestureOrchestrator(activation_delay=0.4, cooldown_duration=0.8)
        self._fire_fist(o)
        result = o.update(Gesture.PEACE, 0.7)
        assert result.outer_state == LifecycleState.ACTIVATING

    def test_different_gesture_during_cooldown_eventually_fires(self):
        o = GestureOrchestrator(activation_delay=0.4, cooldown_duration=0.8)
        self._fire_fist(o)
        o.update(Gesture.PEACE, 0.7)  # COOLDOWN -> ACTIVATING
        result = o.update(Gesture.PEACE, 1.2)
        assert len(result.signals) == 1
        assert result.signals[0] == OrchestratorSignal(
            OrchestratorAction.FIRE, Gesture.PEACE
        )

    def test_same_gesture_during_cooldown_stays_blocked(self):
        o = GestureOrchestrator(activation_delay=0.4, cooldown_duration=0.8)
        self._fire_fist(o)
        result = o.update(Gesture.FIST, 0.7)
        assert result.outer_state == LifecycleState.COOLDOWN

    def test_same_gesture_after_cooldown_elapsed_stays_blocked(self):
        o = GestureOrchestrator(activation_delay=0.4, cooldown_duration=0.8)
        self._fire_fist(o)
        result = o.update(Gesture.FIST, 1.5)
        assert result.outer_state == LifecycleState.COOLDOWN

    def test_rapid_switch_during_cooldown_fires_final_gesture(self):
        o = GestureOrchestrator(activation_delay=0.4, cooldown_duration=0.8)
        self._fire_fist(o)
        o.update(Gesture.PEACE, 0.7)  # COOLDOWN -> ACTIVATING(PEACE)
        o.update(Gesture.POINTING, 0.8)  # ACTIVATING reset to POINTING
        result = o.update(Gesture.POINTING, 1.3)
        assert len(result.signals) == 1
        assert result.signals[0] == OrchestratorSignal(
            OrchestratorAction.FIRE, Gesture.POINTING
        )

    def test_different_gesture_after_cooldown_elapsed_starts_activating(self):
        o = GestureOrchestrator(activation_delay=0.4, cooldown_duration=0.8)
        self._fire_fist(o)
        result = o.update(Gesture.PEACE, 1.5)
        assert result.outer_state == LifecycleState.ACTIVATING


# ─── Hold Mode (ported from TestHoldMode*) ───


class TestHoldMode:
    """Test ACTIVE(HOLD) state for hold-mode gestures."""

    def test_hold_mode_activating_to_active_hold(self):
        o = GestureOrchestrator(
            activation_delay=0.4, gesture_modes={"fist": "hold_key"}
        )
        o.update(Gesture.FIST, 0.0)
        result = o.update(Gesture.FIST, 0.5)
        assert result.outer_state == LifecycleState.ACTIVE
        assert result.temporal_state == TemporalState.HOLD
        assert len(result.signals) == 1
        assert result.signals[0] == OrchestratorSignal(
            OrchestratorAction.HOLD_START, Gesture.FIST
        )

    def test_hold_mode_stays_active_hold_while_gesture_continues(self):
        o = GestureOrchestrator(
            activation_delay=0.4, gesture_modes={"fist": "hold_key"}
        )
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # -> ACTIVE(HOLD)
        result = o.update(Gesture.FIST, 0.6)
        assert result.outer_state == LifecycleState.ACTIVE
        assert result.temporal_state == TemporalState.HOLD
        assert result.signals == []

    def test_hold_release_delay_absorbs_flicker(self):
        o = GestureOrchestrator(
            activation_delay=0.4, hold_release_delay=0.1,
            gesture_modes={"fist": "hold_key"},
        )
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # -> ACTIVE(HOLD)
        result = o.update(None, 0.55)  # gesture lost, release delay starts
        assert result.outer_state == LifecycleState.ACTIVE
        assert result.temporal_state == TemporalState.HOLD
        assert result.signals == []
        # Gesture returns within 0.1s
        result = o.update(Gesture.FIST, 0.6)
        assert result.outer_state == LifecycleState.ACTIVE
        assert result.temporal_state == TemporalState.HOLD

    def test_hold_release_after_delay_expires(self):
        o = GestureOrchestrator(
            activation_delay=0.4, hold_release_delay=0.1,
            gesture_modes={"fist": "hold_key"},
        )
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # -> ACTIVE(HOLD)
        o.update(None, 0.55)  # gesture lost
        result = o.update(None, 0.7)  # release delay expired
        assert result.outer_state == LifecycleState.COOLDOWN
        assert len(result.signals) == 1
        assert result.signals[0] == OrchestratorSignal(
            OrchestratorAction.HOLD_END, Gesture.FIST
        )

    def test_hold_end_emitted_exactly_once(self):
        o = GestureOrchestrator(
            activation_delay=0.4, cooldown_duration=0.3,
            hold_release_delay=0.1, gesture_modes={"fist": "hold_key"},
        )
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # -> ACTIVE(HOLD)
        o.update(None, 0.55)  # gesture lost
        o.update(None, 0.7)  # hold_end emitted
        result = o.update(None, 0.8)  # should be in COOLDOWN, no signal
        assert result.signals == []

    def test_tap_mode_unchanged_when_hold_modes_exist(self):
        o = GestureOrchestrator(
            activation_delay=0.4,
            gesture_modes={"fist": "hold_key", "peace": "tap"},
        )
        o.update(Gesture.PEACE, 0.0)
        result = o.update(Gesture.PEACE, 0.5)
        assert len(result.signals) == 1
        assert result.signals[0] == OrchestratorSignal(
            OrchestratorAction.FIRE, Gesture.PEACE
        )

    def test_multiple_rapid_drops_within_delay(self):
        o = GestureOrchestrator(
            activation_delay=0.4, hold_release_delay=0.1,
            gesture_modes={"fist": "hold_key"},
        )
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # -> ACTIVE(HOLD)
        # Rapid flicker
        assert o.update(None, 0.55).signals == []  # drop 1
        assert o.update(Gesture.FIST, 0.57).signals == []  # return 1
        assert o.update(None, 0.59).signals == []  # drop 2
        result = o.update(Gesture.FIST, 0.61)  # return 2
        assert result.outer_state == LifecycleState.ACTIVE
        assert result.temporal_state == TemporalState.HOLD


class TestHoldModeGestureChange:
    """Test gesture changes during ACTIVE(HOLD) state."""

    def test_different_gesture_during_hold_emits_hold_end(self):
        o = GestureOrchestrator(
            activation_delay=0.4, gesture_modes={"fist": "hold_key"}
        )
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # -> ACTIVE(HOLD)
        result = o.update(Gesture.PEACE, 0.6)
        assert len(result.signals) == 1
        assert result.signals[0] == OrchestratorSignal(
            OrchestratorAction.HOLD_END, Gesture.FIST
        )
        assert result.outer_state == LifecycleState.ACTIVATING

    def test_different_gesture_during_hold_starts_activating_new(self):
        o = GestureOrchestrator(
            activation_delay=0.4, gesture_modes={"fist": "hold_key"}
        )
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # -> ACTIVE(HOLD)
        o.update(Gesture.PEACE, 0.6)  # -> HOLD_END + ACTIVATING(PEACE)
        result = o.update(Gesture.PEACE, 1.1)
        assert len(result.signals) == 1
        assert result.signals[0] == OrchestratorSignal(
            OrchestratorAction.FIRE, Gesture.PEACE
        )

    def test_different_gesture_during_release_delay(self):
        o = GestureOrchestrator(
            activation_delay=0.4, hold_release_delay=0.1,
            gesture_modes={"fist": "hold_key"},
        )
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # -> ACTIVE(HOLD)
        o.update(None, 0.55)  # gesture lost, release delay starts
        result = o.update(Gesture.PEACE, 0.58)  # different gesture within delay
        assert len(result.signals) == 1
        assert result.signals[0] == OrchestratorSignal(
            OrchestratorAction.HOLD_END, Gesture.FIST
        )
        assert result.outer_state == LifecycleState.ACTIVATING


class TestHoldModeCooldownCycle:
    """Test full hold cycle including cooldown."""

    def test_full_hold_cycle(self):
        o = GestureOrchestrator(
            activation_delay=0.4, cooldown_duration=0.3,
            hold_release_delay=0.1, gesture_modes={"fist": "hold_key"},
        )
        # IDLE -> ACTIVATING
        o.update(Gesture.FIST, 0.0)

        # ACTIVATING -> ACTIVE(HOLD) + HOLD_START
        result = o.update(Gesture.FIST, 0.5)
        assert result.outer_state == LifecycleState.ACTIVE
        assert result.temporal_state == TemporalState.HOLD
        assert result.signals[0].action == OrchestratorAction.HOLD_START

        # Stay ACTIVE(HOLD)
        result = o.update(Gesture.FIST, 0.6)
        assert result.signals == []

        # Gesture lost
        o.update(None, 0.7)

        # Release delay expires -> COOLDOWN + HOLD_END
        result = o.update(None, 0.85)
        assert result.signals[0] == OrchestratorSignal(
            OrchestratorAction.HOLD_END, Gesture.FIST
        )
        assert result.outer_state == LifecycleState.COOLDOWN

        # Cooldown expires + release -> IDLE
        result = o.update(None, 1.2)
        assert result.outer_state == LifecycleState.IDLE


# ─── Properties ───


class TestProperties:
    """Test is_activating and activating_gesture properties."""

    def test_is_activating_false_in_idle(self):
        o = GestureOrchestrator()
        assert o.is_activating is False

    def test_is_activating_true_in_activating(self):
        o = GestureOrchestrator()
        o.update(Gesture.FIST, 0.0)
        assert o.is_activating is True

    def test_is_activating_false_in_cooldown(self):
        o = GestureOrchestrator(activation_delay=0.4)
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # fires
        o.update(Gesture.FIST, 0.6)  # -> cooldown
        assert o.is_activating is False

    def test_is_activating_false_in_active_hold(self):
        o = GestureOrchestrator(
            activation_delay=0.4, gesture_modes={"fist": "hold_key"}
        )
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # -> ACTIVE(HOLD)
        assert o.is_activating is False

    def test_activating_gesture_during_activating(self):
        o = GestureOrchestrator()
        o.update(Gesture.FIST, 0.0)
        assert o.activating_gesture == Gesture.FIST

    def test_activating_gesture_none_in_idle(self):
        o = GestureOrchestrator()
        assert o.activating_gesture is None


# ─── Per-Gesture Cooldowns ───


class TestPerGestureCooldowns:
    """Test per-gesture cooldown override behavior."""

    def test_per_gesture_cooldown_used(self):
        o = GestureOrchestrator(
            activation_delay=0.1, cooldown_duration=0.3,
            gesture_cooldowns={"fist": 0.5},
        )
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.2)  # fires
        o.update(Gesture.FIST, 0.3)  # -> cooldown at t=0.3
        # At t=0.7 (0.4s elapsed), still in cooldown (0.5s per-gesture)
        result = o.update(None, 0.7)
        assert result.outer_state == LifecycleState.COOLDOWN
        # At t=0.9 (0.6s elapsed > 0.5s), should transition to IDLE
        result = o.update(None, 0.9)
        assert result.outer_state == LifecycleState.IDLE

    def test_no_gesture_cooldowns_uses_global(self):
        o = GestureOrchestrator(activation_delay=0.1, cooldown_duration=0.3)
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.2)  # fires
        o.update(Gesture.FIST, 0.3)  # -> cooldown at t=0.3
        result = o.update(None, 0.7)
        assert result.outer_state == LifecycleState.IDLE

    def test_gesture_not_in_cooldowns_uses_global(self):
        o = GestureOrchestrator(
            activation_delay=0.1, cooldown_duration=0.3,
            gesture_cooldowns={"pinch": 0.6},
        )
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.2)  # fires
        o.update(Gesture.FIST, 0.3)  # -> cooldown at t=0.3
        result = o.update(None, 0.7)
        assert result.outer_state == LifecycleState.IDLE

    def test_per_gesture_cooldown_timing_boundary(self):
        o = GestureOrchestrator(
            activation_delay=0.1, cooldown_duration=0.3,
            gesture_cooldowns={"pinch": 0.6},
        )
        o.update(Gesture.PINCH, 0.0)
        o.update(Gesture.PINCH, 0.2)  # fires + cooldown starts at t=0.2
        # 0.5s elapsed (t=0.7), still in cooldown (0.6s per-gesture)
        result = o.update(None, 0.7)
        assert result.outer_state == LifecycleState.COOLDOWN
        # 0.7s elapsed (t=0.9), cooldown over
        result = o.update(None, 0.9)
        assert result.outer_state == LifecycleState.IDLE


# ─── Reset ───


class TestReset:
    """Test reset() method."""

    def test_reset_returns_to_idle(self):
        o = GestureOrchestrator()
        o.update(Gesture.FIST, 0.0)
        o.reset()
        result = o.update(None, 0.1)
        assert result.outer_state == LifecycleState.IDLE

    def test_reset_clears_activating_gesture(self):
        o = GestureOrchestrator()
        o.update(Gesture.FIST, 0.0)
        o.reset()
        assert o.activating_gesture is None

    def test_reset_clears_hold_state(self):
        o = GestureOrchestrator(
            activation_delay=0.4, gesture_modes={"fist": "hold_key"}
        )
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # -> ACTIVE(HOLD)
        o.reset()
        result = o.update(None, 0.6)
        assert result.outer_state == LifecycleState.IDLE
        assert result.temporal_state is None


# ─── flush_pending() ───


class TestFlushPending:
    """Test flush_pending() method -- now always returns empty result."""

    def test_flush_pending_no_op_in_idle(self):
        o = GestureOrchestrator()
        result = o.flush_pending()
        assert result.signals == []

    def test_flush_pending_no_op_in_activating(self):
        o = GestureOrchestrator()
        o.update(Gesture.FIST, 0.0)
        result = o.flush_pending()
        assert result.signals == []


# ─── Temporal State Invariants ───


class TestTemporalStateInvariants:
    """Test that temporal_state is None when not in ACTIVE."""

    def test_temporal_state_none_in_idle(self):
        o = GestureOrchestrator()
        result = o.update(None, 0.0)
        assert result.temporal_state is None

    def test_temporal_state_none_in_activating(self):
        o = GestureOrchestrator()
        result = o.update(Gesture.FIST, 0.0)
        assert result.temporal_state is None

    def test_temporal_state_none_in_cooldown(self):
        o = GestureOrchestrator(activation_delay=0.4)
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # fires
        result = o.update(Gesture.FIST, 0.6)  # -> cooldown
        assert result.temporal_state is None

    def test_temporal_state_hold_in_active(self):
        o = GestureOrchestrator(
            activation_delay=0.4, gesture_modes={"fist": "hold_key"}
        )
        o.update(Gesture.FIST, 0.0)
        result = o.update(Gesture.FIST, 0.5)
        assert result.outer_state == LifecycleState.ACTIVE
        assert result.temporal_state == TemporalState.HOLD


# ─── Base Gesture Tracking ───


class TestBaseGesture:
    """Test base_gesture field in OrchestratorResult."""

    def test_base_gesture_none_in_idle(self):
        o = GestureOrchestrator()
        result = o.update(None, 0.0)
        assert result.base_gesture is None

    def test_base_gesture_set_during_activating(self):
        o = GestureOrchestrator()
        result = o.update(Gesture.FIST, 0.0)
        assert result.base_gesture == Gesture.FIST

    def test_base_gesture_set_during_active_hold(self):
        o = GestureOrchestrator(
            activation_delay=0.4, gesture_modes={"fist": "hold_key"}
        )
        o.update(Gesture.FIST, 0.0)
        result = o.update(Gesture.FIST, 0.5)
        assert result.base_gesture == Gesture.FIST


# ─── Edge Cases (dedicated tests from CONTEXT.md) ───


class TestEdgeCases:
    """Edge cases with dedicated tests."""

    def test_edge_1_direct_gesture_transitions(self):
        """COOLDOWN + different gesture -> ACTIVATING."""
        o = GestureOrchestrator(activation_delay=0.4, cooldown_duration=0.8)
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # fires
        o.update(Gesture.FIST, 0.6)  # -> cooldown
        result = o.update(Gesture.PEACE, 0.7)
        assert result.outer_state == LifecycleState.ACTIVATING

    def test_edge_2_static_first_priority_gate(self):
        """is_activating property returns True during ACTIVATING."""
        o = GestureOrchestrator()
        o.update(Gesture.FIST, 0.0)
        assert o.is_activating is True

    def test_edge_6_per_gesture_cooldown_durations(self):
        """Per-gesture cooldown from gesture_cooldowns dict."""
        o = GestureOrchestrator(
            activation_delay=0.1, cooldown_duration=0.3,
            gesture_cooldowns={"fist": 0.5},
        )
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.2)  # fires
        o.update(Gesture.FIST, 0.3)  # -> cooldown at t=0.3
        # 0.4s elapsed, still in cooldown (0.5s per-gesture)
        result = o.update(None, 0.7)
        assert result.outer_state == LifecycleState.COOLDOWN
        # 0.6s elapsed, should be IDLE
        result = o.update(None, 0.9)
        assert result.outer_state == LifecycleState.IDLE

    def test_edge_7_hold_release_delay_grace_period(self):
        """Hold release delay grace period (flicker absorption)."""
        o = GestureOrchestrator(
            activation_delay=0.4, hold_release_delay=0.1,
            gesture_modes={"fist": "hold_key"},
        )
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # -> ACTIVE(HOLD)
        o.update(None, 0.55)  # gesture lost
        result = o.update(Gesture.FIST, 0.6)  # returns within delay
        assert result.outer_state == LifecycleState.ACTIVE
        assert result.temporal_state == TemporalState.HOLD

    def test_edge_9_same_gesture_cooldown_blocking(self):
        """COOLDOWN + same gesture -> stays COOLDOWN."""
        o = GestureOrchestrator(activation_delay=0.4, cooldown_duration=0.8)
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # fires
        o.update(Gesture.FIST, 0.6)  # -> cooldown
        result = o.update(Gesture.FIST, 0.7)
        assert result.outer_state == LifecycleState.COOLDOWN

    def test_edge_10_reset_clears_all_state(self):
        """reset() method clears all state (used for hand switch)."""
        o = GestureOrchestrator(
            activation_delay=0.4, gesture_modes={"fist": "hold_key"}
        )
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # -> ACTIVE(HOLD)
        o.reset()
        assert o.activating_gesture is None
        assert o.is_activating is False


# ─── MOVING_FIRE ───


class TestMovingFire:
    """Test MOVING_FIRE signal emission with motion_state parameter."""

    def test_moving_fire_on_tap_fire(self):
        """MOVING_FIRE emitted alongside FIRE on tap when moving."""
        o = GestureOrchestrator(activation_delay=0.4)
        o.update(Gesture.FIST, 0.0)
        result = o.update(
            Gesture.FIST, 0.5,
            motion_state=MotionState(moving=True, direction=Direction.LEFT),
        )
        actions = [s.action for s in result.signals]
        assert OrchestratorAction.FIRE in actions
        assert OrchestratorAction.MOVING_FIRE in actions
        moving_sig = [
            s for s in result.signals
            if s.action == OrchestratorAction.MOVING_FIRE
        ][0]
        assert moving_sig.gesture == Gesture.FIST
        assert moving_sig.direction == Direction.LEFT

    def test_moving_fire_during_hold(self):
        """MOVING_FIRE emitted each frame during ACTIVE(HOLD) when moving."""
        o = GestureOrchestrator(
            activation_delay=0.4, gesture_modes={"fist": "hold_key"}
        )
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # -> ACTIVE(HOLD) + HOLD_START
        result = o.update(
            Gesture.FIST, 0.6,
            motion_state=MotionState(moving=True, direction=Direction.RIGHT),
        )
        actions = [s.action for s in result.signals]
        assert OrchestratorAction.MOVING_FIRE in actions
        moving_sig = [
            s for s in result.signals
            if s.action == OrchestratorAction.MOVING_FIRE
        ][0]
        assert moving_sig.gesture == Gesture.FIST
        assert moving_sig.direction == Direction.RIGHT

    def test_no_moving_fire_during_activating(self):
        """No MOVING_FIRE during ACTIVATING (gesture not yet confirmed)."""
        o = GestureOrchestrator(activation_delay=0.4)
        o.update(Gesture.FIST, 0.0)
        result = o.update(
            Gesture.FIST, 0.3,
            motion_state=MotionState(moving=True, direction=Direction.LEFT),
        )
        assert result.outer_state == LifecycleState.ACTIVATING
        actions = [s.action for s in result.signals]
        assert OrchestratorAction.MOVING_FIRE not in actions

    def test_no_moving_fire_during_cooldown(self):
        """No MOVING_FIRE during COOLDOWN."""
        o = GestureOrchestrator(activation_delay=0.4, cooldown_duration=0.8)
        o.update(Gesture.FIST, 0.0)
        o.update(Gesture.FIST, 0.5)  # fires -> cooldown
        o.update(Gesture.FIST, 0.6)  # in cooldown
        result = o.update(
            Gesture.FIST, 0.7,
            motion_state=MotionState(moving=True, direction=Direction.LEFT),
        )
        assert result.outer_state == LifecycleState.COOLDOWN
        actions = [s.action for s in result.signals]
        assert OrchestratorAction.MOVING_FIRE not in actions

    def test_no_moving_fire_when_motion_state_none(self):
        """No MOVING_FIRE when motion_state is None."""
        o = GestureOrchestrator(activation_delay=0.4)
        o.update(Gesture.FIST, 0.0)
        result = o.update(Gesture.FIST, 0.5, motion_state=None)
        actions = [s.action for s in result.signals]
        assert OrchestratorAction.FIRE in actions
        assert OrchestratorAction.MOVING_FIRE not in actions

    def test_no_moving_fire_when_not_moving(self):
        """No MOVING_FIRE when motion_state.moving is False."""
        o = GestureOrchestrator(activation_delay=0.4)
        o.update(Gesture.FIST, 0.0)
        result = o.update(
            Gesture.FIST, 0.5,
            motion_state=MotionState(moving=False),
        )
        actions = [s.action for s in result.signals]
        assert OrchestratorAction.FIRE in actions
        assert OrchestratorAction.MOVING_FIRE not in actions

    def test_moving_fire_has_correct_direction(self):
        """MOVING_FIRE signal.direction matches motion_state.direction."""
        o = GestureOrchestrator(activation_delay=0.4)
        o.update(Gesture.FIST, 0.0)
        result = o.update(
            Gesture.FIST, 0.5,
            motion_state=MotionState(moving=True, direction=Direction.UP),
        )
        moving_sig = [
            s for s in result.signals
            if s.action == OrchestratorAction.MOVING_FIRE
        ][0]
        assert moving_sig.direction == Direction.UP

    def test_motion_state_none_no_crash(self):
        """update() with motion_state=None in every state does not crash."""
        o = GestureOrchestrator(
            activation_delay=0.4, cooldown_duration=0.3,
            gesture_modes={"peace": "hold_key"},
        )
        # IDLE
        o.update(None, 0.0, motion_state=None)
        # ACTIVATING
        o.update(Gesture.FIST, 0.1, motion_state=None)
        o.update(Gesture.FIST, 0.3, motion_state=None)
        # ACTIVE(CONFIRMED) -> COOLDOWN (tap fires)
        o.update(Gesture.FIST, 0.6, motion_state=None)
        # COOLDOWN
        o.update(Gesture.FIST, 0.7, motion_state=None)
        # Back to idle
        o.update(None, 1.5, motion_state=None)
        # Hold mode
        o.update(Gesture.PEACE, 2.0, motion_state=None)
        o.update(Gesture.PEACE, 2.5, motion_state=None)  # ACTIVE(HOLD)
        o.update(Gesture.PEACE, 2.6, motion_state=None)  # still holding
        # No crash = pass

    def test_no_moving_fire_when_direction_none(self):
        """No MOVING_FIRE when motion_state.moving is True but direction is None."""
        o = GestureOrchestrator(activation_delay=0.4)
        o.update(Gesture.FIST, 0.0)
        result = o.update(
            Gesture.FIST, 0.5,
            motion_state=MotionState(moving=True, direction=None),
        )
        actions = [s.action for s in result.signals]
        assert OrchestratorAction.FIRE in actions
        assert OrchestratorAction.MOVING_FIRE not in actions


# ─── SEQUENCE_FIRE ───


class TestSequenceFire:
    """Test SEQUENCE_FIRE signal emission with sequence tracking."""

    def _fire_gesture(self, o, gesture, t_start):
        """Helper: fire a gesture via tap (IDLE -> ACTIVATING -> FIRE -> COOLDOWN).

        Returns the result from the firing frame.
        """
        o.update(gesture, t_start)  # IDLE -> ACTIVATING
        return o.update(gesture, t_start + 0.5)  # fires (activation_delay=0.4)

    def _release_cooldown(self, o, t):
        """Helper: release hand to exit cooldown -> IDLE."""
        o.update(None, t)

    def test_sequence_fire_on_matching_pair(self):
        """SEQUENCE_FIRE emitted when second gesture fires within window."""
        o = GestureOrchestrator(
            activation_delay=0.4,
            sequence_definitions={(Gesture.FIST, Gesture.PEACE)},
        )
        # Fire FIST
        self._fire_gesture(o, Gesture.FIST, 1.0)  # fires at t=1.5
        self._release_cooldown(o, 2.5)  # back to IDLE

        # Fire PEACE within 0.5s of FIST fire (t=1.5)
        o.update(Gesture.PEACE, 1.5)  # IDLE -> ACTIVATING
        result = o.update(Gesture.PEACE, 2.0)  # fires at t=2.0 (delta from FIST fire: 2.0 - 1.5 = 0.5 <= 0.5)
        actions = [s.action for s in result.signals]
        assert OrchestratorAction.SEQUENCE_FIRE in actions
        seq_sig = [
            s for s in result.signals
            if s.action == OrchestratorAction.SEQUENCE_FIRE
        ][0]
        assert seq_sig.gesture == Gesture.FIST
        assert seq_sig.second_gesture == Gesture.PEACE

    def test_no_sequence_fire_for_unregistered_pair(self):
        """No SEQUENCE_FIRE for pairs not in sequence_definitions."""
        o = GestureOrchestrator(
            activation_delay=0.4,
            sequence_definitions={(Gesture.FIST, Gesture.PEACE)},
        )
        # Fire FIST
        self._fire_gesture(o, Gesture.FIST, 1.0)
        self._release_cooldown(o, 2.5)

        # Fire OPEN_PALM (not registered pair)
        o.update(Gesture.OPEN_PALM, 1.5)
        result = o.update(Gesture.OPEN_PALM, 2.0)
        actions = [s.action for s in result.signals]
        assert OrchestratorAction.SEQUENCE_FIRE not in actions

    def test_no_sequence_fire_for_reversed_pair(self):
        """No SEQUENCE_FIRE for (B, A) when only (A, B) is registered."""
        o = GestureOrchestrator(
            activation_delay=0.4,
            sequence_definitions={(Gesture.FIST, Gesture.PEACE)},
        )
        # Fire PEACE first (reversed order)
        self._fire_gesture(o, Gesture.PEACE, 1.0)
        self._release_cooldown(o, 2.5)

        # Fire FIST
        o.update(Gesture.FIST, 1.5)
        result = o.update(Gesture.FIST, 2.0)
        actions = [s.action for s in result.signals]
        assert OrchestratorAction.SEQUENCE_FIRE not in actions

    def test_no_sequence_fire_outside_window(self):
        """No SEQUENCE_FIRE when time between fires exceeds sequence_window."""
        o = GestureOrchestrator(
            activation_delay=0.4,
            sequence_definitions={(Gesture.FIST, Gesture.PEACE)},
            sequence_window=0.5,
        )
        # Fire FIST at t=1.5
        self._fire_gesture(o, Gesture.FIST, 1.0)
        self._release_cooldown(o, 2.5)

        # Fire PEACE at t=2.6 (1.1s after FIST fired, outside 0.5s window)
        o.update(Gesture.PEACE, 2.6)
        result = o.update(Gesture.PEACE, 3.0)
        actions = [s.action for s in result.signals]
        assert OrchestratorAction.SEQUENCE_FIRE not in actions

    def test_sequence_fire_at_window_boundary(self):
        """SEQUENCE_FIRE emitted at exactly the window boundary (<=)."""
        o = GestureOrchestrator(
            activation_delay=0.4,
            sequence_definitions={(Gesture.FIST, Gesture.PEACE)},
            sequence_window=0.5,
        )
        # Fire FIST at t=1.5 (start=1.0, delay=0.4, fires at 1.5)
        self._fire_gesture(o, Gesture.FIST, 1.0)
        self._release_cooldown(o, 2.5)

        # Fire PEACE at exactly t=2.0 (delta = 2.0 - 1.5 = 0.5, exactly at boundary)
        o.update(Gesture.PEACE, 1.5)
        result = o.update(Gesture.PEACE, 2.0)
        actions = [s.action for s in result.signals]
        assert OrchestratorAction.SEQUENCE_FIRE in actions

    def test_sequence_window_configurable(self):
        """Custom sequence_window=1.0 allows longer gaps."""
        o = GestureOrchestrator(
            activation_delay=0.4,
            sequence_definitions={(Gesture.FIST, Gesture.PEACE)},
            sequence_window=1.0,
        )
        # Fire FIST at t=1.5
        self._fire_gesture(o, Gesture.FIST, 1.0)
        self._release_cooldown(o, 2.5)

        # Fire PEACE at t=2.5 (1.0s after FIST, within 1.0s window)
        o.update(Gesture.PEACE, 2.0)
        result = o.update(Gesture.PEACE, 2.5)
        actions = [s.action for s in result.signals]
        assert OrchestratorAction.SEQUENCE_FIRE in actions

    def test_sequence_window_default_half_second(self):
        """Default sequence_window is 0.5s (no explicit param)."""
        o = GestureOrchestrator(
            activation_delay=0.4,
            sequence_definitions={(Gesture.FIST, Gesture.PEACE)},
        )
        # Fire FIST at t=1.5
        self._fire_gesture(o, Gesture.FIST, 1.0)
        self._release_cooldown(o, 2.5)

        # Fire PEACE at t=2.0 (0.5s after FIST, within default 0.5s)
        o.update(Gesture.PEACE, 1.5)
        result = o.update(Gesture.PEACE, 2.0)
        actions = [s.action for s in result.signals]
        assert OrchestratorAction.SEQUENCE_FIRE in actions

    def test_sequence_fire_includes_both_gestures(self):
        """SEQUENCE_FIRE signal has gesture=first, second_gesture=second."""
        o = GestureOrchestrator(
            activation_delay=0.4,
            sequence_definitions={(Gesture.FIST, Gesture.PEACE)},
        )
        self._fire_gesture(o, Gesture.FIST, 1.0)
        self._release_cooldown(o, 2.5)
        o.update(Gesture.PEACE, 1.5)
        result = o.update(Gesture.PEACE, 2.0)
        seq_sig = [
            s for s in result.signals
            if s.action == OrchestratorAction.SEQUENCE_FIRE
        ][0]
        assert seq_sig.gesture == Gesture.FIST
        assert seq_sig.second_gesture == Gesture.PEACE

    def test_standalone_fire_also_emitted(self):
        """Both standalone FIRE for B and SEQUENCE_FIRE are emitted."""
        o = GestureOrchestrator(
            activation_delay=0.4,
            sequence_definitions={(Gesture.FIST, Gesture.PEACE)},
        )
        self._fire_gesture(o, Gesture.FIST, 1.0)
        self._release_cooldown(o, 2.5)
        o.update(Gesture.PEACE, 1.5)
        result = o.update(Gesture.PEACE, 2.0)
        actions = [s.action for s in result.signals]
        assert OrchestratorAction.FIRE in actions
        assert OrchestratorAction.SEQUENCE_FIRE in actions
        # Verify FIRE is for PEACE
        fire_sig = [
            s for s in result.signals
            if s.action == OrchestratorAction.FIRE
        ][0]
        assert fire_sig.gesture == Gesture.PEACE

    def test_no_sequence_tracking_with_empty_definitions(self):
        """No SEQUENCE_FIRE when sequence_definitions is not provided."""
        o = GestureOrchestrator(activation_delay=0.4)
        self._fire_gesture(o, Gesture.FIST, 1.0)
        self._release_cooldown(o, 2.5)
        o.update(Gesture.PEACE, 1.5)
        result = o.update(Gesture.PEACE, 2.0)
        actions = [s.action for s in result.signals]
        assert OrchestratorAction.FIRE in actions
        assert OrchestratorAction.SEQUENCE_FIRE not in actions
