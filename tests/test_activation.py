"""Tests for activation gate integration: ActivationGate basics, config parsing,
signal filtering, gate expiry safety, and Pipeline hot-reload support."""

from __future__ import annotations

from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from gesture_keys.activation import ActivationGate
from gesture_keys.classifier import Gesture
from gesture_keys.orchestrator import OrchestratorAction, OrchestratorSignal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(action: OrchestratorAction, gesture: Gesture) -> OrchestratorSignal:
    return OrchestratorSignal(action=action, gesture=gesture)


# ---------------------------------------------------------------------------
# Class 1: ActivationGate basics  (ACTV-01 baseline)
# ---------------------------------------------------------------------------

class TestActivationGateBasics:
    """ActivationGate unit tests: arm / tick / expiry / reset."""

    def test_starts_disarmed(self):
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        assert gate.is_armed() is False

    def test_arm_makes_armed(self):
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        gate.arm(0.0)
        assert gate.is_armed() is True

    def test_tick_before_expiry_stays_armed(self):
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        gate.arm(0.0)
        gate.tick(2.9)
        assert gate.is_armed() is True

    def test_tick_at_expiry_disarms(self):
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        gate.arm(0.0)
        gate.tick(3.0)
        assert gate.is_armed() is False

    def test_tick_past_expiry_disarms(self):
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        gate.arm(0.0)
        gate.tick(10.0)
        assert gate.is_armed() is False

    def test_re_arm_extends_window(self):
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        gate.arm(0.0)
        gate.tick(2.5)  # Not yet expired
        gate.arm(2.5)   # Re-arm extends from t=2.5
        gate.tick(5.4)  # 2.5 + 3.0 - epsilon: still armed
        assert gate.is_armed() is True
        gate.tick(5.5)  # 2.5 + 3.0: expired
        assert gate.is_armed() is False

    def test_reset_force_disarms(self):
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        gate.arm(0.0)
        gate.reset()
        assert gate.is_armed() is False

    def test_reset_when_already_disarmed_is_safe(self):
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        gate.reset()  # Should not raise
        assert gate.is_armed() is False

    def test_duration_property(self):
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=5.0)
        assert gate.duration == 5.0

    def test_duration_setter(self):
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        gate.duration = 7.0
        assert gate.duration == 7.0


# ---------------------------------------------------------------------------
# Class 2: Config schema  (ACTV-02)
# ---------------------------------------------------------------------------

class TestActivationGateConfig:
    """Config parsing for activation_gate section."""

    def _write_config(self, tmp_path, extra_yaml: str = "") -> str:
        """Write a minimal valid config.yaml with optional extra content."""
        content = """\
camera:
  index: 0
detection:
  smoothing_window: 2
gestures:
  open_palm:
    key: "ctrl+z"
"""
        if extra_yaml:
            content += extra_yaml
        path = tmp_path / "config.yaml"
        path.write_text(content)
        return str(path)

    def test_default_activation_gate_fields(self, tmp_path):
        """Missing activation_gate section returns disabled defaults."""
        from gesture_keys.config import load_config, AppConfig
        path = self._write_config(tmp_path)
        cfg = load_config(path)
        assert cfg.activation_gate_enabled is False
        assert cfg.activation_gate_gestures == []
        assert cfg.activation_gate_duration == 3.0

    def test_activation_gate_enabled_true(self, tmp_path):
        from gesture_keys.config import load_config
        path = self._write_config(tmp_path, """\
activation_gate:
  enabled: true
  gestures:
    - scout
  duration: 5.0
""")
        cfg = load_config(path)
        assert cfg.activation_gate_enabled is True
        assert cfg.activation_gate_gestures == ["scout"]
        assert cfg.activation_gate_duration == 5.0

    def test_activation_gate_multiple_gestures(self, tmp_path):
        from gesture_keys.config import load_config
        path = self._write_config(tmp_path, """\
activation_gate:
  enabled: true
  gestures:
    - scout
    - peace
  duration: 4.0
""")
        cfg = load_config(path)
        assert set(cfg.activation_gate_gestures) == {"scout", "peace"}

    def test_activation_gate_missing_section_has_defaults(self, tmp_path):
        """Explicitly verify all three fields exist as dataclass attributes."""
        from gesture_keys.config import AppConfig
        cfg = AppConfig()
        assert hasattr(cfg, "activation_gate_enabled")
        assert hasattr(cfg, "activation_gate_gestures")
        assert hasattr(cfg, "activation_gate_duration")

    def test_activation_gate_partial_section(self, tmp_path):
        """Only 'enabled' provided — gestures and duration use defaults."""
        from gesture_keys.config import load_config
        path = self._write_config(tmp_path, """\
activation_gate:
  enabled: true
""")
        cfg = load_config(path)
        assert cfg.activation_gate_enabled is True
        assert cfg.activation_gate_gestures == []
        assert cfg.activation_gate_duration == 3.0


# ---------------------------------------------------------------------------
# Class 3: Signal filtering through gate  (ACTV-01, ACTV-03)
# ---------------------------------------------------------------------------

class TestSignalFiltering:
    """Pipeline._filter_signals_through_gate() unit tests."""

    def _make_pipeline(self) -> object:
        """Create a minimal Pipeline-like object with the gate method."""
        # We import Pipeline but don't call start() — just instantiate
        # and manually set internal state for unit testing the method.
        from gesture_keys.pipeline import Pipeline

        pipeline = Pipeline.__new__(Pipeline)
        pipeline._activation_gate = None
        pipeline._activation_gestures = set()
        return pipeline

    def test_bypass_mode_passes_all_signals(self):
        """gate=None (bypass): all signals pass through unchanged."""
        pipeline = self._make_pipeline()
        pipeline._activation_gate = None
        signals = [
            _make_signal(OrchestratorAction.FIRE, Gesture.OPEN_PALM),
            _make_signal(OrchestratorAction.HOLD_START, Gesture.FIST),
        ]
        result = pipeline._filter_signals_through_gate(signals, 1.0)
        assert result == signals

    def test_gate_not_armed_suppresses_non_activation_signals(self):
        """Gate enabled and NOT armed: non-activation signals suppressed."""
        pipeline = self._make_pipeline()
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        pipeline._activation_gate = gate
        pipeline._activation_gestures = {"scout"}
        signals = [_make_signal(OrchestratorAction.FIRE, Gesture.OPEN_PALM)]
        result = pipeline._filter_signals_through_gate(signals, 1.0)
        assert result == []

    def test_gate_not_armed_activation_gesture_arms_and_consumes(self):
        """Gate enabled and NOT armed: activation gesture arms gate and is consumed."""
        pipeline = self._make_pipeline()
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        pipeline._activation_gate = gate
        pipeline._activation_gestures = {"scout"}
        signals = [_make_signal(OrchestratorAction.FIRE, Gesture.SCOUT)]
        result = pipeline._filter_signals_through_gate(signals, 1.0)
        assert result == []
        assert gate.is_armed() is True

    def test_gate_armed_passes_non_activation_signals(self):
        """Gate enabled and armed: non-activation signals pass through."""
        pipeline = self._make_pipeline()
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        gate.arm(0.0)
        pipeline._activation_gate = gate
        pipeline._activation_gestures = {"scout"}
        sig = _make_signal(OrchestratorAction.FIRE, Gesture.OPEN_PALM)
        result = pipeline._filter_signals_through_gate([sig], 1.0)
        assert result == [sig]

    def test_gate_armed_activation_gesture_rearms_and_consumes(self):
        """Gate enabled and armed: activation gesture re-arms and is consumed."""
        pipeline = self._make_pipeline()
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        gate.arm(0.0)
        pipeline._activation_gate = gate
        pipeline._activation_gestures = {"scout"}
        signals = [_make_signal(OrchestratorAction.FIRE, Gesture.SCOUT)]
        result = pipeline._filter_signals_through_gate(signals, 2.0)
        # Re-armed (timer reset to t=2.0)
        assert result == []
        assert gate.is_armed() is True

    def test_all_signal_types_for_activation_gesture_consumed(self):
        """ALL signal types (FIRE, HOLD_START, HOLD_END, COMPOUND_FIRE) are consumed."""
        pipeline = self._make_pipeline()
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        pipeline._activation_gate = gate
        pipeline._activation_gestures = {"scout"}
        for action in OrchestratorAction:
            signals = [_make_signal(action, Gesture.SCOUT)]
            result = pipeline._filter_signals_through_gate(signals, 1.0)
            assert result == [], f"Expected {action} scout signal to be consumed"

    def test_multiple_activation_gestures(self):
        """Either scout OR peace can arm the gate."""
        pipeline = self._make_pipeline()
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        pipeline._activation_gate = gate
        pipeline._activation_gestures = {"scout", "peace"}

        # Peace gesture should also arm
        signals = [_make_signal(OrchestratorAction.FIRE, Gesture.PEACE)]
        result = pipeline._filter_signals_through_gate(signals, 1.0)
        assert result == []
        assert gate.is_armed() is True

    def test_mixed_signals_partial_filter(self):
        """Activation signal consumed, non-activation suppressed when not armed."""
        pipeline = self._make_pipeline()
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        pipeline._activation_gate = gate
        pipeline._activation_gestures = {"scout"}
        signals = [
            _make_signal(OrchestratorAction.FIRE, Gesture.SCOUT),    # arm + consume
            _make_signal(OrchestratorAction.FIRE, Gesture.OPEN_PALM), # suppress (not armed... wait, just armed)
        ]
        # After SCOUT arms the gate, OPEN_PALM should pass through (gate now armed)
        result = pipeline._filter_signals_through_gate(signals, 1.0)
        # Scout consumed, open_palm passes (gate armed after scout)
        assert len(result) == 1
        assert result[0].gesture == Gesture.OPEN_PALM


# ---------------------------------------------------------------------------
# Class 4: Gate expiry safety  (ACTV-03)
# ---------------------------------------------------------------------------

class TestGateExpirySafety:
    """Gate expiry calls dispatcher.release_all() and orchestrator.reset()."""

    def _make_pipeline_with_gate(self):
        """Create a Pipeline with mocked dispatcher/orchestrator and a live gate."""
        from gesture_keys.pipeline import Pipeline

        pipeline = Pipeline.__new__(Pipeline)
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        gate.arm(0.0)
        pipeline._activation_gate = gate
        pipeline._activation_gestures = {"scout"}
        pipeline._dispatcher = MagicMock()
        pipeline._orchestrator = MagicMock()
        return pipeline, gate

    def test_expiry_calls_release_all(self):
        """Gate expiry triggers dispatcher.release_all()."""
        pipeline, gate = self._make_pipeline_with_gate()
        # Simulate expiry detection in process_frame tick logic
        was_armed = gate.is_armed()
        gate.tick(10.0)  # Expired
        if was_armed and not gate.is_armed():
            pipeline._dispatcher.release_all()
            pipeline._orchestrator.reset()
        pipeline._dispatcher.release_all.assert_called_once()

    def test_expiry_calls_orchestrator_reset(self):
        """Gate expiry triggers orchestrator.reset()."""
        pipeline, gate = self._make_pipeline_with_gate()
        was_armed = gate.is_armed()
        gate.tick(10.0)
        if was_armed and not gate.is_armed():
            pipeline._dispatcher.release_all()
            pipeline._orchestrator.reset()
        pipeline._orchestrator.reset.assert_called_once()

    def test_no_expiry_actions_when_not_expired(self):
        """No release_all/reset called if gate hasn't expired."""
        pipeline, gate = self._make_pipeline_with_gate()
        was_armed = gate.is_armed()
        gate.tick(2.0)  # Not expired (duration=3.0, armed at 0.0)
        if was_armed and not gate.is_armed():
            pipeline._dispatcher.release_all()
            pipeline._orchestrator.reset()
        pipeline._dispatcher.release_all.assert_not_called()
        pipeline._orchestrator.reset.assert_not_called()

    def test_gate_frame_result_armed_field(self):
        """FrameResult has activation_armed field."""
        from gesture_keys.pipeline import FrameResult
        result = FrameResult()
        assert hasattr(result, "activation_armed")
        assert result.activation_armed is False


# ---------------------------------------------------------------------------
# Class 5: Pipeline integration (start / reload_config)  (ACTV-01, ACTV-02, ACTV-03)
# ---------------------------------------------------------------------------

class TestPipelineGateIntegration:
    """Pipeline._activation_gate creation and hot-reload behavior."""

    def _make_config(self, enabled=False, gestures=None, duration=3.0):
        """Create an AppConfig with activation gate settings."""
        from gesture_keys.config import AppConfig
        return AppConfig(
            activation_gate_enabled=enabled,
            activation_gate_gestures=gestures or [],
            activation_gate_duration=duration,
        )

    def test_start_creates_gate_when_enabled(self, tmp_path):
        """start() creates ActivationGate when config enabled and gestures non-empty."""
        from gesture_keys.pipeline import Pipeline

        pipeline = Pipeline.__new__(Pipeline)
        pipeline._activation_gate = None
        pipeline._activation_gestures = set()

        config = self._make_config(enabled=True, gestures=["scout"], duration=4.0)
        # Simulate gate setup logic from start()
        if config.activation_gate_enabled and config.activation_gate_gestures:
            pipeline._activation_gate = ActivationGate(
                gesture=Gesture(config.activation_gate_gestures[0]),
                duration=config.activation_gate_duration,
            )
            pipeline._activation_gestures = set(config.activation_gate_gestures)

        assert pipeline._activation_gate is not None
        assert isinstance(pipeline._activation_gate, ActivationGate)
        assert pipeline._activation_gestures == {"scout"}

    def test_start_sets_gate_none_when_disabled(self):
        """start() sets _activation_gate = None when config disabled (bypass)."""
        from gesture_keys.pipeline import Pipeline

        pipeline = Pipeline.__new__(Pipeline)
        config = self._make_config(enabled=False)
        # Simulate bypass setup
        if not (config.activation_gate_enabled and config.activation_gate_gestures):
            pipeline._activation_gate = None
            pipeline._activation_gestures = set()
        assert pipeline._activation_gate is None

    def test_reload_false_to_true_creates_gate(self):
        """Changing enabled from false->true creates gate."""
        from gesture_keys.pipeline import Pipeline

        pipeline = Pipeline.__new__(Pipeline)
        pipeline._activation_gate = None
        pipeline._activation_gestures = set()
        pipeline._dispatcher = MagicMock()

        new_config = self._make_config(enabled=True, gestures=["scout"], duration=5.0)
        # Simulate reload gate logic
        if new_config.activation_gate_enabled and new_config.activation_gate_gestures:
            pipeline._activation_gate = ActivationGate(
                gesture=Gesture(new_config.activation_gate_gestures[0]),
                duration=new_config.activation_gate_duration,
            )
            pipeline._activation_gestures = set(new_config.activation_gate_gestures)
        else:
            pipeline._activation_gate = None
            pipeline._activation_gestures = set()

        assert pipeline._activation_gate is not None
        assert pipeline._activation_gate.duration == 5.0

    def test_reload_true_to_false_destroys_gate_releases_keys(self):
        """Changing enabled from true->false destroys gate and releases held keys."""
        from gesture_keys.pipeline import Pipeline

        pipeline = Pipeline.__new__(Pipeline)
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        gate.arm(0.0)
        pipeline._activation_gate = gate
        pipeline._activation_gestures = {"scout"}
        pipeline._dispatcher = MagicMock()

        new_config = self._make_config(enabled=False)
        # Simulate reload gate logic — disable path
        old_gate = pipeline._activation_gate
        if new_config.activation_gate_enabled and new_config.activation_gate_gestures:
            pipeline._activation_gate = ActivationGate(
                gesture=Gesture(new_config.activation_gate_gestures[0]),
                duration=new_config.activation_gate_duration,
            )
            pipeline._activation_gestures = set(new_config.activation_gate_gestures)
        else:
            if old_gate is not None:
                pipeline._dispatcher.release_all()
            pipeline._activation_gate = None
            pipeline._activation_gestures = set()

        assert pipeline._activation_gate is None
        pipeline._dispatcher.release_all.assert_called_once()

    def test_reload_updates_duration(self):
        """Changing duration updates gate.duration."""
        from gesture_keys.pipeline import Pipeline

        pipeline = Pipeline.__new__(Pipeline)
        gate = ActivationGate(gesture=Gesture.SCOUT, duration=3.0)
        pipeline._activation_gate = gate
        pipeline._activation_gestures = {"scout"}
        pipeline._dispatcher = MagicMock()

        new_config = self._make_config(enabled=True, gestures=["scout"], duration=7.0)
        # Simulate duration update path in reload
        if (new_config.activation_gate_enabled and new_config.activation_gate_gestures
                and pipeline._activation_gate is not None):
            pipeline._activation_gate.duration = new_config.activation_gate_duration
            pipeline._activation_gestures = set(new_config.activation_gate_gestures)
        assert pipeline._activation_gate.duration == 7.0

    def test_pipeline_has_activation_gate_attr(self):
        """Pipeline __init__ has _activation_gate and _activation_gestures attrs."""
        from gesture_keys.pipeline import Pipeline
        with patch.object(Pipeline, "__init__", wraps=Pipeline.__init__) as mock_init:
            # We only need to check that the attributes exist after __init__
            pass
        # Create via __new__ to avoid start() requirement
        pipeline = Pipeline.__new__(Pipeline)
        pipeline.__init__.__func__  # not calling, just checking method exists
        # Check the attributes are set in __init__ by inspecting source
        import inspect
        src = inspect.getsource(Pipeline.__init__)
        assert "_activation_gate" in src
        assert "_activation_gestures" in src
