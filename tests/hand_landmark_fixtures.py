from __future__ import annotations

import numpy as np


FINGER_CHAINS = {
    "thumb": (1, 2, 3, 4),
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}


def open_hand() -> np.ndarray:
    """Return a deterministic open-hand fixture in a common 3D scale."""

    points = np.zeros((21, 3), dtype=np.float64)
    points[0] = (0.0, 0.0, 0.0)
    points[list(FINGER_CHAINS["thumb"])] = (
        (0.38, 0.34, 0.0),
        (0.58, 0.48, 0.0),
        (0.78, 0.62, 0.0),
        (0.98, 0.76, 0.0),
    )
    for name, x, y in (
        ("index", 0.42, 0.92),
        ("middle", 0.14, 1.02),
        ("ring", -0.16, 0.96),
        ("pinky", -0.42, 0.82),
    ):
        chain = FINGER_CHAINS[name]
        points[list(chain)] = (
            (x, y, 0.0),
            (x, y + 0.42, 0.0),
            (x, y + 0.76, 0.0),
            (x, y + 1.06, 0.0),
        )
    return points


def transformed(points: np.ndarray, scale: float = 3.5) -> np.ndarray:
    """Apply a rigid transform and uniform scale to a landmark fixture."""

    rotation = np.array(
        (
            (0.0, -1.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
        )
    )
    return (points @ rotation.T) * scale + np.array((4.0, -3.0, 2.0))
