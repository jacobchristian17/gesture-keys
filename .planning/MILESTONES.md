# Milestones

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

