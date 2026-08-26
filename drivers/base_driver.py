"""灵巧手驱动抽象接口。

所有驱动(仿真 / LHandPro EtherCAT)都实现同一套接口,
主程序只跟这个接口打交道, 换硬件不用改上层代码。
"""

from abc import ABC, abstractmethod
from typing import List, Optional


class BaseHandDriver(ABC):
    """灵巧手驱动基类。"""

    @abstractmethod
    def connect(self) -> bool:
        """建立与灵巧手的连接。成功返回 True。"""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """断开连接并释放资源。"""
        ...

    @abstractmethod
    def stop(self) -> None:
        """立即停止执行器; 重复调用必须安全。"""
        ...

    @abstractmethod
    def recover(self) -> bool:
        """解除驱动急停锁存；不执行回零或下发位置。"""
        ...

    @abstractmethod
    def set_joint_positions(self, positions: List[float],
                            speed: Optional[List[float]] = None) -> bool:
        """下发各关节目标位置。

        positions: 长度 = 关节数, 数值含义见 config.yaml 的 hand.joints.range
        """
        ...

    def get_state(self) -> Optional[dict]:
        """读取灵巧手当前状态(温度/电流/位置等), 不支持则返回 None。"""
        return None

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        ...
