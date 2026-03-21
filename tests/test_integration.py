"""Integration tests for gesture-keys console output behavior."""

import importlib
import logging
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from gesture_keys.classifier import Gesture

# Force-import __main__ module so patch() can resolve it
import gesture_keys.__main__ as _main_mod


def _make_landmark(x=0.0, y=0.0, z=0.0):
    """Create a mock landmark with x, y, z attributes."""
    return SimpleNamespace(x=x, y=y, z=z)


def _make_open_palm_landmarks():
    """Create landmarks that classify as OPEN_PALM."""
    landmarks = [_make_landmark(0.5, 0.5, 0.0) for _ in range(21)]
    landmarks[0] = _make_landmark(0.5, 0.8, 0.0)    # WRIST
    landmarks[3] = _make_landmark(0.3, 0.6, 0.0)    # THUMB_IP
    landmarks[4] = _make_landmark(0.2, 0.55, 0.0)   # THUMB_TIP (extended)
    landmarks[6] = _make_landmark(0.4, 0.5, 0.0)    # INDEX_PIP
    landmarks[8] = _make_landmark(0.4, 0.2, 0.0)    # INDEX_TIP (extended)
    landmarks[10] = _make_landmark(0.5, 0.5, 0.0)   # MIDDLE_PIP
    landmarks[12] = _make_landmark(0.5, 0.2, 0.0)   # MIDDLE_TIP (extended)
    landmarks[14] = _make_landmark(0.6, 0.5, 0.0)   # RING_PIP
    landmarks[16] = _make_landmark(0.6, 0.2, 0.0)   # RING_TIP (extended)
    landmarks[18] = _make_landmark(0.7, 0.5, 0.0)   # PINKY_PIP
    landmarks[20] = _make_landmark(0.7, 0.2, 0.0)   # PINKY_TIP (extended)
    return landmarks


def _make_mock_frame():
    """Create a fake BGR frame (480x640x3)."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


class TestConsoleOutput:
    """Test that console output shows gesture transitions correctly."""

    @patch.object(_main_mod, "cv2")
    @patch.object(_main_mod, "HandDetector")
    @patch.object(_main_mod, "CameraCapture")
    @patch.object(_main_mod, "parse_args")
    def test_gesture_transitions_logged(
        self, mock_parse_args, mock_camera_cls, mock_detector_cls,
        mock_cv2, caplog
    ):
        """Verify gesture transitions are logged and non-transitions are not.

        Simulates a sequence: 3 frames with no hand (smoother fills buffer),
        then 3 frames with OPEN_PALM landmarks (smoother produces OPEN_PALM),
        then 3 frames with no hand again (smoother produces None).
        """
        # Setup args: no preview mode
        mock_args = MagicMock()
        mock_args.preview = False
        mock_args.config = "config.yaml"
        mock_parse_args.return_value = mock_args

        # Setup camera: returns a frame each call, then stops after N calls
        mock_camera = MagicMock()
        mock_camera.start.return_value = mock_camera

        frame = _make_mock_frame()
        open_palm_landmarks = _make_open_palm_landmarks()

        # Build a sequence of frames:
        # 3 frames no hand -> 3 frames open_palm -> 3 frames no hand
        call_count = [0]
        max_calls = 9

        def camera_read_side_effect():
            call_count[0] += 1
            if call_count[0] > max_calls:
                raise KeyboardInterrupt()
            return True, frame

        mock_camera.read.side_effect = camera_read_side_effect
        mock_camera_cls.return_value = mock_camera

        # Setup detector: returns landmarks based on call sequence
        mock_detector = MagicMock()
        detect_count = [0]

        def detect_side_effect(f, ts):
            detect_count[0] += 1
            # Frames 4-6: return OPEN_PALM landmarks
            if 4 <= detect_count[0] <= 6:
                return open_palm_landmarks
            return []

        mock_detector.detect.side_effect = detect_side_effect
        mock_detector_cls.return_value = mock_detector

        # Run main with logging capture
        with caplog.at_level(logging.INFO, logger="gesture_keys"):
            _main_mod.main()

        # Verify: should see transitions logged
        gesture_messages = [
            r.message for r in caplog.records
            if "Gesture:" in r.message
        ]

        # We expect at most a few transitions:
        # Initial None (after buffer fills), then OPEN_PALM, then back to None
        assert len(gesture_messages) >= 1, (
            f"Expected gesture transition log messages, got: {gesture_messages}"
        )

        # Verify non-transition frames did NOT produce extra log entries
        # With 9 frames total, we should see far fewer than 9 gesture messages
        assert len(gesture_messages) <= 4, (
            f"Too many gesture messages ({len(gesture_messages)}); "
            f"transitions only should produce 2-3 messages"
        )

    @patch.object(_main_mod, "cv2")
    @patch.object(_main_mod, "HandDetector")
    @patch.object(_main_mod, "CameraCapture")
    @patch.object(_main_mod, "parse_args")
    def test_startup_banner_printed(
        self, mock_parse_args, mock_camera_cls, mock_detector_cls,
        mock_cv2, capsys
    ):
        """Verify startup banner prints 4 lines: version, camera, config, started."""
        mock_args = MagicMock()
        mock_args.preview = False
        mock_args.config = "config.yaml"
        mock_parse_args.return_value = mock_args

        mock_camera = MagicMock()
        mock_camera.start.return_value = mock_camera
        # Immediately raise KeyboardInterrupt to exit after banner
        mock_camera.read.side_effect = KeyboardInterrupt()
        mock_camera_cls.return_value = mock_camera

        mock_detector = MagicMock()
        mock_detector_cls.return_value = mock_detector

        _main_mod.main()

        captured = capsys.readouterr()
        lines = [l for l in captured.out.strip().split("\n") if l.strip()]

        assert len(lines) == 4, (
            f"Expected 4 banner lines, got {len(lines)}: {lines}"
        )
        assert "Gesture Keys v" in lines[0]
        assert "Camera:" in lines[1]
        assert "Config:" in lines[2]
        assert "gestures loaded" in lines[2]
        assert "Detection started" in lines[3]

    @patch.object(_main_mod, "cv2")
    @patch.object(_main_mod, "HandDetector")
    @patch.object(_main_mod, "CameraCapture")
    @patch.object(_main_mod, "parse_args")
    def test_none_transitions_logged(
        self, mock_parse_args, mock_camera_cls, mock_detector_cls,
        mock_cv2, caplog
    ):
        """Verify that transitions to None are also logged."""
        mock_args = MagicMock()
        mock_args.preview = False
        mock_args.config = "config.yaml"
        mock_parse_args.return_value = mock_args

        mock_camera = MagicMock()
        mock_camera.start.return_value = mock_camera

        frame = _make_mock_frame()
        open_palm_landmarks = _make_open_palm_landmarks()

        call_count = [0]
        max_calls = 9

        def camera_read_side_effect():
            call_count[0] += 1
            if call_count[0] > max_calls:
                raise KeyboardInterrupt()
            return True, frame

        mock_camera.read.side_effect = camera_read_side_effect
        mock_camera_cls.return_value = mock_camera

        mock_detector = MagicMock()
        detect_count = [0]

        def detect_side_effect(f, ts):
            detect_count[0] += 1
            # Frames 1-3: OPEN_PALM landmarks (fills buffer, produces OPEN_PALM)
            if detect_count[0] <= 3:
                return open_palm_landmarks
            # Frames 4-9: no hand (eventually produces None)
            return []

        mock_detector.detect.side_effect = detect_side_effect
        mock_detector_cls.return_value = mock_detector

        with caplog.at_level(logging.INFO, logger="gesture_keys"):
            _main_mod.main()

        gesture_messages = [
            r.message for r in caplog.records
            if "Gesture:" in r.message
        ]

        # Should include a "Gesture: None" message (transition from OPEN_PALM to None)
        none_messages = [m for m in gesture_messages if "None" in m]
        assert len(none_messages) >= 1, (
            f"Expected at least one None transition, got messages: {gesture_messages}"
        )
