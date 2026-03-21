# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-03-21
**Phases:** 3 | **Plans:** 7

### What Was Built
- 6-gesture hand classifier from MediaPipe landmarks with configurable thresholds
- Full detection pipeline: camera → landmarks → classifier → smoother → debouncer → keystroke sender
- Preview window with landmark skeleton overlay, gesture label, and FPS counter
- System tray app with active toggle, config editing, and clean shutdown
- Config hot-reload without restart

### What Worked
- Bottom-up pipeline architecture (detection → keystroke → tray) let each phase be independently testable
- TDD approach caught issues early — tests written before implementation
- Human verification checkpoints caught real issues (tray icon invisible with RGB on Windows 11)
- Priority-ordered gesture classification eliminated ambiguity without complex logic

### What Was Inefficient
- Tray icon RGB vs RGBA issue required debugging cycle during checkpoint — could have been caught by research noting Windows tray icon requirements
- `_parse_key_mappings` was duplicated between `__main__.py` and `tray.py` — should be extracted to a shared utility
- Integration tests needed updating when `main()` was rewired to tray mode — test coupling to entry point behavior

### Patterns Established
- RGBA with transparent background for Windows system tray icons
- `icon.visible = True` + startup notification for reliable pystray display
- Lazy imports for optional heavy dependencies (pystray/Pillow in tray mode only)
- threading.Event for clean shutdown signaling between threads

### Key Lessons
1. Windows tray icons require RGBA format — RGB renders invisible on some configurations
2. pystray setup callback should set `icon.visible = True` explicitly for reliable display
3. Human verification checkpoints are essential for platform-specific UI features

### Cost Observations
- Model mix: primarily opus with sonnet for verification
- Entire milestone completed in a single day
- Notable: 7 plans across 3 phases executed efficiently with wave-based parallelization

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 3 | 7 | Initial project — established TDD + human verification pattern |

### Top Lessons (Verified Across Milestones)

1. Human verification checkpoints catch platform-specific issues that automated tests miss
2. Bottom-up architecture with independently testable phases reduces integration risk
