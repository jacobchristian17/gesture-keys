# Milestones

## v1.2 Continuous and Seamless Commands (Shipped: 2026-03-23)

**Phases completed:** 3 phases, 8 plans
**Lines of code:** 6,661 Python (total project)
**Timeline:** 3 days (2026-03-21 → 2026-03-24)
**Commits:** 108
**Git range:** e121508..0df104d

**Key accomplishments:**
- Direct gesture-to-gesture transitions without returning to "none" first (COOLDOWN->ACTIVATING path)
- Color-coded debounce state indicator (IDLE/ACTIVATING/COOLDOWN) in preview window
- Swipe-to-static transition latency reduced from ~1.3s to ~300ms via exit resets and settling frame reduction
- Tuned real-world defaults (activation_delay 0.15s, cooldown 0.3s, smoothing_window 2, settling_frames 3)
- Per-gesture cooldown overrides configurable in config.yaml
- Static-first priority gate preventing swipe detection from preempting static gestures

---

## v1.0 MVP (Shipped: 2026-03-21)

**Phases completed:** 3 phases, 7 plans
**Lines of code:** 2,949 Python
**Timeline:** 1 day (2026-03-21)

**Key accomplishments:**
- 6-gesture classifier from MediaPipe hand landmarks with priority-ordered rules and per-gesture thresholds
- Threaded camera capture with right-hand-only filtering via MediaPipe Task API
- Preview window with 21-landmark skeleton overlay, gesture label, and FPS counter
- Debounce state machine (activate/cooldown) firing keyboard commands via pynput in any foreground app
- Config hot-reload without restart, YAML-based gesture-to-key mappings
- System tray app with Active/Inactive toggle, Edit Config, and clean Quit

---

