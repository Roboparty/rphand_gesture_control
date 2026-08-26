"""手势识别模块: 基于 MediaPipe Hands 的 21 点手部关键点检测。

输出两类信息:
  1. 每根手指的连续弯曲度 curl ∈ [0, 1]  (0=完全伸直, 1=完全弯曲) —— 给 mirror 模式用
  2. 离散手势标签 (fist / open_palm / pinch / point / victory / thumbs_up) —— 给 gesture 模式用
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import mediapipe as mp
import numpy as np

FINGERS = ("thumb", "index", "middle", "ring", "pinky")

# MediaPipe 21 个关键点的索引
# 每根手指: (掌根/根部关节, 中间关节, 指尖)
_FINGER_JOINTS = {
    "thumb":  (2, 3, 4),     # MCP, IP, TIP
    "index":  (5, 6, 8),     # MCP, PIP, TIP
    "middle": (9, 10, 12),
    "ring":   (13, 14, 16),
    "pinky":  (17, 18, 20),
}

GESTURE_NAMES_CN = {
    "none": "未识别", "unknown": "未知",
    "open_palm": "张开手掌", "fist": "握拳",
    "pinch": "捏合", "point": "食指指点",
    "victory": "剪刀手", "thumbs_up": "点赞",
}


@dataclass
class HandObservation:
    """单帧识别结果。"""
    detected: bool = False
    handedness: str = "Right"                       # Left / Right
    # image landmarks 是相对图像宽、高归一化的坐标，适合绘制到画面。
    # 注意：x、y、z 的归一化尺度并不完全一致，因此不能直接拿来做三维几何计算。
    landmarks: Optional[np.ndarray] = None          # (21, 3) 归一化图像坐标
    # world landmarks 的三个轴采用统一尺度，适合求夹角和距离。
    # 它们不用于绘图，因为它们不是图像像素坐标。
    world_landmarks: Optional[np.ndarray] = None    # (21, 3) MediaPipe 世界坐标
    curls: Dict[str, float] = field(default_factory=lambda: {f: 0.0 for f in FINGERS})
    thumb_spread: float = 0.0                       # 拇指侧摆张角 0=贴掌 1=张开
    pinch_strength: float = 0.0                     # 拇指与食指捏合强度 0=分开 1=接触
    gesture: str = "none"


def _angle_deg(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """三个点构成的夹角 (顶点 b), 单位: 度。"""
    v1, v2 = a - b, c - b
    n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if n1 < 1e-6 or n2 < 1e-6:
        return 180.0
    cos = np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0)
    return math.degrees(math.acos(cos))


def _compute_pinch_strength(
    lm: np.ndarray,
    contact_distance: float = 0.15,
    release_distance: float = 0.45,
) -> float:
    """根据拇指与食指指尖距离返回连续捏合强度。"""
    palm_scale = float(np.linalg.norm(lm[0] - lm[9]))
    if palm_scale < 1e-6:
        return 0.0
    normalized_distance = np.linalg.norm(lm[4] - lm[8]) / palm_scale
    strength = (
        release_distance - normalized_distance
    ) / (release_distance - contact_distance)
    return float(np.clip(strength, 0.0, 1.0))


def _image_landmarks_to_equal_scale(lm: np.ndarray,
                                    image_width: int,
                                    image_height: int) -> np.ndarray:
    """把归一化图像坐标恢复到三个轴近似等尺度的空间。

    正常情况下，几何计算会优先使用 MediaPipe 输出的 world landmarks。
    这个函数只用于 world landmarks 缺失时的后备路径。

    MediaPipe 的 image landmark 中：
      - x 相对图像宽度归一化；
      - y 相对图像高度归一化；
      - z 的尺度约与 x 相同。

    因此必须分别乘回宽、高；z 则乘图像宽度。这样至少不会因为
    1280x720 等非正方形画面而直接扭曲夹角。返回值是一个副本，
    不会破坏用于绘图的原始归一化坐标。
    """
    scale = np.array([image_width, image_height, image_width], dtype=np.float32)
    return lm * scale


class GestureRecognizer:
    """封装 MediaPipe Hands, 输出弯曲度 + 手势标签。"""

    def __init__(self, max_num_hands: int = 1,
                 min_detection_confidence: float = 0.6,
                 min_tracking_confidence: float = 0.5,
                 smooth_factor: float = 0.4):
        self._hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._drawer = mp.solutions.drawing_utils
        self._styles = mp.solutions.drawing_styles
        # 指数滑动平均平滑, 抑制关键点抖动
        self._alpha = 1.0 - min(max(smooth_factor, 0.0), 1.0)
        self._smooth_curls: Dict[str, float] = {f: 0.0 for f in FINGERS}
        self._smooth_spread: float = 0.0
        self._smooth_pinch_strength: float = 0.0

    def close(self) -> None:
        self._hands.close()

    # ------------------------------------------------------------------
    def process(self, frame_bgr: np.ndarray) -> HandObservation:
        """输入一帧 BGR 图像, 返回识别结果。"""
        rgb = frame_bgr[:, :, ::-1]
        results = self._hands.process(rgb)
        obs = HandObservation()
        if not results.multi_hand_landmarks:
            self._smooth_curls = {f: 0.0 for f in FINGERS}
            self._smooth_spread = 0.0
            self._smooth_pinch_strength = 0.0
            return obs

        # image landmarks 与输入图像一一对应，后面 draw_landmarks() 仍用它画骨架。
        image_lm = results.multi_hand_landmarks[0]
        obs.detected = True
        obs.landmarks = np.array(
            [[p.x, p.y, p.z] for p in image_lm.landmark],
            dtype=np.float32,
        )
        if results.multi_handedness:
            obs.handedness = results.multi_handedness[0].classification[0].label

        # Part 1 坐标修复：几何计算不再直接使用归一化图像坐标。
        # MediaPipe Hands 会随关键点结果提供 world landmarks；它的三个轴处于
        # 同一尺度，因此手指夹角和距离不会被图像宽高比直接扭曲。
        world_results = getattr(results, "multi_hand_world_landmarks", None)
        if world_results:
            world_lm = world_results[0]
            obs.world_landmarks = np.array(
                [[p.x, p.y, p.z] for p in world_lm.landmark],
                dtype=np.float32,
            )
            geometry_lm = obs.world_landmarks
        else:
            # 理论上检测到手时通常会有 world landmarks。保留这个后备路径，
            # 避免个别 MediaPipe 版本或异常帧导致整个识别循环中断。
            h, w = frame_bgr.shape[:2]
            geometry_lm = _image_landmarks_to_equal_scale(obs.landmarks, w, h)

        # 从这里开始，所有角度和距离都只使用统一尺度的 geometry_lm。
        # 原来的弯曲公式、阈值和平滑算法保持不变，便于单独验证坐标修复。
        raw = self._compute_curls(geometry_lm)
        for f in FINGERS:
            self._smooth_curls[f] = self._alpha * raw[f] + (1 - self._alpha) * self._smooth_curls[f]
        obs.curls = dict(self._smooth_curls)
        raw_spread = self._compute_thumb_spread(geometry_lm)
        self._smooth_spread = self._alpha * raw_spread + (1 - self._alpha) * self._smooth_spread
        obs.thumb_spread = self._smooth_spread
        raw_pinch_strength = _compute_pinch_strength(geometry_lm)
        self._smooth_pinch_strength = (
            self._alpha * raw_pinch_strength
            + (1 - self._alpha) * self._smooth_pinch_strength
        )
        obs.pinch_strength = self._smooth_pinch_strength
        obs.gesture = self._classify(geometry_lm, obs.curls)
        return obs

    def draw_landmarks(self, frame_bgr: np.ndarray, obs: HandObservation) -> None:
        """把关键点和骨架画到画面上 (会修改传入的帧)。"""
        if not obs.detected or obs.landmarks is None:
            return
        h, w = frame_bgr.shape[:2]
        lm_list = mp.solutions.hands  # 仅取连接定义用
        conns = lm_list.HAND_CONNECTIONS
        pts = [(int(p[0] * w), int(p[1] * h)) for p in obs.landmarks]
        for a, b in conns:
            import cv2
            cv2.line(frame_bgr, pts[a], pts[b], (0, 200, 0), 2)
        import cv2
        for x, y in pts:
            cv2.circle(frame_bgr, (x, y), 4, (0, 100, 255), -1)

    # ------------------------------------------------------------------
    def _compute_curls(self, lm: np.ndarray) -> Dict[str, float]:
        """由关键点计算每根手指的弯曲度。

        原理: 手指中间关节的夹角, 伸直≈180°, 完全弯曲≈60°以下。
        curl = (180 - angle) / (180 - 60), 裁剪到 [0, 1]。
        """
        curls = {}
        for f, (j0, j1, j2) in _FINGER_JOINTS.items():
            ang = _angle_deg(lm[j0], lm[j1], lm[j2])
            curl = (180.0 - ang) / 120.0
            curls[f] = float(np.clip(curl, 0.0, 1.0))
        return curls

    def _compute_thumb_spread(self, lm: np.ndarray) -> float:
        """拇指侧摆(roll)张角, 归一化到 [0, 1]。

        原理: 拇指指向 (MCP->TIP) 与食指掌骨方向 (腕->食指MCP) 的夹角,
        拇指贴掌时约 15°, 完全张开时约 60°。
        """
        # 借用 _angle_deg(a, b, c): 顶点在拇指 MCP, 一条边到拇指尖,
        # 另一条边沿食指掌骨方向的平移向量
        tip, mcp = lm[4], lm[2]
        index_dir_point = mcp + (lm[5] - lm[0])
        ang = _angle_deg(tip, mcp, index_dir_point)
        return float(np.clip((ang - 15.0) / 45.0, 0.0, 1.0))

    def _classify(self, lm: np.ndarray, curls: Dict[str, float]) -> str:
        """规则式手势分类。"""
        c = curls
        bent = {f: c[f] > 0.65 for f in FINGERS}
        straight = {f: c[f] < 0.35 for f in FINGERS}

        # 拇指与食指指尖距离 (相对于手掌尺度归一化, 便于不同距离下稳定)
        palm_scale = np.linalg.norm(lm[0] - lm[9]) + 1e-6
        pinch_dist = np.linalg.norm(lm[4] - lm[8]) / palm_scale

        if all(straight[f] for f in FINGERS):
            return "open_palm"
        if all(bent[f] for f in FINGERS):
            return "fist"
        # 拇指食指指尖接近 -> 捏合
        if pinch_dist < 0.35:
            return "pinch"
        if straight["thumb"] and all(bent[f] for f in ("index", "middle", "ring", "pinky")):
            return "thumbs_up"
        if straight["index"] and bent["middle"] and bent["ring"] and bent["pinky"]:
            return "point"
        if straight["index"] and straight["middle"] and bent["ring"] and bent["pinky"]:
            return "victory"
        return "unknown"
