"""Tests for camera capture and hand detection."""

import threading
from unittest.mock import MagicMock, patch, PropertyMock
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

        # Give the thread a moment to actually start
        import time
        time.sleep(0.05)

        # Find the thread that is running _update
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
        # Don't start the thread - just test initial state
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
        time.sleep(0.1)  # Let capture thread run

        ret, frame = cc.read()
        assert ret is True
        assert frame is not None
        # Verify it is a copy, not the same object
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
