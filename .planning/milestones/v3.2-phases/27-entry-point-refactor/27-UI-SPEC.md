---
phase: 27
slug: entry-point-refactor
status: draft
shadcn_initialized: false
preset: none
created: 2026-03-30
---

# Phase 27 — UI Design Contract

> Visual and interaction contract for entry point refactor. This phase targets a Python CLI application with an OpenCV camera preview window — no web UI. The contract covers console output formatting and camera window behavior across mode routing.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none |
| Preset | not applicable |
| Component library | OpenCV (cv2) for camera preview |
| Icon library | none |
| Font | System terminal font (console), cv2.FONT_HERSHEY_SIMPLEX (preview) |

---

## Spacing Scale

Not applicable — this phase has no web layout. OpenCV preview spacing is defined in `preview.py` (BAR_HEIGHT = 40px, text insets at 10px). No changes to preview layout in this phase.

Exceptions: none

---

## Typography

### Console Output

| Role | Format | Example |
|------|--------|---------|
| Banner title | Plain print, line 1 | `Gesture Keys v0.x.x` |
| Banner detail | Plain print, lines 2-3 | `Camera: index 0` / `Config: config.yaml (5 actions loaded)` |
| Banner start | Plain print, line 4 | `Detection started...` |
| Deprecation warning | Plain print to stdout | `Warning: --preview is deprecated and will be removed. Camera preview is now the default mode.` |
| Log INFO | logging module, INFO level | `SIGNAL fire gesture=fist` |
| Log DEBUG | logging module, DEBUG level (--debug only) | `FRAME raw=fist smooth=fist state=IDLE` |

### OpenCV Preview (unchanged from existing)

| Role | Size | Weight | Font |
|------|------|--------|------|
| Gesture label | 0.7 scale | thickness 2 | HERSHEY_SIMPLEX |
| FPS counter | 0.6 scale | thickness 1 | HERSHEY_SIMPLEX |
| Debounce state | 0.5 scale | thickness 1 | HERSHEY_SIMPLEX |
| Hand indicator | 0.6 scale | thickness 1 | HERSHEY_SIMPLEX |

No changes to preview typography in this phase.

---

## Color

### Console Output

Console output uses no color codes. All output is plain text via `print()` and the `logging` module.

### OpenCV Preview (unchanged from existing)

| Element | BGR Value | Purpose |
|---------|-----------|---------|
| Bottom bar background | (50, 50, 50) | Dark gray status bar |
| Gesture label | (255, 255, 255) | White text, always visible |
| FPS counter | (0, 255, 0) | Green, quick visual scan |
| IDLE state | (128, 128, 128) | Gray, inactive |
| ACTIVATING state | (0, 255, 255) | Yellow, pending |
| COOLDOWN state | (0, 128, 255) | Orange, waiting |
| FIRED state | (0, 255, 0) | Green, action taken |
| Left hand indicator | (255, 200, 0) | Cyan-blue |
| Right hand indicator | (0, 200, 255) | Orange |

No changes to preview colors in this phase.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Banner line 1 | `Gesture Keys v{version}` |
| Banner line 2 | `Camera: index {N}` |
| Banner line 3 | `Config: {path} ({N} actions loaded)` |
| Banner line 4 | `Detection started...` |
| Deprecation warning (--preview) | `Warning: --preview is deprecated and will be removed. Camera preview is now the default mode.` |
| Window title | `Gesture Keys` (existing, unchanged) |

### Mode-Specific Console Behavior

| Mode | Banner | Console Logging | Camera Window |
|------|--------|-----------------|---------------|
| dev-camera (`python -m gesture_keys`) | Yes, via `print_banner()` | INFO level | Yes |
| tray-headless (frozen exe or `--tray`) | No banner | No console (hidden) | No |
| camera-subprocess (`--view-camera`) | No banner | INFO level | Yes |

### Empty/Error States

| State | Behavior | Source |
|-------|----------|--------|
| No camera found | Existing Pipeline error handling (unchanged) | Pipeline.start() |
| Config not found | Existing load_config error (unchanged) | load_config() |
| Invalid flag combination | argparse default error message | argparse |

### Destructive Actions

None in this phase. Mode routing is non-destructive selection.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| not applicable | none | not applicable |

No component registries — this is a Python CLI application.

---

## Interaction Contract

### Mode Routing Logic

```
main()
  |-- frozen exe? --> run_tray_mode()
  |-- --tray flag? --> run_tray_mode()
  |-- --view-camera flag? --> run_camera_mode()  [no banner, INFO console, camera window]
  |-- default --> run_dev_mode()  [banner, INFO console, camera window]
```

### Flag Behavior

| Flag | Visible | Effect |
|------|---------|--------|
| (none) | Yes | Default dev mode with camera preview |
| `--preview` | Yes (deprecated) | Print deprecation warning, then run dev mode |
| `--tray` | Yes | Force tray mode from Python (no frozen exe needed) |
| `--view-camera` | No (SUPPRESS) | Camera subprocess mode for Phase 28 tray integration |
| `--debug` | Yes | Upgrade console logging from INFO to DEBUG in all modes |
| `--config PATH` | Yes | Config file path (existing, unchanged) |

### Exit Behavior (unchanged)

| Trigger | Action |
|---------|--------|
| ESC key in preview | Break loop, cleanup, exit |
| Close window (X button) | Detected via `cv2.getWindowProperty`, break loop |
| Ctrl+C | KeyboardInterrupt caught, cleanup, exit |
| Tray "Exit" | TrayApp handles shutdown |

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
