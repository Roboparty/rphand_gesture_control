r"""无摄像头时的单张图片测试工具。

这个脚本只负责调用现有 GestureRecognizer，并把结果打印、画回图片。
它不会修改识别算法，也不会连接或控制真实灵巧手。

示例：
    .\.venv\Scripts\python.exe offline_image_test.py diag_now.jpg \
        --output part1_diag_result.jpg
"""

import argparse
import os
import sys

import cv2

from gesture_recognizer import GestureRecognizer


def main() -> int:
    parser = argparse.ArgumentParser(description="用单张图片测试手势识别和世界坐标路径")
    parser.add_argument("image", help="输入图片路径")
    parser.add_argument("--output", help="可选：保存绘制关键点后的结果图片")
    args = parser.parse_args()

    image_path = os.path.abspath(args.image)
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"[FAIL] 无法读取图片: {image_path}")
        return 1

    # 单张图片没有连续帧，不能使用时间平滑；smooth_factor=0.0 表示直接观察原始结果。
    recognizer = GestureRecognizer(
        max_num_hands=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.5,
        smooth_factor=0.0,
    )

    try:
        obs = recognizer.process(frame)
        recognizer.draw_landmarks(frame, obs)
    finally:
        recognizer.close()

    print(f"image: {image_path}")
    print(f"detected: {obs.detected}")
    print(f"handedness: {obs.handedness if obs.detected else 'N/A'}")
    print(f"gesture: {obs.gesture}")
    print(f"world_landmarks: {obs.world_landmarks is not None}")

    if obs.detected:
        print("curls:")
        for finger, value in obs.curls.items():
            print(f"  {finger}: {value:.4f}")
        print(f"thumb_spread: {obs.thumb_spread:.4f}")

    if args.output:
        output_path = os.path.abspath(args.output)
        if not cv2.imwrite(output_path, frame):
            print(f"[FAIL] 无法保存结果图片: {output_path}")
            return 1
        print(f"output: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
