# RP-Hand Electron GUI 设计规格

## 1. 目标

为现有 Windows 灵巧手控制程序增加一个开箱即用的 Electron 外壳。第一版只迁移当前 OpenCV 窗口，不重新设计界面，不增加控制能力，也不修改手势识别、关节映射、CAN-FD 或安全状态机。

Electron 窗口必须完整保留当前 `draw_hud()` 生成的画面结构和样式，唯一新增的可见控件是急停按钮。

## 2. 第一版范围

包含：

- 单个 Electron 窗口。
- 原有摄像头画面、MediaPipe 骨架和右侧 HUD 原样显示。
- 原有 `q`、`m`、空格和 `e` 键盘操作继续有效。
- 在右侧 HUD 空白区域覆盖一个可点击的急停按钮。
- Electron 关闭时通知 Python 正常退出；若 Python 未及时退出，再终止子进程。
- 源码开发模式可以直接运行，Windows 打包阶段复用现有 PyInstaller 资源。

不包含：

- GEO-01、GEO-02、GEO-03 或校准功能。
- 新的设备选择、模式选择、参数编辑、录制或历史记录。
- 重画 HUD、修改颜色、修改文案、修改布局。
- 恢复 SAFE-03 的速度、加速度、单步或反馈限制。
- macOS 和 Linux 打包。

## 3. 界面

Electron 内容区按摄像头原始宽高比显示 Python 已经绘制完成的整帧画面。缩放时使用等比例 `contain`，不裁切、不拉伸；多余区域使用黑色，与当前 OpenCV 窗口观感一致。

急停按钮位于右侧 HUD 的下方空白区域，采用深色底、红色边框和 `EMERGENCY STOP` 文案。按钮不改变 HUD 中既有信息的位置。点击后立即锁定，不允许再次恢复发送；恢复仍需重启程序，与现有 `E` 键行为一致。

窗口获得焦点时：

- `Q`：正常退出。
- `M`：循环切换 mirror、gesture、rps。
- `Space`：暂停或恢复发送。
- `E`：紧急停止。

## 4. 架构

### 4.1 Electron

新增独立的 `electron/` 目录：

- `main.cjs`：创建窗口、启动 Python 子进程、转发命令并管理退出。
- `preload.cjs`：只暴露白名单 IPC，不开启 renderer 的 Node 权限。
- `renderer/`：显示视频帧、转发键盘操作、提供急停按钮和错误状态。
- `package.json`：开发、测试和 Windows 打包脚本。

BrowserWindow 使用 `contextIsolation: true`、`nodeIntegration: false`。Renderer 不执行任意系统命令，也不接收外部网页内容。

### 4.2 Python 桥接模式

现有 CLI/OpenCV 运行方式保持不变。增加一个显式 Electron 桥接入口，在桥接模式下：

1. 仍由 Python 完成摄像头读取、MediaPipe、映射、驱动控制、骨架和 HUD 绘制。
2. 不调用 `cv2.imshow()`。
3. 将绘制后的整帧压缩为 JPEG，通过子进程标准输出发送给 Electron。
4. 从标准输入接收有限命令：`quit`、`cycle_mode`、`toggle_pause`、`emergency_stop`。

桥接协议使用逐行 JSON。日志写入标准错误，避免与帧消息混在一起。帧消息包含递增序号和 Base64 JPEG；第一版限制界面刷新率，控制循环本身不降频。

Electron 不读取、计算或修改关节位置，因此 GUI 无法改变控制算法。

## 5. 数据流

正常帧：

`Camera -> GestureRecognizer -> GestureMapper -> Driver -> draw_landmarks/draw_hud -> JPEG -> Electron`

急停：

`Electron button/E key -> stdin JSON -> TrackingWatchdog.force_stop() -> driver.stop() -> STOPPED HUD frame`

退出：

`Window close/Q -> quit command -> RuntimeResources.close() -> Python exit -> Electron exit`

## 6. 错误处理

- Python 启动失败：Electron 在原画面区域显示简短错误和日志位置，不伪装为正在运行。
- 摄像头或驱动连接失败：保留 Python 当前错误结果，Electron 显示退出状态。
- 协议消息损坏：忽略单条消息并记录日志，不执行控制命令。
- Python 意外退出：禁用急停按钮并显示进程已退出。
- Electron 意外关闭：主进程先请求正常退出，再在超时后终止子进程。

## 7. 测试与验收

自动测试不得连接真实灵巧手。

- CLI 模式现有测试继续通过。
- 桥接模式在 `sim` 驱动下能输出有效 JPEG 帧。
- `cycle_mode`、`toggle_pause`、`emergency_stop` 和 `quit` 能到达原有控制分支。
- 点击急停或按 `E` 后只调用一次 `driver.stop()`，并保持 STOPPED。
- 关闭 Electron 后 Python、摄像头和仿真驱动全部退出。
- Electron 首屏能显示与 OpenCV 版本相同的 HUD 画面。

第一阶段验收以开发模式跑通为准；第二阶段再生成可双击启动的 Windows 安装包。

## 8. 非回归约束

- 不改变默认配置、模式、摄像头参数和驱动参数。
- 不改变 `draw_hud()` 的像素绘制逻辑。
- 不改变现有 CLI 运行命令。
- 不引入新的控制数值变换。
- SAFE-03 保持撤回状态。
