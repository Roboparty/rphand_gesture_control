"""Collect real open-palm and fist angle ranges without connecting the hand."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import yaml

from geometry_diagnostics import measure_four_finger_angles, summarize_angle_samples
from gesture_recognizer import GestureRecognizer, _image_landmarks_to_equal_scale


POSE_LABELS = {
    "open": "OPEN PALM",
    "fist": "CLOSED FIST",
}


def _parse_args():
    parser = argparse.ArgumentParser(
        description="只使用摄像头采集手指角度，不会连接或驱动 CAN-FD 灵巧手。",
    )
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--camera", type=int, default=None)
    parser.add_argument("--seconds", type=float, default=2.5)
    parser.add_argument("--countdown", type=float, default=2.0)
    parser.add_argument(
        "--output",
        default="diagnostics/hand_geometry_ranges.json",
    )
    return parser.parse_args()


def _open_camera(camera_config: dict):
    index = int(camera_config["index"])
    if os.name == "nt":
        camera = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    else:
        camera = cv2.VideoCapture(index)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, int(camera_config["width"]))
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, int(camera_config["height"]))
    if not camera.isOpened():
        camera.release()
        raise RuntimeError(f"无法打开摄像头 {index}")
    return camera


def _geometry_landmarks(observation, frame: np.ndarray):
    if observation.world_landmarks is not None:
        return observation.world_landmarks
    if observation.landmarks is None:
        return None
    height, width = frame.shape[:2]
    return _image_landmarks_to_equal_scale(
        observation.landmarks,
        width,
        height,
    )


def _save_results(path: Path, camera_index: int, captures: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "camera_index": camera_index,
        "driver_connected": False,
        "poses": {
            pose: summarize_angle_samples(samples)
            for pose, samples in captures.items()
        },
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    args = _parse_args()
    config_path = Path(args.config).resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    camera_config = dict(config["camera"])
    if args.camera is not None:
        camera_config["index"] = args.camera

    recognizer_config = config["recognizer"]
    recognizer = GestureRecognizer(
        max_num_hands=recognizer_config["max_num_hands"],
        min_detection_confidence=recognizer_config["min_detection_confidence"],
        min_tracking_confidence=recognizer_config["min_tracking_confidence"],
        smooth_factor=0.0,
    )
    camera = _open_camera(camera_config)
    output_path = Path(args.output).resolve()
    captures = {"open": [], "fist": []}
    active_pose = None
    countdown_until = 0.0
    capture_until = 0.0
    saved = False

    print("安全采样模式：未加载任何灵巧手驱动。")
    print("按 O 采集完全张开，按 F 采集完全握拳，按 Q 退出。")

    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError("摄像头读取失败")
            if camera_config.get("mirror", True):
                frame = cv2.flip(frame, 1)

            observation = recognizer.process(frame)
            recognizer.draw_landmarks(frame, observation)
            now = time.monotonic()

            if active_pose is not None and now >= countdown_until:
                if capture_until == 0.0:
                    capture_until = now + max(args.seconds, 0.1)
                geometry = _geometry_landmarks(observation, frame)
                if geometry is not None:
                    captures[active_pose].append(
                        measure_four_finger_angles(geometry),
                    )
                if now >= capture_until:
                    print(
                        f"{POSE_LABELS[active_pose]}: "
                        f"采集 {len(captures[active_pose])} 帧",
                    )
                    active_pose = None
                    capture_until = 0.0
                    if all(captures.values()):
                        _save_results(
                            output_path,
                            int(camera_config["index"]),
                            captures,
                        )
                        saved = True
                        print(f"角度报告已保存：{output_path}")

            status = "O: open  F: fist  Q: quit"
            if active_pose is not None:
                if now < countdown_until:
                    remaining = max(0.0, countdown_until - now)
                    status = f"Prepare {POSE_LABELS[active_pose]}  {remaining:.1f}s"
                else:
                    remaining = max(0.0, capture_until - now)
                    status = f"Capturing {POSE_LABELS[active_pose]}  {remaining:.1f}s"
            elif saved:
                status = "Saved. O/F: recapture  Q: quit"

            cv2.rectangle(frame, (0, 0), (frame.shape[1], 54), (15, 15, 15), -1)
            cv2.putText(
                frame,
                status,
                (18, 36),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow("Hand geometry calibration (camera only)", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key in (ord("o"), ord("f")) and active_pose is None:
                active_pose = "open" if key == ord("o") else "fist"
                captures[active_pose] = []
                countdown_until = time.monotonic() + max(args.countdown, 0.0)
                capture_until = 0.0
    finally:
        recognizer.close()
        camera.release()
        cv2.destroyAllWindows()

    if not saved:
        print("未同时完成张手和握拳采样，没有写入报告。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
