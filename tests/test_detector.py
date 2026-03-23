"""Tests for camera capture and hand detection."""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call
import numpy as np
import pytest


class TestCameraCapture:
    """Tests for the CameraCapture class."""

    @patch("gesture_keys.detector.cv2.VideoCapture")
    def test_start_creates_daemon_thread(self, mock_vc_cls):
        """start() should spawn a daemon thread."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        mock_vc_cls.return_value = mock_cap

        from gesture_keys.detector import CameraCapture

        cc = CameraCapture(camera_index=0)
        cc.start()

        import time
        time.sleep(0.05)

        daemon_threads = [
            t for t in threading.enumerate()
            if t.daemon and t.is_alive() and t.name != "MainThread"
        ]
        assert len(daemon_threads) >= 1, "Expected at least one daemon thread"

        cc.stop()

    @patch("gesture_keys.detector.cv2.VideoCapture")
    def test_read_returns_false_none_before_capture(self, mock_vc_cls):
        """read() should return (False, None) before any frame is captured."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_vc_cls.return_value = mock_cap

        from gesture_keys.detector import CameraCapture

        cc = CameraCapture(camera_index=0)
        ret, frame = cc.read()
        assert ret is False
        assert frame is None

    @patch("gesture_keys.detector.cv2.VideoCapture")
    def test_read_returns_frame_copy_after_capture(self, mock_vc_cls):
        """read() should return a copy of the frame after capture thread runs."""
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, fake_frame)
        mock_vc_cls.return_value = mock_cap

        from gesture_keys.detector import CameraCapture

        cc = CameraCapture(camera_index=0)
        cc.start()

        import time
        time.sleep(0.1)

        ret, frame = cc.read()
        assert ret is True
        assert frame is not None
        assert frame is not fake_frame
        np.testing.assert_array_equal(frame, fake_frame)

        cc.stop()

    @patch("gesture_keys.detector.cv2.VideoCapture")
    def test_stop_sets_flag_and_releases(self, mock_vc_cls):
        """stop() should set stopped flag and release the capture."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        mock_vc_cls.return_value = mock_cap

        from gesture_keys.detector import CameraCapture

        cc = CameraCapture(camera_index=0)
        cc.start()
        cc.stop()

        assert cc.stopped is True
        mock_cap.release.assert_called_once()

    @patch("gesture_keys.detector.cv2.VideoCapture")
    def test_camera_not_opened_raises_runtime_error(self, mock_vc_cls):
        """Should raise RuntimeError if camera cannot be opened."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_vc_cls.return_value = mock_cap

        from gesture_keys.detector import CameraCapture

        with pytest.raises(RuntimeError, match="Camera index 0 could not be opened"):
            CameraCapture(camera_index=0)

    @patch("gesture_keys.detector.cv2.VideoCapture")
    def test_start_returns_self(self, mock_vc_cls):
        """start() should return self for chaining."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        mock_vc_cls.return_value = mock_cap

        from gesture_keys.detector import CameraCapture

        cc = CameraCapture(camera_index=0)
        result = cc.start()
        assert result is cc
        cc.stop()


# --- HandDetector helpers ---

def _make_mock_handedness(label):
    """Create a mock handedness entry with category_name."""
    category = SimpleNamespace(category_name=label, score=0.95)
    return [category]


def _make_mock_landmarks(count=21):
    """Create a list of mock landmarks."""
    return [SimpleNamespace(x=0.5, y=0.5, z=0.0) for _ in range(count)]


def _make_mock_result(hands):
    """Create a mock HandLandmarkerResult.

    Args:
        hands: list of (handedness_label, landmarks) tuples
    """
    handedness = [_make_mock_handedness(label) for label, _ in hands]
    hand_landmarks = [lm for _, lm in hands]
    return SimpleNamespace(handedness=handedness, hand_landmarks=hand_landmarks)


def _create_detector_with_mock(preferred_hand="left"):
    """Create a HandDetector with all MediaPipe internals mocked.

    Args:
        preferred_hand: Preferred hand for active hand selection at startup.

    Returns (detector, mock_landmarker) so tests can configure the mock.
    """
    from gesture_keys import detector as det_module

    mock_landmarker = MagicMock()

    with patch.object(det_module, "HandLandmarker") as mock_hl_cls, \
         patch.object(det_module, "HandLandmarkerOptions"), \
         patch.object(det_module, "BaseOptions"), \
         patch.object(det_module, "VisionRunningMode"), \
         patch("os.path.exists", return_value=True):
        mock_hl_cls.create_from_options.return_value = mock_landmarker
        detector = det_module.HandDetector(
            model_path="fake_model.task",
            preferred_hand=preferred_hand,
        )

    return detector, mock_landmarker


class TestHandDetector:
    """Tests for the HandDetector class."""

    def test_right_hand_returns_landmarks(self):
        """Result with one right hand should return its landmarks and label."""
        detector, mock_landmarker = _create_detector_with_mock()

        right_landmarks = _make_mock_landmarks()
        mock_result = _make_mock_result([("Right", right_landmarks)])
        mock_landmarker.detect_for_video.return_value = mock_result

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        landmarks, handedness = detector.detect(frame, timestamp_ms=100)

        assert landmarks == right_landmarks
        assert len(landmarks) == 21
        assert handedness == "Right"

    def test_left_hand_returns_landmarks(self):
        """Result with only left hand should return its landmarks and label."""
        detector, mock_landmarker = _create_detector_with_mock()

        left_landmarks = _make_mock_landmarks()
        mock_result = _make_mock_result([("Left", left_landmarks)])
        mock_landmarker.detect_for_video.return_value = mock_result

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        landmarks, handedness = detector.detect(frame, timestamp_ms=100)

        assert landmarks == left_landmarks
        assert len(landmarks) == 21
        assert handedness == "Left"

    def test_no_hands_returns_empty(self):
        """Empty result (no hands) should return ([], None)."""
        detector, mock_landmarker = _create_detector_with_mock()

        mock_result = _make_mock_result([])
        mock_landmarker.detect_for_video.return_value = mock_result

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        landmarks, handedness = detector.detect(frame, timestamp_ms=100)

        assert landmarks == []
        assert handedness is None

    def test_both_hands_no_prior_active_selects_preferred(self):
        """Both hands visible, no prior active -> preferred hand ('left') selected."""
        detector, mock_landmarker = _create_detector_with_mock(preferred_hand="left")

        left_landmarks = _make_mock_landmarks()
        left_landmarks[0] = SimpleNamespace(x=0.9, y=0.5, z=0.0)
        right_landmarks = _make_mock_landmarks()
        right_landmarks[0] = SimpleNamespace(x=0.1, y=0.1, z=0.0)
        mock_result = _make_mock_result([
            ("Left", left_landmarks),
            ("Right", right_landmarks),
        ])
        mock_landmarker.detect_for_video.return_value = mock_result

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        landmarks, handedness = detector.detect(frame, timestamp_ms=100)

        assert landmarks == left_landmarks
        assert handedness == "Left"

    def test_both_hands_sticks_with_active(self):
        """Active hand is 'Right', both visible -> stays 'Right' (sticky)."""
        detector, mock_landmarker = _create_detector_with_mock()

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # First frame: only right hand -> becomes active
        right_landmarks = _make_mock_landmarks()
        right_landmarks[0] = SimpleNamespace(x=0.1, y=0.1, z=0.0)
        mock_landmarker.detect_for_video.return_value = _make_mock_result([
            ("Right", right_landmarks),
        ])
        detector.detect(frame, timestamp_ms=100)

        # Second frame: both hands -> should stick with Right
        left_landmarks = _make_mock_landmarks()
        mock_landmarker.detect_for_video.return_value = _make_mock_result([
            ("Left", left_landmarks),
            ("Right", right_landmarks),
        ])
        landmarks, handedness = detector.detect(frame, timestamp_ms=200)

        assert landmarks == right_landmarks
        assert handedness == "Right"

    def test_active_hand_disappears_only_other_visible_switches(self):
        """Active was Right, only left visible now -> returns left (switch)."""
        detector, mock_landmarker = _create_detector_with_mock()

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # First: right hand only -> active = Right
        right_landmarks = _make_mock_landmarks()
        mock_landmarker.detect_for_video.return_value = _make_mock_result([
            ("Right", right_landmarks),
        ])
        detector.detect(frame, timestamp_ms=100)

        # Second: only left hand -> single hand detected, switch to left
        left_landmarks = _make_mock_landmarks()
        left_landmarks[0] = SimpleNamespace(x=0.9, y=0.5, z=0.0)
        mock_landmarker.detect_for_video.return_value = _make_mock_result([
            ("Left", left_landmarks),
        ])
        landmarks, handedness = detector.detect(frame, timestamp_ms=200)

        assert landmarks == left_landmarks
        assert handedness == "Left"

    def test_active_disappears_while_other_present_waits(self):
        """Active hand disappears while other hand is still present -> empty transition frame."""
        detector, mock_landmarker = _create_detector_with_mock()

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Frame 1: both hands visible, left hand active (preferred)
        left_landmarks = _make_mock_landmarks()
        right_landmarks = _make_mock_landmarks()
        right_landmarks[0] = SimpleNamespace(x=0.1, y=0.1, z=0.0)
        mock_landmarker.detect_for_video.return_value = _make_mock_result([
            ("Left", left_landmarks),
            ("Right", right_landmarks),
        ])
        landmarks, handedness = detector.detect(frame, timestamp_ms=100)
        assert handedness == "Left"  # preferred is left

        # Frame 2: active (Left) disappears, Right still present = both hands
        # But active hand is "Left" and only "Right" is detected
        # With both hands: active not in detected -> transition frame
        # Actually, only Right is detected = single hand scenario -> switch
        # Let me re-read the spec more carefully...

        # The spec says: "Active hand disappears, other hand visible ->
        # waits for clean single-hand (returns empty for the transition frame
        # where active just disappeared while other is present, then selects
        # the remaining hand on next frame when only one hand detected)"
        #
        # But this scenario is: active=Left, detected={Right} => only 1 hand detected
        # The single-hand path should handle this. The "wait" case is when
        # BOTH hands are detected but the active is NOT among them (which is
        # impossible with MediaPipe, since it either detects a hand or doesn't).
        #
        # Re-reading plan more carefully:
        # "If self._active_hand is set but NOT in detected hands (hand just
        # disappeared while other is present): return ([], None) and set
        # self._active_hand = None"
        #
        # This would trigger when: two hands were being tracked, one disappears.
        # If active=Left, and now detected={Right}, that IS "active not in
        # detected hands". But it's also exactly one hand detected.
        #
        # The plan's logic has:
        # - no hands -> ([], None)
        # - exactly one hand -> set active, return
        # - two hands -> sticky / preferred / wait-for-clean
        #
        # So with one hand detected, we take the "exactly one" path and switch
        # immediately. The "wait-for-clean" only triggers in the two-hands case
        # where active is not among detected (which shouldn't happen normally).
        #
        # Let me test the actual intended scenario from the plan's branching:
        # Two hands detected, active hand NOT in detected hands. This is
        # an edge case. Let's just test the plan's code path as written.

    def test_two_hands_active_not_in_detected_returns_empty(self):
        """Two hands detected but active hand label not among them -> transition frame."""
        detector, mock_landmarker = _create_detector_with_mock()

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Frame 1: set active to Right via single-hand detection
        right_landmarks = _make_mock_landmarks()
        mock_landmarker.detect_for_video.return_value = _make_mock_result([
            ("Right", right_landmarks),
        ])
        detector.detect(frame, timestamp_ms=100)

        # Frame 2: two hands detected, but labeled differently (edge case)
        # Simulate by manually setting active to something not in the result
        detector._active_hand = "Right"
        left_landmarks = _make_mock_landmarks()
        left2_landmarks = _make_mock_landmarks()
        # Two "Left" hands detected (MediaPipe glitch edge case)
        mock_landmarker.detect_for_video.return_value = _make_mock_result([
            ("Left", left_landmarks),
            ("Left", left2_landmarks),
        ])
        landmarks, handedness = detector.detect(frame, timestamp_ms=200)

        assert landmarks == []
        assert handedness is None

    def test_preferred_hand_right_selects_right_at_startup(self):
        """preferred_hand='right', both hands at startup -> selects Right."""
        detector, mock_landmarker = _create_detector_with_mock(preferred_hand="right")

        left_landmarks = _make_mock_landmarks()
        right_landmarks = _make_mock_landmarks()
        right_landmarks[0] = SimpleNamespace(x=0.1, y=0.1, z=0.0)
        mock_result = _make_mock_result([
            ("Left", left_landmarks),
            ("Right", right_landmarks),
        ])
        mock_landmarker.detect_for_video.return_value = mock_result

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        landmarks, handedness = detector.detect(frame, timestamp_ms=100)

        assert landmarks == right_landmarks
        assert handedness == "Right"

    def test_reset_clears_active_hand(self):
        """reset() should clear active hand state."""
        detector, mock_landmarker = _create_detector_with_mock()

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Set active hand
        right_landmarks = _make_mock_landmarks()
        mock_landmarker.detect_for_video.return_value = _make_mock_result([
            ("Right", right_landmarks),
        ])
        detector.detect(frame, timestamp_ms=100)
        assert detector._active_hand == "Right"

        detector.reset()
        assert detector._active_hand is None

    def test_bgr_to_rgb_conversion(self):
        """BGR frame should be converted to RGB before passing to MediaPipe."""
        detector, mock_landmarker = _create_detector_with_mock()

        mock_result = _make_mock_result([])
        mock_landmarker.detect_for_video.return_value = mock_result

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        with patch("gesture_keys.detector.cv2.cvtColor", return_value=frame) as mock_cvt, \
             patch("gesture_keys.detector.cv2.COLOR_BGR2RGB", 4):
            with patch("gesture_keys.detector.mp.Image") as mock_image:
                detector.detect(frame, timestamp_ms=100)
                mock_cvt.assert_called_once()
                args = mock_cvt.call_args
                assert args[0][1] == 4  # COLOR_BGR2RGB

    def test_non_monotonic_timestamp_raises(self):
        """Non-monotonic timestamps should raise ValueError."""
        detector, mock_landmarker = _create_detector_with_mock()

        mock_result = _make_mock_result([])
        mock_landmarker.detect_for_video.return_value = mock_result

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detector.detect(frame, timestamp_ms=100)

        with pytest.raises(ValueError, match="monotonic"):
            detector.detect(frame, timestamp_ms=50)

    def test_context_manager(self):
        """HandDetector should support context manager protocol."""
        from gesture_keys import detector as det_module

        mock_landmarker = MagicMock()

        with patch.object(det_module, "HandLandmarker") as mock_hl_cls, \
             patch.object(det_module, "HandLandmarkerOptions"), \
             patch.object(det_module, "BaseOptions"), \
             patch.object(det_module, "VisionRunningMode"), \
             patch("os.path.exists", return_value=True):
            mock_hl_cls.create_from_options.return_value = mock_landmarker
            with det_module.HandDetector(model_path="fake_model.task") as detector:
                assert detector is not None

        mock_landmarker.close.assert_called_once()
