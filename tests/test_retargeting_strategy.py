from types import SimpleNamespace

import pytest

from retargeting_strategy import (
    RETARGETING_DEXPILOT,
    RETARGETING_STABLE,
    RetargetingCoordinator,
)


class RecordingStableMapper:
    joint_names = ["thumb_bend", "thumb_rotate", "index_finger"]
    num_joints = 3

    def __init__(self):
        self.calls = []

    def calibrate_inputs(self, values):
        return dict(values)

    def map_mirror(self, values, pinch_strength=0.0, finger_retractions=None):
        self.calls.append((dict(values), pinch_strength, dict(finger_retractions)))
        return [1000.0, 2000.0, 3000.0]


class ExperimentalMapper:
    def __init__(self, *, error=None):
        self.error = error
        self.reset_calls = []

    def reset(self, current_positions=None):
        self.reset_calls.append(
            None if current_positions is None else list(current_positions)
        )

    def map_observation(self, _observation):
        if self.error:
            raise self.error
        return [4000.0, 5000.0, 6000.0], {
            "thumb": 0.4,
            "thumb_spread": 0.5,
            "index": 0.6,
        }


def observation():
    return SimpleNamespace(
        curls={"thumb": 0.1, "index": 0.3},
        thumb_spread=0.2,
        pinch_strength=0.7,
        finger_retractions={"middle": 0.4, "ring": 0.5, "pinky": 0.6},
        world_landmarks=None,
    )


def test_stable_strategy_preserves_existing_mapper_inputs_and_outputs():
    stable = RecordingStableMapper()
    coordinator = RetargetingCoordinator(stable_mapper=stable)

    result = coordinator.map_observation(observation())

    assert result.positions == [1000.0, 2000.0, 3000.0]
    assert result.selected_strategy == RETARGETING_STABLE
    assert result.effective_strategy == RETARGETING_STABLE
    assert result.fallback_reason == ""
    assert stable.calls == [
        (
            {"thumb": 0.1, "index": 0.3, "thumb_spread": 0.2},
            0.7,
            {"middle": 0.4, "ring": 0.5, "pinky": 0.6},
        )
    ]


def test_unknown_strategy_is_rejected_without_changing_selection():
    coordinator = RetargetingCoordinator(stable_mapper=RecordingStableMapper())

    with pytest.raises(ValueError, match="未知重定向策略"):
        coordinator.set_strategy("other", current_positions=[0, 0, 0])

    assert coordinator.selected_strategy == RETARGETING_STABLE


def test_dexpilot_strategy_initializes_from_current_positions():
    experimental = ExperimentalMapper()
    coordinator = RetargetingCoordinator(RecordingStableMapper(), experimental)

    coordinator.set_strategy(RETARGETING_DEXPILOT, [1000, 2000, 3000])
    result = coordinator.map_observation(observation())

    assert experimental.reset_calls[-1] == [1000, 2000, 3000]
    assert result.positions == [4000.0, 5000.0, 6000.0]
    assert result.selected_strategy == RETARGETING_DEXPILOT
    assert result.effective_strategy == RETARGETING_DEXPILOT
    assert result.fallback_reason == ""


def test_invalid_experimental_frame_falls_back_to_stable_for_that_frame():
    coordinator = RetargetingCoordinator(
        RecordingStableMapper(),
        ExperimentalMapper(error=ValueError("bad frame")),
    )
    coordinator.set_strategy(RETARGETING_DEXPILOT, [0, 0, 0])

    result = coordinator.map_observation(observation())

    assert result.selected_strategy == RETARGETING_DEXPILOT
    assert result.effective_strategy == RETARGETING_STABLE
    assert result.positions == [1000.0, 2000.0, 3000.0]
    assert result.fallback_reason == "bad frame"
