"""Tests for the unified Pipeline class and FrameResult dataclass."""

from unittest.mock import MagicMock, patch, PropertyMock
import pytest

from gesture_keys.orchestrator import LifecycleState, TemporalState, OrchestratorResult


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
        assert result.swiping is False
        assert result.frame_valid is True
        assert result.orchestrator is None

    def test_field_assignment(self):
        from gesture_keys.pipeline import FrameResult, DebounceState
        from gesture_keys.classifier import Gesture

        orch_result = OrchestratorResult(
            outer_state=LifecycleState.ACTIVE,
            temporal_state=TemporalState.HOLD,
        )
        landmarks = [[0.1, 0.2, 0.3]]
        result = FrameResult(
            landmarks=landmarks,
            handedness="Right",
            gesture=Gesture.FIST,
            raw_gesture=Gesture.OPEN_PALM,
            debounce_state=DebounceState.FIRED,
            swiping=True,
            frame_valid=False,
            orchestrator=orch_result,
        )
        assert result.landmarks is landmarks
        assert result.handedness == "Right"
        assert result.gesture == Gesture.FIST
        assert result.raw_gesture == Gesture.OPEN_PALM
        assert result.debounce_state == DebounceState.FIRED
        assert result.swiping is True
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

    def test_swipe_window_maps_to_swipe_window(self):
        from gesture_keys.pipeline import _map_to_debounce_state, DebounceState
        result = OrchestratorResult(outer_state=LifecycleState.SWIPE_WINDOW)
        assert _map_to_debounce_state(result) == DebounceState.SWIPE_WINDOW

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
        assert pipeline._swipe_detector is None
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
        assert not hasattr(pipeline, '_pre_swipe_gesture')
        assert not hasattr(pipeline, '_was_swiping')
        assert not hasattr(pipeline, '_compound_swipe_suppress_until')
        assert not hasattr(pipeline, '_debouncer')


class TestPipelineStartStop:
    """Test Pipeline.start() creates components and stop() releases resources."""

    def _make_mock_config(self):
        """Create a mock AppConfig with all required attributes."""
        config = MagicMock()
        config.camera_index = 0
        config.preferred_hand = "Right"
        config.gestures = {
            "fist": {"key": "space", "threshold": 0.8},
        }
        config.smoothing_window = 5
        config.gesture_swipe_mappings = {}
        config.activation_delay = 0.5
        config.cooldown_duration = 0.3
        config.gesture_cooldowns = {}
        config.gesture_modes = {}
        config.hold_release_delay = 0.3
        config.swipe_window = 0.5
        config.min_hand_size = 0.15
        config.max_hand_size = 1.0
        config.distance_enabled = True
        config.swipe_min_velocity = 0.5
        config.swipe_min_displacement = 0.1
        config.swipe_axis_ratio = 1.5
        config.swipe_cooldown = 0.5
        config.swipe_settling_frames = 3
        config.swipe_enabled = False
        config.swipe_mappings = {}
        config.hold_repeat_interval = 0.03
        config.activation_gate_enabled = False
        config.activation_gate_gestures = []
        config.activation_gate_duration = 3.0
        return config

    @patch("gesture_keys.pipeline.ConfigWatcher")
    @patch("gesture_keys.pipeline.SwipeDetector")
    @patch("gesture_keys.pipeline.DistanceFilter")
    @patch("gesture_keys.pipeline.KeystrokeSender")
    @patch("gesture_keys.pipeline.GestureOrchestrator")
    @patch("gesture_keys.pipeline.GestureSmoother")
    @patch("gesture_keys.pipeline.GestureClassifier")
    @patch("gesture_keys.pipeline.HandDetector")
    @patch("gesture_keys.pipeline.CameraCapture")
    @patch("gesture_keys.pipeline.load_config")
    def test_start_creates_components(
        self, mock_load_config, mock_camera_cls, mock_detector_cls,
        mock_classifier_cls, mock_smoother_cls, mock_orchestrator_cls,
        mock_sender_cls, mock_distance_cls, mock_swipe_cls, mock_watcher_cls,
    ):
        from gesture_keys.pipeline import Pipeline

        mock_load_config.return_value = self._make_mock_config()
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
        assert pipeline._swipe_detector is not None
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
        pipeline._swipe_detector = MagicMock()
        pipeline._dispatcher = MagicMock()

        pipeline.reset_pipeline()

        pipeline._smoother.reset.assert_called_once()
        pipeline._orchestrator.reset.assert_called_once()
        pipeline._swipe_detector.reset.assert_called_once()
        pipeline._dispatcher.release_all.assert_called_once()
