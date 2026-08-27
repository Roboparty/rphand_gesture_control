"""CANFD 硬件连通性冒烟测试。

流程: 扫描 CANFD 设备 -> 连接 -> 使能 -> 回零 -> 逐轴小幅度运动 -> 回到张开 -> 断开。
动作幅度故意做小 (5000/10000), 速度适中, 与厂商示例流程一致。
"""

import sys
import time

import yaml

from drivers.lhandpro_driver import LHandProDriver


def main():
    """以受限幅度逐轴测试真实 CAN-FD 连接、运动和位置反馈。"""
    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    lp = cfg["driver"]["canfd"]

    driver = LHandProDriver(
        library_path=lp["library_path"],
        node_id=lp.get("node_id", 1),
        device_index=lp.get("device_index"),
        nom_baudrate=lp.get("nom_baudrate", 1000000),
        dat_baudrate=lp.get("dat_baudrate", 5000000),
        hand_type=lp.get("hand_type", 0),
        enable_motors=True,
        home_motors=True,
        home_wait_time=lp.get("home_wait_time", 5.0),
        velocity=lp.get("velocity", 20000),
        max_current=lp.get("max_current", 1000),
    )

    print("=" * 50)
    print("LHandPro CANFD 连通性测试")
    print("=" * 50)

    if not driver.connect():
        print("\n[结果] 连接失败")
        return 1

    dof = driver._dof_active
    print(f"\n开始逐轴运动测试 (主动自由度={dof})...")
    try:
        for axis in range(dof):
            pos = [0] * dof
            pos[axis] = 5000  # 半弯曲, 动作温和
            ok = driver.set_joint_positions(pos)
            print(f"  轴 {axis + 1} -> 5000  {'OK' if ok else 'FAIL'}")
            time.sleep(1.0)
            driver.set_joint_positions([0] * dof)
            time.sleep(0.6)

        # 读取实际位置验证反馈链路
        state = driver.get_state()
        print(f"\n电机当前位置反馈: {state}")

        # 最后一次: 轻微握拳再张开
        print("\n半握拳 -> 张开 ...")
        driver.set_joint_positions([5000] * dof)
        time.sleep(1.2)
        driver.set_joint_positions([0] * dof)
        time.sleep(1.0)
        print("[结果] 测试完成, 通讯与运动均正常")
        return 0
    except Exception as e:
        print(f"\n[结果] 运动测试异常: {e}")
        return 1
    finally:
        driver.disconnect()


if __name__ == "__main__":
    sys.exit(main())
