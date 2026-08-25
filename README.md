# 摄像头手势识别 → LHandPro 灵巧手控制 (Windows x64 / CANFD)

通过普通 RGB 摄像头识别你的手势，实时驱动 LHandPro 灵巧手。
底层直接集成厂商 SDK（`LHandProLib.dll` + `HCanbus.dll` CANFD 驱动），无需再手写 C 绑定。

**已在真机上验证通过**（2026-07-25）：CANFD 连接、回零、逐轴运动、位置反馈、
摄像头手势识别全流程均正常（总自由度 11，主动自由度 6）。

## 功能

- **mirror 模式（连续映射）**：你的手指弯多少，灵巧手对应关节就弯多少，30 Hz 实时跟随。
- **gesture 模式（手势指令）**：识别到握拳 / 张开 / 捏合 / 指点 / 剪刀手 / 点赞，执行预设动作。
- 已内置厂商 Python SDK（`vendor/`），驱动开箱即用。
- 自带 `sim` 仿真驱动，不接手也能调试手势识别。
- 画面右侧 HUD 实时显示：手势标签、各手指弯曲度、灵巧手各关节指令位置。

## 环境准备（Windows x64）

1. USB-CANFD 适配器连接电脑与灵巧手，灵巧手上电。
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
   注意：`mediapipe` 请用 **0.10.14**（新版 0.10.30+ 移除了 `mp.solutions` 接口）。
   ```bash
   pip install mediapipe==0.10.14
   ```

## 运行

```bash
# 1. 硬件连通性测试（连接 → 使能 → 回零 → 逐轴半弯曲 → 张开）
python test_connection.py

# 2. 无硬件调试手势识别（仿真驱动）
python main.py --driver sim

# 3. 手势控制真实灵巧手
python main.py --driver lhandpro

# 手势指令模式
python main.py --driver lhandpro --mode gesture
```

按键：`q` 退出（请用 q 退出，会正常停止电机并断开），`m` 切换模式，`空格` 暂停/恢复发送（安全开关）。

连接流程：扫描 CANFD 适配器（`device_index` 可指定）→ 使能电机 → 回零（约 5 秒）→ 开始跟随。
**回零和动作前请确保手周围没有遮挡物。**

## 配置说明（config.yaml）

| 配置项 | 说明 |
|---|---|
| `driver.canfd.library_path` | `LHandProLib.dll` 路径，默认指向工作区解压的 SDK |
| `driver.canfd.node_id` | CANFD 节点 ID（默认 1，需与手的配置一致） |
| `driver.canfd.device_index` | 适配器序号，`null`=自动选第一个 |
| `driver.canfd.nom_baudrate` / `dat_baudrate` | 仲裁域 1 Mbps / 数据域 5 Mbps（厂商默认） |
| `driver.canfd.velocity` / `max_current` | 运动速度 / 最大电流（厂商默认 20000 / 1000） |
| `camera.index` | 摄像头编号（本机 0/1 均可用，已强制 DirectShow 后端） |
| `hand.joints` | 关节映射：0=张开、10000=完全弯曲；方向反了就把 range 对调成 `[10000, 0]` |
| `presets` | gesture 模式下各手势的预设关节位置 |
| `recognizer.smooth_factor` | 手势防抖平滑系数 |

## 项目结构

```
gesture_hand_control/
├── main.py                  # 主程序：采集 → 识别 → 映射 → 下发 → HUD
├── test_connection.py       # CANFD 硬件连通性冒烟测试
├── gesture_recognizer.py    # MediaPipe 21 点检测、手指弯曲度、手势分类
├── gesture_mapping.py       # 弯曲度/手势 → 灵巧手关节位置
├── config.yaml              # 全部可调参数
├── drivers/
│   ├── base_driver.py       # 驱动抽象接口
│   ├── sim_driver.py        # 仿真驱动（无硬件调试）
│   └── lhandpro_driver.py   # LHandPro CANFD 驱动（封装厂商 SDK）
├── vendor/                  # 厂商 SDK Python 封装（从 CANFD_python 示例拷贝）
│   ├── canfd_lib.py         # CANFD 通信库
│   ├── lib/HCanbus.dll      # Windows CANFD 底层驱动
│   └── lhandprolib_python_sdk/
└── requirements.txt
```

## 常见问题

- **"No CANFD device found"**：检查 USB-CANFD 适配器连接与驱动安装。
- **连上但手不动**：检查 `node_id` 和波特率是否与手的配置一致。
- **摄像头打不开 / 读不到帧**：改 `camera.index`（0/1 切换试试）；程序已默认 DirectShow 后端。
- **`module 'mediapipe' has no attribute 'solutions'`**：mediapipe 版本太新，`pip install mediapipe==0.10.14`。
- **弯曲方向相反**：把对应关节 `range: [0, 10000]` 改成 `[10000, 0]`。
- **手势抖动**：调大 `recognizer.smooth_factor`；指令太密可调低 `control.send_rate_hz`。
