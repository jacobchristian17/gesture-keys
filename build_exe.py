"""Build GestureKeys.exe using PyInstaller."""

import PyInstaller.__main__
import os
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")

PyInstaller.__main__.run([
    os.path.join(ROOT, "gesture_keys", "__main__.py"),
    "--name=GestureKeys",
    "--noconsole",
    "--onedir",
    # Bundle the model file
    f"--add-data={os.path.join(ROOT, 'models', 'hand_landmarker.task')}{os.pathsep}models",
    # Bundle default config next to exe
    f"--add-data={os.path.join(ROOT, 'config.yaml')}{os.pathsep}.",
    # Hidden imports that PyInstaller may miss
    "--hidden-import=pystray._win32",
    "--hidden-import=PIL._tkinter_finder",
    "--hidden-import=mediapipe",
    "--hidden-import=pynput.keyboard._win32",
    "--hidden-import=pynput.mouse._win32",
    # Collect mediapipe data files
    "--collect-data=mediapipe",
    # Clean build
    "--clean",
    "--noconfirm",
])

print(f"\nBuild complete! Output: {os.path.join(DIST, 'GestureKeys')}")
print("Run: dist\\GestureKeys\\GestureKeys.exe")
