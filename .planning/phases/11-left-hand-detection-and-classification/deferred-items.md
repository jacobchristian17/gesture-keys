# Deferred Items - Phase 11

## Pre-existing Test Failures

These test failures exist before any Phase 11 changes and are out of scope:

1. `test_config.py::TestLoadConfigDefault::test_key_mappings` - config.yaml has `fist: space` but test expects `fist: esc`
2. `test_config.py::TestAppConfigTimingFields::test_default_config_has_timing_fields` - config.yaml has `activation_delay: 0.2` but test expects `0.15`
3. `test_config.py::TestSettlingFramesConfig::test_load_config_settling_frames_from_default_config` - config.yaml has `settling_frames: 2` but test expects `3`
