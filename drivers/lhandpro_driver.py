"""LHandPro 灵巧手驱动 (CANFD 通讯)。

基于厂商 SDK 自带的 Python 封装 (已拷贝到项目 vendor/ 目录):
  vendor/lhandprolib_python_sdk/   - LHandProLib.dll 的 ctypes 封装 + CANFD 控制器
  vendor/canfd_lib.py              - CANFD 通信库 (Windows 走 HCanbus.dll)
  vendor/lib/HCanbus.dll           - Windows CANFD 底层驱动

通讯链路:
  本驱动 -> LHandProLib.dll (生成 CANFD 帧) -> HCanbus.dll -> USB-CANFD 适配器 -> 灵巧手

前置条件 (Windows x64):
  1. USB-CANFD 适配器已连接电脑和灵巧手, 灵巧手已上电
  2. config.yaml 中 driver.canfd.library_path 指向 x64/bin/LHandProLib.dll
  3. CANFD 节点 ID / 波特率与灵巧手配置一致 (默认 node_id=1,
     仲裁域 1Mbps / 数据域 5Mbps, 与厂商示例一致)
"""

import os
import sys
import time
from typing import List, Optional

from .base_driver import BaseHandDriver

# 把 vendor 目录加入模块搜索路径 (controller_canfd 里用的是 `from canfd_lib import ...`)
# 打包后优先使用 exe 旁边的 vendor/ 数据目录
def _find_vendor_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "vendor"))
    candidates.append(os.path.normpath(os.path.join(here, "..", "vendor")))
    for c in candidates:
        if os.path.isdir(c):
            return os.path.normpath(c)
    return os.path.normpath(candidates[-1])

_VENDOR_DIR = _find_vendor_dir()
if _VENDOR_DIR not in sys.path:
    sys.path.insert(0, _VENDOR_DIR)


class LHandProDriver(BaseHandDriver):
    """LHandPro CANFD 驱动, 封装厂商 LHandProController (CANFD 模式)。"""

    def __init__(self, library_path: str,
                 node_id: int = 1,
                 device_index: Optional[int] = None,
                 nom_baudrate: int = 1000000,
                 dat_baudrate: int = 5000000,
                 hand_type: int = 0,
                 hand_direction: Optional[int] = None,
                 enable_motors: bool = True,
                 home_motors: bool = True,
                 home_wait_time: float = 5.0,
                 velocity: int = 20000,
                 max_current: int = 1000):
        """
        library_path: LHandProLib.dll 的路径
        node_id:      CANFD 节点 ID (默认 1, 需与灵巧手配置一致)
        device_index: CANFD 适配器序号; None = 自动选第一个
        nom_baudrate: 仲裁域波特率 (厂商默认 1 Mbps)
        dat_baudrate: 数据域波特率 (厂商默认 5 Mbps)
        hand_type:    手型 0=6自由度 / 1=6S / 2=16自由度
        velocity:     位置速度 (厂商示例默认 20000)
        max_current:  最大电流 (厂商示例默认 1000)
        """
        self._library_path = library_path
        self._node_id = node_id
        self._device_index = device_index
        self._nom_baudrate = nom_baudrate
        self._dat_baudrate = dat_baudrate
        self._hand_type = hand_type
        self._hand_direction = hand_direction  # 0=右手 1=左手, None=用 SDK 默认
        self._enable_motors = enable_motors
        self._home_motors = home_motors
        self._home_wait_time = home_wait_time
        self._velocity = velocity
        self._max_current = max_current

        self._controller = None
        self._dof_active = 0
        self._connected = False
        self._last_log = 0.0

    # ------------------------------------------------------------------
    def connect(self) -> bool:
        try:
            # 先用显式路径预加载 LHandProLib.dll (全局单例),
            # 控制器内部创建 PyLHandProLib() 时会直接复用
            from lhandprolib_python_sdk.lhandprolib_loader import (
                get_global_lhandprolib_lib)
            from app_paths import resolve_app_path
            lib_path = resolve_app_path(self._library_path)
            if not os.path.exists(lib_path):
                print(f"[LHandPro] 找不到动态库: {lib_path}\n"
                      f"  请在 config.yaml 的 driver.canfd.library_path 填写正确路径")
                return False
            get_global_lhandprolib_lib(lib_path)
            print(f"[LHandPro] 已加载动态库: {lib_path}")

            from lhandprolib_python_sdk.controller import LHandProController
            self._controller = LHandProController(
                hand_type=self._hand_type,
                canfd_node_id=self._node_id,
            )

            print(f"[LHandPro] 正在通过 CANFD 连接设备 (node_id={self._node_id}, "
                  f"nom={self._nom_baudrate}bps, dat={self._dat_baudrate}bps)...")
            ok = self._controller.connect(
                enable_motors=self._enable_motors,
                home_motors=self._home_motors,
                home_wait_time=self._home_wait_time,
                device_index=self._device_index,
                auto_select=self._device_index is None,
                canfd_nom_baudrate=self._nom_baudrate,
                canfd_dat_baudrate=self._dat_baudrate,
            )
            if not ok:
                print("[LHandPro] 连接失败, 请检查: USB-CANFD 适配器 / 手的电源 / "
                      "节点ID / 波特率是否与手一致")
                return False

            self._dof_total, self._dof_active = self._controller.get_dof()
            if self._hand_direction is not None and self._controller.sdk_handle is not None:
                self._controller.sdk_handle.set_hand_direction(self._hand_direction)
                print(f"[LHandPro] 手方向已设置: {'左手' if self._hand_direction == 1 else '右手'}")
            print(f"[LHandPro] 连接成功, 总自由度={self._dof_total}, "
                  f"主动自由度={self._dof_active}")
            self._connected = True
            return True
        except ImportError as e:
            print(f"[LHandPro] 依赖缺失: {e}")
            return False
        except Exception as e:
            print(f"[LHandPro] 连接异常: {e}")
            return False

    def disconnect(self) -> None:
        if self._controller is not None and self._connected:
            try:
                print("[LHandPro] 停止电机并断开...")
                self._controller.stop_motors()
                self._controller.disconnect()
            except Exception as e:
                print(f"[LHandPro] 断开时异常: {e}")
        self._connected = False

    # ------------------------------------------------------------------
    def set_joint_positions(self, positions: List[float],
                            speed: Optional[List[float]] = None) -> bool:
        """下发关节目标位置 (非阻塞)。

        positions: 长度应等于主动自由度; 若 config 里关节数与手的
                   主动自由度不一致, 自动截断/补 0 并周期性提示。
        """
        if not self._connected or self._controller is None or self._controller.sdk_handle is None:
            return False

        pos = [int(p) for p in positions]
        if len(pos) != self._dof_active:
            if len(pos) < self._dof_active:
                pos = pos + [0] * (self._dof_active - len(pos))
            else:
                pos = pos[:self._dof_active]
            now = time.time()
            if now - self._last_log > 5.0:
                print(f"[LHandPro] 注意: 配置关节数({len(positions)})与手的主动自由度"
                      f"({self._dof_active})不一致, 已自动对齐")
                self._last_log = now

        try:
            sdk = self._controller.sdk_handle
            for index, p in enumerate(pos, start=1):  # 电机编号从 1 开始
                sdk.set_target_position(index, p)
                sdk.set_position_velocity(index, self._velocity)
                sdk.set_max_current(index, self._max_current)
            sdk.move_motors(0)  # 0 = 全部电机
            return True
        except Exception as e:
            print(f"[LHandPro] 位置下发失败: {e}")
            return False

    def get_state(self) -> Optional[dict]:
        """读取各电机当前实际位置 (失败返回 None, 不影响控制)。"""
        if not self._connected or self._controller is None or self._controller.sdk_handle is None:
            return None
        try:
            sdk = self._controller.sdk_handle
            return {f"motor_{i}": sdk.get_now_position(i)
                    for i in range(1, self._dof_active + 1)}
        except Exception:
            return None

    @property
    def is_connected(self) -> bool:
        return self._connected
