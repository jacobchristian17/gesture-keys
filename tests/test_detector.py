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


def _create_detector_with_mock():
    """Create a HandDetector with all MediaPipe internals mocked.

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
        detector = det_module.HandDetector(model_path="fake_model.task")

    return detector, mock_landmarker


class TestHandDetector:
    """Tests for the HandDetector class."""

    def test_right_hand_returns_landmarks(self):
        """Result with one right hand should return its landmarks."""
        detector, mock_landmarker = _create_detector_with_mock()

        right_landmarks = _make_mock_landmarks()
        mock_result = _make_mock_result([("Right", right_landmarks)])
        mock_landmarker.detect_for_video.return_value = mock_result

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(frame, timestamp_ms=100)

        assert result == right_landmarks
        assert len(result) == 21

    def test_left_hand_returns_empty(self):
        """Result with only left hand should return empty list."""
        detector, mock_landmarker = _create_detector_with_mock()

        left_landmarks = _make_mock_landmarks()
        mock_result = _make_mock_result([("Left", left_landmarks)])
        mock_landmarker.detect_for_video.return_value = mock_result

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(frame, timestamp_ms=100)

        assert result == []

    def test_both_hands_returns_right_only(self):
        """Result with both hands should return only the right hand landmarks."""
        detector, mock_landmarker = _create_detector_with_mock()

        left_landmarks = _make_mock_landmarks()
        right_landmarks = _make_mock_landmarks()
        right_landmarks[0] = SimpleNamespace(x=0.1, y=0.1, z=0.0)
        mock_result = _make_mock_result([
            ("Left", left_landmarks),
            ("Right", right_landmarks),
        ])
        mock_landmarker.detect_for_video.return_value = mock_result

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(frame, timestamp_ms=100)

        assert result == right_landmarks
        assert result[0].x == 0.1

    def test_no_hands_returns_empty(self):
        """Empty result (no hands) should return empty list."""
        detector, mock_landmarker = _create_detector_with_mock()

        mock_result = _make_mock_result([])
        mock_landmarker.detect_for_video.return_value = mock_result

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(frame, timestamp_ms=100)

        assert result == []

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
