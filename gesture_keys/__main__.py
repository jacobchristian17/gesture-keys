"""CLI entry point for gesture-keys: python -m gesture_keys."""

import argparse
import logging
import os
import sys
import time

import cv2

from gesture_keys import __version__
from gesture_keys.config import load_config
from gesture_keys.pipeline import Pipeline
from gesture_keys.preview import draw_hand_landmarks, render_preview

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
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug logging (shows every frame's gesture and state)",
    )
    return parser.parse_args()


def hide_console_window():
    """Hide the console window on Windows (tray mode only)."""
    if sys.platform == 'win32':
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE


def run_tray_mode(args):
    """Run in system tray mode (default, no preview)."""
    hide_console_window()
    from gesture_keys.tray import TrayApp
    app = TrayApp(config_path=args.config)
    app.run()


def print_banner(config, config_path):
    """Print a concise 4-line startup banner.

    Args:
        config: AppConfig instance.
        config_path: Path string used to load the config.
    """
    gesture_count = len(config.actions)
    print(f"Gesture Keys v{__version__}")
    print(f"Camera: index {config.camera_index}")
    print(f"Config: {config_path} ({gesture_count} actions loaded)")
    print("Detection started...")


def run_preview_mode(args):
    """Run the gesture detection loop with camera preview.

    Args:
        args: Parsed argparse namespace with config and preview fields.
    """
    config = load_config(args.config)
    print_banner(config, args.config)

    # Setup logging: [HH:MM:SS] format per CONTEXT.md
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        format="[%(asctime)s] %(message)s",
        datefmt="%H:%M:%S",
        level=log_level,
    )

    pipeline = Pipeline(args.config)
    pipeline.start()

    prev_time = time.perf_counter()
    fps = 0.0
    try:
        while True:
            # FPS calculation
            current_time = time.perf_counter()
            dt = current_time - prev_time
            if dt > 0:
                fps = 1.0 / dt
            prev_time = current_time

            result = pipeline.process_frame()
            if not result.frame_valid:
                continue

            # Per-frame debug logging (preview-only)
            if args.debug and result.landmarks:
                motion_info = ""
                if result.motion_state and result.motion_state.moving:
                    motion_info = f" motion={result.motion_state.direction.value if result.motion_state.direction else '?'}"
                logger.debug(
                    "FRAME raw=%s smooth=%s state=%s%s",
                    result.raw_gesture.value if result.raw_gesture else "None",
                    result.gesture.value if result.gesture else "None",
                    result.debounce_state.value,
                    motion_info,
                )

            # Log orchestrator signals at INFO level (visible in normal --preview)
            if result.orchestrator and result.orchestrator.signals:
                for sig in result.orchestrator.signals:
                    parts = [f"SIGNAL {sig.action.value}"]
                    if sig.gesture:
                        parts.append(f"gesture={sig.gesture.value}")
                    if sig.direction:
                        parts.append(f"dir={sig.direction.value}")
                    if sig.second_gesture:
                        parts.append(f"seq={sig.second_gesture.value}")
                    logger.info(" ".join(parts))

            # Log motion state transitions
            if result.motion_state and result.motion_state.moving:
                if not getattr(run_preview_mode, '_was_moving', False):
                    dir_name = result.motion_state.direction.value if result.motion_state.direction else "unknown"
                    logger.info("MOTION started dir=%s", dir_name)
                    run_preview_mode._was_moving = True
            else:
                if getattr(run_preview_mode, '_was_moving', False):
                    run_preview_mode._was_moving = False

            # Preview rendering
            if args.preview:
                frame = pipeline.last_frame
                if result.landmarks:
                    draw_hand_landmarks(frame, result.landmarks)
                gesture_label = result.gesture.value if result.gesture else None
                render_preview(
                    frame, gesture_label, fps,
                    debounce_state=result.debounce_state.value,
                    handedness=result.handedness,
                )

                key = cv2.waitKey(1) & 0xFF
                if key == 27:
                    break
                try:
                    if cv2.getWindowProperty("Gesture Keys", cv2.WND_PROP_VISIBLE) < 1:
                        break
                except cv2.error:
                    break

    except KeyboardInterrupt:
        pass
    finally:
        pipeline.stop()
        if args.preview:
            cv2.destroyAllWindows()


def main():
    """Run gesture-keys: tray mode by default, preview mode with --preview."""
    args = parse_args()
    # Resolve config path relative to exe directory when frozen (PyInstaller)
    if not os.path.isabs(args.config) and getattr(sys, 'frozen', False):
        base = os.path.dirname(os.path.abspath(sys.argv[0]))
        args.config = os.path.join(base, args.config)
    if args.preview:
        run_preview_mode(args)
    else:
        run_tray_mode(args)


if __name__ == "__main__":
    main()
