---
phase: 28
slug: tray-view-camera
status: draft
shadcn_initialized: false
preset: none
created: 2026-03-31
---

# Phase 28 — UI Design Contract

> Visual and interaction contract for "View Camera" tray menu item. This phase targets a Python desktop application using pystray for the system tray and OpenCV for the camera preview subprocess. No web UI.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none |
| Preset | not applicable |
| Component library | pystray (tray menu), OpenCV (camera preview subprocess) |
| Icon library | none |
| Font | System tray default (OS-rendered menu text) |

---

## Spacing Scale

Not applicable -- this phase adds a single menu item to an OS-rendered system tray context menu. Spacing is controlled by the operating system. The camera preview window layout is unchanged from existing `preview.py` (BAR_HEIGHT = 40px).

Exceptions: none

---

## Typography

### System Tray Menu (OS-rendered)

All tray menu text is rendered by the operating system using the system default font. No custom typography control is available or needed.

| Role | Content | Notes |
|------|---------|-------|
| Menu item label (idle) | `View Camera` | Standard OS menu font |
| Menu item label (active) | `View Camera (Running)` | Communicates camera is open; grayed-out/disabled state |

### OpenCV Preview (unchanged)

Camera preview window typography is inherited from existing `preview.py`. No changes in this phase.

---

## Color

### Tray Icon (unchanged)

| Element | Value | Purpose |
|---------|-------|---------|
| Tray icon circle | #00cc66 (green) | Existing 64x64 RGBA icon with green circle |

### Camera Preview (unchanged)

All camera preview colors are inherited from existing `preview.py`. No changes in this phase.

### Menu Item States (OS-rendered)

| State | OS Behavior |
|-------|-------------|
| Enabled | Standard menu item appearance |
| Disabled (camera running) | Grayed-out text, not clickable |

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Menu item (idle) | `View Camera` |
| Menu item (camera running) | `View Camera (Running)` |
| Tray notification on camera open | `Opening camera preview...` |
| Tray notification on camera close | `Camera closed. Detection resumed.` |
| Error: subprocess spawn failed | `Failed to open camera preview. Check logs for details.` |

### Menu Order

The "View Camera" item is inserted between "Edit Config" and "Quit" with a separator:

```
Active / Inactive    (toggle, existing)
---
Edit Config          (existing)
View Camera          (new)
---
Quit                 (existing)
```

### States

| State | Menu Item Text | Menu Item Enabled | Detection | Camera |
|-------|---------------|-------------------|-----------|--------|
| Normal (idle) | `View Camera` | Yes | Running | Not running |
| Camera opening | `View Camera (Running)` | No | Stopped | Starting |
| Camera running | `View Camera (Running)` | No | Stopped | Running |
| Camera closed | `View Camera` | Yes | Restarting | Not running |

### Empty/Error States

| State | Behavior | User Sees |
|-------|----------|-----------|
| Camera in use by another app | Subprocess fails, tray resumes detection | Notification: `Failed to open camera preview. Check logs for details.` |
| Subprocess crashes | Wait thread detects exit, tray resumes detection | Notification: `Camera closed. Detection resumed.` |
| User closes camera window | Subprocess exits cleanly, tray resumes | Notification: `Camera closed. Detection resumed.` |
| User clicks "View Camera" while already running | Menu item is disabled | No action (grayed out) |

### Destructive Actions

None. "View Camera" temporarily pauses detection but automatically resumes -- non-destructive.

---

## Interaction Contract

### Click Flow

```
User clicks "View Camera"
  --> Menu item disabled, text changes to "View Camera (Running)"
  --> Tray notification: "Opening camera preview..."
  --> Pipeline.stop() called (releases camera, clears stuck keys)
  --> subprocess.Popen spawns camera process
  --> Background thread calls Popen.wait()
  --> User interacts with camera preview window
  --> User closes camera window (ESC or X button)
  --> Popen.wait() returns
  --> Detection loop restarts (Pipeline recreated)
  --> Menu item re-enabled, text changes back to "View Camera"
  --> Tray notification: "Camera closed. Detection resumed."
```

### Subprocess Command

| Context | Command |
|---------|---------|
| Python dev mode | `sys.executable -m gesture_keys --view-camera --config {path}` |
| Frozen exe | `sys.executable --view-camera --config {path}` |

### Thread Model

| Thread | Purpose |
|--------|---------|
| Main thread | pystray event loop (unchanged) |
| Detection thread | Paused during camera, resumes after |
| Camera monitor thread | Calls `Popen.wait()`, triggers resume on exit |

### Menu Refresh

pystray requires `icon.update_menu()` after state changes to reflect enabled/disabled and text changes.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| not applicable | none | not applicable |

No component registries -- this is a Python desktop application.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
