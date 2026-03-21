"""Camera capture and hand detection for gesture-keys."""

import logging
import os
import threading
import urllib.request

import cv2
import mediapipe as mp

logger = logging.getLogger(__name__)

# MediaPipe Task API imports
BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)


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


class HandDetector:
    """MediaPipe HandLandmarker wrapper with right-hand filtering.

    Uses the Task API in VIDEO running mode. Only right-hand landmarks
    are returned; left hands are silently ignored.
    """

    def __init__(self, model_path: str = "models/hand_landmarker.task"):
        self._ensure_model(model_path)

        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=VisionRunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = HandLandmarker.create_from_options(options)
        self._last_timestamp_ms = -1

    @staticmethod
    def _ensure_model(model_path: str) -> None:
        """Download the model file if it does not exist."""
        if os.path.exists(model_path):
            return

        model_dir = os.path.dirname(model_path)
        if model_dir:
            os.makedirs(model_dir, exist_ok=True)

        logger.info("Downloading hand landmarker model to %s ...", model_path)

        def _progress(block_num, block_size, total_size):
            if total_size > 0:
                pct = min(100, block_num * block_size * 100 // total_size)
                if block_num % 50 == 0:
                    logger.info("  Download progress: %d%%", pct)

        urllib.request.urlretrieve(MODEL_URL, model_path, reporthook=_progress)
        logger.info("Model downloaded successfully.")

    def detect(self, frame, timestamp_ms: int) -> list:
        """Detect right-hand landmarks from a BGR frame.

        Args:
            frame: BGR numpy array from OpenCV.
            timestamp_ms: Strictly monotonic timestamp in milliseconds.

        Returns:
            List of 21 landmarks for the first right hand, or empty list.

        Raises:
            ValueError: If timestamp_ms is not strictly greater than the previous call.
        """
        if timestamp_ms <= self._last_timestamp_ms:
            raise ValueError(
                f"Timestamps must be strictly monotonic: "
                f"got {timestamp_ms}, last was {self._last_timestamp_ms}"
            )

        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)
        self._last_timestamp_ms = timestamp_ms

        # Filter for right hand only
        for i, handedness in enumerate(result.handedness):
            if handedness[0].category_name == "Right":
                return result.hand_landmarks[i]

        return []

    def close(self):
        """Release the HandLandmarker resource."""
        self._landmarker.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
