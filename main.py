"""摄像头手势识别 -> LHandPro 灵巧手控制 主程序。

用法:
    pip install -r requirements.txt
    python main.py                          # 默认 sim 仿真驱动 + mirror 模式
    python main.py --driver sim --mode gesture
    python main.py --driver lhandpro        # 接真实灵巧手 (需先配置 config.yaml)

按键:
    q     退出
    m     切换 mirror / gesture 模式
    空格   暂停 / 恢复向灵巧手发送指令 (安全开关)
"""

import argparse
import os
import sys
import time
from contextlib import nullcontext, redirect_stdout

import cv2
import numpy as np
import yaml

from app_paths import app_dir, resolve_app_path
from app_runtime import RuntimeResources
from control_safety import TrackingState, TrackingWatchdog
from gesture_preset_controller import GesturePresetController
from gesture_recognizer import GestureRecognizer, GESTURE_NAMES_CN, HandObservation
from gesture_mapping import GestureMapper
from hud_renderer import draw_hud
from rock_paper_scissors import RockPaperScissorsController
from runtime_telemetry import build_runtime_state
from drivers.sim_driver import SimHandDriver
from electron_bridge import (
    KEY_MODE_GESTURE,
    KEY_MODE_MIRROR,
    KEY_MODE_RPS,
    KEY_RECOVER_CONTROL,
    KEY_TOGGLE_DETECTION,
    ElectronBridge,
)

def load_config(path: str) -> dict:
    """从开发目录或打包后的资源目录读取 YAML 配置。"""
    with open(resolve_app_path(path), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def make_driver(cfg: dict, joint_names):
    """根据配置创建真实 CAN-FD 驱动或无硬件仿真驱动。"""
    dtype = cfg["driver"]["type"]
    if dtype == "lhandpro":
        from drivers.lhandpro_driver import LHandProDriver
        lp = cfg["driver"]["canfd"]
        return LHandProDriver(
            library_path=lp["library_path"],
            node_id=lp.get("node_id", 1),
            device_index=lp.get("device_index"),
            nom_baudrate=lp.get("nom_baudrate", 1000000),
            dat_baudrate=lp.get("dat_baudrate", 5000000),
            hand_type=lp.get("hand_type", 0),
            hand_direction=lp.get("hand_direction"),
            enable_motors=lp.get("enable_motors", True),
            home_motors=lp.get("home_motors", True),
            home_wait_time=lp.get("home_wait_time", 5.0),
            velocity=lp.get("velocity", 20000),
            max_current=lp.get("max_current", 1000),
        )
    return SimHandDriver(joint_names)


# ----------------------------------------------------------------------
def main(argv=None) -> int:
    """解析启动参数并建立本次运行所需资源的统一生命周期。"""
    if sys.platform == "win32":
        # 控制台切 UTF-8 并设置窗口标题, 避免中文日志乱码
        os.system("chcp 65001 >nul & title RP-Hand手势识别")
    ap = argparse.ArgumentParser(description="摄像头手势识别控制 LHandPro 灵巧手")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--driver", choices=["sim", "lhandpro"], default=None, help="覆盖 config 的驱动类型")
    ap.add_argument("--mode", choices=["mirror", "gesture", "rps"], default=None,
                    help="覆盖 config 的控制模式 (rps=石头剪刀布对战)")
    ap.add_argument("--camera", type=int, default=None, help="覆盖 config 的摄像头编号")
    ap.add_argument("--duration", type=float, default=None, help="运行 N 秒后自动安全退出 (默认不限)")
    ap.add_argument("--electron-bridge", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    if args.driver:
        cfg["driver"]["type"] = args.driver
    if args.mode:
        cfg["control"]["mode"] = args.mode
    if args.camera is not None:
        cfg["camera"]["index"] = args.camera

    protocol_stdout = sys.stdout
    bridge = ElectronBridge(sys.stdin, protocol_stdout) if args.electron_bridge else None
    log_context = redirect_stdout(sys.stderr) if bridge is not None else nullcontext()
    try:
        with log_context:
            # 入口统一拥有运行资源；无论 _run 正常返回还是抛出异常，
            # 离开 with 时都会按确定顺序释放驱动、摄像头和识别器。
            with RuntimeResources(destroy_windows=cv2.destroyAllWindows) as resources:
                return _run(cfg, args, resources, bridge=bridge)
    finally:
        if bridge is not None:
            bridge.close()


def _run(cfg: dict, args, resources: RuntimeResources, bridge=None) -> int:
    """执行实时识别与控制循环；资源释放由调用方统一负责。"""

    rcfg = cfg["recognizer"]
    recognizer = GestureRecognizer(
        max_num_hands=rcfg["max_num_hands"],
        min_detection_confidence=rcfg["min_detection_confidence"],
        min_tracking_confidence=rcfg["min_tracking_confidence"],
        smooth_factor=rcfg["smooth_factor"],
    )
    resources.recognizer = recognizer
    mapper = GestureMapper(
        cfg["hand"]["joints"],
        cfg.get("presets", {}),
        cfg["hand"].get("input_calibration", {}),
        cfg["hand"].get("pinch_assist", {}),
    )
    driver = make_driver(cfg, mapper.joint_names)
    resources.driver = driver
    if not driver.connect():
        print("驱动连接失败, 可先用 --driver sim 调试手势识别部分。")
        return 1

    ccfg = cfg["camera"]
    # Windows 上部分摄像头用默认 MSMF 后端抓不到帧, 强制 DirectShow
    if sys.platform == "win32":
        cap = cv2.VideoCapture(ccfg["index"], cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(ccfg["index"])
    resources.camera = cap
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, ccfg["width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ccfg["height"])
    if not cap.isOpened():
        print(f"无法打开摄像头 {ccfg['index']}")
        return 1

    mode = cfg["control"]["mode"]
    detection_enabled = True
    sending = True
    send_interval = 1.0 / max(cfg["control"]["send_rate_hz"], 1)
    tracking_cfg = cfg.get("safety", {}).get("tracking", {})
    watchdog = TrackingWatchdog(
        safe_positions=[joint["range"][0] for joint in cfg["hand"]["joints"]],
        grace_period_s=tracking_cfg.get("grace_period_s", 0.35),
        safe_return_duration_s=tracking_cfg.get("safe_return_duration_s", 1.2),
        lost_action=tracking_cfg.get("lost_action", "open"),
    )
    hold_needed = cfg["control"]["command_hold_frames"]
    gesture_controller = GesturePresetController(hold_frames=hold_needed)
    last_sent = float("-inf")
    rps_controller = RockPaperScissorsController(
        hold_frames=hold_needed,
        cooldown_s=cfg["control"].get("rps_cooldown_s", 3.0),
    )

    print("运行中...  q=退出  m=切换模式  空格=暂停/恢复发送  e=紧急停止  r=受控恢复")
    fail_count = 0
    t_start = time.time()
    while True:
        if args.duration is not None and time.time() - t_start >= args.duration:
            print(f"已运行 {args.duration:.0f} 秒, 自动安全退出")
            break
        ok, frame = cap.read()
        if not ok:
            fail_count += 1
            if fail_count > 30:  # 连续失败约1秒才放弃 (摄像头初始化期可能丢帧)
                print("持续无法读取摄像头帧, 退出")
                break
            time.sleep(0.03)
            continue
        fail_count = 0
        if ccfg.get("mirror", True):
            frame = cv2.flip(frame, 1)

        if detection_enabled:
            obs = recognizer.process(frame)
            recognizer.draw_landmarks(frame, obs)
        else:
            obs = HandObservation()

        positions = None
        display_inputs = None
        if obs.detected:
            vals = dict(obs.curls)
            vals["thumb_spread"] = obs.thumb_spread
            display_inputs = mapper.calibrate_inputs(vals)
            if mode == "mirror":
                positions = mapper.map_mirror(
                    vals,
                    pinch_strength=obs.pinch_strength,
                )
            elif mode == "rps":
                rps_decision = rps_controller.update(
                    obs.gesture,
                    detected=True,
                    now=time.time(),
                    map_preset=mapper.map_preset,
                )
                positions = rps_decision.positions
                if rps_decision.log_message:
                    print(rps_decision.log_message)
            else:  # gesture 模式: 手势稳定 hold_needed 帧才触发预设动作
                gesture_decision = gesture_controller.update(
                    obs.gesture,
                    detected=True,
                    map_preset=mapper.map_preset,
                )
                positions = gesture_decision.positions
                if gesture_decision.gesture is not None:
                    gesture = gesture_decision.gesture
                    print(
                        f"[手势触发] {gesture} -> "
                        f"{GESTURE_NAMES_CN.get(gesture, gesture)}"
                    )
        elif mode == "rps":
            rps_controller.update(
                None,
                detected=False,
                now=time.time(),
                map_preset=mapper.map_preset,
            )
        elif mode == "gesture":
            gesture_controller.update(
                None,
                detected=False,
                map_preset=mapper.map_preset,
            )

        now = time.monotonic()
        decision = watchdog.update(
            positions,
            now=now,
            tracking_detected=obs.detected,
        )
        if decision.should_stop:
            driver.stop()
            sending = False

        safety_command = (
            positions is not None
            or decision.state in {TrackingState.SAFE_RETURN, TrackingState.SAFE_HOLD}
        )
        output_allowed = sending or not detection_enabled
        if (decision.target is not None and safety_command and output_allowed
                and driver.is_connected and now - last_sent >= send_interval):
            if driver.set_joint_positions(decision.target):
                watchdog.note_output(decision.target)
            last_sent = now

        if decision.target is not None:
            hud_positions = decision.target
        else:
            state = driver.get_state()
            hud_positions = list(state.values()) if state else [0] * mapper.num_joints

        safety_banner = {
            TrackingState.GRACE: "TRACKING LOST - HOLDING",
            TrackingState.SAFE_RETURN: "TRACKING LOST - SAFE RETURN",
            TrackingState.SAFE_HOLD: "SAFE POSE",
            TrackingState.STOPPED: "EMERGENCY STOP",
        }.get(decision.state, "")
        banner = safety_banner or (
            rps_controller.banner if mode == "rps" else ""
        )
        pos_max = max(max(j["range"]) for j in cfg["hand"]["joints"])
        if bridge is None:
            draw_hud(
                frame,
                obs,
                hud_positions,
                mapper.joint_names,
                mode,
                sending,
                driver.is_connected,
                pos_max,
                banner=banner,
                display_inputs=display_inputs,
            )
            cv2.imshow("RP-Hand", frame)
            key = cv2.waitKey(1) & 0xFF
        else:
            bridge.submit_frame(
                frame,
                now=now,
                state=build_runtime_state(
                    mode=mode,
                    detection_enabled=detection_enabled,
                    sending=sending,
                    safety_state=decision.state.value,
                    observation=obs,
                    display_inputs=display_inputs,
                    positions=hud_positions,
                    joint_names=mapper.joint_names,
                    position_max=pos_max,
                    driver_connected=driver.is_connected,
                    banner=banner,
                ),
            )
            key = bridge.poll_key()
        if key == ord("q"):
            break
        elif key in {KEY_MODE_MIRROR, KEY_MODE_GESTURE, KEY_MODE_RPS}:
            mode = {
                KEY_MODE_MIRROR: "mirror",
                KEY_MODE_GESTURE: "gesture",
                KEY_MODE_RPS: "rps",
            }[key]
            gesture_controller.reset()
            rps_controller.reset()
            print(f"切换到 {mode} 模式")
        elif key == KEY_TOGGLE_DETECTION:
            detection_enabled = not detection_enabled
            if not detection_enabled:
                watchdog.request_safe_return(now)
            else:
                watchdog.resume_tracking_policy(now)
            gesture_controller.reset()
            rps_controller.reset()
            print("已开启手部识别" if detection_enabled else "已关闭手部识别")
        elif key == ord("m"):
            modes = ["mirror", "gesture", "rps"]
            mode = modes[(modes.index(mode) + 1) % len(modes)]
            gesture_controller.reset()
            rps_controller.reset()
            print(f"切换到 {mode} 模式")
        elif key == ord(" "):
            if watchdog.state is TrackingState.STOPPED:
                print("急停已锁定, 请排除故障后重启程序")
            else:
                sending = not sending
                print("恢复发送" if sending else "已暂停发送 (灵巧手保持当前姿态)")
        elif key == ord("e"):
            if watchdog.force_stop():
                driver.stop()
                sending = False
                print("紧急停止已触发, 排除风险后可执行受控恢复")
        elif key in {KEY_RECOVER_CONTROL, ord("r")}:
            if watchdog.state is not TrackingState.STOPPED:
                print("当前未处于急停状态, 无需恢复")
            elif driver.recover():
                # Recovery never resumes vision-driven commands directly.
                # It first disables tracking and returns to the safe pose.
                watchdog.recover_to_safe_return(now)
                detection_enabled = False
                sending = False
                gesture_controller.reset()
                rps_controller.reset()
                print("控制已恢复, 正在安全回张; 请确认状态后重新开启识别与发送")
            else:
                print("恢复控制失败, 急停保持锁定")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
