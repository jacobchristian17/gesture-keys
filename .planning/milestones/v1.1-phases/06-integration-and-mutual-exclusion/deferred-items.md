# Deferred Items - Phase 06

## Pre-existing Test Failures (Out of Scope)

Discovered during 06-04 execution. config.yaml has been customized by the user but default config tests still expect original values:

1. `test_smoothing_window_default` - expects 3, config.yaml has 1
2. `test_default_threshold_values` - expects original thresholds, config.yaml has different values
3. `test_key_mappings` - expects original key mappings, config.yaml has different mappings
4. `test_default_config_has_timing_fields` - expects activation_delay=0.4, config has 0.3; expects cooldown_duration=0.8, config has 0.5

**Resolution:** These tests verify original default values but config.yaml is a user-editable file. Tests should either be updated to match current config.yaml or test against a fixture config.
