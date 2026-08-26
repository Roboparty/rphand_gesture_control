from __future__ import annotations

import numpy as np
import pytest

from geometry_diagnostics import measure_four_finger_angles, summarize_angle_samples


FOUR_FINGER_INDICES = {
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}


def _straight_landmarks() -> np.ndarray:
    landmarks = np.zeros((21, 3), dtype=np.float32)
    for row, indices in enumerate(FOUR_FINGER_INDICES.values()):
        y = float(row)
        landmarks[list(indices)] = (
            (0, y, 0),
            (1, y, 0),
            (2, y, 0),
            (3, y, 0),
        )
    return landmarks


def test_measure_four_finger_angles_reports_legacy_pip_and_dip():
    landmarks = _straight_landmarks()
    mcp, pip, dip, tip = FOUR_FINGER_INDICES["index"]
    landmarks[[mcp, pip, dip, tip]] = (
        (0, 0, 0),
        (1, 0, 0),
        (1, 1, 0),
        (0, 1, 0),
    )

    angles = measure_four_finger_angles(landmarks)

    assert angles["index"] == pytest.approx({
        "legacy": 45.0,
        "pip": 90.0,
        "dip": 90.0,
    })
    assert angles["middle"] == pytest.approx({
        "legacy": 180.0,
        "pip": 180.0,
        "dip": 180.0,
    })


def test_summarize_angle_samples_uses_robust_percentiles():
    samples = [
        {
            finger: {"legacy": value, "pip": value + 1, "dip": value + 2}
            for finger in FOUR_FINGER_INDICES
        }
        for value in (10.0, 20.0, 30.0, 40.0, 50.0)
    ]

    summary = summarize_angle_samples(samples)

    assert summary["sample_count"] == 5
    assert summary["fingers"]["index"]["legacy"] == pytest.approx({
        "min": 10.0,
        "p05": 12.0,
        "median": 30.0,
        "p95": 48.0,
        "max": 50.0,
    })


def test_summarize_angle_samples_rejects_empty_input():
    with pytest.raises(ValueError, match="至少需要一帧"):
        summarize_angle_samples([])
