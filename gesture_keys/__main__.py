"""CLI entry point for gesture-keys: python -m gesture_keys."""

import argparse
import logging
import time

import cv2

from gesture_keys import __version__
from gesture_keys.classifier import GestureClassifier
from gesture_keys.config import load_config
from gesture_keys.detector import CameraCapture, HandDetector
from gesture_keys.preview import draw_hand_landmarks, render_preview
from gesture_keys.smoother import GestureSmoother

logger = logging.getLogger("gesture_keys")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="gesture_keys",
        description="Hand gesture to keyboard command mapping",
    )
    parser.add_argument(
        "--preview", action="store_true",
        help="Open camera preview window with landmark overlay",
    )
    parser.add_argument(
        "--config", default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    return parser.parse_args()


def print_banner(config, config_path):
    """Print a concise 4-line startup banner.

    Args:
        config: AppConfig instance.
        config_path: Path string used to load the config.
    """
    gesture_count = len(config.gestures)
    print(f"Gesture Keys v{__version__}")
    print(f"Camera: index {config.camera_index}")
    print(f"Config: {config_path} ({gesture_count} gestures loaded)")
    print("Detection started...")


def main():
    """Run the main gesture detection loop."""
    args = parse_args()

    # Load config
    config = load_config(args.config)

    # Print startup banner
    print_banner(config, args.config)

    # Setup logging: [HH:MM:SS] format per CONTEXT.md
    logging.basicConfig(
        format="[%(asctime)s] %(message)s",
        datefmt="%H:%M:%S",
        level=logging.INFO,
    )

    # Create pipeline components
    camera = CameraCapture(config.camera_index).start()
    detector = HandDetector()
    classifier = GestureClassifier(config.gestures)
    smoother = GestureSmoother(config.smoothing_window)

    prev_gesture = None
    prev_time = time.perf_counter()
    fps = 0.0

    try:
        while True:
            ret, frame = camera.read()
            if not ret or frame is None:
                continue

            # Calculate FPS from frame delta
            current_time = time.perf_counter()
            dt = current_time - prev_time
            if dt > 0:
                fps = 1.0 / dt
            prev_time = current_time

            # Detect right-hand landmarks
            timestamp_ms = int(time.time() * 1000)
            landmarks = detector.detect(frame, timestamp_ms)

            # Classify and smooth
            if landmarks:
                raw_gesture = classifier.classify(landmarks)
                gesture = smoother.update(raw_gesture)
            else:
                gesture = smoother.update(None)

            # Log transitions (including None transitions)
            if gesture != prev_gesture:
                gesture_name = gesture.value if gesture else "None"
                logger.info("Gesture: %s", gesture_name)
                prev_gesture = gesture

            # Preview rendering
            if args.preview:
                if landmarks:
                    draw_hand_landmarks(frame, landmarks)
                gesture_label = gesture.value if gesture else None
                render_preview(frame, gesture_label, fps)

                key = cv2.waitKey(1) & 0xFF
                if key == 27:  # ESC
                    break
                # Check if window was closed via X button
                try:
                    if cv2.getWindowProperty("Gesture Keys", cv2.WND_PROP_VISIBLE) < 1:
                        break
                except cv2.error:
                    break

    except KeyboardInterrupt:
        pass
    finally:
        camera.stop()
        detector.close()
        if args.preview:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
