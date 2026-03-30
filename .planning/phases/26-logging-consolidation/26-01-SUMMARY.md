---
plan: 26-01
phase: 26-logging-consolidation
status: complete
started: 2026-03-30
completed: 2026-03-30
---

# Plan 26-01: Logging Consolidation — Summary

## What Was Built

Centralized all logging configuration into `setup_logging()` with `console` and `debug` keyword parameters, making debug.log opt-in and eliminating ad-hoc handler code.

## Tasks Completed

| # | Task | Status | Commit |
|---|------|--------|--------|
| 1 | Refactor setup_logging() with console/debug params | Complete | 8b94573 |
| 2 | Update __main__.py callers, remove ad-hoc handlers | Complete | a6bb8f4 |

## Key Changes

### gesture_keys/logging_setup.py
- `setup_logging()` now accepts `console: bool = False` and `debug: bool = False`
- preview.log always created (INFO level) — unchanged
- debug.log only created when `debug=True` — was always-on
- Console StreamHandler only added when `console=True` — was external
- Added `CONSOLE_FORMAT` constant

### gesture_keys/__main__.py
- `run_tray_mode()`: `setup_logging(debug=args.debug)` — debug.log opt-in
- `run_preview_mode()`: `setup_logging(console=True, debug=args.debug)` — console+debug via centralized call
- Removed 5 lines of ad-hoc StreamHandler code

### tests/test_logging_setup.py
- 6 tests covering all parameter combinations
- Backward compatibility verified

## key-files

### created
- tests/test_logging_setup.py

### modified
- gesture_keys/logging_setup.py
- gesture_keys/__main__.py

## Self-Check: PASSED

All acceptance criteria verified:
- setup_logging() accepts console and debug params ✓
- All handlers created in one place ✓
- No ad-hoc StreamHandler in __main__.py ✓
- 6/6 logging tests pass ✓
- Backward compatible default call works ✓

## Deviations

None.

## Issues

Pre-existing test failure in test_config.py (sequence_window default mismatch) — unrelated to logging changes.
