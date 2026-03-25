"""TDD tests for trigger string parsing and data model."""

import pytest

from gesture_keys.classifier import Gesture
from gesture_keys.trigger import (
    Direction,
    SequenceTrigger,
    Trigger,
    TriggerParseError,
    TriggerState,
    parse_trigger,
)


# --- Static triggers (TRIG-01) ---


class TestStaticTriggers:
    def test_fist_static(self):
        result = parse_trigger("fist:static")
        assert isinstance(result, Trigger)
        assert result.gesture == Gesture.FIST
        assert result.state == TriggerState.STATIC
        assert result.direction is None

    def test_open_palm_static(self):
        result = parse_trigger("open_palm:static")
        assert result.gesture == Gesture.OPEN_PALM
        assert result.state == TriggerState.STATIC
        assert result.direction is None

    def test_pinch_static(self):
        result = parse_trigger("pinch:static")
        assert result.gesture == Gesture.PINCH
        assert result.state == TriggerState.STATIC


# --- Holding triggers (TRIG-02) ---


class TestHoldingTriggers:
    def test_fist_holding(self):
        result = parse_trigger("fist:holding")
        assert isinstance(result, Trigger)
        assert result.gesture == Gesture.FIST
        assert result.state == TriggerState.HOLDING
        assert result.direction is None

    def test_peace_holding(self):
        result = parse_trigger("peace:holding")
        assert result.state == TriggerState.HOLDING


# --- Moving triggers (TRIG-03) ---


class TestMovingTriggers:
    def test_open_palm_moving_left(self):
        result = parse_trigger("open_palm:moving:left")
        assert isinstance(result, Trigger)
        assert result.gesture == Gesture.OPEN_PALM
        assert result.state == TriggerState.MOVING
        assert result.direction == Direction.LEFT

    def test_fist_moving_right(self):
        result = parse_trigger("fist:moving:right")
        assert result.direction == Direction.RIGHT

    def test_fist_moving_up(self):
        result = parse_trigger("fist:moving:up")
        assert result.direction == Direction.UP

    def test_fist_moving_down(self):
        result = parse_trigger("fist:moving:down")
        assert result.direction == Direction.DOWN


# --- Sequence triggers (TRIG-04) ---


class TestSequenceTriggers:
    def test_fist_to_open_palm(self):
        result = parse_trigger("fist > open_palm")
        assert isinstance(result, SequenceTrigger)
        assert result.first.gesture == Gesture.FIST
        assert result.first.state == TriggerState.STATIC
        assert result.second.gesture == Gesture.OPEN_PALM
        assert result.second.state == TriggerState.STATIC

    def test_peace_to_fist(self):
        result = parse_trigger("peace > fist")
        assert isinstance(result, SequenceTrigger)
        assert result.first.gesture == Gesture.PEACE
        assert result.second.gesture == Gesture.FIST

    def test_sequence_defaults_to_static(self):
        result = parse_trigger("fist > open_palm")
        assert result.first.state == TriggerState.STATIC
        assert result.second.state == TriggerState.STATIC

    def test_sequence_with_explicit_state(self):
        result = parse_trigger("fist:holding > open_palm")
        assert isinstance(result, SequenceTrigger)
        assert result.first.state == TriggerState.HOLDING
        assert result.second.state == TriggerState.STATIC


# --- Validation errors (TRIG-05) ---


class TestValidationErrors:
    def test_invalid_state(self):
        with pytest.raises(TriggerParseError, match="invalid_state"):
            parse_trigger("fist:invalid_state")

    def test_moving_without_direction(self):
        with pytest.raises(TriggerParseError, match="direction"):
            parse_trigger("fist:moving")

    def test_unknown_gesture(self):
        with pytest.raises(TriggerParseError, match="not_a_gesture"):
            parse_trigger("not_a_gesture:static")

    def test_direction_on_non_moving(self):
        with pytest.raises(TriggerParseError):
            parse_trigger("fist:static:left")

    def test_empty_string(self):
        with pytest.raises(TriggerParseError):
            parse_trigger("")

    def test_invalid_direction(self):
        with pytest.raises(TriggerParseError, match="diagonal"):
            parse_trigger("fist:moving:diagonal")

    def test_incomplete_sequence(self):
        with pytest.raises(TriggerParseError):
            parse_trigger("fist > ")
