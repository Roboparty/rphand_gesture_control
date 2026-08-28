from types import SimpleNamespace

import pytest

from retargeting_strategy import RETARGETING_STABLE, RetargetingCoordinator


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
