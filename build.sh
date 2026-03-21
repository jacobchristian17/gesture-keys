#!/usr/bin/env bash
# Build GestureKeys.exe via PyInstaller

# Kill running GestureKeys process to release file locks
taskkill //F //IM GestureKeys.exe 2>/dev/null && echo "Stopped running GestureKeys" || true

python build_exe.py
