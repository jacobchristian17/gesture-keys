"""System tray integration for gesture-keys using pystray."""

import logging
import os
import subprocess
import sys
import threading
import time

import pystray
from PIL import Image, ImageDraw

from gesture_keys.config import load_config
from gesture_keys.pipeline import Pipeline

logger = logging.getLogger("gesture_keys")


class TrayApp:
    """System tray application wrapping the gesture detection pipeline.

    Provides Active/Inactive toggle, Edit Config, and Quit menu items
    via a pystray system tray icon.

    Args:
        config_path: Path to the YAML configuration file.
    """

    def __init__(self, config_path: str, debug: bool = False) -> None:
        self._config_path = os.path.abspath(config_path)
        self._debug = debug
        self._active = threading.Event()
        self._active.set()  # Start active
        self._shutdown = threading.Event()
        self._camera_active = threading.Event()
        self._icon = None
        self._detection_thread = None

    def _create_icon_image(self) -> Image.Image:
        """Create a 64x64 RGBA icon image with a green circle.

        Returns:
            PIL Image suitable for use as a tray icon.
        """
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([8, 8, 56, 56], fill="#00cc66")
        return img

    def _build_menu(self) -> pystray.Menu:
        """Build the system tray context menu.

        Returns:
            pystray.Menu with Active toggle, Edit Config, and Quit items.
        """
        return pystray.Menu(
            pystray.MenuItem(
                text=lambda item: "Active" if self._active.is_set() else "Inactive",
                action=self._on_toggle,
                checked=lambda item: self._active.is_set(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Edit Config", self._on_edit_config),
            pystray.MenuItem(
                text=lambda item: "View Camera (Running)" if self._camera_active.is_set() else "View Camera",
                action=self._on_view_camera,
                enabled=lambda item: not self._camera_active.is_set(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        )

    def _on_toggle(self, icon, item) -> None:
        """Toggle detection between active and inactive states."""
        if self._active.is_set():
            self._active.clear()
        else:
            self._active.set()

    def _on_edit_config(self, icon, item) -> None:
        """Open the config file in the default editor."""
        os.startfile(self._config_path)

    def _on_view_camera(self, icon, item) -> None:
        """Stop detection, spawn camera preview subprocess, monitor for exit."""
        try:
            self._camera_active.set()
            self._active.clear()
            icon.notify("Opening camera preview...", "Gesture Keys")

            if getattr(sys, 'frozen', False):
                cmd = [sys.executable, '--view-camera', '--config', self._config_path]
            else:
                cmd = [sys.executable, '-m', 'gesture_keys', '--view-camera', '--config', self._config_path]

            if self._debug:
                cmd.append('--debug')

            kwargs = {}
            if sys.platform == 'win32':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

            proc = subprocess.Popen(cmd, **kwargs)
            icon.update_menu()

            threading.Thread(
                target=self._monitor_camera_process, args=(proc,), daemon=True
            ).start()
        except Exception:
            logger.exception("Failed to spawn camera subprocess")
            self._camera_active.clear()
            self._active.set()
            icon.notify("Failed to open camera preview. Check logs for details.", "Gesture Keys")
            icon.update_menu()

    def _monitor_camera_process(self, proc) -> None:
        """Wait for camera subprocess to exit, then resume detection."""
        proc.wait()
        self._camera_active.clear()
        self._active.set()
        self._icon.update_menu()
        self._icon.notify("Camera closed. Detection resumed.", "Gesture Keys")

    def _on_quit(self, icon, item) -> None:
        """Shut down the application cleanly.

        Sets shutdown event, unblocks any active.wait() to prevent deadlock,
        and stops the tray icon.
        """
        self._shutdown.set()
        self._active.set()  # Unblock wait to prevent deadlock
        icon.stop()

    def _detection_loop(self) -> None:
        """Run the gesture detection pipeline in a background thread.

        Outer loop checks shutdown/active state. Inner loop runs detection.
        Pipeline is released when going inactive or shutting down.
        """
        while not self._shutdown.is_set():
            # Wait for active state, checking shutdown periodically
            if not self._active.wait(timeout=0.5):
                continue

            # Double-check shutdown after wait
            if self._shutdown.is_set():
                break

            # Load config with error handling before Pipeline creation
            try:
                config = load_config(self._config_path)
            except Exception as e:
                logger.error("Failed to load config: %s", e)
                time.sleep(1.0)
                continue

            pipeline = Pipeline(self._config_path)
            pipeline.start()
            try:
                while self._active.is_set() and not self._shutdown.is_set() and not self._camera_active.is_set():
                    pipeline.process_frame()
            finally:
                pipeline.stop()

    def _start_detection(self) -> None:
        """Start the detection loop in a daemon thread."""
        self._detection_thread = threading.Thread(
            target=self._detection_loop, daemon=True
        )
        self._detection_thread.start()

    def _on_setup(self, icon) -> None:
        """Setup callback after icon is visible. Starts detection and notifies."""
        icon.visible = True
        icon.notify("Gesture Keys is running", "Gesture Keys")
        self._start_detection()

    def run(self) -> None:
        """Run the tray application.

        Creates the pystray icon and starts the detection loop.
        Blocks until the icon is stopped (via Quit menu item).
        """
        self._icon = pystray.Icon(
            "gesture-keys",
            icon=self._create_icon_image(),
            title="Gesture Keys",
            menu=self._build_menu(),
        )
        self._icon.run(setup=self._on_setup)
