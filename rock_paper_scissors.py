"""Rock-paper-scissors mode state and counter-pose selection."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional, Sequence


RPS_COUNTER = {
    "fist": "open_palm",
    "open_palm": "victory",
    "victory": "fist",
}
RPS_EN = {
    "fist": "ROCK",
    "open_palm": "PAPER",
    "victory": "SCISSORS",
}
RPS_CN = {
    "fist": "石头",
    "open_palm": "布",
    "victory": "剪刀",
}


@dataclass(frozen=True)
class RpsDecision:
    """The optional motor pose and log produced by one observation."""

    positions: Optional[list[float]] = None
    log_message: str = ""


class RockPaperScissorsController:
    """Own stability, cooldown, and rearming state for RPS mode."""

    def __init__(self, hold_frames: int, cooldown_s: float):
        if hold_frames < 1:
            raise ValueError("hold_frames must be at least 1")
        if cooldown_s < 0:
            raise ValueError("cooldown_s cannot be negative")
        self._history = deque(maxlen=hold_frames)
        self._cooldown_s = float(cooldown_s)
        self._armed = True
        self._last_player_gesture: Optional[str] = None
        self._last_round_at = float("-inf")
        self._banner = ""

    @property
    def banner(self) -> str:
        return self._banner

    def reset(self) -> None:
        """Clear transient mode state while preserving the active cooldown."""
        self._history.clear()
        self._armed = True
        self._banner = ""

    def update(
        self,
        gesture: Optional[str],
        detected: bool,
        now: float,
        map_preset: Callable[[str], Optional[Sequence[float]]],
    ) -> RpsDecision:
        if not detected:
            # Removing the hand starts a new round, matching the original UI.
            self._history.clear()
            self._armed = True
            return RpsDecision()

        assert gesture is not None
        self._history.append(gesture)
        if gesture != self._last_player_gesture:
            self._armed = True

        stable = (
            len(self._history) == self._history.maxlen
            and len(set(self._history)) == 1
        )
        if not stable or gesture not in RPS_COUNTER:
            return RpsDecision()

        if self._armed and now - self._last_round_at >= self._cooldown_s:
            counter = RPS_COUNTER[gesture]
            pose = map_preset(counter)
            if pose is None:
                return RpsDecision()
            self._armed = False
            self._last_player_gesture = gesture
            self._last_round_at = now
            self._banner = (
                f"You: {RPS_EN[gesture]}   Me: {RPS_EN[counter]}   ->  I WIN!"
            )
            return RpsDecision(
                positions=list(pose),
                log_message=(
                    f"[猜拳] 你出{RPS_CN[gesture]}, "
                    f"我出{RPS_CN[counter]}, 我赢了"
                ),
            )

        if not self._armed:
            remaining = self._cooldown_s - (now - self._last_round_at)
            if remaining > 0:
                self._banner = f"Next round in {remaining:.0f}s (change gesture)"
        return RpsDecision()
