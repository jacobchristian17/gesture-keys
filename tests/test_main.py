"""Tests for __main__.py entry point mode routing."""

import sys
from unittest.mock import patch, MagicMock

import pytest

from gesture_keys.__main__ import parse_args, main


class TestParseArgs:
    """Tests for parse_args() flag handling."""

    def test_no_flags_defaults(self):
        """No flags: preview=False, tray=False, view_camera=False, debug=False, config=config.yaml."""
        with patch("sys.argv", ["gesture_keys"]):
            args = parse_args()
        assert args.preview is False
        assert args.tray is False
        assert args.view_camera is False
        assert args.debug is False
        assert args.config == "config.yaml"

    def test_tray_flag(self):
        """--tray sets tray=True."""
        with patch("sys.argv", ["gesture_keys", "--tray"]):
            args = parse_args()
        assert args.tray is True

    def test_view_camera_flag(self):
        """--view-camera sets view_camera=True."""
        with patch("sys.argv", ["gesture_keys", "--view-camera"]):
            args = parse_args()
        assert args.view_camera is True

    def test_preview_flag(self):
        """--preview sets preview=True."""
        with patch("sys.argv", ["gesture_keys", "--preview"]):
            args = parse_args()
        assert args.preview is True

    def test_debug_flag(self):
        """--debug sets debug=True."""
        with patch("sys.argv", ["gesture_keys", "--debug"]):
            args = parse_args()
        assert args.debug is True

    def test_config_flag(self):
        """--config sets custom config path."""
        with patch("sys.argv", ["gesture_keys", "--config", "custom.yaml"]):
            args = parse_args()
        assert args.config == "custom.yaml"


class TestMainRouting:
    """Tests for main() mode routing logic."""

    def test_frozen_routes_to_tray(self):
        """Frozen exe routes to run_tray_mode."""
        with patch("gesture_keys.__main__.run_tray_mode") as mock_tray, \
             patch("gesture_keys.__main__.parse_args") as mock_parse, \
             patch.object(sys, "frozen", True, create=True):
            mock_parse.return_value = MagicMock(
                preview=False, tray=False, view_camera=False,
                config="config.yaml", debug=False,
            )
            main()
            mock_tray.assert_called_once()

    def test_tray_flag_routes_to_tray(self):
        """--tray flag routes to run_tray_mode when not frozen."""
        with patch("gesture_keys.__main__.run_tray_mode") as mock_tray, \
             patch("gesture_keys.__main__.parse_args") as mock_parse:
            mock_parse.return_value = MagicMock(
                preview=False, tray=True, view_camera=False,
                config="config.yaml", debug=False,
            )
            # Ensure not frozen
            if hasattr(sys, "frozen"):
                delattr(sys, "frozen")
            main()
            mock_tray.assert_called_once()

    def test_view_camera_routes_to_camera(self):
        """--view-camera flag routes to run_camera_mode."""
        with patch("gesture_keys.__main__.run_camera_mode") as mock_camera, \
             patch("gesture_keys.__main__.parse_args") as mock_parse:
            mock_parse.return_value = MagicMock(
                preview=False, tray=False, view_camera=True,
                config="config.yaml", debug=False,
            )
            if hasattr(sys, "frozen"):
                delattr(sys, "frozen")
            main()
            mock_camera.assert_called_once()

    def test_no_flags_routes_to_dev(self):
        """No flags and not frozen routes to run_dev_mode."""
        with patch("gesture_keys.__main__.run_dev_mode") as mock_dev, \
             patch("gesture_keys.__main__.parse_args") as mock_parse:
            mock_parse.return_value = MagicMock(
                preview=False, tray=False, view_camera=False,
                config="config.yaml", debug=False,
            )
            if hasattr(sys, "frozen"):
                delattr(sys, "frozen")
            main()
            mock_dev.assert_called_once()

    def test_preview_flag_warns_then_dev(self, capsys):
        """--preview prints deprecation warning then routes to run_dev_mode."""
        with patch("gesture_keys.__main__.run_dev_mode") as mock_dev, \
             patch("gesture_keys.__main__.parse_args") as mock_parse:
            mock_parse.return_value = MagicMock(
                preview=True, tray=False, view_camera=False,
                config="config.yaml", debug=False,
            )
            if hasattr(sys, "frozen"):
                delattr(sys, "frozen")
            main()
            mock_dev.assert_called_once()
            captured = capsys.readouterr()
            assert "deprecated" in captured.out.lower()

    def test_frozen_takes_priority_over_tray_flag(self):
        """When frozen and --tray, frozen check wins (both route to tray anyway)."""
        with patch("gesture_keys.__main__.run_tray_mode") as mock_tray, \
             patch("gesture_keys.__main__.parse_args") as mock_parse, \
             patch.object(sys, "frozen", True, create=True):
            mock_parse.return_value = MagicMock(
                preview=False, tray=True, view_camera=False,
                config="config.yaml", debug=False,
            )
            main()
            mock_tray.assert_called_once()

    def test_frozen_with_view_camera_routes_to_camera(self):
        """When frozen and --view-camera, routes to run_camera_mode (not tray)."""
        with patch("gesture_keys.__main__.run_tray_mode") as mock_tray, \
             patch("gesture_keys.__main__.run_camera_mode") as mock_camera, \
             patch("gesture_keys.__main__.parse_args") as mock_parse, \
             patch.object(sys, "frozen", True, create=True):
            mock_parse.return_value = MagicMock(
                preview=False, tray=False, view_camera=True,
                config="config.yaml", debug=False,
            )
            main()
            mock_camera.assert_called_once()
            mock_tray.assert_not_called()

    def test_tray_takes_priority_over_view_camera(self):
        """When --tray and --view-camera, --tray wins (elif ordering)."""
        with patch("gesture_keys.__main__.run_tray_mode") as mock_tray, \
             patch("gesture_keys.__main__.run_camera_mode") as mock_camera, \
             patch("gesture_keys.__main__.parse_args") as mock_parse:
            mock_parse.return_value = MagicMock(
                preview=False, tray=True, view_camera=True,
                config="config.yaml", debug=False,
            )
            if hasattr(sys, "frozen"):
                delattr(sys, "frozen")
            main()
            mock_tray.assert_called_once()
            mock_camera.assert_not_called()

    def test_preview_deprecation_message_content(self, capsys):
        """Deprecation warning contains expected text."""
        with patch("gesture_keys.__main__.run_dev_mode"), \
             patch("gesture_keys.__main__.parse_args") as mock_parse:
            mock_parse.return_value = MagicMock(
                preview=True, tray=False, view_camera=False,
                config="config.yaml", debug=False,
            )
            if hasattr(sys, "frozen"):
                delattr(sys, "frozen")
            main()
            captured = capsys.readouterr()
            assert "Camera preview is now the default mode" in captured.out
