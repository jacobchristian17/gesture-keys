"""Unit tests for TrayApp system tray integration."""

import subprocess
import sys
import threading
from unittest.mock import MagicMock, patch, call

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


class TestViewCamera:
    """Tests for View Camera lifecycle: spawn, monitor, resume."""

    def test_init_has_camera_active_event(self):
        """TrayApp has _camera_active event, initially not set."""
        from gesture_keys.tray import TrayApp

        app = TrayApp(config_path="config.yaml")
        assert hasattr(app, "_camera_active")
        assert not app._camera_active.is_set()

    def test_build_menu_has_view_camera_item(self):
        """_build_menu contains a View Camera menu item."""
        from gesture_keys.tray import TrayApp

        app = TrayApp(config_path="config.yaml")
        menu = app._build_menu()

        # pystray.Menu stores items; find one with "View Camera" text
        found = False
        for item in menu:
            # MenuItem with callable text: invoke it
            if hasattr(item, "_text") and callable(item._text):
                text = item._text(item)
                if "View Camera" in text:
                    found = True
                    break
            elif hasattr(item, "text") and callable(item.text):
                text = item.text(item)
                if "View Camera" in text:
                    found = True
                    break
        assert found, "View Camera item not found in menu"

    @patch("gesture_keys.tray.threading.Thread")
    @patch("gesture_keys.tray.subprocess.Popen")
    def test_on_view_camera_sets_state_and_spawns(self, mock_popen, mock_thread):
        """_on_view_camera sets camera_active, clears active, calls Popen."""
        from gesture_keys.tray import TrayApp

        app = TrayApp(config_path="config.yaml")
        icon_mock = MagicMock()
        item_mock = MagicMock()
        app._icon = icon_mock

        mock_popen.return_value = MagicMock()
        mock_thread.return_value = MagicMock()  # Prevent monitor thread from running

        app._on_view_camera(icon_mock, item_mock)

        assert app._camera_active.is_set()
        assert not app._active.is_set()
        mock_popen.assert_called_once()

        # Check command includes --view-camera and --config
        cmd = mock_popen.call_args[0][0]
        assert "--view-camera" in cmd
        assert "--config" in cmd

        # Verify monitor thread was started
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()

    @patch("gesture_keys.tray.threading.Thread")
    @patch("gesture_keys.tray.subprocess.Popen")
    def test_on_view_camera_command_non_frozen(self, mock_popen, mock_thread):
        """Non-frozen: command includes '-m', 'gesture_keys'."""
        from gesture_keys.tray import TrayApp

        # Ensure not frozen
        if hasattr(sys, "frozen"):
            delattr(sys, "frozen")

        app = TrayApp(config_path="config.yaml")
        icon_mock = MagicMock()
        app._icon = icon_mock
        mock_popen.return_value = MagicMock()
        mock_thread.return_value = MagicMock()

        app._on_view_camera(icon_mock, MagicMock())

        cmd = mock_popen.call_args[0][0]
        assert "-m" in cmd
        assert "gesture_keys" in cmd
        assert "--view-camera" in cmd
        assert "--debug" not in cmd

    @patch("gesture_keys.tray.threading.Thread")
    @patch("gesture_keys.tray.subprocess.Popen")
    def test_on_view_camera_command_non_frozen_with_debug(self, mock_popen, mock_thread):
        """Non-frozen with debug: command includes '--debug'."""
        from gesture_keys.tray import TrayApp

        if hasattr(sys, "frozen"):
            delattr(sys, "frozen")

        app = TrayApp(config_path="config.yaml", debug=True)
        icon_mock = MagicMock()
        app._icon = icon_mock
        mock_popen.return_value = MagicMock()
        mock_thread.return_value = MagicMock()

        app._on_view_camera(icon_mock, MagicMock())

        cmd = mock_popen.call_args[0][0]
        assert "--view-camera" in cmd
        assert "--debug" in cmd

    @patch("gesture_keys.tray.threading.Thread")
    @patch("gesture_keys.tray.subprocess.Popen")
    def test_on_view_camera_command_frozen(self, mock_popen, mock_thread):
        """Frozen: command does NOT include '-m' or 'gesture_keys' module."""
        from gesture_keys.tray import TrayApp

        app = TrayApp(config_path="config.yaml")
        icon_mock = MagicMock()
        app._icon = icon_mock
        mock_popen.return_value = MagicMock()
        mock_thread.return_value = MagicMock()

        with patch.object(sys, "frozen", True, create=True):
            app._on_view_camera(icon_mock, MagicMock())

        cmd = mock_popen.call_args[0][0]
        assert "-m" not in cmd
        assert "--view-camera" in cmd
        assert "--config" in cmd
        assert "--debug" not in cmd

    @patch("gesture_keys.tray.threading.Thread")
    @patch("gesture_keys.tray.subprocess.Popen")
    def test_on_view_camera_command_frozen_with_debug(self, mock_popen, mock_thread):
        """Frozen with debug: command includes '--debug'."""
        from gesture_keys.tray import TrayApp

        app = TrayApp(config_path="config.yaml", debug=True)
        icon_mock = MagicMock()
        app._icon = icon_mock
        mock_popen.return_value = MagicMock()
        mock_thread.return_value = MagicMock()

        with patch.object(sys, "frozen", True, create=True):
            app._on_view_camera(icon_mock, MagicMock())

        cmd = mock_popen.call_args[0][0]
        assert "--view-camera" in cmd
        assert "--debug" in cmd

    def test_monitor_camera_process_resumes_detection(self):
        """_monitor_camera_process clears camera_active, sets active, notifies."""
        from gesture_keys.tray import TrayApp

        app = TrayApp(config_path="config.yaml")
        app._icon = MagicMock()
        app._camera_active.set()
        app._active.clear()

        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0

        app._monitor_camera_process(mock_proc)

        assert not app._camera_active.is_set()
        assert app._active.is_set()
        app._icon.update_menu.assert_called_once()
        app._icon.notify.assert_called_once()
        notify_args = app._icon.notify.call_args[0]
        assert "Camera closed" in notify_args[0]
        assert "Detection resumed" in notify_args[0]

    @patch("gesture_keys.tray.subprocess.Popen", side_effect=OSError("spawn failed"))
    def test_on_view_camera_error_handling(self, mock_popen):
        """On Popen failure, clears camera_active, sets active, notifies error."""
        from gesture_keys.tray import TrayApp

        app = TrayApp(config_path="config.yaml")
        icon_mock = MagicMock()
        app._icon = icon_mock

        app._on_view_camera(icon_mock, MagicMock())

        assert not app._camera_active.is_set(), "camera_active should be cleared on error"
        assert app._active.is_set(), "active should be restored on error"
        # Check error notification
        notify_calls = icon_mock.notify.call_args_list
        error_notified = any(
            "Failed to open camera preview" in str(c) for c in notify_calls
        )
        assert error_notified, "Should notify user of spawn failure"

    @patch("gesture_keys.tray.Pipeline")
    @patch("gesture_keys.tray.load_config")
    def test_detection_loop_exits_on_camera_active(
        self, mock_load_config, mock_pipeline_cls
    ):
        """Detection loop breaks inner loop when _camera_active is set."""
        from gesture_keys.config import AppConfig
        from gesture_keys.tray import TrayApp

        mock_load_config.return_value = AppConfig()
        mock_pipeline = MagicMock()
        mock_pipeline_cls.return_value = mock_pipeline

        app = TrayApp(config_path="config.yaml")

        call_count = 0

        def process_frame_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                app._camera_active.set()  # Simulate camera opening
                app._shutdown.set()  # Also shutdown to exit outer loop
            return MagicMock()

        mock_pipeline.process_frame.side_effect = process_frame_side_effect

        app._detection_loop()

        mock_pipeline.start.assert_called()
        mock_pipeline.stop.assert_called()
        assert call_count >= 3
