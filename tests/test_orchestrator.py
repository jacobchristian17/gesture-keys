"""Tests for the gesture orchestrator hierarchical FSM.

Ported from test_debounce.py with adaptations for hierarchical state model:
- DebounceState.FIRED -> LifecycleState.ACTIVE with TemporalState.CONFIRMED (or COOLDOWN after 1-frame)
- DebounceState.HOLDING -> LifecycleState.ACTIVE with TemporalState.HOLD
- DebounceSignal -> OrchestratorSignal in result.signals list
"""

import pytest

from gesture_keys.classifier import Gesture
from gesture_keys.orchestrator import (
    GestureOrchestrator,
    LifecycleState,
    OrchestratorAction,
    OrchestratorResult,
    OrchestratorSignal,
    TemporalState,
)


# ─── Type Definitions ───


class TestTypeDefinitions:
    """Test that type definitions exist and have correct values."""

    def test_orchestrator_action_values(self):
        assert OrchestratorAction.FIRE.value == "fire"
        assert OrchestratorAction.HOLD_START.value == "hold_start"
        assert OrchestratorAction.HOLD_END.value == "hold_end"

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
