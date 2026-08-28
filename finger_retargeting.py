"""轻量级手指重定向几何特征。

本模块只处理纯 NumPy 坐标，不依赖 MediaPipe、驱动或 GUI。这样既方便
单元测试，也为后续接入完整 dex-retargeting 策略保留清晰边界。
"""

from __future__ import annotations

from typing import Dict

import numpy as np


TARGET_FINGER_INDICES = {
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}


def _tip_retraction(points: np.ndarray) -> float:
    """返回一根手指的尺度无关指尖回缩量。

    `points` 按 MCP、PIP、DIP、TIP 排列。伸直时 MCP 到 TIP 的直线距离
    接近三段骨链之和，结果接近 0；蜷缩时直线距离缩短，结果逐渐增大。
    """

    segments = np.diff(points, axis=0)
    chain_length = float(np.linalg.norm(segments, axis=1).sum())
    if chain_length < 1e-6:
        return 0.0
    direct_reach = float(np.linalg.norm(points[-1] - points[0]))
    return float(np.clip(1.0 - direct_reach / chain_length, 0.0, 1.0))


def compute_tip_retractions(landmarks: np.ndarray) -> Dict[str, float]:
    """计算中指、无名指和小指的指尖回缩量。"""

    return {
        finger: _tip_retraction(landmarks[list(indices)])
        for finger, indices in TARGET_FINGER_INDICES.items()
    }
