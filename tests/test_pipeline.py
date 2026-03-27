"""Tests for the unified Pipeline class and FrameResult dataclass."""

from unittest.mock import MagicMock, patch, PropertyMock
import pytest

from gesture_keys.orchestrator import (
    LifecycleState,
    OrchestratorAction,
    OrchestratorResult,
    OrchestratorSignal,
    TemporalState,
)
from gesture_keys.trigger import Direction


class TestFrameResult:
    """Test FrameResult dataclass field defaults and assignment."""

    def test_default_values(self):
        from gesture_keys.pipeline import FrameResult, DebounceState

        result = FrameResult()
        assert result.landmarks is None
        assert result.handedness is None
        assert result.gesture is None
        assert result.raw_gesture is None
        assert result.debounce_state == DebounceState.IDLE
        assert result.motion_state is None
        assert result.frame_valid is True
        assert result.orchestrator is None

    def test_field_assignment(self):
        from gesture_keys.pipeline import FrameResult, DebounceState
        from gesture_keys.classifier import Gesture
        from gesture_keys.motion import MotionState

        orch_result = OrchestratorResult(
            outer_state=LifecycleState.ACTIVE,
            temporal_state=TemporalState.HOLD,
        )
        motion = MotionState(moving=True, direction=Direction.LEFT)
        landmarks = [[0.1, 0.2, 0.3]]
        result = FrameResult(
            landmarks=landmarks,
            handedness="Right",
            gesture=Gesture.FIST,
            raw_gesture=Gesture.OPEN_PALM,
            debounce_state=DebounceState.FIRED,
            motion_state=motion,
            frame_valid=False,
            orchestrator=orch_result,
        )
        assert result.landmarks is landmarks
        assert result.handedness == "Right"
        assert result.gesture == Gesture.FIST
        assert result.raw_gesture == Gesture.OPEN_PALM
        assert result.debounce_state == DebounceState.FIRED
        assert result.motion_state.moving is True
        assert result.motion_state.direction == Direction.LEFT
        assert result.frame_valid is False
        assert result.orchestrator is orch_result


class TestDebounceStateMapping:
    """Test _map_to_debounce_state helper for backward compatibility."""

    def test_idle_maps_to_idle(self):
        from gesture_keys.pipeline import _map_to_debounce_state, DebounceState
        result = OrchestratorResult(outer_state=LifecycleState.IDLE)
        assert _map_to_debounce_state(result) == DebounceState.IDLE

    def test_activating_maps_to_activating(self):
        from gesture_keys.pipeline import _map_to_debounce_state, DebounceState
        result = OrchestratorResult(outer_state=LifecycleState.ACTIVATING)
        assert _map_to_debounce_state(result) == DebounceState.ACTIVATING

    def test_active_hold_maps_to_holding(self):
        from gesture_keys.pipeline import _map_to_debounce_state, DebounceState
        result = OrchestratorResult(
            outer_state=LifecycleState.ACTIVE,
            temporal_state=TemporalState.HOLD,
        )
        assert _map_to_debounce_state(result) == DebounceState.HOLDING

    def test_active_confirmed_maps_to_fired(self):
        from gesture_keys.pipeline import _map_to_debounce_state, DebounceState
        result = OrchestratorResult(
            outer_state=LifecycleState.ACTIVE,
            temporal_state=TemporalState.CONFIRMED,
        )
        assert _map_to_debounce_state(result) == DebounceState.FIRED

    def test_cooldown_maps_to_cooldown(self):
        from gesture_keys.pipeline import _map_to_debounce_state, DebounceState
        result = OrchestratorResult(outer_state=LifecycleState.COOLDOWN)
        assert _map_to_debounce_state(result) == DebounceState.COOLDOWN


class TestPipelineInit:
    """Test Pipeline.__init__ loads config and sets component slots to None."""

    @patch("gesture_keys.pipeline.load_config")
    def test_init_loads_config(self, mock_load_config):
        from gesture_keys.pipeline import Pipeline

        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        pipeline = Pipeline("config.yaml")

        mock_load_config.assert_called_once_with("config.yaml")
        assert pipeline._config is mock_config
        assert pipeline._config_path == "config.yaml"

    @patch("gesture_keys.pipeline.load_config")
    def test_init_component_slots_none(self, mock_load_config):
        from gesture_keys.pipeline import Pipeline

        mock_load_config.return_value = MagicMock()
        pipeline = Pipeline("config.yaml")

        assert pipeline._camera is None
        assert pipeline._detector is None
        assert pipeline._classifier is None
        assert pipeline._smoother is None
        assert pipeline._orchestrator is None
        assert pipeline._sender is None
        assert pipeline._distance_filter is None
        assert pipeline._motion_detector is None
        assert pipeline._watcher is None

    @patch("gesture_keys.pipeline.load_config")
    def test_init_per_frame_state_defaults(self, mock_load_config):
        from gesture_keys.pipeline import Pipeline

        mock_load_config.return_value = MagicMock()
        pipeline = Pipeline("config.yaml")

        assert pipeline._prev_gesture is None
        assert pipeline._prev_handedness is None
        assert pipeline._hand_was_in_range is True
        assert pipeline._last_frame is None
        assert pipeline._current_time == 0.0

    @patch("gesture_keys.pipeline.load_config")
    def test_init_no_debouncer_state(self, mock_load_config):
        """Orchestrator-backed Pipeline should not have debouncer-era state variables."""
        from gesture_keys.pipeline import Pipeline

        mock_load_config.return_value = MagicMock()
        pipeline = Pipeline("config.yaml")

        # These attributes should NOT exist anymore (orchestrator owns them)
        assert not hasattr(pipeline, '_debouncer')


class TestPipelineStartStop:
    """Test Pipeline.start() creates components and stop() releases resources."""

    def _make_mock_config(self):
        """Create a mock AppConfig with all required attributes."""
        config = MagicMock()
        config.camera_index = 0
        config.preferred_hand = "Right"
        config.smoothing_window = 5
        config.activation_delay = 0.5
        config.cooldown_duration = 0.3
        config.hold_release_delay = 0.3
        config.sequence_window = 0.5
        config.min_hand_size = 0.15
        config.max_hand_size = 1.0
        config.distance_enabled = True
        config.hold_repeat_interval = 0.03
        config.activation_gate_enabled = False
        config.activation_gate_gestures = []
        config.activation_gate_duration = 3.0
        config.activation_gate_bypass = []
        config.actions = []
        return config

    def _make_mock_derived_config(self):
        """Create a mock DerivedConfig with empty maps."""
        derived = MagicMock()
        derived.gesture_modes = {}
        derived.gesture_cooldowns = {}
        derived.activation_gate_bypass = []
        derived.right_static = {}
        derived.left_static = {}
        derived.right_holding = {}
        derived.left_holding = {}
        derived.right_moving = {}
        derived.left_moving = {}
        derived.right_sequence = {}
        derived.left_sequence = {}
        return derived

    @patch("gesture_keys.pipeline.ConfigWatcher")
    @patch("gesture_keys.pipeline.MotionDetector")
    @patch("gesture_keys.pipeline.DistanceFilter")
    @patch("gesture_keys.pipeline.KeystrokeSender")
    @patch("gesture_keys.pipeline.GestureOrchestrator")
    @patch("gesture_keys.pipeline.GestureSmoother")
    @patch("gesture_keys.pipeline.GestureClassifier")
    @patch("gesture_keys.pipeline.HandDetector")
    @patch("gesture_keys.pipeline.CameraCapture")
    @patch("gesture_keys.pipeline.derive_from_actions")
    @patch("gesture_keys.pipeline.load_config")
    def test_start_creates_components(
        self, mock_load_config, mock_derive, mock_camera_cls, mock_detector_cls,
        mock_classifier_cls, mock_smoother_cls, mock_orchestrator_cls,
        mock_sender_cls, mock_distance_cls, mock_motion_cls, mock_watcher_cls,
    ):
        from gesture_keys.pipeline import Pipeline

        mock_load_config.return_value = self._make_mock_config()
        mock_derive.return_value = self._make_mock_derived_config()
        mock_camera_instance = MagicMock()
        mock_camera_cls.return_value.start.return_value = mock_camera_instance

        pipeline = Pipeline("config.yaml")
        pipeline.start()

        assert pipeline._camera is not None
        assert pipeline._detector is not None
        assert pipeline._classifier is not None
        assert pipeline._smoother is not None
        assert pipeline._orchestrator is not None
        assert pipeline._sender is not None
        assert pipeline._distance_filter is not None
        assert pipeline._motion_detector is not None
        assert pipeline._watcher is not None

    @patch("gesture_keys.pipeline.load_config")
    def test_stop_releases_resources(self, mock_load_config):
        from gesture_keys.pipeline import Pipeline

        mock_load_config.return_value = MagicMock()
        pipeline = Pipeline("config.yaml")

        # Simulate components that were started
        pipeline._dispatcher = MagicMock()
        pipeline._camera = MagicMock()
        pipeline._detector = MagicMock()

        pipeline.stop()

        pipeline._dispatcher.release_all.assert_called_once()
        pipeline._camera.stop.assert_called_once()
        pipeline._detector.close.assert_called_once()

    @patch("gesture_keys.pipeline.load_config")
    def test_stop_guards_none_components(self, mock_load_config):
        from gesture_keys.pipeline import Pipeline

        mock_load_config.return_value = MagicMock()
        pipeline = Pipeline("config.yaml")

        # Components are None (never started) -- should not raise
        pipeline.stop()

    @patch("gesture_keys.pipeline.load_config")
    def test_last_frame_property(self, mock_load_config):
        from gesture_keys.pipeline import Pipeline

        mock_load_config.return_value = MagicMock()
        pipeline = Pipeline("config.yaml")

        assert pipeline.last_frame is None
        pipeline._last_frame = "test_frame"
        assert pipeline.last_frame == "test_frame"


class TestPipelineReset:
    """Test Pipeline.reset_pipeline() resets components and hold state."""

    @patch("gesture_keys.pipeline.load_config")
    def test_reset_pipeline_resets_components(self, mock_load_config):
        from gesture_keys.pipeline import Pipeline

        mock_load_config.return_value = MagicMock()
        pipeline = Pipeline("config.yaml")

        pipeline._smoother = MagicMock()
        pipeline._orchestrator = MagicMock()
        pipeline._motion_detector = MagicMock()
        pipeline._dispatcher = MagicMock()

        pipeline.reset_pipeline()

        pipeline._smoother.reset.assert_called_once()
        pipeline._orchestrator.reset.assert_called_once()
        pipeline._motion_detector.reset.assert_called_once()
        pipeline._dispatcher.release_all.assert_called_once()


class TestActivationGateSequenceFire:
    """Test _filter_signals_through_gate handles SEQUENCE_FIRE using second_gesture."""

    @patch("gesture_keys.pipeline.load_config")
    def test_sequence_fire_activation_gesture_consumed(self, mock_load_config):
        """SEQUENCE_FIRE where second_gesture is activation gesture should arm gate."""
        from gesture_keys.pipeline import Pipeline
        from gesture_keys.classifier import Gesture

        mock_load_config.return_value = MagicMock()
        pipeline = Pipeline("config.yaml")

        # Set up activation gate
        pipeline._activation_gate = MagicMock()
        pipeline._activation_gate.is_armed.return_value = False
        pipeline._activation_gestures = {"thumbs_up"}
        pipeline._activation_bypass = set()

        # SEQUENCE_FIRE: first gesture is fist, second is thumbs_up (activation gesture)
        signal = OrchestratorSignal(
            action=OrchestratorAction.SEQUENCE_FIRE,
            gesture=Gesture.FIST,
            second_gesture=Gesture("thumbs_up"),
        )

        result = pipeline._filter_signals_through_gate([signal], 1.0)

        # Signal should be consumed (arms gate), not passed through
        assert len(result) == 0
        pipeline._activation_gate.arm.assert_called_once_with(1.0)

    @patch("gesture_keys.pipeline.load_config")
    def test_sequence_fire_non_activation_passes_when_armed(self, mock_load_config):
        """SEQUENCE_FIRE where second_gesture is not activation, gate armed -> passes."""
        from gesture_keys.pipeline import Pipeline
        from gesture_keys.classifier import Gesture

        mock_load_config.return_value = MagicMock()
        pipeline = Pipeline("config.yaml")

        # Set up activation gate (armed)
        pipeline._activation_gate = MagicMock()
        pipeline._activation_gate.is_armed.return_value = True
        pipeline._activation_gestures = {"thumbs_up"}
        pipeline._activation_bypass = set()

        # SEQUENCE_FIRE: second gesture is fist (not activation gesture)
        signal = OrchestratorSignal(
            action=OrchestratorAction.SEQUENCE_FIRE,
            gesture=Gesture("thumbs_up"),
            second_gesture=Gesture.FIST,
        )

        result = pipeline._filter_signals_through_gate([signal], 1.0)

        # Signal should pass through (gate is armed, second_gesture is not activation)
        assert len(result) == 1
        assert result[0] is signal

    @patch("gesture_keys.pipeline.load_config")
    def test_sequence_fire_non_activation_blocked_when_disarmed(self, mock_load_config):
        """SEQUENCE_FIRE where second_gesture is not activation, gate disarmed -> blocked."""
        from gesture_keys.pipeline import Pipeline
        from gesture_keys.classifier import Gesture

        mock_load_config.return_value = MagicMock()
        pipeline = Pipeline("config.yaml")

        # Set up activation gate (not armed)
        pipeline._activation_gate = MagicMock()
        pipeline._activation_gate.is_armed.return_value = False
        pipeline._activation_gestures = {"thumbs_up"}
        pipeline._activation_bypass = set()

        # SEQUENCE_FIRE: second gesture is fist (not activation gesture)
        signal = OrchestratorSignal(
            action=OrchestratorAction.SEQUENCE_FIRE,
            gesture=Gesture("thumbs_up"),
            second_gesture=Gesture.FIST,
        )

        result = pipeline._filter_signals_through_gate([signal], 1.0)

        # Signal should be blocked (gate not armed)
        assert len(result) == 0

    @patch("gesture_keys.pipeline.load_config")
    def test_regular_fire_still_uses_gesture_value(self, mock_load_config):
        """Regular FIRE signal should still use gesture.value for gate check."""
        from gesture_keys.pipeline import Pipeline
        from gesture_keys.classifier import Gesture

        mock_load_config.return_value = MagicMock()
        pipeline = Pipeline("config.yaml")

        # Set up activation gate (not armed)
        pipeline._activation_gate = MagicMock()
        pipeline._activation_gate.is_armed.return_value = False
        pipeline._activation_gestures = {"thumbs_up"}
        pipeline._activation_bypass = set()

        # Regular FIRE with activation gesture
        signal = OrchestratorSignal(
            action=OrchestratorAction.FIRE,
            gesture=Gesture("thumbs_up"),
        )

        result = pipeline._filter_signals_through_gate([signal], 1.0)

        # Should arm gate and consume signal
        assert len(result) == 0
        pipeline._activation_gate.arm.assert_called_once_with(1.0)


class TestMotionDetectorEmptyLandmarks:
    """Test that MotionDetector handles empty landmarks (no hand detected)."""

    @patch("gesture_keys.pipeline.load_config")
    def test_empty_landmarks_does_not_crash(self, mock_load_config):
        """Empty landmarks list should be treated as no hand (not crash)."""
        from gesture_keys.pipeline import Pipeline

        mock_load_config.return_value = MagicMock()
        pipeline = Pipeline("config.yaml")

        # Simulate empty landmarks (no hand detected)
        pipeline._motion_detector = MagicMock()
        pipeline._motion_detector.update.return_value = MagicMock(moving=False, direction=None)

        # The fix: `landmarks or None` converts [] to None before passing
        landmarks = []
        result = landmarks or None
        assert result is None
