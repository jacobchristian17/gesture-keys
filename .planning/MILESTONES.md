# Milestones

## v2.0 Structured Gesture Architecture (Shipped: 2026-03-25)

**Phases completed:** 4 phases, 9 plans, 2 tasks

**Lines of code:** 54,373 Python (total project)
**Timeline:** 5 days (2026-03-21 → 2026-03-26)
**Git range:** e1736f8..1f183b4

**Key accomplishments:**
- Unified Pipeline class eliminating 90% code duplication between preview and tray modes (~70 and ~29 lines respectively)
- Hierarchical GestureOrchestrator FSM replacing scattered debouncer + main-loop coordination with clean state machine
- ActionResolver + ActionDispatcher with tap and hold_key fire modes, structured gesture-to-action mappings
- Centralized stuck-key prevention across all exit paths (gate expiry, hand switch, distance out-of-range, app toggle)
- Activation gate with configurable arm/disarm, bypass mode (default off), and hot-reload support
- App-controlled tap-repeat at 33Hz fixing Windows SendInput non-repeat behavior for hold_key mode

---

## v1.3 Left Hand Support (Shipped: 2026-03-24)

**Phases completed:** 3 phases, 5 plans, 8 tasks
**Lines of code:** 7,549 Python (total project)
**Timeline:** 3 days (2026-03-21 → 2026-03-24)
**Git range:** 5fa3045..f04d74f

**Key accomplishments:**
- Both-hand detection with active hand selection (sticky, preferred, transition jitter prevention)
- Left-hand classification verified hand-agnostic across all 7 gestures — zero classifier changes needed
- Deep-merge config resolution for per-hand gesture and swipe mappings via left_gestures YAML section
- Hand-aware mapping pre-parsed at startup with instant hand-switch swap and hot-reload re-resolution
- Preview overlay hand indicator (L/R) with distinct per-hand colors (cyan-blue Left, orange Right)

---

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

