"""Tests for gesture_keys.distance module."""

import logging
import math

import pytest

from gesture_keys.distance import DistanceFilter


class TestDistanceFilterCheck:
    """Test DistanceFilter.check() pass/fail behavior."""

    def test_passes_when_palm_span_above_threshold(self, mock_landmarks_close_hand):
        df = DistanceFilter(min_hand_size=0.15, enabled=True)
        assert df.check(mock_landmarks_close_hand) is True

    def test_rejects_when_palm_span_below_threshold(self, mock_landmarks_far_hand):
        df = DistanceFilter(min_hand_size=0.15, enabled=True)
        assert df.check(mock_landmarks_far_hand) is False

    def test_passes_when_disabled_regardless_of_span(self, mock_landmarks_far_hand):
        df = DistanceFilter(min_hand_size=0.15, enabled=False)
        # Far hand would fail if enabled, but disabled always passes
        assert df.check(mock_landmarks_far_hand) is True

    def test_passes_at_exact_threshold(self, mock_landmarks_close_hand):
        # Palm span is 0.25, set threshold to exactly 0.25
        df = DistanceFilter(min_hand_size=0.25, enabled=True)
        assert df.check(mock_landmarks_close_hand) is True

    def test_rejects_just_above_threshold(self, mock_landmarks_far_hand):
        # Palm span is 0.08, set threshold to 0.09
        df = DistanceFilter(min_hand_size=0.09, enabled=True)
        assert df.check(mock_landmarks_far_hand) is False


class TestDistanceFilterTransitionLogging:
    """Test that transition logging fires once per state change."""

    def test_logs_once_when_going_out_of_range(
        self, mock_landmarks_close_hand, mock_landmarks_far_hand, caplog
    ):
        df = DistanceFilter(min_hand_size=0.15, enabled=True)
        with caplog.at_level(logging.DEBUG, logger="gesture_keys"):
            df.check(mock_landmarks_close_hand)  # in range (initial)
            caplog.clear()
            df.check(mock_landmarks_far_hand)  # transition to out of range
        assert len([r for r in caplog.records if "filtered" in r.message.lower()]) == 1

    def test_logs_once_when_returning_to_range(
        self, mock_landmarks_close_hand, mock_landmarks_far_hand, caplog
    ):
        df = DistanceFilter(min_hand_size=0.15, enabled=True)
        with caplog.at_level(logging.DEBUG, logger="gesture_keys"):
            df.check(mock_landmarks_close_hand)  # in range
            df.check(mock_landmarks_far_hand)  # out of range
            caplog.clear()
            df.check(mock_landmarks_close_hand)  # back in range
        assert len([r for r in caplog.records if "in range" in r.message.lower()]) == 1

    def test_repeated_out_of_range_no_extra_logs(
        self, mock_landmarks_far_hand, caplog
    ):
        df = DistanceFilter(min_hand_size=0.15, enabled=True)
        with caplog.at_level(logging.DEBUG, logger="gesture_keys"):
            # First call: _was_in_range=True, now out -> logs once
            df.check(mock_landmarks_far_hand)
            caplog.clear()
            # Subsequent calls: already out of range -> no more logs
            df.check(mock_landmarks_far_hand)
            df.check(mock_landmarks_far_hand)
            df.check(mock_landmarks_far_hand)
        assert len(caplog.records) == 0


class TestComputePalmSpan:
    """Test _compute_palm_span returns correct Euclidean distance."""

    def test_known_distance_close_hand(self, mock_landmarks_close_hand):
        df = DistanceFilter()
        span = df._compute_palm_span(mock_landmarks_close_hand)
        assert math.isclose(span, 0.25, abs_tol=1e-9)

    def test_known_distance_far_hand(self, mock_landmarks_far_hand):
        df = DistanceFilter()
        span = df._compute_palm_span(mock_landmarks_far_hand)
        assert math.isclose(span, 0.08, abs_tol=1e-9)


class TestDistanceFilterProperties:
    """Test min_hand_size and enabled are settable via properties."""

    def test_enabled_property_getter(self):
        df = DistanceFilter(enabled=True)
        assert df.enabled is True

    def test_enabled_property_setter(self):
        df = DistanceFilter(enabled=True)
        df.enabled = False
        assert df.enabled is False

    def test_min_hand_size_property_getter(self):
        df = DistanceFilter(min_hand_size=0.20)
        assert df.min_hand_size == 0.20

    def test_min_hand_size_property_setter(self):
        df = DistanceFilter(min_hand_size=0.15)
        df.min_hand_size = 0.25
        assert df.min_hand_size == 0.25
