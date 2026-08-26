"""手势 -> 灵巧手关节位置 的映射。

两种模式:
  mirror  模式: 手指弯曲度 (0~1) 按 config 里每个关节的 range 线性映射为关节位置
  gesture 模式: 识别到的手势标签 -> config.presets 里对应的预设关节位置
"""

from typing import Dict, List, Optional

FINGERS = ("thumb", "index", "middle", "ring", "pinky")


class GestureMapper:

    def __init__(self, joint_cfg: List[dict], presets: Dict[str, List[float]],
                 input_calibration: Optional[Dict[str, dict]] = None):
        """
        joint_cfg: config.yaml 里 hand.joints 的列表
        presets:   config.yaml 里 presets 字典
        input_calibration: 各输入通道的张开端基线
        """
        self._joints = joint_cfg
        self._presets = presets
        self._input_calibration = input_calibration or {}
        for src, calibration in self._input_calibration.items():
            open_value = float(calibration.get("open", 0.0))
            closed_value = float(calibration.get("closed", 1.0))
            if not 0.0 <= open_value < 1.0:
                raise ValueError(f"{src} 的 open 必须小于 1 且不小于 0")
            if not open_value < closed_value <= 1.0:
                raise ValueError(f"{src} 的 closed 必须大于 open 且不大于 1")

    @property
    def joint_names(self) -> List[str]:
        return [j["name"] for j in self._joints]

    @property
    def num_joints(self) -> int:
        return len(self._joints)

    # ------------------------------------------------------------------
    def calibrate_inputs(self, values: Dict[str, float]) -> Dict[str, float]:
        """把真实张开端的残余值重新映射为 0，同时保留闭合端 1。"""
        corrected = dict(values)
        for src, raw_value in values.items():
            calibration = self._input_calibration.get(src)
            if calibration is None:
                continue
            open_value = float(calibration.get("open", 0.0))
            closed_value = float(calibration.get("closed", 1.0))
            normalized = (float(raw_value) - open_value) / (closed_value - open_value)
            corrected[src] = min(max(normalized, 0.0), 1.0)
        return corrected

    def map_mirror(self, curls: Dict[str, float]) -> List[float]:
        """连续映射: 弯曲度 -> 关节位置。

        range = [开, 合]: curl=0 输出 range[0], curl=1 输出 range[1]。
        src 为 null 的关节保持 range[0]。
        """
        calibrated = self.calibrate_inputs(curls)
        out = []
        for j in self._joints:
            lo, hi = j["range"]
            src = j.get("src")
            curl = calibrated.get(src, 0.0) if src else 0.0
            out.append(lo + (hi - lo) * curl)
        return out

    def map_preset(self, gesture: str) -> Optional[List[float]]:
        """手势标签 -> 预设位置; 没有对应预设则返回 None。"""
        pose = self._presets.get(gesture)
        if pose is None:
            return None
        if len(pose) != self.num_joints:
            raise ValueError(
                f"预设 '{gesture}' 的长度({len(pose)})与关节数({self.num_joints})不一致, "
                f"请检查 config.yaml")
        return list(pose)
