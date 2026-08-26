"""仿真驱动: 不接真实硬件时使用。

把收到的关节位置存起来并打印, 主程序的 HUD 会把它们画成条形图,
方便在没有灵巧手的情况下联调手势识别与映射逻辑。
"""

import time
from typing import List, Optional

from .base_driver import BaseHandDriver


class SimHandDriver(BaseHandDriver):

    def __init__(self, joint_names: List[str]):
        self._joint_names = joint_names
        self._positions: List[float] = [0.0] * len(joint_names)
        self._connected = False
        self._stopped = False
        self._last_log = 0.0

    def connect(self) -> bool:
        self._connected = True
        self._stopped = False
        print("[SimDriver] 仿真灵巧手已连接 (无真实硬件)")
        return True

    def disconnect(self) -> None:
        self.stop()
        self._connected = False
        print("[SimDriver] 仿真灵巧手已断开")

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        print("[SimDriver] 仿真灵巧手已停止")

    def recover(self) -> bool:
        if not self._connected:
            return False
        self._stopped = False
        print("[SimDriver] 仿真灵巧手已恢复控制")
        return True

    def set_joint_positions(self, positions: List[float],
                            speed: Optional[List[float]] = None) -> bool:
        if not self._connected or self._stopped:
            return False
        self._positions = list(positions)
        # 每 0.5 秒打印一次, 避免刷屏
        now = time.time()
        if now - self._last_log > 0.5:
            self._last_log = now
            pairs = ", ".join(f"{n}={int(p)}" for n, p in zip(self._joint_names, positions))
            print(f"[SimDriver] 关节位置 -> {pairs}")
        return True

    def get_state(self) -> Optional[dict]:
        return dict(zip(self._joint_names, self._positions))

    @property
    def is_connected(self) -> bool:
        return self._connected
