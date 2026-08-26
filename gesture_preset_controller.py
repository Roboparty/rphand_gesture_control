"""Stable-frame controller for the gesture preset mode."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional, Sequence


@dataclass(frozen=True)
class GesturePresetDecision:
    """One optional preset produced by a stable discrete gesture."""

    positions: Optional[list[float]] = None
    gesture: Optional[str] = None


class GesturePresetController:
    """Own gesture stability and re-trigger state outside the runtime loop."""

    def __init__(self, hold_frames: int) -> None:
        if hold_frames < 1:
            raise ValueError("hold_frames must be at least 1")
        self._history: deque[str] = deque(maxlen=hold_frames)
        self._last_triggered: Optional[str] = None

    def reset(self) -> None:
        self._history.clear()
        self._last_triggered = None

    def update(
        self,
        gesture: Optional[str],
        *,
        detected: bool,
        map_preset: Callable[[str], Optional[Sequence[float]]],
    ) -> GesturePresetDecision:
        if not detected or gesture is None:
            self._history.clear()
            return GesturePresetDecision()

        self._history.append(gesture)
        stable = (
            len(self._history) == self._history.maxlen
            and len(set(self._history)) == 1
        )
        if not stable or gesture == self._last_triggered:
            return GesturePresetDecision()

        pose = map_preset(gesture)
        if pose is None:
            return GesturePresetDecision()
        self._last_triggered = gesture
        return GesturePresetDecision(list(pose), gesture)
