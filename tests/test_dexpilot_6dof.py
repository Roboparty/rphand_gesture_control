from types import SimpleNamespace

import numpy as np
import pytest

from dexpilot_6dof import (
    ContactTracker,
    DexPilot6DofMapper,
    GeometryError,
    palm_local_landmarks,
    thumb_tip_distances,
)
from tests.hand_landmark_fixtures import open_hand, transformed


JOINTS = [
    {"name": "thumb_rotate", "src": "thumb_spread", "range": [0, 10000]},
    {"name": "thumb_bend", "src": "thumb", "range": [0, 10000]},
    {"name": "index_finger", "src": "index", "range": [0, 10000]},
    {"name": "middle_finger", "src": "middle", "range": [0, 10000]},
    {"name": "ring_finger", "src": "ring", "range": [0, 10000]},
    {"name": "pinky_finger", "src": "pinky", "range": [0, 10000]},
]
CONFIG = {
    "temporal_weight": 0.20,
    "project_distance": 0.30,
    "escape_distance": 0.42,
    "base_weight": 1.0,
    "contact_weight": 2.5,
    "opposition_targets": {
        "index": 0.35,
        "middle": 0.52,
        "ring": 0.70,
        "pinky": 0.88,
    },
}


def observation(points, curls=None, handedness="Right"):
    return SimpleNamespace(
        world_landmarks=points,
        handedness=handedness,
        curls=curls
        or {
            name: 0.0
            for name in ("thumb", "index", "middle", "ring", "pinky")
        },
        thumb_spread=0.0,
    )


def test_palm_frame_removes_translation_rotation_and_scale():
    original = palm_local_landmarks(open_hand())
    moved = palm_local_landmarks(transformed(open_hand()))

    assert moved == pytest.approx(original, abs=1e-6)


def test_left_and_right_mirror_inputs_keep_the_same_six_dof_targets():
    """当前六个无符号特征允许任一人手控制同一只硬件手。"""

    right_points = open_hand()
    left_points = right_points.copy()
    left_points[:, 0] *= -1
    right_mapper = DexPilot6DofMapper(JOINTS, input_calibration={}, config=CONFIG)
    left_mapper = DexPilot6DofMapper(JOINTS, input_calibration={}, config=CONFIG)

    right_positions, _ = right_mapper.map_observation(
        observation(right_points, handedness="Right")
    )
    left_positions, _ = left_mapper.map_observation(
        observation(left_points, handedness="Left")
    )

    assert left_positions == pytest.approx(right_positions)


def test_thumb_tip_distances_are_palm_width_normalized():
    distances = thumb_tip_distances(palm_local_landmarks(open_hand()))

    assert set(distances) == {"index", "middle", "ring", "pinky"}
    assert all(np.isfinite(value) and value > 0 for value in distances.values())


@pytest.mark.parametrize(
    "bad",
    [
        np.zeros((20, 3)),
        np.full((21, 3), np.nan),
        np.zeros((21, 3)),
    ],
)
def test_invalid_or_degenerate_geometry_is_rejected(bad):
    with pytest.raises(GeometryError):
        palm_local_landmarks(bad)


def test_contact_hysteresis_does_not_flicker_between_thresholds():
    tracker = ContactTracker(project_distance=0.30, escape_distance=0.42)

    assert tracker.update({"index": 0.29}) == {
        "index": pytest.approx((0.42 - 0.29) / 0.42)
    }
    assert "index" in tracker.update({"index": 0.36})
    assert tracker.update({"index": 0.43}) == {}


def test_contact_tracker_prioritizes_the_closest_finger():
    tracker = ContactTracker(project_distance=0.30, escape_distance=0.42)

    weights = tracker.update({"index": 0.25, "middle": 0.10})

    assert weights["middle"] > weights["index"] > 0


def test_optimizer_returns_finite_bounded_six_joint_targets():
    mapper = DexPilot6DofMapper(JOINTS, input_calibration={}, config=CONFIG)

    positions, display = mapper.map_observation(observation(open_hand()))

    assert len(positions) == 6
    assert all(np.isfinite(value) and 0 <= value <= 10000 for value in positions)
    assert all(np.isfinite(value) and 0 <= value <= 1 for value in display.values())


def test_thumb_flexion_drives_the_second_hardware_axis():
    """DH116 轴 1 是外展，单独屈曲时只能显著驱动轴 2。"""

    mapper = DexPilot6DofMapper(
        JOINTS,
        input_calibration={},
        config=CONFIG,
    )
    curls = {"thumb": 1, "index": 0, "middle": 0, "ring": 0, "pinky": 0}

    positions, _ = mapper.map_observation(observation(open_hand(), curls))

    assert positions[0] < 2000
    assert positions[1] > 8000


def test_dexpilot_rejects_joint_order_that_swaps_thumb_axes():
    swapped_joints = [JOINTS[1], JOINTS[0], *JOINTS[2:]]

    with pytest.raises(ValueError, match="关节顺序"):
        DexPilot6DofMapper(
            swapped_joints,
            input_calibration={},
            config=CONFIG,
        )


def test_single_ring_curl_does_not_close_unrelated_fingers():
    mapper = DexPilot6DofMapper(JOINTS, input_calibration={}, config=CONFIG)
    curls = {"thumb": 0, "index": 0, "middle": 0, "ring": 1, "pinky": 0}

    positions, _ = mapper.map_observation(observation(open_hand(), curls))

    assert positions[4] > 8000
    assert max(positions[2], positions[3], positions[5]) < 2000


def test_temporal_regularization_limits_the_first_changed_frame():
    mapper = DexPilot6DofMapper(JOINTS, input_calibration={}, config=CONFIG)
    mapper.reset([0] * 6)
    curls = {"thumb": 0, "index": 1, "middle": 0, "ring": 0, "pinky": 0}

    first, _ = mapper.map_observation(observation(open_hand(), curls))
    second, _ = mapper.map_observation(observation(open_hand(), curls))

    assert 0 < first[2] < second[2] <= 10000


def test_thumb_opposition_increases_from_index_contact_to_pinky_contact():
    rotations = []
    for tip_index in (8, 12, 16, 20):
        points = open_hand()
        points[4] = points[tip_index]
        mapper = DexPilot6DofMapper(JOINTS, input_calibration={}, config=CONFIG)
        mapper.reset([0] * 6)

        positions, _ = mapper.map_observation(observation(points))
        rotations.append(positions[0])

    assert rotations == sorted(rotations)
    assert len(set(round(value, 6) for value in rotations)) == 4
