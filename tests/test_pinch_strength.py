import numpy as np
import pytest

from gesture_recognizer import _compute_pinch_strength


def _landmarks_with_normalized_pinch_distance(distance: float) -> np.ndarray:
    landmarks = np.zeros((21, 3), dtype=np.float32)
    landmarks[0] = [0.0, 0.0, 0.0]
    landmarks[9] = [1.0, 0.0, 0.0]
    landmarks[4] = [0.0, 0.0, 0.0]
    landmarks[8] = [distance, 0.0, 0.0]
    return landmarks


@pytest.mark.parametrize(
    ("distance", "expected"),
    [(0.50, 0.0), (0.45, 0.0), (0.30, 0.5), (0.15, 1.0), (0.05, 1.0)],
)
def test_pinch_strength_maps_tip_distance_to_a_bounded_continuous_value(
    distance: float,
    expected: float,
):
    landmarks = _landmarks_with_normalized_pinch_distance(distance)

    assert _compute_pinch_strength(landmarks) == pytest.approx(expected)


def test_pinch_strength_increases_monotonically_as_fingertips_approach():
    distances = [0.45, 0.35, 0.25, 0.15]
    strengths = [
        _compute_pinch_strength(_landmarks_with_normalized_pinch_distance(value))
        for value in distances
    ]

    assert strengths == sorted(strengths)
