# Phase 26: Logging Consolidation - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase)

<domain>
## Phase Boundary

Centralize all logging configuration into setup_logging() with console and debug parameters. Make debug.log opt-in. Wire --debug flag to all launch modes.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — infrastructure phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key codebase observations:
- `setup_logging()` in logging_setup.py currently always creates both preview.log and debug.log file handlers
- `run_preview_mode()` in __main__.py adds a console StreamHandler ad-hoc (lines 86-90)
- `run_tray_mode()` calls setup_logging() which unconditionally creates debug.log
- `--debug` argparse flag exists but only affects console handler level in preview mode
- `run_preview_mode._was_moving` function-attribute tracks motion state transitions

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `logging_setup.py`: setup_logging(), _logs_dir(), RotatingFileHandler config
- `__main__.py`: parse_args() with --debug flag, run_tray_mode(), run_preview_mode()

### Established Patterns
- RotatingFileHandler with 5MB max, 3 backups
- LOG_FORMAT = "[%(asctime)s] %(levelname)s %(message)s"
- Console format uses simpler "[%(asctime)s] %(message)s"
- Logger name: "gesture_keys"
- Duplicate handler prevention via `if logger.handlers: return`

### Integration Points
- setup_logging() called from both run_tray_mode() and run_preview_mode()
- Console handler manually added after setup_logging() in run_preview_mode()
- args.debug read in run_preview_mode() to set console log level

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — infrastructure phase.

</deferred>
