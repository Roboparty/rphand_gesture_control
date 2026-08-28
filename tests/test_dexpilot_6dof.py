import numpy as np
import pytest

from dexpilot_6dof import GeometryError, palm_local_landmarks, thumb_tip_distances
from tests.hand_landmark_fixtures import open_hand, transformed


def test_palm_frame_removes_translation_rotation_and_scale():
    original = palm_local_landmarks(open_hand())
    moved = palm_local_landmarks(transformed(open_hand()))

    assert moved == pytest.approx(original, abs=1e-6)


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
