"""Camera capture and hand detection for gesture-keys."""

import logging
import threading

import cv2

logger = logging.getLogger(__name__)


class CameraCapture:
    """Threaded camera capture using OpenCV VideoCapture.

    Reads frames on a daemon thread to avoid blocking the main loop.
    Only the latest frame is kept (no queue buildup).
    """

    def __init__(self, camera_index: int = 0):
        self.cap = cv2.VideoCapture(camera_index)
        if not self.cap.isOpened():
            raise RuntimeError(
                f"Camera index {camera_index} could not be opened"
            )
        self._lock = threading.Lock()
        self._frame = None
        self._ret = False
        self.stopped = False

    def start(self):
        """Start the capture thread. Returns self for chaining."""
        thread = threading.Thread(target=self._update, daemon=True)
        thread.start()
        return self

    def _update(self):
        """Continuously read frames until stopped."""
        while not self.stopped:
            ret, frame = self.cap.read()
            with self._lock:
                self._ret = ret
                self._frame = frame

    def read(self):
        """Return the latest frame as (ret, frame_copy).

        Returns (False, None) if no frame has been captured yet.
        Returns a copy of the frame to avoid exposing the mutable internal reference.
        """
        with self._lock:
            if self._frame is None:
                return False, None
            return self._ret, self._frame.copy()

    def stop(self):
        """Stop the capture thread and release the camera."""
        self.stopped = True
        self.cap.release()
