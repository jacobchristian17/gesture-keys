# Phase 04 Deferred Items

## Pre-existing Test Failures

3 tests in `tests/test_config.py` fail against the current `config.yaml` defaults:
- `TestLoadConfigDefault::test_smoothing_window_default` -- expects 3, config has 1
- `TestLoadConfigDefault::test_key_mappings` -- expected keys don't match current config
- `TestAppConfigTimingFields::test_default_config_has_timing_fields` -- timing values changed

These are pre-existing and unrelated to Phase 04 changes. The config.yaml was updated without updating the corresponding tests.
