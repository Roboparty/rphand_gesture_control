# Electron Light Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Electron 添加浅色不透明 HUD、手部识别开关和明确的模式下拉菜单，同时保持现有安全逻辑。

**Architecture:** Python 仍负责摄像头、MediaPipe、映射和安全状态，Electron 只显示帧并发送白名单控制命令。帧协议增加轻量 `state` 元数据，使 GUI 控件与 Python 的真实模式和识别状态同步。

**Tech Stack:** Python 3.12、OpenCV、MediaPipe、Electron 44、原生 HTML/CSS/JavaScript、Node test runner、pytest。

---

### Task 1: 扩展桥接协议

**Files:**
- Modify: `electron_bridge.py`
- Modify: `electron/bridge-protocol.cjs`
- Test: `tests/test_electron_bridge.py`
- Test: `electron/test/bridge-protocol.test.cjs`

- [ ] 先写失败测试，要求协议接受 `toggle_detection`、三个明确模式命令，并在帧中保留状态。
- [ ] 运行对应 Python 与 Node 测试，确认因命令和状态尚不存在而失败。
- [ ] 扩展白名单和帧消息，保持现有四个命令兼容。
- [ ] 重跑测试并确认通过。

### Task 2: 实装 Python 控制状态

**Files:**
- Modify: `main.py`
- Test: `tests/test_main_electron_bridge.py`

- [ ] 写失败测试：关闭识别后不调用识别器且输出安全返回；指定模式命令直接设置目标模式。
- [ ] 运行测试确认失败原因正确。
- [ ] 在主循环中处理识别开关和指定模式，帧提交时附带真实状态。
- [ ] 重跑 Python 测试确认通过。

### Task 3: 构建浅色 Electron 控件

**Files:**
- Modify: `electron/renderer/index.html`
- Modify: `electron/renderer/styles.css`
- Modify: `electron/renderer/app.js`
- Modify: `electron/renderer/layout.cjs`
- Modify: `electron/test/layout.test.cjs`
- Create: `electron/test/controls.test.cjs`

- [ ] 写失败测试，锁定 switch、select、标签、控件区域和 44px 目标尺寸。
- [ ] 运行 Electron 测试确认失败。
- [ ] 加入原生可访问控件、浅色样式和响应式定位。
- [ ] 绑定命令并使用帧状态同步控件。
- [ ] 重跑 Electron 测试确认通过。

### Task 4: Electron 专属不透明 HUD

**Files:**
- Modify: `main.py`
- Test: `tests/test_main_electron_bridge.py`

- [ ] 写失败测试，要求 Electron 帧使用 light HUD 标志而普通窗口不使用。
- [ ] 实现 light HUD 配色参数，并仅在 bridge 模式开启。
- [ ] 重跑 Python 全量测试。

### Task 5: 验证与打包

**Files:**
- Modify: `electron/package.json`
- Modify: `electron/package-lock.json`

- [ ] 运行 `python -m pytest tests -q`。
- [ ] 运行 `npm test`。
- [ ] 启动 Electron 开发版检查布局、焦点和状态同步。
- [ ] 将版本升为 `0.2.0` 并运行 `npm run dist:win`。
- [ ] 核对安装包、内置配置和 SHA256。
