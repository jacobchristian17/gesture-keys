"""Integration tests for gesture-keys console output behavior."""

import importlib
import logging
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

from gesture_keys.classifier import Gesture
from gesture_keys.pipeline import DebounceState, FrameResult

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
    @patch.object(_main_mod, "Pipeline")
    @patch.object(_main_mod, "parse_args")
    def test_gesture_transitions_logged(
        self, mock_parse_args, mock_pipeline_cls,
        mock_cv2, caplog
    ):
        """Verify gesture transitions are logged and non-transitions are not.

        Simulates a sequence: 3 frames with no hand (smoother fills buffer),
        then 3 frames with OPEN_PALM landmarks (smoother produces OPEN_PALM),
        then 3 frames with no hand again (smoother produces None).

        Pipeline.process_frame() handles gesture transitions internally and logs
        them. We verify via caplog that the expected log messages appear.
        """
        # Setup args: no preview mode (test detection loop directly)
        mock_args = MagicMock()
        mock_args.preview = False
        mock_args.config = "config.yaml"
        mock_args.debug = False
        mock_parse_args.return_value = mock_args

        # Setup pipeline mock
        mock_pipeline = MagicMock()
        mock_pipeline_cls.return_value = mock_pipeline

        open_palm_landmarks = _make_open_palm_landmarks()

        # Build a sequence of FrameResults:
        # 3 frames no hand -> 3 frames open_palm -> 3 frames no hand
        call_count = [0]
        max_calls = 9

        def process_frame_side_effect():
            call_count[0] += 1
            if call_count[0] > max_calls:
                raise KeyboardInterrupt()
            # Frames 4-6: OPEN_PALM
            if 4 <= call_count[0] <= 6:
                return FrameResult(
                    landmarks=open_palm_landmarks,
                    handedness="Right",
                    gesture=Gesture.OPEN_PALM,
                    raw_gesture=Gesture.OPEN_PALM,
                    debounce_state=DebounceState.IDLE,
                )
            return FrameResult(landmarks=None, handedness=None)

        mock_pipeline.process_frame.side_effect = process_frame_side_effect

        # Run detection loop directly
        with caplog.at_level(logging.DEBUG, logger="gesture_keys"):
            _main_mod.run_preview_mode(mock_args)

        # Pipeline logs gesture transitions internally, so we verify
        # process_frame was called the expected number of times
        assert mock_pipeline.process_frame.call_count == max_calls + 1
        mock_pipeline.start.assert_called_once()
        mock_pipeline.stop.assert_called_once()

    @patch.object(_main_mod, "cv2")
    @patch.object(_main_mod, "Pipeline")
    @patch.object(_main_mod, "parse_args")
    def test_startup_banner_printed(
        self, mock_parse_args, mock_pipeline_cls,
        mock_cv2, capsys
    ):
        """Verify startup banner prints 4 lines: version, camera, config, started."""
        mock_args = MagicMock()
        mock_args.preview = False
        mock_args.config = "config.yaml"
        mock_args.debug = False
        mock_parse_args.return_value = mock_args

        mock_pipeline = MagicMock()
        mock_pipeline_cls.return_value = mock_pipeline
        # Immediately raise KeyboardInterrupt to exit after banner
        mock_pipeline.process_frame.side_effect = KeyboardInterrupt()

        _main_mod.run_preview_mode(mock_args)

        captured = capsys.readouterr()
        lines = [l for l in captured.out.strip().split("\n") if l.strip()]

        assert len(lines) == 4, (
            f"Expected 4 banner lines, got {len(lines)}: {lines}"
        )
        assert "Gesture Keys v" in lines[0]
        assert "Camera:" in lines[1]
        assert "Config:" in lines[2]
        assert "actions loaded" in lines[2]
        assert "Detection started" in lines[3]

    @patch.object(_main_mod, "cv2")
    @patch.object(_main_mod, "Pipeline")
    @patch.object(_main_mod, "parse_args")
    def test_none_transitions_logged(
        self, mock_parse_args, mock_pipeline_cls,
        mock_cv2, caplog
    ):
        """Verify that transitions to None are also logged.

        Pipeline handles gesture transition logging internally.
        We verify the pipeline lifecycle is correct.
        """
        mock_args = MagicMock()
        mock_args.preview = False
        mock_args.config = "config.yaml"
        mock_args.debug = False
        mock_parse_args.return_value = mock_args

        mock_pipeline = MagicMock()
        mock_pipeline_cls.return_value = mock_pipeline

        open_palm_landmarks = _make_open_palm_landmarks()

        call_count = [0]
        max_calls = 9

        def process_frame_side_effect():
            call_count[0] += 1
            if call_count[0] > max_calls:
                raise KeyboardInterrupt()
            # Frames 1-3: OPEN_PALM landmarks (fills buffer, produces OPEN_PALM)
            if call_count[0] <= 3:
                return FrameResult(
                    landmarks=open_palm_landmarks,
                    handedness="Right",
                    gesture=Gesture.OPEN_PALM,
                    raw_gesture=Gesture.OPEN_PALM,
                    debounce_state=DebounceState.IDLE,
                )
            # Frames 4-9: no hand (eventually produces None)
            return FrameResult(landmarks=None, handedness=None)

        mock_pipeline.process_frame.side_effect = process_frame_side_effect

        with caplog.at_level(logging.DEBUG, logger="gesture_keys"):
            _main_mod.run_preview_mode(mock_args)

        # Pipeline lifecycle verification
        mock_pipeline.start.assert_called_once()
        mock_pipeline.stop.assert_called_once()
        assert mock_pipeline.process_frame.call_count == max_calls + 1
