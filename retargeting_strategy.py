"""运行时可切换的手部重定向策略边界。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, Sequence

import numpy as np

if TYPE_CHECKING:
    from gesture_recognizer import HandObservation


RETARGETING_STABLE = "stable"
RETARGETING_DEXPILOT = "dexpilot"
VALID_RETARGETING_STRATEGIES = {RETARGETING_STABLE, RETARGETING_DEXPILOT}


@dataclass(frozen=True)
class RetargetingResult:
    """一次映射的硬件目标、显示输入和实际执行策略。"""

    positions: list[float]
    display_inputs: dict[str, float]
    selected_strategy: str
    effective_strategy: str
    fallback_reason: str = ""


class ExperimentalMapper(Protocol):
    """实验映射器需要实现的最小接口。"""

    def reset(self, current_positions: Sequence[float] | None = None) -> None: ...

    def map_observation(
        self,
        observation: HandObservation,
    ) -> tuple[list[float], dict[str, float]]: ...


class RetargetingCoordinator:
    """在不改变稳定映射的前提下管理算法选择。"""

    def __init__(
        self,
        stable_mapper,
        experimental_mapper: ExperimentalMapper | None = None,
        strategy: str = RETARGETING_STABLE,
    ) -> None:
        self._stable_mapper = stable_mapper
        self._experimental_mapper = experimental_mapper
        self._selected_strategy = RETARGETING_STABLE
        self.set_strategy(strategy, current_positions=None)

    @property
    def selected_strategy(self) -> str:
        return self._selected_strategy

    def set_strategy(
        self,
        strategy: str,
        current_positions: Sequence[float] | None,
    ) -> None:
        if strategy not in VALID_RETARGETING_STRATEGIES:
            raise ValueError(f"未知重定向策略: {strategy}")
        if strategy == RETARGETING_DEXPILOT and self._experimental_mapper is None:
            raise ValueError("DexPilot 6DOF 映射器尚未初始化")

        self._selected_strategy = strategy
        if self._experimental_mapper is not None:
            self._experimental_mapper.reset(current_positions)

    def _stable_result(
        self,
        observation: HandObservation,
        *,
        selected: str = RETARGETING_STABLE,
        fallback_reason: str = "",
    ) -> RetargetingResult:
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
        if self._selected_strategy == RETARGETING_STABLE:
            return self._stable_result(observation)

        # set_strategy() guarantees the experimental mapper exists before this path.
        assert self._experimental_mapper is not None
        try:
            positions, display = self._experimental_mapper.map_observation(observation)
            return RetargetingResult(
                positions=list(positions),
                display_inputs=dict(display),
                selected_strategy=RETARGETING_DEXPILOT,
                effective_strategy=RETARGETING_DEXPILOT,
            )
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
            # Invalid tracking frames fall back for one frame; programmer errors surface.
            return self._stable_result(
                observation,
                selected=RETARGETING_DEXPILOT,
                fallback_reason=str(exc),
            )
