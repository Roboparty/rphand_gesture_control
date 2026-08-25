"""无窗口冒烟测试: 摄像头 -> 手势识别 -> 映射 -> 仿真驱动, 跑约 5 秒。"""

import sys
import time

import cv2
import yaml

from gesture_recognizer import GestureRecognizer, GESTURE_NAMES_CN
from gesture_mapping import GestureMapper
from drivers.sim_driver import SimHandDriver


def main():
    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    rcfg = cfg["recognizer"]
    recognizer = GestureRecognizer(
        max_num_hands=rcfg["max_num_hands"],
        min_detection_confidence=rcfg["min_detection_confidence"],
        min_tracking_confidence=rcfg["min_tracking_confidence"],
        smooth_factor=rcfg["smooth_factor"],
    )
    mapper = GestureMapper(cfg["hand"]["joints"], cfg.get("presets", {}))
    driver = SimHandDriver(mapper.joint_names)
    assert driver.connect(), "仿真驱动连接失败"

    cap = cv2.VideoCapture(cfg["camera"]["index"], cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"[FAIL] 无法打开摄像头 {cfg['camera']['index']}")
        return 1

    frames = detected = 0
    gestures = {}
    t0 = time.time()
    while time.time() - t0 < 5.0:
        ok, frame = cap.read()
        if not ok:
            continue
        frames += 1
        if cfg["camera"].get("mirror", True):
            frame = cv2.flip(frame, 1)
        obs = recognizer.process(frame)
        if obs.detected:
            detected += 1
            gestures[obs.gesture] = gestures.get(obs.gesture, 0) + 1
            pos = mapper.map_mirror(obs.curls)
            driver.set_joint_positions(pos)

    cap.release()
    recognizer.close()
    driver.disconnect()

    print(f"摄像头帧数: {frames}, 识别到手: {detected}")
    if gestures:
        for g, n in sorted(gestures.items(), key=lambda x: -x[1]):
            print(f"  手势 {g} ({GESTURE_NAMES_CN.get(g, g)}): {n} 帧")
    else:
        print("  (5 秒内未检测到手, 属正常 —— 摄像头前没人挥手)")

    if frames < 30:
        print("[FAIL] 摄像头取帧太少")
        return 1
    print("[OK] 摄像头 + 手势识别 + 映射 + 驱动 全链路正常")
    return 0


if __name__ == "__main__":
    sys.exit(main())
