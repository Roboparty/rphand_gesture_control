"""Safety primitives for turning tracking results into hardware commands."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence


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
