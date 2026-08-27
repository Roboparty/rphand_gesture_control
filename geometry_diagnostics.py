"""Camera-only helpers for measuring real hand joint-angle ranges."""

from __future__ import annotations

from typing import Dict, Iterable

import numpy as np

from gesture_recognizer import _angle_deg


FOUR_FINGER_JOINTS = {
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}


def measure_four_finger_angles(landmarks: np.ndarray) -> Dict[str, Dict[str, float]]:
    """Measure legacy, PIP, and DIP angles without converting them to curl."""
    points = np.asarray(landmarks, dtype=np.float32)
    if points.shape != (21, 3):
        raise ValueError("landmarks 必须是 (21, 3) 数组")

    measurements: Dict[str, Dict[str, float]] = {}
    for finger, (mcp, pip, dip, tip) in FOUR_FINGER_JOINTS.items():
        measurements[finger] = {
            "legacy": _angle_deg(points[mcp], points[pip], points[tip]),
            "pip": _angle_deg(points[mcp], points[pip], points[dip]),
            "dip": _angle_deg(points[pip], points[dip], points[tip]),
        }
    return measurements


def summarize_angle_samples(
    samples: Iterable[Dict[str, Dict[str, float]]],
) -> Dict[str, object]:
    """Summarize captured frames with percentiles that resist outliers."""
    captured = list(samples)
    if not captured:
        raise ValueError("至少需要一帧有效手部数据")

    fingers: Dict[str, Dict[str, Dict[str, float]]] = {}
    for finger in FOUR_FINGER_JOINTS:
        metrics: Dict[str, Dict[str, float]] = {}
        for metric in ("legacy", "pip", "dip"):
            values = np.asarray(
                [sample[finger][metric] for sample in captured],
                dtype=np.float64,
            )
            metrics[metric] = {
                "min": float(np.min(values)),
                "p05": float(np.percentile(values, 5)),
                "median": float(np.median(values)),
                "p95": float(np.percentile(values, 95)),
                "max": float(np.max(values)),
            }
        fingers[finger] = metrics

    return {
        "sample_count": len(captured),
        "fingers": fingers,
    }
