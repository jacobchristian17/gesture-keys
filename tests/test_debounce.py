"""Tests for the debounce state machine."""

import logging

import pytest

from gesture_keys.classifier import Gesture
from gesture_keys.debounce import DebounceAction, DebounceSignal, DebounceState, GestureDebouncer


class TestDebounceStateTransitions:
    """Test basic state machine transitions."""

    def test_starts_in_idle(self):
        d = GestureDebouncer()
        assert d.state == DebounceState.IDLE

    def test_idle_to_activating_on_gesture(self):
        d = GestureDebouncer()
        result = d.update(Gesture.FIST, 0.0)
        assert result is None
        assert d.state == DebounceState.ACTIVATING

    def test_idle_stays_idle_on_none(self):
        d = GestureDebouncer()
        result = d.update(None, 0.0)
        assert result is None
        assert d.state == DebounceState.IDLE

    def test_activating_to_fired_after_delay(self):
        d = GestureDebouncer(activation_delay=0.4)
        d.update(Gesture.FIST, 0.0)
        result = d.update(Gesture.FIST, 0.5)
        assert result == DebounceSignal(DebounceAction.FIRE, Gesture.FIST)
        assert d.state == DebounceState.FIRED

    def test_activating_no_fire_before_delay(self):
        d = GestureDebouncer(activation_delay=0.4)
        d.update(Gesture.FIST, 0.0)
        result = d.update(Gesture.FIST, 0.3)
        assert result is None
        assert d.state == DebounceState.ACTIVATING

    def test_activating_resets_on_gesture_switch(self):
        d = GestureDebouncer(activation_delay=0.4)
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.PEACE, 0.3)
        # Should need a fresh 0.4s from the switch
        result = d.update(Gesture.PEACE, 0.6)
        assert result is None
        assert d.state == DebounceState.ACTIVATING
        # Now it should fire (0.3 + 0.4 = 0.7)
        result = d.update(Gesture.PEACE, 0.8)
        assert result == DebounceSignal(DebounceAction.FIRE, Gesture.PEACE)

    def test_activating_to_idle_on_none(self):
        d = GestureDebouncer()
        d.update(Gesture.FIST, 0.0)
        result = d.update(None, 0.1)
        assert result is None
        assert d.state == DebounceState.IDLE

    def test_fired_to_cooldown_on_next_update(self):
        d = GestureDebouncer(activation_delay=0.4)
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # fires
        assert d.state == DebounceState.FIRED
        d.update(Gesture.FIST, 0.6)
        assert d.state == DebounceState.COOLDOWN

    def test_cooldown_blocks_same_gesture(self):
        d = GestureDebouncer(activation_delay=0.4, cooldown_duration=0.8)
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # fires
        d.update(Gesture.FIST, 0.6)  # -> cooldown
        # During cooldown, same gesture stays blocked
        result = d.update(Gesture.FIST, 0.7)
        assert result is None
        assert d.state == DebounceState.COOLDOWN

    def test_cooldown_to_idle_after_elapsed_and_release(self):
        d = GestureDebouncer(activation_delay=0.4, cooldown_duration=0.8)
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # fires
        d.update(Gesture.FIST, 0.6)  # -> cooldown at t=0.6
        # Cooldown elapsed (0.6 + 0.8 = 1.4), gesture released
        result = d.update(None, 1.5)
        assert result is None
        assert d.state == DebounceState.IDLE

    def test_cooldown_stays_if_gesture_held_after_elapsed(self):
        d = GestureDebouncer(activation_delay=0.4, cooldown_duration=0.8)
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # fires
        d.update(Gesture.FIST, 0.6)  # -> cooldown at t=0.6
        # Cooldown elapsed but gesture still held -> stays in cooldown
        result = d.update(Gesture.FIST, 1.5)
        assert result is None
        assert d.state == DebounceState.COOLDOWN

    def test_brief_gesture_never_fires(self):
        d = GestureDebouncer(activation_delay=0.4)
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.2)
        d.update(None, 0.3)  # released early
        assert d.state == DebounceState.IDLE
        # Never fired
        d.update(Gesture.FIST, 0.5)
        assert d.state == DebounceState.ACTIVATING

    def test_fires_exactly_once_per_hold(self):
        d = GestureDebouncer(activation_delay=0.4, cooldown_duration=0.8)
        d.update(Gesture.FIST, 0.0)
        fire1 = d.update(Gesture.FIST, 0.5)  # fires
        assert fire1 == DebounceSignal(DebounceAction.FIRE, Gesture.FIST)
        # All subsequent updates should return None (cooldown)
        fire2 = d.update(Gesture.FIST, 0.6)
        fire3 = d.update(Gesture.FIST, 0.7)
        fire4 = d.update(Gesture.FIST, 0.8)
        assert fire2 is None
        assert fire3 is None
        assert fire4 is None


class TestDirectTransitions:
    """Test COOLDOWN->ACTIVATING transitions for different gestures."""

    def _fire_fist(self, d):
        """Helper: fire FIST and enter cooldown. Returns at cooldown state."""
        d.update(Gesture.FIST, 0.0)       # IDLE -> ACTIVATING
        d.update(Gesture.FIST, 0.5)       # ACTIVATING -> FIRED
        d.update(Gesture.FIST, 0.6)       # FIRED -> COOLDOWN
        assert d.state == DebounceState.COOLDOWN

    def test_different_gesture_during_cooldown_starts_activating(self):
        d = GestureDebouncer(activation_delay=0.4, cooldown_duration=0.8)
        self._fire_fist(d)
        result = d.update(Gesture.PEACE, 0.7)
        assert result is None
        assert d.state == DebounceState.ACTIVATING

    def test_different_gesture_during_cooldown_eventually_fires(self):
        d = GestureDebouncer(activation_delay=0.4, cooldown_duration=0.8)
        self._fire_fist(d)
        d.update(Gesture.PEACE, 0.7)  # COOLDOWN -> ACTIVATING
        assert d.state == DebounceState.ACTIVATING
        # Hold PEACE for activation_delay (0.7 + 0.4 = 1.1)
        result = d.update(Gesture.PEACE, 1.2)
        assert result == DebounceSignal(DebounceAction.FIRE, Gesture.PEACE)

    def test_same_gesture_during_cooldown_stays_blocked(self):
        d = GestureDebouncer(activation_delay=0.4, cooldown_duration=0.8)
        self._fire_fist(d)
        result = d.update(Gesture.FIST, 0.7)
        assert result is None
        assert d.state == DebounceState.COOLDOWN

    def test_same_gesture_after_cooldown_elapsed_stays_blocked(self):
        d = GestureDebouncer(activation_delay=0.4, cooldown_duration=0.8)
        self._fire_fist(d)
        # Cooldown elapses (0.6 + 0.8 = 1.4), FIST still held
        result = d.update(Gesture.FIST, 1.5)
        assert result is None
        assert d.state == DebounceState.COOLDOWN

    def test_rapid_switch_during_cooldown_fires_final_gesture(self):
        d = GestureDebouncer(activation_delay=0.4, cooldown_duration=0.8)
        self._fire_fist(d)
        d.update(Gesture.PEACE, 0.7)     # COOLDOWN -> ACTIVATING(PEACE)
        assert d.state == DebounceState.ACTIVATING
        d.update(Gesture.POINTING, 0.8)  # ACTIVATING reset to POINTING
        assert d.state == DebounceState.ACTIVATING
        # Hold POINTING for activation_delay (0.8 + 0.4 = 1.2)
        result = d.update(Gesture.POINTING, 1.3)
        assert result == DebounceSignal(DebounceAction.FIRE, Gesture.POINTING)

    def test_cooldown_gesture_cleared_on_transition_to_activating(self):
        d = GestureDebouncer(activation_delay=0.4, cooldown_duration=0.8)
        self._fire_fist(d)
        d.update(Gesture.PEACE, 0.7)  # COOLDOWN -> ACTIVATING
        assert d._cooldown_gesture is None

    def test_cooldown_gesture_cleared_on_transition_to_idle(self):
        d = GestureDebouncer(activation_delay=0.4, cooldown_duration=0.8)
        self._fire_fist(d)
        # Cooldown elapses, release hand
        d.update(None, 1.5)
        assert d.state == DebounceState.IDLE
        assert d._cooldown_gesture is None

    def test_reset_clears_cooldown_gesture(self):
        d = GestureDebouncer(activation_delay=0.4, cooldown_duration=0.8)
        self._fire_fist(d)
        assert d.state == DebounceState.COOLDOWN
        d.reset()
        assert d._cooldown_gesture is None
        assert d.state == DebounceState.IDLE

    def test_different_gesture_after_cooldown_elapsed_starts_activating(self):
        d = GestureDebouncer(activation_delay=0.4, cooldown_duration=0.8)
        self._fire_fist(d)
        # Cooldown elapses (0.6 + 0.8 = 1.4), different gesture appears
        result = d.update(Gesture.PEACE, 1.5)
        assert result is None
        assert d.state == DebounceState.ACTIVATING


class TestDebounceReset:
    """Test reset functionality."""

    def test_reset_returns_to_idle(self):
        d = GestureDebouncer()
        d.update(Gesture.FIST, 0.0)
        assert d.state == DebounceState.ACTIVATING
        d.reset()
        assert d.state == DebounceState.IDLE


class TestDebounceLogging:
    """Test that state transitions are logged at DEBUG level."""

    def test_idle_to_activating_logged(self, caplog):
        d = GestureDebouncer()
        with caplog.at_level(logging.DEBUG, logger="gesture_keys"):
            d.update(Gesture.FIST, 0.0)
        assert "IDLE" in caplog.text and "ACTIVATING" in caplog.text

    def test_fired_logged(self, caplog):
        d = GestureDebouncer(activation_delay=0.4)
        d.update(Gesture.FIST, 0.0)
        with caplog.at_level(logging.DEBUG, logger="gesture_keys"):
            d.update(Gesture.FIST, 0.5)
        assert "FIRED" in caplog.text


class TestIsActivatingProperty:
    """Tests for the is_activating read-only property."""

    def test_is_activating_false_in_idle(self):
        d = GestureDebouncer()
        assert d.is_activating is False

    def test_is_activating_true_in_activating(self):
        d = GestureDebouncer()
        d.update(Gesture.FIST, 0.0)
        assert d.state == DebounceState.ACTIVATING
        assert d.is_activating is True

    def test_is_activating_false_in_fired(self):
        d = GestureDebouncer(activation_delay=0.4)
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # fires
        assert d.state == DebounceState.FIRED
        assert d.is_activating is False

    def test_is_activating_false_in_cooldown(self):
        d = GestureDebouncer(activation_delay=0.4)
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # fires
        d.update(Gesture.FIST, 0.6)  # -> cooldown
        assert d.state == DebounceState.COOLDOWN
        assert d.is_activating is False


class TestDebounceSignal:
    """Test DebounceSignal and DebounceAction types."""

    def test_debounce_action_values(self):
        assert DebounceAction.FIRE.value == "fire"
        assert DebounceAction.HOLD_START.value == "hold_start"
        assert DebounceAction.HOLD_END.value == "hold_end"

    def test_debounce_signal_creation(self):
        signal = DebounceSignal(DebounceAction.FIRE, Gesture.FIST)
        assert signal.action == DebounceAction.FIRE
        assert signal.gesture == Gesture.FIST

    def test_debounce_signal_unpacking(self):
        signal = DebounceSignal(DebounceAction.HOLD_START, Gesture.PEACE)
        action, gesture = signal
        assert action == DebounceAction.HOLD_START
        assert gesture == Gesture.PEACE


class TestPerGestureCooldowns:
    """Test per-gesture cooldown override behavior."""

    def test_per_gesture_cooldown_used_for_matching_gesture(self):
        """Debouncer with gesture_cooldowns uses per-gesture cooldown."""
        d = GestureDebouncer(
            activation_delay=0.1, cooldown_duration=0.3,
            gesture_cooldowns={"fist": 0.5},
        )
        d.update(Gesture.FIST, 0.0)       # IDLE -> ACTIVATING
        d.update(Gesture.FIST, 0.2)       # ACTIVATING -> FIRED
        d.update(Gesture.FIST, 0.3)       # FIRED -> COOLDOWN at t=0.3
        assert d.state == DebounceState.COOLDOWN
        # At t=0.7 (0.4s elapsed), still in cooldown (0.5s per-gesture)
        d.update(None, 0.7)
        assert d.state == DebounceState.COOLDOWN
        # At t=0.9 (0.6s elapsed > 0.5s), should transition to IDLE
        d.update(None, 0.9)
        assert d.state == DebounceState.IDLE

    def test_no_gesture_cooldowns_uses_global(self):
        """Debouncer without gesture_cooldowns uses global cooldown_duration."""
        d = GestureDebouncer(activation_delay=0.1, cooldown_duration=0.3)
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.2)       # fires
        d.update(Gesture.FIST, 0.3)       # -> cooldown at t=0.3
        # At t=0.7 (0.4s > 0.3s global), should be IDLE
        d.update(None, 0.7)
        assert d.state == DebounceState.IDLE

    def test_gesture_not_in_cooldowns_uses_global(self):
        """Gesture not in gesture_cooldowns dict falls back to global."""
        d = GestureDebouncer(
            activation_delay=0.1, cooldown_duration=0.3,
            gesture_cooldowns={"pinch": 0.6},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.2)       # fires
        d.update(Gesture.FIST, 0.3)       # -> cooldown at t=0.3
        # FIST not in gesture_cooldowns, uses global 0.3s
        d.update(None, 0.7)
        assert d.state == DebounceState.IDLE

    def test_per_gesture_cooldown_timing_boundary(self):
        """Per-gesture cooldown: fire pinch (0.6s) -> 0.5s still cooldown, 0.7s idle."""
        d = GestureDebouncer(
            activation_delay=0.1, cooldown_duration=0.3,
            gesture_cooldowns={"pinch": 0.6},
        )
        d.update(Gesture.PINCH, 0.0)
        d.update(Gesture.PINCH, 0.2)      # fires
        d.update(Gesture.PINCH, 0.3)      # -> cooldown at t=0.3
        # 0.5s elapsed (t=0.8), still in cooldown
        d.update(None, 0.8)
        assert d.state == DebounceState.COOLDOWN
        # 0.7s elapsed (t=1.0), cooldown over
        d.update(None, 1.0)
        assert d.state == DebounceState.IDLE


class TestHoldModeBasic:
    """Test HOLDING state for hold-mode gestures."""

    def test_hold_mode_activating_to_holding(self):
        """Hold gesture transitions ACTIVATING -> HOLDING (not FIRED)."""
        d = GestureDebouncer(
            activation_delay=0.4,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)  # IDLE -> ACTIVATING
        result = d.update(Gesture.FIST, 0.5)  # ACTIVATING -> HOLDING
        assert result == DebounceSignal(DebounceAction.HOLD_START, Gesture.FIST)
        assert d.state == DebounceState.HOLDING

    def test_hold_mode_stays_holding_while_gesture_continues(self):
        """While gesture is maintained, stay in HOLDING and return None."""
        d = GestureDebouncer(
            activation_delay=0.4,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        result = d.update(Gesture.FIST, 0.6)
        assert result is None
        assert d.state == DebounceState.HOLDING

    def test_hold_mode_release_delay_absorbs_flicker(self):
        """Gesture drops briefly but returns within release delay -> stays HOLDING."""
        d = GestureDebouncer(
            activation_delay=0.4,
            hold_release_delay=0.1,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        result = d.update(None, 0.55)  # gesture lost, release delay starts
        assert result is None
        assert d.state == DebounceState.HOLDING
        # Gesture returns within 0.1s
        result = d.update(Gesture.FIST, 0.6)
        assert result is None
        assert d.state == DebounceState.HOLDING

    def test_hold_mode_release_after_delay_expires(self):
        """Gesture lost and release delay expires -> emit hold_end, COOLDOWN."""
        d = GestureDebouncer(
            activation_delay=0.4,
            hold_release_delay=0.1,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        d.update(None, 0.55)  # gesture lost
        result = d.update(None, 0.7)  # release delay expired (0.55 + 0.1 < 0.7)
        assert result == DebounceSignal(DebounceAction.HOLD_END, Gesture.FIST)
        assert d.state == DebounceState.COOLDOWN

    def test_hold_mode_emits_hold_end_exactly_once(self):
        """After hold_end is emitted, subsequent updates return None."""
        d = GestureDebouncer(
            activation_delay=0.4,
            cooldown_duration=0.3,
            hold_release_delay=0.1,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        d.update(None, 0.55)  # gesture lost
        d.update(None, 0.7)  # hold_end emitted
        result = d.update(None, 0.8)  # should be None (in COOLDOWN)
        assert result is None

    def test_tap_mode_unchanged_when_hold_modes_exist(self):
        """Tap-mode gestures still use FIRED path even when hold modes configured."""
        d = GestureDebouncer(
            activation_delay=0.4,
            gesture_modes={"fist": "hold", "peace": "tap"},
        )
        d.update(Gesture.PEACE, 0.0)
        result = d.update(Gesture.PEACE, 0.5)
        assert result == DebounceSignal(DebounceAction.FIRE, Gesture.PEACE)
        assert d.state == DebounceState.FIRED

    def test_multiple_rapid_drops_within_delay(self):
        """Rapid flicker: gesture drops and returns multiple times within delay."""
        d = GestureDebouncer(
            activation_delay=0.4,
            hold_release_delay=0.1,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        # Rapid flicker
        assert d.update(None, 0.55) is None         # drop 1
        assert d.update(Gesture.FIST, 0.57) is None # return 1
        assert d.update(None, 0.59) is None         # drop 2
        assert d.update(Gesture.FIST, 0.61) is None # return 2
        assert d.state == DebounceState.HOLDING

    def test_is_activating_false_in_holding(self):
        """is_activating property returns False during HOLDING state."""
        d = GestureDebouncer(
            activation_delay=0.4,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        assert d.is_activating is False


class TestHoldModeGestureChange:
    """Test gesture changes during HOLDING state."""

    def test_different_gesture_during_holding_emits_hold_end(self):
        """Different gesture while HOLDING -> hold_end for current."""
        d = GestureDebouncer(
            activation_delay=0.4,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        result = d.update(Gesture.PEACE, 0.6)
        assert result == DebounceSignal(DebounceAction.HOLD_END, Gesture.FIST)
        assert d.state == DebounceState.ACTIVATING

    def test_different_gesture_during_holding_starts_activating_new(self):
        """After hold_end from gesture change, new gesture is activating."""
        d = GestureDebouncer(
            activation_delay=0.4,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        d.update(Gesture.PEACE, 0.6)  # -> hold_end + ACTIVATING(PEACE)
        # Now hold PEACE for activation_delay
        result = d.update(Gesture.PEACE, 1.1)
        assert result == DebounceSignal(DebounceAction.FIRE, Gesture.PEACE)

    def test_different_gesture_during_release_delay(self):
        """Different gesture appears during release delay -> hold_end + ACTIVATING."""
        d = GestureDebouncer(
            activation_delay=0.4,
            hold_release_delay=0.1,
            gesture_modes={"fist": "hold"},
        )
        d.update(Gesture.FIST, 0.0)
        d.update(Gesture.FIST, 0.5)  # -> HOLDING
        d.update(None, 0.55)  # gesture lost, release delay starts
        result = d.update(Gesture.PEACE, 0.58)  # different gesture within delay
        assert result == DebounceSignal(DebounceAction.HOLD_END, Gesture.FIST)
        assert d.state == DebounceState.ACTIVATING


class TestHoldModeCooldownCycle:
    """Test full hold cycle including cooldown."""

    def test_full_hold_cycle(self):
        """IDLE -> ACTIVATING -> HOLDING -> COOLDOWN -> IDLE."""
        d = GestureDebouncer(
            activation_delay=0.4,
            cooldown_duration=0.3,
            hold_release_delay=0.1,
            gesture_modes={"fist": "hold"},
        )
        # IDLE -> ACTIVATING
        d.update(Gesture.FIST, 0.0)
        assert d.state == DebounceState.ACTIVATING

        # ACTIVATING -> HOLDING
        result = d.update(Gesture.FIST, 0.5)
        assert result == DebounceSignal(DebounceAction.HOLD_START, Gesture.FIST)
        assert d.state == DebounceState.HOLDING

        # Stay HOLDING
        assert d.update(Gesture.FIST, 0.6) is None

        # Gesture lost
        d.update(None, 0.7)
        assert d.state == DebounceState.HOLDING  # release delay

        # Release delay expires -> COOLDOWN
        result = d.update(None, 0.85)
        assert result == DebounceSignal(DebounceAction.HOLD_END, Gesture.FIST)
        assert d.state == DebounceState.COOLDOWN

        # Cooldown expires + release -> IDLE
        d.update(None, 1.2)
        assert d.state == DebounceState.IDLE
