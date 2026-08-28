# DexPilot-Inspired 6DOF Retargeting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reversible `DexPilot 6DOF（实验）` mapping algorithm beside the current stable mapping, with safe runtime switching and Electron A/B controls.

**Architecture:** A `RetargetingCoordinator` owns an unchanged stable `GestureMapper` adapter and an independent pure-NumPy `DexPilot6DofMapper`. The experimental mapper converts MediaPipe world landmarks to a normalized palm frame, constructs curl and thumb-contact objectives, solves a bounded six-variable weighted least-squares projection, and returns the same six hardware targets as the stable mapper. Runtime safety, sending, emergency stop, recovery, presets, and the CAN-FD driver remain outside both strategies.

**Tech Stack:** Python 3.12, NumPy, MediaPipe, pytest, Electron 44, Node test runner, PyInstaller, electron-builder/NSIS.

---

## File Structure

- Create `dexpilot_6dof.py`: palm-local geometry, contact hysteresis, weighted projection, and the experimental mapper.
- Create `retargeting_strategy.py`: strategy constants, result type, stable/experimental coordination, switching, and fallback.
- Create `tests/hand_landmark_fixtures.py`: deterministic synthetic 21-point hands shared by geometry tests.
- Create `tests/test_dexpilot_6dof.py`: pure geometry and optimizer tests.
- Create `tests/test_retargeting_strategy.py`: stable regression, switching continuity, and fallback tests.
- Modify `gesture_mapping.py`: expose only a small normalized-channel-to-joint-range projection helper; leave stable formulas unchanged.
- Modify `main.py`: construct the coordinator, route mirror observations through it, and process two new algorithm commands.
- Modify `electron_bridge.py`: whitelist stable/DexPilot command keys.
- Modify `runtime_telemetry.py`: publish selected/effective strategy and fallback reason.
- Modify `config.yaml`: add default strategy and experimental weights without changing stable calibration.
- Modify `electron/bridge-protocol.cjs`: validate the two new commands and retargeting telemetry.
- Modify `electron/renderer/index.html`: replace the single control-mode option with the two algorithm options.
- Modify `electron/renderer/app.js`: send retargeting commands and synchronize the selector from backend state.
- Modify `electron/renderer/telemetry-state.cjs`: expose strategy status to the renderer view model.
- Modify Python and Electron tests adjacent to the changed protocol.
- Modify `README.md`: document the experimental selector, limitations, and stable fallback.

## Task 1: Lock Stable Mapping and Add the Strategy Boundary

**Files:**
- Create: `tests/test_retargeting_strategy.py`
- Create: `retargeting_strategy.py`
- Modify: `gesture_mapping.py:124-147`
- Test: `tests/test_gesture_mapping.py`

- [ ] **Step 1: Write the failing stable-strategy regression tests**

Add tests that prove the coordinator passes the existing observation fields to `GestureMapper` unchanged and reports the stable strategy:

```python
from types import SimpleNamespace

import pytest

from retargeting_strategy import RETARGETING_STABLE, RetargetingCoordinator


class RecordingStableMapper:
    joint_names = ["thumb_bend", "thumb_rotate", "index_finger"]
    num_joints = 3

    def __init__(self):
        self.calls = []

    def calibrate_inputs(self, values):
        return dict(values)

    def map_mirror(self, values, pinch_strength=0.0, finger_retractions=None):
        self.calls.append((dict(values), pinch_strength, dict(finger_retractions)))
        return [1000.0, 2000.0, 3000.0]


def observation():
    return SimpleNamespace(
        curls={"thumb": 0.1, "index": 0.3},
        thumb_spread=0.2,
        pinch_strength=0.7,
        finger_retractions={"middle": 0.4, "ring": 0.5, "pinky": 0.6},
        world_landmarks=None,
    )


def test_stable_strategy_preserves_existing_mapper_inputs_and_outputs():
    stable = RecordingStableMapper()
    coordinator = RetargetingCoordinator(stable_mapper=stable)

    result = coordinator.map_observation(observation())

    assert result.positions == [1000.0, 2000.0, 3000.0]
    assert result.selected_strategy == RETARGETING_STABLE
    assert result.effective_strategy == RETARGETING_STABLE
    assert result.fallback_reason == ""
    assert stable.calls == [(
        {"thumb": 0.1, "index": 0.3, "thumb_spread": 0.2},
        0.7,
        {"middle": 0.4, "ring": 0.5, "pinky": 0.6},
    )]


def test_unknown_strategy_is_rejected_without_changing_selection():
    coordinator = RetargetingCoordinator(stable_mapper=RecordingStableMapper())

    with pytest.raises(ValueError, match="未知重定向策略"):
        coordinator.set_strategy("other", current_positions=[0, 0, 0])

    assert coordinator.selected_strategy == RETARGETING_STABLE
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_retargeting_strategy.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'retargeting_strategy'`.

- [ ] **Step 3: Implement the stable strategy boundary**

Create `retargeting_strategy.py` with immutable result data and a coordinator that defaults to stable mode:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from gesture_recognizer import HandObservation

RETARGETING_STABLE = "stable"
RETARGETING_DEXPILOT = "dexpilot"
VALID_RETARGETING_STRATEGIES = {RETARGETING_STABLE, RETARGETING_DEXPILOT}


@dataclass(frozen=True)
class RetargetingResult:
    positions: list[float]
    display_inputs: dict[str, float]
    selected_strategy: str
    effective_strategy: str
    fallback_reason: str = ""


class ExperimentalMapper(Protocol):
    def reset(self, current_positions: Sequence[float] | None = None) -> None: ...
    def map_observation(self, observation: HandObservation) -> tuple[list[float], dict[str, float]]: ...


class RetargetingCoordinator:
    def __init__(self, stable_mapper, experimental_mapper: ExperimentalMapper | None = None,
                 strategy: str = RETARGETING_STABLE) -> None:
        self._stable_mapper = stable_mapper
        self._experimental_mapper = experimental_mapper
        self._selected_strategy = RETARGETING_STABLE
        self.set_strategy(strategy, current_positions=None)

    @property
    def selected_strategy(self) -> str:
        return self._selected_strategy

    def set_strategy(self, strategy: str,
                     current_positions: Sequence[float] | None) -> None:
        if strategy not in VALID_RETARGETING_STRATEGIES:
            raise ValueError(f"未知重定向策略: {strategy}")
        if strategy == RETARGETING_DEXPILOT and self._experimental_mapper is None:
            raise ValueError("DexPilot 6DOF 映射器尚未初始化")
        self._selected_strategy = strategy
        if self._experimental_mapper is not None:
            self._experimental_mapper.reset(current_positions)

    def _stable_result(self, observation: HandObservation, *,
                       selected: str = RETARGETING_STABLE,
                       fallback_reason: str = "") -> RetargetingResult:
        values = dict(observation.curls)
        values["thumb_spread"] = observation.thumb_spread
        display = self._stable_mapper.calibrate_inputs(values)
        positions = self._stable_mapper.map_mirror(
            values,
            pinch_strength=observation.pinch_strength,
            finger_retractions=getattr(observation, "finger_retractions", None),
        )
        return RetargetingResult(
            positions=list(positions),
            display_inputs=display,
            selected_strategy=selected,
            effective_strategy=RETARGETING_STABLE,
            fallback_reason=fallback_reason,
        )

    def map_observation(self, observation: HandObservation) -> RetargetingResult:
        return self._stable_result(observation)
```

Extract a side-effect-free range helper in `gesture_mapping.py`, then use it inside the existing `map_mirror` loop without changing results:

```python
def project_normalized_value(value: float, joint: dict) -> float:
    lo, hi = joint["range"]
    unit = min(max(float(value), 0.0), 1.0)
    return lo + (hi - lo) * unit
```

- [ ] **Step 4: Run stable mapping and strategy tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_retargeting_strategy.py tests/test_gesture_mapping.py -q
```

Expected: all tests pass, including the existing real-hardware endpoint tests.

- [ ] **Step 5: Commit the strategy boundary**

```powershell
git add retargeting_strategy.py gesture_mapping.py tests/test_retargeting_strategy.py tests/test_gesture_mapping.py
git commit -m "refactor: 建立可切换的手部重定向策略边界" -m "保留现有 GestureMapper 行为，并增加统一结果类型与安全的策略选择入口。"
```

## Task 2: Implement Palm-Local Geometry

**Files:**
- Create: `tests/hand_landmark_fixtures.py`
- Create: `tests/test_dexpilot_6dof.py`
- Create: `dexpilot_6dof.py`

- [ ] **Step 1: Add deterministic hand-landmark fixtures**

Create `tests/hand_landmark_fixtures.py` with a full 21-point open hand and transforms used by multiple tests:

```python
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
    points = np.zeros((21, 3), dtype=np.float64)
    points[0] = (0.0, 0.0, 0.0)
    points[list(FINGER_CHAINS["thumb"])] = (
        (0.38, 0.34, 0.0), (0.58, 0.48, 0.0),
        (0.78, 0.62, 0.0), (0.98, 0.76, 0.0),
    )
    for name, x, y in (
        ("index", 0.42, 0.92), ("middle", 0.14, 1.02),
        ("ring", -0.16, 0.96), ("pinky", -0.42, 0.82),
    ):
        chain = FINGER_CHAINS[name]
        points[list(chain)] = (
            (x, y, 0.0), (x, y + 0.42, 0.0),
            (x, y + 0.76, 0.0), (x, y + 1.06, 0.0),
        )
    return points


def transformed(points: np.ndarray, scale: float = 3.5) -> np.ndarray:
    rotation = np.array(((0.0, -1.0, 0.0),
                         (1.0, 0.0, 0.0),
                         (0.0, 0.0, 1.0)))
    return (points @ rotation.T) * scale + np.array((4.0, -3.0, 2.0))
```

- [ ] **Step 2: Write failing geometry tests**

Add to `tests/test_dexpilot_6dof.py`:

```python
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


@pytest.mark.parametrize("bad", [
    np.zeros((20, 3)),
    np.full((21, 3), np.nan),
    np.zeros((21, 3)),
])
def test_invalid_or_degenerate_geometry_is_rejected(bad):
    with pytest.raises(GeometryError):
        palm_local_landmarks(bad)
```

- [ ] **Step 3: Run tests and verify they fail**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dexpilot_6dof.py -q
```

Expected: collection fails because `dexpilot_6dof.py` does not exist.

- [ ] **Step 4: Implement palm-local geometry**

Create `dexpilot_6dof.py` with strict validation and a right-handed palm frame:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np

FINGER_CHAINS = {
    "thumb": (1, 2, 3, 4), "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12), "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}
FINGER_TIPS = {"index": 8, "middle": 12, "ring": 16, "pinky": 20}


class GeometryError(ValueError):
    pass


def _unit(vector: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(vector))
    if length < 1e-6:
        raise GeometryError("掌心坐标轴退化")
    return vector / length


def palm_local_landmarks(landmarks: np.ndarray) -> np.ndarray:
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
    thumb_tip = local_points[4]
    return {
        finger: float(np.linalg.norm(thumb_tip - local_points[index]))
        for finger, index in FINGER_TIPS.items()
    }
```

- [ ] **Step 5: Run geometry tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dexpilot_6dof.py -q
```

Expected: all geometry tests pass.

- [ ] **Step 6: Commit pure geometry**

```powershell
git add dexpilot_6dof.py tests/hand_landmark_fixtures.py tests/test_dexpilot_6dof.py
git commit -m "feat: 增加 DexPilot 掌心局部几何特征" -m "提供平移、旋转和尺度无关的坐标系，并计算归一化拇指指尖距离。"
```

## Task 3: Add Contact Hysteresis and the Six-Variable Optimizer

**Files:**
- Modify: `dexpilot_6dof.py`
- Modify: `tests/test_dexpilot_6dof.py`

- [ ] **Step 1: Write failing contact-state tests**

Add tests for project/escape hysteresis:

```python
from dexpilot_6dof import ContactTracker


def test_contact_hysteresis_does_not_flicker_between_thresholds():
    tracker = ContactTracker(project_distance=0.30, escape_distance=0.42)

    assert tracker.update({"index": 0.29}) == {"index": pytest.approx(1 / 30)}
    assert "index" in tracker.update({"index": 0.36})
    assert tracker.update({"index": 0.43}) == {}


def test_contact_tracker_prioritizes_the_closest_finger():
    tracker = ContactTracker(project_distance=0.30, escape_distance=0.42)
    weights = tracker.update({"index": 0.25, "middle": 0.10})
    assert weights["middle"] > weights["index"] > 0
```

The contact weight is `(escape_distance - distance) / escape_distance`, clipped to `[0, 1]`.

- [ ] **Step 2: Write failing optimizer tests**

Add a six-joint test configuration and tests for limits, temporal regularization, independent fingers, and increasing thumb opposition:

```python
from types import SimpleNamespace

from dexpilot_6dof import DexPilot6DofMapper

JOINTS = [
    {"name": "thumb_bend", "src": "thumb", "range": [0, 10000]},
    {"name": "thumb_rotate", "src": "thumb_spread", "range": [0, 10000]},
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
    "opposition_targets": {"index": 0.35, "middle": 0.52, "ring": 0.70, "pinky": 0.88},
}


def observation(points, curls=None):
    return SimpleNamespace(
        world_landmarks=points,
        curls=curls or {name: 0.0 for name in ("thumb", "index", "middle", "ring", "pinky")},
        thumb_spread=0.0,
    )


def test_optimizer_returns_finite_bounded_six_joint_targets():
    mapper = DexPilot6DofMapper(JOINTS, input_calibration={}, config=CONFIG)
    positions, display = mapper.map_observation(observation(open_hand()))
    assert len(positions) == 6
    assert all(0 <= value <= 10000 for value in positions)
    assert all(0 <= value <= 1 for value in display.values())


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
```

- [ ] **Step 3: Run contact and optimizer tests to verify failure**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dexpilot_6dof.py -q
```

Expected: failures identify missing `ContactTracker` and `DexPilot6DofMapper`.

- [ ] **Step 4: Implement contact hysteresis**

Add a stateful tracker that resets on strategy changes:

```python
@dataclass
class ContactTracker:
    project_distance: float
    escape_distance: float
    active: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not 0 < self.project_distance < self.escape_distance:
            raise ValueError("接触投影距离必须小于释放距离")

    def reset(self) -> None:
        self.active.clear()

    def update(self, distances: Mapping[str, float]) -> dict[str, float]:
        weights = {}
        for finger, distance in distances.items():
            value = float(distance)
            if finger in self.active:
                if value > self.escape_distance:
                    self.active.remove(finger)
                    continue
            elif value <= self.project_distance:
                self.active.add(finger)
            if finger in self.active:
                weights[finger] = float(np.clip(
                    (self.escape_distance - value) / self.escape_distance,
                    0.0,
                    1.0,
                ))
        return weights
```

- [ ] **Step 5: Implement calibrated objectives and weighted projection**

Implement `DexPilot6DofMapper` with these fixed channel orders:

```python
CHANNELS = ("thumb", "thumb_spread", "index", "middle", "ring", "pinky")
CONTACT_CHANNEL_INDEX = {"index": 2, "middle": 3, "ring": 4, "pinky": 5}


def _calibrate(value: float, calibration: Mapping[str, float] | None) -> float:
    if not calibration:
        return float(np.clip(value, 0.0, 1.0))
    opened = float(calibration.get("open", 0.0))
    closed = float(calibration.get("closed", 1.0))
    if not 0 <= opened < closed <= 1:
        raise ValueError("实验映射校准端点无效")
    return float(np.clip((value - opened) / (closed - opened), 0.0, 1.0))


def _solve_weighted_targets(rows, targets, weights, previous, temporal_weight):
    matrix = np.asarray(rows, dtype=np.float64)
    target = np.asarray(targets, dtype=np.float64)
    weight = np.asarray(weights, dtype=np.float64)
    lhs = matrix.T @ (weight[:, None] * matrix) + temporal_weight * np.eye(6)
    rhs = matrix.T @ (weight * target) + temporal_weight * previous
    solution = np.linalg.solve(lhs, rhs)
    if not np.isfinite(solution).all():
        raise GeometryError("DexPilot 6DOF 求解结果无效")
    return np.clip(solution, 0.0, 1.0)
```

`map_observation()` must:

1. Build palm-local landmarks and contact distances.
2. Calibrate the five curls and `thumb_spread` into the six base targets.
3. Add six identity rows with `base_weight`.
4. For each active thumb contact, add a thumb-bend target of `0.82`, that finger's current-or-contact target of `max(base, 0.72 * strength)`, and its configured thumb-opposition target, each weighted by `contact_weight * strength`.
5. Add the temporal term, solve, remember the normalized solution, and project each value through its joint `range`.
6. Return `(positions, display_inputs)` where display keys remain `thumb`, `thumb_spread`, `index`, `middle`, `ring`, and `pinky`.

- [ ] **Step 6: Run optimizer tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dexpilot_6dof.py -q
```

Expected: all geometry, hysteresis, limit, isolation, and temporal tests pass.

- [ ] **Step 7: Commit the experimental optimizer**

```powershell
git add dexpilot_6dof.py tests/test_dexpilot_6dof.py
git commit -m "feat: 实现六自由度 DexPilot 实验映射" -m "使用指尖接触滞回、掌心局部特征和带时序约束的有界加权投影生成六路关节目标。"
```

## Task 4: Complete Coordinator Switching and Failure Fallback

**Files:**
- Modify: `retargeting_strategy.py`
- Modify: `tests/test_retargeting_strategy.py`

- [ ] **Step 1: Write failing DexPilot selection and fallback tests**

```python
from retargeting_strategy import RETARGETING_DEXPILOT


class ExperimentalMapper:
    def __init__(self, *, error=None):
        self.error = error
        self.reset_calls = []

    def reset(self, current_positions=None):
        self.reset_calls.append(None if current_positions is None else list(current_positions))

    def map_observation(self, _observation):
        if self.error:
            raise self.error
        return [4000.0, 5000.0, 6000.0], {"thumb": 0.4, "thumb_spread": 0.5, "index": 0.6}


def test_dexpilot_strategy_initializes_from_current_positions():
    experimental = ExperimentalMapper()
    coordinator = RetargetingCoordinator(RecordingStableMapper(), experimental)
    coordinator.set_strategy(RETARGETING_DEXPILOT, [1000, 2000, 3000])
    result = coordinator.map_observation(observation())
    assert experimental.reset_calls[-1] == [1000, 2000, 3000]
    assert result.positions == [4000.0, 5000.0, 6000.0]
    assert result.effective_strategy == RETARGETING_DEXPILOT


def test_invalid_experimental_frame_falls_back_to_stable_for_that_frame():
    coordinator = RetargetingCoordinator(
        RecordingStableMapper(), ExperimentalMapper(error=ValueError("bad frame"))
    )
    coordinator.set_strategy(RETARGETING_DEXPILOT, [0, 0, 0])
    result = coordinator.map_observation(observation())
    assert result.selected_strategy == RETARGETING_DEXPILOT
    assert result.effective_strategy == RETARGETING_STABLE
    assert result.positions == [1000.0, 2000.0, 3000.0]
    assert result.fallback_reason == "bad frame"
```

- [ ] **Step 2: Run the tests and verify the DexPilot paths fail**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_retargeting_strategy.py -q
```

Expected: the coordinator still always returns the stable result.

- [ ] **Step 3: Implement experimental selection and guarded fallback**

Update `map_observation()`:

```python
def map_observation(self, observation: HandObservation) -> RetargetingResult:
    if self._selected_strategy == RETARGETING_STABLE:
        return self._stable_result(observation)
    try:
        positions, display = self._experimental_mapper.map_observation(observation)
        return RetargetingResult(
            positions=list(positions),
            display_inputs=dict(display),
            selected_strategy=RETARGETING_DEXPILOT,
            effective_strategy=RETARGETING_DEXPILOT,
        )
    except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
        return self._stable_result(
            observation,
            selected=RETARGETING_DEXPILOT,
            fallback_reason=str(exc),
        )
```

Import NumPy explicitly for `np.linalg.LinAlgError`. Do not catch `BaseException` or unrelated programmer errors.

- [ ] **Step 4: Run coordinator tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_retargeting_strategy.py -q
```

Expected: stable, DexPilot, switch initialization, unknown-mode, and fallback tests pass.

- [ ] **Step 5: Commit switching and fallback**

```powershell
git add retargeting_strategy.py tests/test_retargeting_strategy.py
git commit -m "feat: 支持稳定与 DexPilot 映射安全切换" -m "切换时继承当前关节目标，并在实验输入或求解失败时按帧回退稳定算法。"
```

## Task 5: Integrate Runtime Commands, Config, and Telemetry

**Files:**
- Modify: `config.yaml:48-91`
- Modify: `electron_bridge.py:16-33`
- Modify: `runtime_telemetry.py:14-68`
- Modify: `main.py:31-603`
- Modify: `tests/test_electron_bridge.py`
- Modify: `tests/test_runtime_telemetry.py`
- Modify: `tests/test_main_electron_bridge.py`
- Modify: `tests/test_main_safety_integration.py`
- Modify: `tests/test_runtime_lifecycle.py`

- [ ] **Step 1: Write failing Python command and telemetry tests**

Add two command assertions:

```python
assert parse_command_line(
    '{"type":"command","command":"retargeting_stable"}'
) == KEY_RETARGETING_STABLE
assert parse_command_line(
    '{"type":"command","command":"retargeting_dexpilot"}'
) == KEY_RETARGETING_DEXPILOT
```

Extend runtime telemetry tests to call:

```python
state = build_runtime_state(
    mode="mirror",
    retargeting_strategy="dexpilot",
    retargeting_effective="stable",
    retargeting_fallback="掌宽过小",
    # existing arguments unchanged
)
assert state["retargeting_strategy"] == "dexpilot"
assert state["retargeting_effective"] == "stable"
assert state["retargeting_fallback"] == "掌宽过小"
```

- [ ] **Step 2: Run focused tests and verify failure**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_electron_bridge.py tests/test_runtime_telemetry.py -q
```

Expected: imports/signatures fail because the new protocol fields do not exist.

- [ ] **Step 3: Add command constants and telemetry fields**

In `electron_bridge.py` add:

```python
KEY_RETARGETING_STABLE = 0x1006
KEY_RETARGETING_DEXPILOT = 0x1007

COMMAND_KEYS.update({
    "retargeting_stable": KEY_RETARGETING_STABLE,
    "retargeting_dexpilot": KEY_RETARGETING_DEXPILOT,
})
```

In `runtime_telemetry.build_runtime_state`, require the three retargeting arguments and add them beside `mode` in the returned state.

- [ ] **Step 4: Add experimental configuration without changing stable values**

Under `hand:` in `config.yaml` add exactly:

```yaml
  retargeting_strategy: stable
  dexpilot_6dof:
    temporal_weight: 0.20
    project_distance: 0.30
    escape_distance: 0.42
    base_weight: 1.0
    contact_weight: 2.5
    opposition_targets:
      index: 0.35
      middle: 0.52
      ring: 0.70
      pinky: 0.88
```

Do not modify `input_calibration`, `pinch_assist`, `finger_retargeting`, joint ranges, driver current, or velocity.

- [ ] **Step 5: Integrate the coordinator into mirror mode**

In `main.py`:

1. Construct `DexPilot6DofMapper` from the existing joints, input calibration, and new config.
2. Construct `RetargetingCoordinator` with the configured default.
3. Replace only the `mode == "mirror"` direct call with `retargeting.map_observation(obs)`.
4. Keep `mapper.map_preset()` for hidden gesture/RPS behavior.
5. Process `KEY_RETARGETING_STABLE` and `KEY_RETARGETING_DEXPILOT` after each frame, passing `hud_positions` into `set_strategy()`.
6. Pass selected/effective/fallback values to `build_runtime_state()`.

The mirror branch becomes:

```python
if mode == "mirror":
    retargeting_result = retargeting.map_observation(obs)
    positions = retargeting_result.positions
    display_inputs = retargeting_result.display_inputs
```

The key branch becomes:

```python
elif key in {KEY_RETARGETING_STABLE, KEY_RETARGETING_DEXPILOT}:
    strategy = {
        KEY_RETARGETING_STABLE: RETARGETING_STABLE,
        KEY_RETARGETING_DEXPILOT: RETARGETING_DEXPILOT,
    }[key]
    retargeting.set_strategy(strategy, current_positions=hud_positions)
    print(f"切换到 {strategy} 映射算法")
```

- [ ] **Step 6: Update main-loop test doubles and add a switching integration test**

Update fake observations to expose `world_landmarks` and fake coordinators/mappers to accept the new calls. Add a bridge-key sequence that switches to DexPilot and back while the simulator driver stays connected; assert no `driver.stop()` call occurs and that outgoing targets remain six finite values.

- [ ] **Step 7: Run Python integration tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_electron_bridge.py tests/test_runtime_telemetry.py tests/test_main_electron_bridge.py tests/test_main_safety_integration.py tests/test_runtime_lifecycle.py -q
```

Expected: all focused runtime, safety, and lifecycle tests pass.

- [ ] **Step 8: Commit runtime integration**

```powershell
git add config.yaml electron_bridge.py runtime_telemetry.py main.py tests
git commit -m "feat: 接入 DexPilot 运行时切换与遥测" -m "增加独立映射算法命令、配置和回退状态，同时保持急停、暂停与 CAN-FD 安全链路不变。"
```

## Task 6: Add the Electron Algorithm Selector

**Files:**
- Modify: `electron/renderer/index.html:101-106`
- Modify: `electron/renderer/app.js:1-320`
- Modify: `electron/renderer/telemetry-state.cjs`
- Modify: `electron/bridge-protocol.cjs`
- Modify: `electron/test/controls.test.cjs`
- Modify: `electron/test/bridge-protocol.test.cjs`
- Modify: `electron/test/telemetry-state.test.cjs`

- [ ] **Step 1: Write failing Electron protocol and control tests**

Change the controls test to require:

```javascript
assert.match(html, /<label for="retargeting-select">映射算法<\/label>/);
assert.match(html, /id="retargeting-select"/);
assert.match(html, /value="stable"[^>]*>轻量映射（稳定）/);
assert.match(html, /value="dexpilot"[^>]*>DexPilot 6DOF（实验）/);
assert.match(appJs, /sendCommand\(`retargeting_\$\{retargetingSelect\.value\}`\)/);
```

Extend bridge protocol tests:

```javascript
assert.equal(
  commandLine('retargeting_dexpilot'),
  '{"type":"command","command":"retargeting_dexpilot"}\n',
);
```

Require a frame state with:

```javascript
retargeting_strategy: 'dexpilot',
retargeting_effective: 'stable',
retargeting_fallback: '掌宽过小',
```

and assert unknown strategy values are rejected.

- [ ] **Step 2: Run Electron tests and verify failure**

```powershell
Set-Location electron
npm test
Set-Location ..
```

Expected: controls and protocol tests fail on the missing selector, commands, and telemetry fields.

- [ ] **Step 3: Update the validated bridge protocol**

Add `retargeting_stable` and `retargeting_dexpilot` to `ALLOWED_COMMANDS`, add:

```javascript
const VALID_RETARGETING_STRATEGIES = new Set(['stable', 'dexpilot']);
```

and require valid `retargeting_strategy`, `retargeting_effective`, and string `retargeting_fallback` when parsing a frame state.

- [ ] **Step 4: Replace the single control-mode selector**

Use semantic label/select markup:

```html
<div class="control-row">
  <label for="retargeting-select">映射算法</label>
  <select id="retargeting-select">
    <option value="stable">轻量映射（稳定）</option>
    <option value="dexpilot">DexPilot 6DOF（实验）</option>
  </select>
</div>
```

Reuse the existing select styles by changing selectors from `#mode-select` to `#retargeting-select`; do not alter panel dimensions or colors.

- [ ] **Step 5: Synchronize the selector from backend telemetry**

In `app.js` replace `modeSelect`/`pendingMode` with `retargetingSelect`/`pendingRetargeting`. The change handler sends:

```javascript
retargetingSelect.addEventListener('change', () => {
  pendingRetargeting = retargetingSelect.value;
  window.rpHand.sendCommand(`retargeting_${retargetingSelect.value}`);
});
```

`applyRuntimeState()` clears the pending value only after `state.retargeting_strategy` matches, and disables the selector while emergency stop is latched. Keep `state.mode` for the existing top HUD text.

- [ ] **Step 6: Run all Electron tests**

```powershell
Set-Location electron
npm test
Set-Location ..
```

Expected: all Electron tests pass, including accessibility-size and protocol validation tests.

- [ ] **Step 7: Commit the Electron selector**

```powershell
git add electron
git commit -m "feat: 增加双重定向算法选择控件" -m "Electron 可在稳定映射与 DexPilot 实验映射之间切换，并以 Python 遥测作为真实状态。"
```

## Task 7: Document, Verify, and Package the A/B Build

**Files:**
- Modify: `README.md`
- Verify: all Python and Electron sources
- Build: `electron/dist/RP-Hand Gesture Setup 1.0.0.exe`

- [ ] **Step 1: Document the experimental mode and hardware limit**

Add a README section that states:

```markdown
### 映射算法

- **轻量映射（稳定）**：默认算法，使用已完成的真机端点与 3/4/5 指回缩标定。
- **DexPilot 6DOF（实验）**：使用掌心局部坐标、拇指到各指尖距离和时序约束，重点尝试改善对掌与多指接触。

实验算法不是官方 dex-retargeting 的完整实现。RP-Hand 只有 6 个主动自由度，无法独立复现人手 DIP 弯曲和手指侧摆；效果应以同场景真机 A/B 测试为准。任何异常可立即切回稳定模式，急停和指令发送开关不受算法选择影响。
```

- [ ] **Step 2: Run the complete Python suite**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass; no physical CAN-FD device is opened by tests.

- [ ] **Step 3: Run the complete Electron suite**

```powershell
Set-Location electron
npm test
Set-Location ..
```

Expected: all Node tests pass.

- [ ] **Step 4: Run a simulator smoke test in each strategy**

Launch the development Electron app with the simulator driver:

```powershell
$env:RP_HAND_DRIVER = 'sim'
Set-Location electron
npm start
```

Verify manually that both selector values are accepted, the top status remains responsive, Space still toggles sending, and emergency stop/recovery remain independent. Close the app normally, then remove the temporary environment variable:

```powershell
Remove-Item Env:RP_HAND_DRIVER -ErrorAction SilentlyContinue
Set-Location ..
```

- [ ] **Step 5: Build the Windows installer**

```powershell
Set-Location electron
npm run dist:win
Set-Location ..
```

Expected artifact: `electron/dist/RP-Hand Gesture Setup 1.0.0.exe`.

- [ ] **Step 6: Record artifact integrity**

```powershell
Get-Item 'electron\dist\RP-Hand Gesture Setup 1.0.0.exe' |
  Select-Object FullName, Length, LastWriteTime
Get-FileHash 'electron\dist\RP-Hand Gesture Setup 1.0.0.exe' -Algorithm SHA256
```

Record the path, byte size, timestamp, and SHA-256 in the handoff message; do not commit generated `dist` output unless the repository already tracks it.

- [ ] **Step 7: Commit documentation and final verified source state**

```powershell
git add README.md
git commit -m "docs: 补充 DexPilot 实验映射使用说明" -m "说明双算法选择、六自由度硬件限制、安全回退和真机 A/B 验证方法。"
```

- [ ] **Step 8: Review the branch before hardware testing**

```powershell
git status --short --branch
git log --oneline --decorate origin/feature/ring-calibration..HEAD
git diff --check origin/feature/ring-calibration...HEAD
```

Expected: clean worktree, only planned DexPilot commits, and no whitespace errors.
