"""受 DexPilot 启发的六自由度手部重定向几何与求解器。"""

from __future__ import annotations

import numpy as np


FINGER_CHAINS = {
    "thumb": (1, 2, 3, 4),
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}
FINGER_TIPS = {"index": 8, "middle": 12, "ring": 16, "pinky": 20}


class GeometryError(ValueError):
    """Raised when a hand frame cannot form a reliable palm coordinate system."""


def _unit(vector: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(vector))
    if length < 1e-6:
        raise GeometryError("掌心坐标轴退化")
    return vector / length


def palm_local_landmarks(landmarks: np.ndarray) -> np.ndarray:
    """Normalize 21 world landmarks into a right-handed palm-local frame."""

    points = np.asarray(landmarks, dtype=np.float64)
    if points.shape != (21, 3) or not np.isfinite(points).all():
        raise GeometryError("手部关键点必须是有限的 21x3 坐标")

    across = points[5] - points[17]
    palm_width = float(np.linalg.norm(across))
    if palm_width < 1e-6:
        raise GeometryError("掌宽过小")

    x_axis = across / palm_width
    forward = points[9] - points[0]
    y_axis = _unit(forward - np.dot(forward, x_axis) * x_axis)
    z_axis = _unit(np.cross(x_axis, y_axis))
    basis = np.column_stack((x_axis, y_axis, z_axis))
    return ((points - points[0]) @ basis) / palm_width


def thumb_tip_distances(local_points: np.ndarray) -> dict[str, float]:
    """Return palm-width-normalized distances from thumb to each fingertip."""

    thumb_tip = local_points[4]
    return {
        finger: float(np.linalg.norm(thumb_tip - local_points[index]))
        for finger, index in FINGER_TIPS.items()
    }
