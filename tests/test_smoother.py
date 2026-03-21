"""Tests for gesture_keys.smoother module."""

import pytest

from gesture_keys.smoother import GestureSmoother
from gesture_keys.classifier import Gesture


class TestSmootherBufferFill:
    """Test that smoother returns None until buffer is full."""

    def test_returns_none_first_call(self):
        smoother = GestureSmoother(window_size=3)
        assert smoother.update(Gesture.FIST) is None

    def test_returns_none_second_call(self):
        smoother = GestureSmoother(window_size=3)
        smoother.update(Gesture.FIST)
        assert smoother.update(Gesture.FIST) is None

    def test_returns_value_on_third_call(self):
        smoother = GestureSmoother(window_size=3)
        smoother.update(Gesture.FIST)
        smoother.update(Gesture.FIST)
        result = smoother.update(Gesture.FIST)
        assert result == Gesture.FIST


class TestSmootherMajorityVote:
    """Test majority vote logic."""

    def test_clear_majority(self):
        smoother = GestureSmoother(window_size=3)
        smoother.update(Gesture.FIST)
        smoother.update(Gesture.OPEN_PALM)
        result = smoother.update(Gesture.FIST)
        # 2 FIST vs 1 OPEN_PALM -> FIST wins
        assert result == Gesture.FIST

    def test_unanimous(self):
        smoother = GestureSmoother(window_size=3)
        smoother.update(Gesture.PEACE)
        smoother.update(Gesture.PEACE)
        result = smoother.update(Gesture.PEACE)
        assert result == Gesture.PEACE

    def test_sliding_window(self):
        smoother = GestureSmoother(window_size=3)
        smoother.update(Gesture.FIST)
        smoother.update(Gesture.FIST)
        smoother.update(Gesture.FIST)
        # Now slide in OPEN_PALM
        result = smoother.update(Gesture.OPEN_PALM)
        # Buffer: [FIST, FIST, OPEN_PALM] -> FIST wins
        assert result == Gesture.FIST


class TestSmootherTieBreaking:
    """Test tie resolution returns None."""

    def test_three_way_tie_returns_none(self):
        smoother = GestureSmoother(window_size=3)
        smoother.update(Gesture.FIST)
        smoother.update(Gesture.OPEN_PALM)
        result = smoother.update(Gesture.PEACE)
        # All different -> no majority -> None
        assert result is None


class TestSmootherNoneHandling:
    """Test that None is a valid value in the buffer."""

    def test_none_as_input(self):
        smoother = GestureSmoother(window_size=3)
        smoother.update(None)
        smoother.update(None)
        result = smoother.update(None)
        assert result is None  # None is the majority

    def test_none_mixed_with_gestures(self):
        smoother = GestureSmoother(window_size=3)
        smoother.update(None)
        smoother.update(Gesture.FIST)
        result = smoother.update(Gesture.FIST)
        # 2 FIST vs 1 None -> FIST wins
        assert result == Gesture.FIST


class TestSmootherReset:
    """Test reset clears the buffer."""

    def test_reset_clears_state(self):
        smoother = GestureSmoother(window_size=3)
        smoother.update(Gesture.FIST)
        smoother.update(Gesture.FIST)
        smoother.update(Gesture.FIST)
        smoother.reset()
        # After reset, buffer is empty again
        assert smoother.update(Gesture.FIST) is None

    def test_works_normally_after_reset(self):
        smoother = GestureSmoother(window_size=3)
        smoother.update(Gesture.FIST)
        smoother.update(Gesture.FIST)
        smoother.update(Gesture.FIST)
        smoother.reset()
        smoother.update(Gesture.PEACE)
        smoother.update(Gesture.PEACE)
        result = smoother.update(Gesture.PEACE)
        assert result == Gesture.PEACE
