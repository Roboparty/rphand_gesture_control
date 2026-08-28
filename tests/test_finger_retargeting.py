from __future__ import annotations

import importlib

import numpy as np
import pytest

from gesture_recognizer import HandObservation


FINGER_INDICES = {
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}


def _straight_landmarks() -> np.ndarray:
    landmarks = np.zeros((21, 3), dtype=np.float32)
    for row, indices in enumerate(FINGER_INDICES.values()):
        y = float(row)
        landmarks[list(indices)] = (
            (0.0, y, 0.0),
            (1.0, y, 0.0),
            (2.0, y, 0.0),
            (3.0, y, 0.0),
        )
    return landmarks


def _compute(landmarks: np.ndarray) -> dict[str, float]:
    module = importlib.import_module("finger_retargeting")
    return module.compute_tip_retractions(landmarks)


def test_straight_fingers_have_zero_tip_retraction():
    assert _compute(_straight_landmarks()) == pytest.approx(
        {"middle": 0.0, "ring": 0.0, "pinky": 0.0}
    )


def test_curled_finger_uses_the_full_mcp_pip_dip_tip_chain():
    landmarks = _straight_landmarks()
    landmarks[list(FINGER_INDICES["pinky"])] = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
    )

    result = _compute(landmarks)

    assert result["pinky"] == pytest.approx(2.0 / 3.0)
    assert result["middle"] == pytest.approx(0.0)
    assert result["ring"] == pytest.approx(0.0)


def test_tip_retraction_is_invariant_to_scale_rotation_and_translation():
    landmarks = _straight_landmarks()
    landmarks[list(FINGER_INDICES["ring"])] = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.2, 1.0, 0.0),
    )
    rotation = np.array(
        ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        dtype=np.float32,
    )
    transformed = (landmarks @ rotation.T) * 4.25 + np.array(
        (3.0, -7.0, 2.0), dtype=np.float32
    )

    assert _compute(transformed) == pytest.approx(_compute(landmarks))


def test_degenerate_tracking_geometry_falls_back_to_zero_retraction():
    landmarks = _straight_landmarks()
    landmarks[list(FINGER_INDICES["middle"])] = (0.0, 0.0, 0.0)

    assert _compute(landmarks)["middle"] == 0.0


def test_hand_observation_exposes_retractions_without_shared_mutable_state():
    first = HandObservation()
    second = HandObservation()

    first.finger_retractions["middle"] = 0.5

    assert second.finger_retractions == {
        "middle": 0.0,
        "ring": 0.0,
        "pinky": 0.0,
    }
