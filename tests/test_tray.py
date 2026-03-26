"""Unit tests for TrayApp system tray integration."""

import threading
from unittest.mock import MagicMock, patch

import pytest


class TestTrayCreatesIcon:
    """TrayApp.__init__ creates internal state; run() creates pystray.Icon."""

    def test_tray_creates_icon(self):
        from gesture_keys.tray import TrayApp

        app = TrayApp(config_path="config.yaml")

        # __init__ state checks
        assert app._active.is_set(), "Should start active"
        assert not app._shutdown.is_set(), "Should not be shutdown"
        assert app._icon is None
        assert app._detection_thread is None

    @patch("gesture_keys.tray.pystray")
    def test_run_creates_pystray_icon(self, mock_pystray):
        from gesture_keys.tray import TrayApp

        app = TrayApp(config_path="config.yaml")

        # Make icon.run() a no-op but capture the setup callback
        mock_icon = MagicMock()
        mock_pystray.Icon.return_value = mock_icon

        app.run()

        mock_pystray.Icon.assert_called_once()
        call_kwargs = mock_pystray.Icon.call_args
        assert call_kwargs[0][0] == "gesture-keys"  # name positional arg
        assert call_kwargs[1]["title"] == "Gesture Keys"
        assert app._icon is mock_icon
        mock_icon.run.assert_called_once()


class TestCreateIconImage:
    """_create_icon_image returns a 64x64 RGB Pillow Image."""

    def test_create_icon_image(self):
        from gesture_keys.tray import TrayApp

        app = TrayApp(config_path="config.yaml")
        img = app._create_icon_image()

        assert img.size == (64, 64)
        assert img.mode == "RGBA"


class TestToggleActiveInactive:
    """Calling _on_toggle flips the active Event."""

    def test_toggle_active_inactive(self):
        from gesture_keys.tray import TrayApp

        app = TrayApp(config_path="config.yaml")
        icon_mock = MagicMock()
        item_mock = MagicMock()

        assert app._active.is_set()

        app._on_toggle(icon_mock, item_mock)
        assert not app._active.is_set()

        app._on_toggle(icon_mock, item_mock)
        assert app._active.is_set()


class TestEditConfigOpensFile:
    """_on_edit_config calls os.startfile with config path."""

    @patch("gesture_keys.tray.os.startfile")
    def test_edit_config_opens_file(self, mock_startfile):
        from gesture_keys.tray import TrayApp

        app = TrayApp(config_path="config.yaml")
        icon_mock = MagicMock()
        item_mock = MagicMock()

        app._on_edit_config(icon_mock, item_mock)

        mock_startfile.assert_called_once_with(app._config_path)


class TestQuitSetsShutdownAndStopsIcon:
    """_on_quit sets shutdown, sets active (unblock), and stops icon."""

    def test_quit_sets_shutdown_and_stops_icon(self):
        from gesture_keys.tray import TrayApp

        app = TrayApp(config_path="config.yaml")
        icon_mock = MagicMock()
        item_mock = MagicMock()

        app._on_quit(icon_mock, item_mock)

        assert app._shutdown.is_set()
        assert app._active.is_set(), "Active must be set to unblock wait"
        icon_mock.stop.assert_called_once()


class TestDetectionLoopExitsOnShutdown:
    """When shutdown is set immediately, detection loop exits without creating Pipeline."""

    @patch("gesture_keys.tray.Pipeline")
    @patch("gesture_keys.tray.load_config")
    def test_detection_loop_exits_on_shutdown(
        self, mock_load_config, mock_pipeline_cls
    ):
        from gesture_keys.tray import TrayApp

        app = TrayApp(config_path="config.yaml")
        app._shutdown.set()  # Immediate shutdown

        app._detection_loop()

        mock_pipeline_cls.assert_not_called()


class TestDetectionLoopPausesOnInactive:
    """When active is cleared then shutdown is set, loop releases pipeline and exits."""

    @patch("gesture_keys.tray.Pipeline")
    @patch("gesture_keys.tray.load_config")
    def test_detection_loop_pauses_on_inactive(
        self,
        mock_load_config,
        mock_pipeline_cls,
    ):
        from gesture_keys.config import AppConfig
        from gesture_keys.tray import TrayApp

        # Configure mock config
        mock_load_config.return_value = AppConfig()

        # Setup pipeline mock
        mock_pipeline = MagicMock()
        mock_pipeline_cls.return_value = mock_pipeline

        app = TrayApp(config_path="config.yaml")

        # After a few process_frame calls, deactivate then shutdown
        call_count = 0

        def process_frame_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                app._active.clear()  # Go inactive
                app._shutdown.set()  # Then shutdown
            return MagicMock()

        mock_pipeline.process_frame.side_effect = process_frame_side_effect

        app._detection_loop()

        # Pipeline should have been started and stopped
        mock_pipeline.start.assert_called()
        mock_pipeline.stop.assert_called()
