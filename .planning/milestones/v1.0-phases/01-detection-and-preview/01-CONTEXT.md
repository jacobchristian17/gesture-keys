# Phase 1: Detection and Preview - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Camera captures hand landmarks via MediaPipe Task API, classifies 6 gestures (open palm, fist, thumbs up, peace, pointing, pinch) from the right hand only, and displays results in a real-time preview window with `--preview` flag. Left hand is ignored. Console output prints detected gesture names as they change.

</domain>

<decisions>
## Implementation Decisions

### Preview window layout
- Full 21-landmark skeleton with connections drawn on the camera feed (MediaPipe default visualization style)
- Solid bottom bar below the feed: gesture label bottom-left, FPS counter bottom-right
- Window size: 640x480 (standard VGA, matches common webcam resolution)
- Left hand ignored silently — no overlay, no label, as if it doesn't exist

### Gesture classification
- 3-frame majority-vote smoothing window (~100ms at 30fps)
- Ambiguous poses fall to None — conservative approach, only fire on clear matches
- Priority-ordered classification: PINCH > FIST > THUMBS_UP > POINTING > PEACE > OPEN_PALM > None
- Gesture thresholds configurable per-gesture in config.yaml (default 0.7)
- Camera index configurable in config.yaml (default 0)

### Project structure
- Package layout: `gesture_keys/` with separate modules (detector.py, classifier.py, preview.py, config.py)
- Entry point: `python -m gesture_keys --preview`
- Dependencies: requirements.txt with pip/venv
- CLI: argparse for flag parsing (--preview, --help, future --config override)
- Default config.yaml ships with sensible key mappings pre-configured

### Console output
- Gesture changes only (print on transitions, not every frame)
- None transitions printed (shows gesture start/end lifecycle)
- Brief startup banner: version, camera info, config loaded, gesture count
- Python logging module with levels (INFO for gesture changes/startup, DEBUG for frame-level)

### Config format
- YAML config with sections: camera, detection, gestures
- Each gesture entry has `key` (mapping) and `threshold` (sensitivity)
- Sensible defaults: open_palm=space, fist=ctrl+z, thumbs_up=ctrl+s, peace=ctrl+c, pointing=enter, pinch=ctrl+v
- Smoothing window size in detection section

### Claude's Discretion
- Exact landmark drawing colors and line thickness
- OpenCV window title and close behavior (ESC key, window X button)
- Logging format string and timestamp precision
- Error handling for camera not found / MediaPipe init failure
- Thread architecture for camera capture vs processing
- MediaPipe Task API model download and caching approach

</decisions>

<specifics>
## Specific Ideas

- Config.yaml structure follows nested format: camera.index, detection.smoothing_window, gestures.<name>.key/threshold
- Startup banner should be concise (4 lines max): version, camera, config, "Detection started..."
- Console timestamp format: [HH:MM:SS] (no milliseconds for change-only logging)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no existing code

### Established Patterns
- None yet — this phase establishes the patterns for subsequent phases

### Integration Points
- config.yaml will be shared with Phase 2 (keyboard mappings) and Phase 3 (tray app)
- detector.py and classifier.py will be imported by Phase 2's debounce/keystroke pipeline
- The threading model chosen here constrains Phase 3's system tray integration (pystray needs main thread)

</code_context>

<deferred>
## Deferred Ideas

- Both-hands support (left + right) with per-hand gesture mappings — user considered but deferred to v2 (DET-05)
- Verbose startup mode showing all gesture mappings and thresholds — could add --verbose flag later
- Continuous frame-by-frame logging mode for debugging — could add with DEBUG log level

</deferred>

---

*Phase: 01-detection-and-preview*
*Context gathered: 2026-03-21*
