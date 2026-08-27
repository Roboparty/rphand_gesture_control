# RP-Hand Gesture

RP-Hand Gesture 是一个面向 Windows x64 的实时灵巧手控制程序。它通过普通 RGB 摄像头和
MediaPipe 获取人手关键点，将手指动作连续映射到 LHandPro 灵巧手，并通过 USB-CANFD 下发控制指令。

当前稳定版本为 **v1.0.0**。该版本以“先能稳定使用”为目标，Electron GUI 只开放连续映射模式；
手势触发和猜拳实验代码仍保留在源码中，但暂不显示在正式界面。

## 主要功能

- 普通摄像头实时识别人手，无需深度相机。
- 连续映射拇指、食指、中指、无名指和小指动作。
- 浅色 Electron 桌面界面，显示识别结果、输入比例和关节指令。
- “手部识别”和“指令发送”使用两个独立开关。
- 支持软件急停、确认恢复和丢手安全回张。
- 内置 LHandPro Python SDK、CAN-FD 用户态库和 Python 运行环境。
- 提供 `sim` 仿真驱动，可在不连接灵巧手时调试摄像头与界面。

本项目已在真实 LHandPro 灵巧手与 CAN-FD 适配器上完成连接、回零、连续映射、急停及恢复测试。

## 安装 v1.0.0

构建后的安装包名称为：

```text
RP-Hand Gesture Setup 1.0.0.exe
```

安装后的应用、开始菜单快捷方式和主程序名称均为 **RP-Hand Gesture**。普通使用者不需要单独安装
Python、Node.js 或 Electron。

### 运行条件

- Windows 10 或 Windows 11，64 位。
- 可正常使用的 RGB 摄像头。
- LHandPro 灵巧手、电源及兼容的 USB-CANFD 适配器。
- 当前验证适配器使用 Windows 内置 WinUSB；其他型号如无法识别，请安装适配器厂商提供的驱动。

安装包目前未进行商业代码签名，Windows SmartScreen 可能显示未知发布者提示。请仅从本仓库的
GitHub Releases 或 RoboParty 官方渠道获取安装包。

### 首次启动

1. 确认灵巧手周围没有障碍物，然后连接 CAN-FD 并给灵巧手上电。
2. 连接摄像头并启动 RP-Hand Gesture。
3. 程序会依次加载配置、连接驱动、打开摄像头并完成灵巧手初始化。
4. 等待画面与右侧状态栏出现后，再开始做手势映射测试。

> 软件急停不能替代硬件急停、机械限位或人工安全监护。真机运行时请始终为灵巧手保留安全空间。

## GUI 控制

| 控件 | 说明 |
|---|---|
| 手部识别 | 开启或关闭摄像头画面中的 MediaPipe 手部识别；关闭后摄像头仍保持预览。 |
| 指令发送 | 单独暂停或恢复向灵巧手发送关节指令，不影响手部识别。 |
| 控制模式 | v1.0.0 正式界面仅开放“连续映射”。 |
| 紧急停止 | 立即停止电机并锁存急停状态。 |
| 恢复控制 | 仅在急停已生效时可用；确认周围安全后重新初始化控制并安全回张。 |

快捷键：

- `Space`：暂停或恢复指令发送。
- `E`：紧急停止。
- `R`：执行受控恢复。
- `Q`：安全退出。

## 从源码运行

### 开发环境

- Python 3.12 x64。
- Node.js 与 npm。
- MediaPipe 0.10.14（项目仍使用 `mp.solutions` 接口）。

```powershell
git clone git@github.com:Roboparty/rphand_gesture_control.git
cd rphand_gesture_control

py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

cd electron
npm install
```

### 启动 Electron GUI

Electron 默认连接真实灵巧手：

```powershell
cd electron
npm start
```

不连接硬件时，可使用仿真驱动：

```powershell
$env:RP_HAND_DRIVER = "sim"
npm start
```

### 命令行运行

```powershell
# 仿真驱动
.\.venv\Scripts\python.exe main.py --driver sim

# 真实 LHandPro 灵巧手
.\.venv\Scripts\python.exe main.py --driver lhandpro

# CAN-FD 硬件连通性测试
.\.venv\Scripts\python.exe test_connection.py
```

命令行/TUI 默认读取 `config.yaml`，其驱动默认值保持为 `sim`，避免开发时意外连接真实硬件。

## 构建 Windows 安装包

```powershell
cd electron
npm run dist:win
```

该命令会先运行 Electron 测试，再使用 PyInstaller 构建 Python 后端，最后通过 electron-builder 生成：

```text
electron/dist/RP-Hand Gesture Setup 1.0.0.exe
```

内部 Python 后端仍使用 `resources/RP-Hand/RP-Hand.exe`，这是 Electron 与 PyInstaller 之间的内部路径，
不会改变安装后向用户显示的 RP-Hand Gesture 名称。

## 测试

```powershell
# Python
.\.venv\Scripts\python.exe -m pytest -q

# Electron
cd electron
npm test
```

使用真实硬件测试前，建议先运行仿真后端冒烟测试，并确认摄像头、急停和恢复流程均正常。

## 手指角度采样

调整几何映射前，可以在不连接灵巧手的情况下采集真实张手与握拳范围：

```powershell
.\.venv\Scripts\python.exe capture_geometry_ranges.py --camera 0
```

窗口中按 `O` 采集完全张开的手掌，按 `F` 采集完全握拳，按 `Q` 退出。报告会写入
`diagnostics/hand_geometry_ranges.json`，该工具不会加载 CAN-FD 驱动或发送关节指令。

## 配置说明

主要配置位于 `config.yaml`：

| 配置项 | 说明 |
|---|---|
| `driver.type` | 命令行默认驱动，建议开发环境保持 `sim`。 |
| `driver.canfd.library_path` | `LHandProLib.dll` 路径。 |
| `driver.canfd.node_id` | CAN-FD 节点 ID，必须与灵巧手配置一致。 |
| `driver.canfd.device_index` | 适配器序号，`null` 表示自动选择第一个。 |
| `driver.canfd.nom_baudrate` / `dat_baudrate` | CAN-FD 仲裁域与数据域波特率。 |
| `camera.index` | 摄像头编号；无法打开时可尝试在 0 和 1 之间切换。 |
| `hand.input_calibration` | 完全张手时 MediaPipe 残余输入的校正值。 |
| `hand.joints` | 输入比例到灵巧手关节位置的映射范围。 |
| `recognizer.smooth_factor` | 手指输入的平滑系数。 |
| `control.send_rate_hz` | 关节指令发送频率。 |

## 项目结构

```text
.
├── main.py                         # Python 主循环与运行编排
├── app_runtime.py                  # 摄像头、驱动等资源生命周期
├── control_safety.py               # 丢手看门狗、急停和恢复状态
├── gesture_recognizer.py           # MediaPipe 检测与手指输入计算
├── gesture_mapping.py              # 手指输入到灵巧手关节的映射
├── runtime_telemetry.py            # GUI/TUI 共用的运行状态
├── electron_bridge.py              # Electron 与 Python 行协议
├── electron/                       # Electron GUI、测试与打包配置
├── drivers/
│   ├── base_driver.py              # 驱动接口
│   ├── sim_driver.py               # 无硬件仿真驱动
│   └── lhandpro_driver.py          # LHandPro CAN-FD 驱动
├── vendor/                         # 厂商 SDK 与 CAN-FD 用户态库
├── tests/                          # Python 测试
├── docs/                           # 架构、计划与排障文档
└── config.yaml                     # 运行和映射配置
```

## 常见问题

- **No CANFD device found**：检查适配器、电源、USB 连接和设备驱动。
- **连接成功但灵巧手不动**：确认“指令发送”已开启，并检查 `node_id` 与波特率。
- **急停后无法操作**：排除故障并确认周围安全，再点击“恢复控制”或按 `R`。
- **摄像头打不开**：关闭占用摄像头的软件，检查 Windows 摄像头权限，或修改 `camera.index`。
- **MediaPipe 没有 `solutions`**：安装 `mediapipe==0.10.14`。
- **手指方向相反**：检查对应关节映射范围，而不是直接提高速度或电流限制。
- **SmartScreen 提示未知发布者**：当前安装包尚未代码签名，请核对下载来源和 SHA-256。

## License

项目自有源代码以 [MIT License](LICENSE) 开源。

`vendor/` 中的厂商 SDK、动态库以及其他第三方组件不因此被重新授权，仍分别遵循其原始许可条款。
