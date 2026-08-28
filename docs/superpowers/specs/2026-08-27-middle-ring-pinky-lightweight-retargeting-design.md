# RP-Hand 中指、无名指与小指轻量重定向设计

## 目标

在 `feature/hand-improve1` 分支上改善中指、无名指和小指的独立蜷缩幅度。目标是让机械手动作更接近人手，不追求严格的逐关节复刻，也不改变当前可用的拇指、食指、捏合、急停、恢复、CAN-FD 与 Electron 控制逻辑。

## 当前问题

识别器目前只使用 `MCP-PIP-TIP` 的单个夹角。单指蜷缩时，遮挡、DIP 形态和 MediaPipe 世界坐标误差会让这个角度只覆盖部分动态范围；映射器又把中指、无名指和小指的闭合端默认视为 `1.0`，所以真机常只能走到约半行程。

## 第一版方案

为中指、无名指和小指增加一个尺度与旋转无关的“指尖回缩量”：

```text
chain = |MCP-PIP| + |PIP-DIP| + |DIP-TIP|
reach = |MCP-TIP| / chain
retraction = 1 - reach
```

手指伸直时，指尖到 MCP 的直线距离接近整条骨链长度，回缩量接近 `0`；手指蜷缩时，直线距离变短，回缩量增大。该特征显式使用 DIP，同时不依赖相机中的手掌朝向。

映射器分别校准旧角度和回缩量，然后对三个目标手指取较强值：

```text
final = max(calibrated_legacy_curl, calibrated_retraction)
```

这样旧算法仍是下限，新信号只补足其漏掉的行程。配置关闭、新数据缺失或几何退化时，输出自动回到旧算法。

## 代码边界

- `finger_retargeting.py`：纯 NumPy 几何特征，可独立测试，未来可承接完整重定向策略。
- `gesture_recognizer.py`：计算并平滑回缩量，写入 `HandObservation`。
- `gesture_mapping.py`：校准、选择目标手指并融合两个信号。
- `main.py`：传递数据，不包含几何或融合公式。
- `config.yaml`：保存开关、目标手指和逐指回缩端点，便于真机 A/B 调整。

## 安全与回退

- 仅对 `middle`、`ring`、`pinky` 生效。
- 不修改关节范围、发送频率、速度、电流、急停与恢复。
- `enabled: false` 即恢复旧算法。
- 自动测试使用合成坐标和仿真驱动，不连接真机。
- 真机先暂停发送观察数值，再低速、无障碍地开启发送测试。

## 后续 dex-retargeting 模式

若轻量方案能改善幅度，第二阶段新增独立策略模式，而不是替换本方案。完整模式将参考 dex-retargeting 的手掌局部坐标、相对指尖向量、关节限制与低通滤波；需要先补齐 LHandPro 的准确 URDF、关节方向和限制，并单独评估 Pinocchio/NLopt 对 Windows 安装包的体积和兼容性。
