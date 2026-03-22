"""Tests for the debounce state machine."""

import logging

import pytest

from gesture_keys.classifier import Gesture
from gesture_keys.debounce import DebounceState, GestureDebouncer


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
        assert result == Gesture.FIST
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
        assert result == Gesture.PEACE

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
        assert fire1 == Gesture.FIST
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
        assert result == Gesture.PEACE

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
        assert result == Gesture.POINTING

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
