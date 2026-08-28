"""受 DexPilot 启发的六自由度手部重定向几何与求解器。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np

from gesture_mapping import project_normalized_value


FINGER_CHAINS = {
    "thumb": (1, 2, 3, 4),
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}
FINGER_TIPS = {"index": 8, "middle": 12, "ring": 16, "pinky": 20}
CHANNELS = ("thumb", "thumb_spread", "index", "middle", "ring", "pinky")
CONTACT_CHANNEL_INDEX = {"index": 2, "middle": 3, "ring": 4, "pinky": 5}


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


@dataclass
class ContactTracker:
    """Track fingertip contact with separate enter and release thresholds."""

    project_distance: float
    escape_distance: float
    active: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not 0 < self.project_distance < self.escape_distance:
            raise ValueError("接触投影距离必须小于释放距离")

    def reset(self) -> None:
        self.active.clear()

    def update(self, distances: Mapping[str, float]) -> dict[str, float]:
        weights: dict[str, float] = {}
        for finger, distance in distances.items():
            value = float(distance)
            if finger in self.active:
                if value > self.escape_distance:
                    self.active.remove(finger)
                    continue
            elif value <= self.project_distance:
                self.active.add(finger)

            if finger in self.active:
                weights[finger] = float(
                    np.clip(
                        (self.escape_distance - value) / self.escape_distance,
                        0.0,
                        1.0,
                    )
                )
        return weights


def _calibrate(
    value: float,
    calibration: Mapping[str, float] | None,
) -> float:
    if not calibration:
        return float(np.clip(value, 0.0, 1.0))

    opened = float(calibration.get("open", 0.0))
    closed = float(calibration.get("closed", 1.0))
    if not 0 <= opened < closed <= 1:
        raise ValueError("实验映射校准端点无效")
    return float(np.clip((value - opened) / (closed - opened), 0.0, 1.0))


def _solve_weighted_targets(
    rows: Sequence[Sequence[float]],
    targets: Sequence[float],
    weights: Sequence[float],
    previous: np.ndarray,
    temporal_weight: float,
) -> np.ndarray:
    matrix = np.asarray(rows, dtype=np.float64)
    target = np.asarray(targets, dtype=np.float64)
    weight = np.asarray(weights, dtype=np.float64)
    lhs = (
        matrix.T @ (weight[:, None] * matrix)
        + temporal_weight * np.eye(len(CHANNELS))
    )
    rhs = matrix.T @ (weight * target) + temporal_weight * previous
    solution = np.linalg.solve(lhs, rhs)
    if not np.isfinite(solution).all():
        raise GeometryError("DexPilot 6DOF 求解结果无效")
    return np.clip(solution, 0.0, 1.0)


class DexPilot6DofMapper:
    """Project palm-local fingertip objectives onto six RP-Hand channels."""

    def __init__(
        self,
        joints: Sequence[dict],
        input_calibration: Mapping[str, Mapping[str, float]],
        config: Mapping[str, object],
    ) -> None:
        if len(joints) != len(CHANNELS):
            raise ValueError("DexPilot 6DOF 需要恰好六个关节")

        self._joints = list(joints)
        self._input_calibration = dict(input_calibration)
        self._temporal_weight = float(config.get("temporal_weight", 0.20))
        self._base_weight = float(config.get("base_weight", 1.0))
        self._contact_weight = float(config.get("contact_weight", 2.5))
        self._opposition_targets = {
            finger: float(value)
            for finger, value in dict(config.get("opposition_targets", {})).items()
        }
        missing = set(CONTACT_CHANNEL_INDEX) - set(self._opposition_targets)
        if missing:
            raise ValueError(f"DexPilot 缺少对掌目标: {', '.join(sorted(missing))}")
        if min(self._temporal_weight, self._base_weight, self._contact_weight) < 0:
            raise ValueError("DexPilot 权重不能为负数")

        self._contacts = ContactTracker(
            project_distance=float(config.get("project_distance", 0.30)),
            escape_distance=float(config.get("escape_distance", 0.42)),
        )
        self._previous = np.zeros(len(CHANNELS), dtype=np.float64)

    def reset(self, current_positions: Sequence[float] | None = None) -> None:
        """Reset contact state and seed temporal continuity from current targets."""

        self._contacts.reset()
        if current_positions is None:
            self._previous = np.zeros(len(CHANNELS), dtype=np.float64)
            return
        if len(current_positions) != len(self._joints):
            raise ValueError("当前关节位置数量与 DexPilot 关节数量不一致")

        normalized = []
        for position, joint in zip(current_positions, self._joints):
            opened, closed = (float(value) for value in joint["range"])
            span = closed - opened
            if abs(span) < 1e-9:
                raise ValueError(f"关节 {joint.get('name', '')} 的范围不能为零")
            normalized.append(np.clip((float(position) - opened) / span, 0.0, 1.0))
        self._previous = np.asarray(normalized, dtype=np.float64)

    def _base_targets(self, observation) -> np.ndarray:
        raw = dict(observation.curls)
        raw["thumb_spread"] = float(observation.thumb_spread)
        return np.asarray(
            [
                _calibrate(raw.get(channel, 0.0), self._input_calibration.get(channel))
                for channel in CHANNELS
            ],
            dtype=np.float64,
        )

    def map_observation(self, observation) -> tuple[list[float], dict[str, float]]:
        local_points = palm_local_landmarks(observation.world_landmarks)
        contact_strengths = self._contacts.update(thumb_tip_distances(local_points))
        base = self._base_targets(observation)

        rows = np.eye(len(CHANNELS), dtype=np.float64).tolist()
        targets = base.tolist()
        weights = [self._base_weight] * len(CHANNELS)

        for finger, strength in contact_strengths.items():
            objective_weight = self._contact_weight * strength
            finger_index = CONTACT_CHANNEL_INDEX[finger]
            for channel_index, target in (
                (0, 0.82),
                (finger_index, max(base[finger_index], 0.72 * strength)),
                (1, self._opposition_targets[finger]),
            ):
                row = np.zeros(len(CHANNELS), dtype=np.float64)
                row[channel_index] = 1.0
                rows.append(row.tolist())
                targets.append(float(target))
                weights.append(objective_weight)

        solution = _solve_weighted_targets(
            rows,
            targets,
            weights,
            self._previous,
            self._temporal_weight,
        )
        self._previous = solution

        positions = [
            project_normalized_value(value, joint)
            for value, joint in zip(solution, self._joints)
        ]
        display_inputs = {
            channel: float(solution[index])
            for index, channel in enumerate(CHANNELS)
        }
        return positions, display_inputs
