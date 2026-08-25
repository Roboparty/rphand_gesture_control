"""Safety primitives for turning tracking results into hardware commands."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence, Union


NumberOrSequence = Union[float, Sequence[float]]


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


def _expand_values(
    value: NumberOrSequence,
    count: int,
    name: str,
    *,
    allow_zero: bool,
) -> list[float]:
    if isinstance(value, (int, float)):
        values = [float(value)] * count
    else:
        values = [float(item) for item in value]
    if len(values) != count:
        raise ValueError(f"{name} must contain {count} values")
    invalid = (
        any(item < 0.0 for item in values)
        if allow_zero
        else any(item <= 0.0 for item in values)
    )
    if invalid:
        requirement = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} values must be {requirement}")
    return values


class TrackingState(str, Enum):
    """Observable states of the hand-tracking safety watchdog."""

    WAITING = "waiting"
    TRACKING = "tracking"
    GRACE = "grace"
    SAFE_RETURN = "safe_return"
    SAFE_HOLD = "safe_hold"
    STOPPED = "stopped"


@dataclass(frozen=True)
class SafetyDecision:
    """Command target and one-shot side effects selected by the watchdog."""

    state: TrackingState
    target: Optional[list[float]]
    should_stop: bool = False


class TrackingWatchdog:
    """Hold short tracking gaps and make prolonged loss deterministic."""

    def __init__(
        self,
        safe_positions: Sequence[float],
        grace_period_s: float,
        safe_return_duration_s: float,
        lost_action: str = "open",
    ):
        if not safe_positions:
            raise ValueError("safe_positions must not be empty")
        if grace_period_s < 0:
            raise ValueError("grace_period_s must be non-negative")
        if safe_return_duration_s < 0:
            raise ValueError("safe_return_duration_s must be non-negative")
        if lost_action not in {"open", "stop"}:
            raise ValueError("lost_action must be 'open' or 'stop'")

        self._safe_positions = [float(value) for value in safe_positions]
        self._grace_period_s = float(grace_period_s)
        self._safe_return_duration_s = float(safe_return_duration_s)
        self._lost_action = lost_action

        self._state = TrackingState.WAITING
        self._last_seen_at: Optional[float] = None
        self._last_target: Optional[list[float]] = None
        self._last_output: Optional[list[float]] = None
        self._return_from: Optional[list[float]] = None
        self._stop_pending = False

    @property
    def state(self) -> TrackingState:
        return self._state

    def note_output(self, positions: Sequence[float]) -> None:
        """Remember the command that actually reached the output pipeline."""

        self._last_output = self._copy_positions(positions)

    def force_stop(self) -> bool:
        """Latch the watchdog in STOPPED and request one hardware stop."""

        if self._state is TrackingState.STOPPED:
            return False
        self._state = TrackingState.STOPPED
        self._stop_pending = True
        return True

    def update(
        self,
        observed_positions: Optional[Sequence[float]],
        now: float,
        tracking_detected: Optional[bool] = None,
    ) -> SafetyDecision:
        """Select a safe target from the current observation and monotonic time."""

        if self._state is TrackingState.STOPPED:
            should_stop = self._stop_pending
            self._stop_pending = False
            return SafetyDecision(TrackingState.STOPPED, None, should_stop)

        is_tracking = (
            observed_positions is not None
            if tracking_detected is None
            else bool(tracking_detected) or observed_positions is not None
        )
        if is_tracking:
            self._last_seen_at = float(now)
            self._return_from = None
            self._state = TrackingState.TRACKING
            if observed_positions is not None:
                target = self._copy_positions(observed_positions)
                self._last_target = target
            else:
                held_target = self._last_output or self._last_target
                target = list(held_target) if held_target is not None else None
            return SafetyDecision(self._state, target)

        if self._last_seen_at is None:
            self._state = TrackingState.WAITING
            return SafetyDecision(self._state, None)

        elapsed = max(0.0, float(now) - self._last_seen_at)
        held_target = self._last_output or self._last_target
        if elapsed <= self._grace_period_s:
            self._state = TrackingState.GRACE
            return SafetyDecision(
                self._state,
                list(held_target) if held_target is not None else None,
            )

        if self._lost_action == "stop":
            self._state = TrackingState.STOPPED
            return SafetyDecision(self._state, None, should_stop=True)

        if self._return_from is None:
            self._return_from = list(held_target or self._safe_positions)

        if self._safe_return_duration_s == 0:
            progress = 1.0
        else:
            progress = min(
                1.0,
                (elapsed - self._grace_period_s) / self._safe_return_duration_s,
            )
            if progress >= 1.0 - 1e-9:
                progress = 1.0

        target = [
            start + (safe - start) * progress
            for start, safe in zip(self._return_from, self._safe_positions)
        ]
        if progress >= 1.0:
            self._state = TrackingState.SAFE_HOLD
            target = list(self._safe_positions)
        else:
            self._state = TrackingState.SAFE_RETURN
        return SafetyDecision(self._state, target)

    def _copy_positions(self, positions: Sequence[float]) -> list[float]:
        values = [float(value) for value in positions]
        if len(values) != len(self._safe_positions):
            raise ValueError(
                f"expected {len(self._safe_positions)} positions, got {len(values)}"
            )
        return values


class CommandLimiter:
    """Clamp and slew-limit joint commands before they reach a driver."""

    def __init__(
        self,
        joint_ranges: Sequence[Sequence[float]],
        initial_positions: Sequence[float],
        deadband: NumberOrSequence,
        max_step: NumberOrSequence,
        max_velocity: NumberOrSequence,
        max_acceleration: NumberOrSequence,
        initial_time: float,
    ):
        if not joint_ranges:
            raise ValueError("joint_ranges must not be empty")
        self._ranges: list[tuple[float, float]] = []
        for joint_range in joint_ranges:
            if len(joint_range) != 2:
                raise ValueError("each joint range must contain two values")
            first, second = (float(value) for value in joint_range)
            self._ranges.append((min(first, second), max(first, second)))

        count = len(self._ranges)
        if len(initial_positions) != count:
            raise ValueError(f"initial_positions must contain {count} values")
        self._deadband = _expand_values(
            deadband, count, "deadband", allow_zero=True
        )
        self._max_step = _expand_values(
            max_step, count, "max_step", allow_zero=False
        )
        self._max_velocity = _expand_values(
            max_velocity, count, "max_velocity", allow_zero=False
        )
        self._max_acceleration = _expand_values(
            max_acceleration, count, "max_acceleration", allow_zero=False
        )
        self._last_output = [
            _clamp(float(value), lower, upper)
            for value, (lower, upper) in zip(initial_positions, self._ranges)
        ]
        self._last_velocity = [0.0] * count
        self._last_time = float(initial_time)

    @property
    def last_output(self) -> list[float]:
        return list(self._last_output)

    def limit(self, target_positions: Sequence[float], now: float) -> list[float]:
        if len(target_positions) != len(self._ranges):
            raise ValueError(
                f"expected {len(self._ranges)} targets, got {len(target_positions)}"
            )

        timestamp = float(now)
        dt = max(0.0, timestamp - self._last_time)
        outputs: list[float] = []
        velocities: list[float] = []

        for index, (raw_target, bounds) in enumerate(
            zip(target_positions, self._ranges)
        ):
            lower, upper = bounds
            previous = self._last_output[index]
            target = _clamp(float(raw_target), lower, upper)
            error = target - previous

            if dt <= 0.0 or abs(error) <= self._deadband[index]:
                outputs.append(previous)
                velocities.append(0.0)
                continue

            desired_velocity = _clamp(
                error / dt,
                -self._max_velocity[index],
                self._max_velocity[index],
            )
            velocity_delta = _clamp(
                desired_velocity - self._last_velocity[index],
                -self._max_acceleration[index] * dt,
                self._max_acceleration[index] * dt,
            )
            velocity = self._last_velocity[index] + velocity_delta
            if velocity * error < 0:
                velocity = 0.0

            step = _clamp(
                velocity * dt,
                -self._max_step[index],
                self._max_step[index],
            )
            if abs(step) > abs(error):
                step = error
            output = _clamp(previous + step, lower, upper)
            outputs.append(output)
            velocities.append((output - previous) / dt)

        self._last_output = outputs
        self._last_velocity = velocities
        self._last_time = timestamp
        return list(outputs)


@dataclass(frozen=True)
class SafetyFault:
    """Latched fault that requires a process restart to clear."""

    code: str
    message: str


class FeedbackMonitor:
    """Turn repeated output and feedback anomalies into a latched fault."""

    def __init__(
        self,
        max_send_failures: int,
        max_feedback_failures: int,
        position_error_limit: float,
        position_error_timeout_s: float,
    ):
        if max_send_failures < 1 or max_feedback_failures < 1:
            raise ValueError("failure thresholds must be at least one")
        if position_error_limit < 0 or position_error_timeout_s < 0:
            raise ValueError("position error thresholds must be non-negative")
        self._max_send_failures = int(max_send_failures)
        self._max_feedback_failures = int(max_feedback_failures)
        self._position_error_limit = float(position_error_limit)
        self._position_error_timeout_s = float(position_error_timeout_s)

        self._send_failures = 0
        self._feedback_failures = 0
        self._position_error_since: Optional[float] = None
        self._fault: Optional[SafetyFault] = None

    @property
    def fault(self) -> Optional[SafetyFault]:
        return self._fault

    def note_send(self, success: bool) -> Optional[SafetyFault]:
        if self._fault is not None:
            return self._fault
        if success:
            self._send_failures = 0
            return None
        self._send_failures += 1
        if self._send_failures >= self._max_send_failures:
            return self._trip("send_failure", "连续关节指令下发失败")
        return None

    def evaluate(
        self,
        target: Sequence[float],
        actual: Optional[Sequence[float]],
        alarms,
        now: float,
    ) -> Optional[SafetyFault]:
        if self._fault is not None:
            return self._fault

        if self._has_alarm(alarms):
            return self._trip("motor_alarm", "检测到电机报警")

        if actual is None:
            self._feedback_failures += 1
            if self._feedback_failures >= self._max_feedback_failures:
                return self._trip("feedback_missing", "连续读取关节反馈失败")
            return None
        self._feedback_failures = 0

        if len(actual) != len(target):
            return self._trip("feedback_shape", "反馈关节数量与目标不一致")

        max_error = max(
            (abs(float(expected) - float(measured))
             for expected, measured in zip(target, actual)),
            default=0.0,
        )
        timestamp = float(now)
        if max_error > self._position_error_limit:
            if self._position_error_since is None:
                self._position_error_since = timestamp
            if timestamp - self._position_error_since >= self._position_error_timeout_s:
                return self._trip("position_error", "关节跟随误差持续超限")
        else:
            self._position_error_since = None
        return None

    def _trip(self, code: str, message: str) -> SafetyFault:
        self._fault = SafetyFault(code=code, message=message)
        return self._fault

    @staticmethod
    def _has_alarm(alarms) -> bool:
        if alarms is None:
            return False
        if isinstance(alarms, dict):
            values = alarms.values()
        elif isinstance(alarms, (list, tuple, set)):
            values = alarms
        else:
            values = [alarms]
        return any(value not in (None, False, 0) for value in values)
