"""Tests for gesture_keys.classifier module."""

import pytest

from gesture_keys.classifier import GestureClassifier, Gesture


@pytest.fixture
def classifier():
    """Create a GestureClassifier with default thresholds."""
    return GestureClassifier()


@pytest.fixture
def classifier_custom():
    """Create a GestureClassifier with custom thresholds."""
    return GestureClassifier(thresholds={"pinch": 0.01})


class TestGestureEnum:
    """Test Gesture enum values."""

    def test_has_all_seven_gestures(self):
        expected = {"OPEN_PALM", "FIST", "THUMBS_UP", "PEACE", "POINTING", "PINCH", "SCOUT"}
        actual = {g.name for g in Gesture}
        assert expected == actual


class TestClassifyGestures:
    """Test individual gesture classification."""

    def test_open_palm(self, classifier, mock_landmarks_open_palm):
        result = classifier.classify(mock_landmarks_open_palm)
        assert result == Gesture.OPEN_PALM

    def test_fist(self, classifier, mock_landmarks_fist):
        result = classifier.classify(mock_landmarks_fist)
        assert result == Gesture.FIST

    def test_thumbs_up(self, classifier, mock_landmarks_thumbs_up):
        result = classifier.classify(mock_landmarks_thumbs_up)
        assert result == Gesture.THUMBS_UP

    def test_peace(self, classifier, mock_landmarks_peace):
        result = classifier.classify(mock_landmarks_peace)
        assert result == Gesture.PEACE

    def test_pointing(self, classifier, mock_landmarks_pointing):
        result = classifier.classify(mock_landmarks_pointing)
        assert result == Gesture.POINTING

    def test_pinch(self, classifier, mock_landmarks_pinch):
        result = classifier.classify(mock_landmarks_pinch)
        assert result == Gesture.PINCH

    def test_scout(self, classifier, mock_landmarks_scout):
        result = classifier.classify(mock_landmarks_scout)
        assert result == Gesture.SCOUT

    def test_none_for_ambiguous(self, classifier, mock_landmarks_none):
        result = classifier.classify(mock_landmarks_none)
        assert result is None


class TestPriorityOrder:
    """Test classification priority: PINCH > FIST > THUMBS_UP > POINTING > PEACE > OPEN_PALM."""

    def test_pinch_wins_over_other_gestures(self, classifier, mock_landmarks_pinch):
        """Pinch landmarks also have extended fingers, but pinch should win."""
        result = classifier.classify(mock_landmarks_pinch)
        assert result == Gesture.PINCH

    def test_fist_checked_before_open_palm(self, classifier, mock_landmarks_fist):
        """Fist should be detected, not fall through to other gestures."""
        result = classifier.classify(mock_landmarks_fist)
        assert result == Gesture.FIST


class TestLeftHandClassification:
    """Test left-hand gesture classification parity with right hand.

    Left-hand fixtures mirror right-hand fixtures with thumb x-positions
    reflected. Since the classifier uses abs() for thumb extension and
    y-axis only for finger extension, classification should be identical.
    """

    def test_left_open_palm(self, classifier, mock_landmarks_left_open_palm):
        result = classifier.classify(mock_landmarks_left_open_palm)
        assert result == Gesture.OPEN_PALM

    def test_left_fist(self, classifier, mock_landmarks_left_fist):
        result = classifier.classify(mock_landmarks_left_fist)
        assert result == Gesture.FIST

    def test_left_thumbs_up(self, classifier, mock_landmarks_left_thumbs_up):
        result = classifier.classify(mock_landmarks_left_thumbs_up)
        assert result == Gesture.THUMBS_UP

    def test_left_peace(self, classifier, mock_landmarks_left_peace):
        result = classifier.classify(mock_landmarks_left_peace)
        assert result == Gesture.PEACE

    def test_left_pointing(self, classifier, mock_landmarks_left_pointing):
        result = classifier.classify(mock_landmarks_left_pointing)
        assert result == Gesture.POINTING

    def test_left_pinch(self, classifier, mock_landmarks_left_pinch):
        result = classifier.classify(mock_landmarks_left_pinch)
        assert result == Gesture.PINCH

    def test_left_scout(self, classifier, mock_landmarks_left_scout):
        result = classifier.classify(mock_landmarks_left_scout)
        assert result == Gesture.SCOUT


class TestCustomThresholds:
    """Test classifier with custom threshold values."""

    def test_tight_pinch_threshold_rejects_loose_pinch(self, mock_landmarks_pinch):
        """Very tight threshold should reject pinch that's not close enough."""
        classifier = GestureClassifier(thresholds={"pinch": 0.001})
        result = classifier.classify(mock_landmarks_pinch)
        # With a very tight threshold, the pinch landmarks (distance ~0.01)
        # should NOT match pinch, so it falls through to another gesture
        assert result != Gesture.PINCH

    def test_loose_pinch_threshold_accepts(self, mock_landmarks_pinch):
        """Loose threshold should accept the pinch."""
        classifier = GestureClassifier(thresholds={"pinch": 0.1})
        result = classifier.classify(mock_landmarks_pinch)
        assert result == Gesture.PINCH
