# RP-Hand Electron GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在完全保留现有 OpenCV 画面、HUD、控制分支和真手响应速度的前提下，为 Windows 增加一个 Electron 外壳，并且只新增一个可锁定的急停按钮。

**Architecture:** Python 继续独占摄像头、MediaPipe、映射、安全状态机和 CAN-FD 驱动；Electron 只显示 Python 已绘制好的 JPEG 帧并发送四个白名单命令。帧编码和标准输出写入位于有界后台线程中，主控制循环只提交最新帧，不等待 GUI，避免再次引入速度限制或跟手延迟。

**Tech Stack:** Python 3.12、OpenCV、pytest、Electron 44.0.0、Node.js 24、Node 内置测试框架、electron-builder 26.15.3、PyInstaller。

---

## 文件结构

- `electron_bridge.py`：逐行 JSON 命令解析、后台帧压缩、Base64 JPEG 发布；不包含控制业务。
- `tests/test_electron_bridge.py`：桥接协议、帧格式、刷新限频和关闭行为的单元测试。
- `main.py`：新增 `--electron-bridge` 参数，把桥接输入映射到现有 `q/m/Space/e` 分支；CLI 路径原样保留。
- `tests/test_main_electron_bridge.py`：验证桥接模式不打开 OpenCV 窗口，并验证急停只触发现有安全分支。
- `electron/bridge-protocol.cjs`：Electron 侧的帧消息校验和命令序列化，保持主进程文件单一职责。
- `electron/test/bridge-protocol.test.cjs`：Node 协议单元测试。
- `electron/main.cjs`：BrowserWindow、Python 子进程、进程退出和 IPC 生命周期。
- `electron/preload.cjs`：向 renderer 暴露最小白名单 API。
- `electron/renderer/index.html`：一个画面容器、一个急停按钮、一个隐藏式错误状态。
- `electron/renderer/styles.css`：黑色等比画面背景和 HUD 内急停覆盖样式。
- `electron/renderer/app.js`：帧更新、急停点击、旧快捷键转发和覆盖按钮定位。
- `electron/renderer/layout.cjs`：纯函数计算 `contain` 图像及急停按钮坐标，供 renderer 和测试复用。
- `electron/test/layout.test.cjs`：不同窗口比例下不裁切、不拉伸、急停仍位于右侧 HUD 的测试。
- `electron/package.json`：开发、测试、Python 打包和 Windows 安装包脚本。
- `electron/build-python.ps1`：调用项目虚拟环境和现有 `RP-Hand.spec` 生成 Python 分发目录。
- `RP-Hand.spec`：只在需要时补充桥接模块收集，保留现有 DLL、配置和图标。
- `.gitignore`：忽略 Electron 安装依赖和构建产物。

### Task 1: 固定 SAFE-03 撤回后的基线

**Files:**
- Verify: `main.py`
- Verify: `control_safety.py`
- Verify: `tests/test_main_safety_integration.py`
- Verify: `tests/test_runtime_lifecycle.py`

- [ ] **Step 1: 确认运行路径没有 SAFE-03 限制器**

Run:

```powershell
rg -n "CommandLimiter|FeedbackMonitor|speed_limit|acceleration_limit|deadband" main.py control_safety.py drivers tests
```

Expected: 命令无匹配并返回退出码 1；`main.py` 仍直接调用 `driver.set_joint_positions(decision.target)`。

- [ ] **Step 2: 运行 Python 基线测试**

Run:

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: `12 passed`，没有真实 CAN-FD 连接。

- [ ] **Step 3: 运行无真手烟雾测试**

Run:

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe smoke_test.py
```

Expected: 仿真驱动完成约 140 帧，正常释放摄像头、识别器和驱动。

- [ ] **Step 4: 记录基线状态**

Run:

```powershell
git diff --stat
git diff -- main.py control_safety.py
```

Expected: 差异只对应已经确认的 SAFE-03 完整撤回；不把这些文件重置到 `f76144d`。

### Task 2: 用测试定义 Python 桥接协议

**Files:**
- Create: `tests/test_electron_bridge.py`
- Create: `electron_bridge.py`

- [ ] **Step 1: 写命令白名单的失败测试**

Create `tests/test_electron_bridge.py` with:

```python
from __future__ import annotations

import base64
import io
import json

import cv2
import numpy as np

from electron_bridge import ElectronBridge, parse_command_line


def test_parse_command_line_maps_only_existing_keyboard_actions():
    assert parse_command_line('{"type":"command","command":"quit"}') == ord("q")
    assert parse_command_line('{"type":"command","command":"cycle_mode"}') == ord("m")
    assert parse_command_line('{"type":"command","command":"toggle_pause"}') == ord(" ")
    assert parse_command_line('{"type":"command","command":"emergency_stop"}') == ord("e")
    assert parse_command_line('{"type":"command","command":"shell"}') is None
    assert parse_command_line('not-json') is None


def test_bridge_publishes_a_valid_jpeg_message():
    output = io.StringIO()
    bridge = ElectronBridge(
        input_stream=io.StringIO(""),
        output_stream=output,
        max_fps=15.0,
        jpeg_quality=75,
    )
    frame = np.full((16, 24, 3), 127, dtype=np.uint8)

    assert bridge.submit_frame(frame, now=1.0) is True
    bridge.close()

    message = json.loads(output.getvalue().strip())
    assert message["type"] == "frame"
    assert message["sequence"] == 1
    encoded = np.frombuffer(base64.b64decode(message["jpeg"]), dtype=np.uint8)
    decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    assert decoded.shape == frame.shape


def test_bridge_limits_only_ui_frames_not_control_calls():
    output = io.StringIO()
    bridge = ElectronBridge(io.StringIO(""), output, max_fps=10.0)
    frame = np.zeros((8, 8, 3), dtype=np.uint8)

    assert bridge.submit_frame(frame, now=1.00) is True
    assert bridge.submit_frame(frame, now=1.05) is False
    assert bridge.submit_frame(frame, now=1.10) is True
    bridge.close()

    messages = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [message["sequence"] for message in messages] == [1, 2]
```

- [ ] **Step 2: 运行测试并确认因模块缺失而失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_electron_bridge.py -q
```

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'electron_bridge'`。

- [ ] **Step 3: 实现最小的非阻塞桥接模块**

Create `electron_bridge.py` with:

```python
"""Electron bridge protocol without robot-control responsibilities."""

from __future__ import annotations

import base64
import json
import queue
import threading
import time
from typing import IO, Optional

import cv2
import numpy as np


COMMAND_KEYS = {
    "quit": ord("q"),
    "cycle_mode": ord("m"),
    "toggle_pause": ord(" "),
    "emergency_stop": ord("e"),
}


def parse_command_line(line: str) -> Optional[int]:
    try:
        payload = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("type") != "command":
        return None
    return COMMAND_KEYS.get(payload.get("command"))


class ElectronBridge:
    def __init__(
        self,
        input_stream: IO[str],
        output_stream: IO[str],
        max_fps: float = 15.0,
        jpeg_quality: int = 75,
    ) -> None:
        self._input_stream = input_stream
        self._output_stream = output_stream
        self._frame_interval = 1.0 / max(float(max_fps), 1.0)
        self._jpeg_quality = int(jpeg_quality)
        self._commands: queue.Queue[int] = queue.Queue()
        self._frames: queue.Queue[np.ndarray] = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._last_submitted_at = float("-inf")
        self._sequence = 0
        self._command_thread = threading.Thread(
            target=self._read_commands,
            name="electron-command-reader",
            daemon=True,
        )
        self._frame_thread = threading.Thread(
            target=self._publish_frames,
            name="electron-frame-publisher",
            daemon=True,
        )
        self._command_thread.start()
        self._frame_thread.start()

    def poll_key(self) -> int:
        try:
            return self._commands.get_nowait()
        except queue.Empty:
            return 0

    def submit_frame(self, frame: np.ndarray, *, now: float | None = None) -> bool:
        submitted_at = time.monotonic() if now is None else float(now)
        if submitted_at - self._last_submitted_at < self._frame_interval:
            return False
        self._last_submitted_at = submitted_at
        latest = frame.copy()
        try:
            self._frames.put_nowait(latest)
        except queue.Full:
            try:
                self._frames.get_nowait()
            except queue.Empty:
                pass
            self._frames.put_nowait(latest)
        return True

    def close(self) -> None:
        self._stop.set()
        self._frame_thread.join(timeout=2.0)

    def _read_commands(self) -> None:
        for line in self._input_stream:
            if self._stop.is_set():
                break
            key = parse_command_line(line)
            if key is not None:
                self._commands.put(key)

    def _publish_frames(self) -> None:
        while not self._stop.is_set() or not self._frames.empty():
            try:
                frame = self._frames.get(timeout=0.05)
            except queue.Empty:
                continue
            ok, encoded = cv2.imencode(
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality],
            )
            if not ok:
                continue
            self._sequence += 1
            message = {
                "type": "frame",
                "sequence": self._sequence,
                "jpeg": base64.b64encode(encoded).decode("ascii"),
            }
            try:
                self._output_stream.write(json.dumps(message, separators=(",", ":")) + "\n")
                self._output_stream.flush()
            except (BrokenPipeError, OSError, ValueError):
                self._stop.set()
                return
```

- [ ] **Step 4: 运行桥接测试并确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_electron_bridge.py -q
```

Expected: `3 passed`。

- [ ] **Step 5: 运行全量 Python 测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: 原 12 项和新增 3 项全部通过。

### Task 3: 将桥接模式接入现有控制循环

**Files:**
- Create: `tests/test_main_electron_bridge.py`
- Modify: `main.py:15-30`
- Modify: `main.py:127-152`
- Modify: `main.py:309-335`

- [ ] **Step 1: 写桥接模式不打开 OpenCV 窗口的失败测试**

Create `tests/test_main_electron_bridge.py` with a deterministic two-frame fixture:

```python
from __future__ import annotations

from copy import deepcopy

import numpy as np

import main as app


class Observation:
    detected = True
    curls = {"thumb": 0.5, "index": 0.5}
    thumb_spread = 0.0
    gesture = "unknown"


class Recognizer:
    def process(self, _frame):
        return Observation()

    def draw_landmarks(self, _frame, _observation):
        return None

    def close(self):
        return None


class Mapper:
    joint_names = ["joint_1"]
    num_joints = 1

    def map_mirror(self, _values):
        return [5000.0]


class Camera:
    def set(self, _prop, _value):
        return None

    def isOpened(self):
        return True

    def read(self):
        return True, np.zeros((16, 24, 3), dtype=np.uint8)

    def release(self):
        return None


class Driver:
    def __init__(self):
        self.stop_calls = 0
        self.stopped = False
        self.connected = False

    def connect(self):
        self.connected = True
        return True

    def disconnect(self):
        self.connected = False

    def stop(self):
        if self.stopped:
            return
        self.stopped = True
        self.stop_calls += 1

    def set_joint_positions(self, _positions, speed=None):
        return True

    def get_state(self):
        return {"joint_1": 5000.0}

    @property
    def is_connected(self):
        return self.connected


class FakeBridge:
    def __init__(self):
        self.keys = iter([ord("e"), ord("q")])
        self.frames = 0
        self.closed = False

    def submit_frame(self, _frame, *, now=None):
        self.frames += 1
        return True

    def poll_key(self):
        return next(self.keys)

    def close(self):
        self.closed = True


def test_electron_bridge_reuses_the_existing_emergency_stop_branch(monkeypatch):
    config = deepcopy(app.load_config("config.yaml"))
    config["camera"]["mirror"] = False
    config["control"]["mode"] = "mirror"
    config["control"]["send_rate_hz"] = 1000
    config["hand"]["joints"] = [
        {"name": "joint_1", "src": "index", "range": [0, 10000]}
    ]
    driver = Driver()
    bridge = FakeBridge()

    monkeypatch.setattr(app, "load_config", lambda _path: config)
    monkeypatch.setattr(app, "GestureRecognizer", lambda **_kwargs: Recognizer())
    monkeypatch.setattr(app, "GestureMapper", lambda *_args, **_kwargs: Mapper())
    monkeypatch.setattr(app, "make_driver", lambda _cfg, _names: driver)
    monkeypatch.setattr(app.cv2, "VideoCapture", lambda *_args: Camera())
    monkeypatch.setattr(app.cv2, "imshow", lambda *_args: (_ for _ in ()).throw(AssertionError("imshow called")))
    monkeypatch.setattr(app.cv2, "waitKey", lambda *_args: (_ for _ in ()).throw(AssertionError("waitKey called")))
    monkeypatch.setattr(app.cv2, "destroyAllWindows", lambda: None)
    monkeypatch.setattr(app, "draw_hud", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "ElectronBridge", lambda *_args, **_kwargs: bridge)
    monkeypatch.setattr(app.os, "system", lambda _command: 0)

    result = app.main(["--driver", "sim", "--electron-bridge"])

    assert result == 0
    assert bridge.frames == 2
    assert bridge.closed is True
    assert driver.stop_calls == 1
```

- [ ] **Step 2: 运行新测试并确认参数尚不存在**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_main_electron_bridge.py -q
```

Expected: FAIL with argparse error `unrecognized arguments: --electron-bridge`。

- [ ] **Step 3: 在 `main.py` 中添加桥接入口且保留 CLI 分支**

Add imports:

```python
from contextlib import nullcontext, redirect_stdout

from electron_bridge import ElectronBridge
```

Add the hidden argument and bridge lifecycle:

```python
ap.add_argument("--electron-bridge", action="store_true", help=argparse.SUPPRESS)
args = ap.parse_args(argv)

protocol_stdout = sys.stdout
bridge = ElectronBridge(sys.stdin, protocol_stdout) if args.electron_bridge else None
log_context = redirect_stdout(sys.stderr) if bridge is not None else nullcontext()
try:
    with log_context:
        with RuntimeResources(destroy_windows=cv2.destroyAllWindows) as resources:
            return _run(cfg, args, resources, bridge=bridge)
finally:
    if bridge is not None:
        bridge.close()
```

Change the function signature and display branch only:

```python
def _run(cfg: dict, args, resources: RuntimeResources, bridge=None) -> int:
```

```python
draw_hud(
    frame,
    obs,
    hud_positions,
    mapper.joint_names,
    mode,
    sending,
    driver.is_connected,
    pos_max,
    banner=safety_banner or (rps_round_msg if mode == "rps" else ""),
)
if bridge is None:
    cv2.imshow("RP-Hand", frame)
    key = cv2.waitKey(1) & 0xFF
else:
    bridge.submit_frame(frame, now=now)
    key = bridge.poll_key()
```

Do not edit the existing `q/m/Space/e` condition chain below this block.

- [ ] **Step 4: 运行桥接集成测试并确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_main_electron_bridge.py -q
```

Expected: `1 passed`，`imshow` 和 `waitKey` 均未调用，`driver.stop()` 恰好调用一次。

- [ ] **Step 5: 运行全量 Python 回归测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q main.py electron_bridge.py
```

Expected: 全部测试通过，compileall 退出码为 0。

### Task 4: 用测试定义 Electron 消息和画面坐标

**Files:**
- Create: `electron/package.json`
- Create: `electron/bridge-protocol.cjs`
- Create: `electron/renderer/layout.cjs`
- Create: `electron/test/bridge-protocol.test.cjs`
- Create: `electron/test/layout.test.cjs`

- [ ] **Step 1: 创建 Electron 测试脚本和失败测试**

Create `electron/package.json`:

```json
{
  "name": "rp-hand-electron",
  "version": "0.1.0",
  "private": true,
  "main": "main.cjs",
  "scripts": {
    "start": "electron .",
    "test": "node --test test/*.test.cjs",
    "build:python": "powershell -ExecutionPolicy Bypass -File build-python.ps1",
    "dist:win": "npm run test && npm run build:python && electron-builder --win nsis"
  },
  "devDependencies": {
    "electron": "44.0.0",
    "electron-builder": "26.15.3"
  }
}
```

Create `electron/test/bridge-protocol.test.cjs`:

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');
const { commandLine, parseFrameLine } = require('../bridge-protocol.cjs');

test('serializes only the four existing controls', () => {
  assert.equal(commandLine('quit'), '{"type":"command","command":"quit"}\n');
  assert.equal(commandLine('emergency_stop'), '{"type":"command","command":"emergency_stop"}\n');
  assert.throws(() => commandLine('shell'), /Unsupported command/);
});

test('accepts a valid frame and rejects unrelated or malformed lines', () => {
  assert.deepEqual(
    parseFrameLine('{"type":"frame","sequence":7,"jpeg":"YWJj"}'),
    { type: 'frame', sequence: 7, jpeg: 'YWJj' },
  );
  assert.equal(parseFrameLine('{"type":"status"}'), null);
  assert.equal(parseFrameLine('not-json'), null);
});
```

Create `electron/test/layout.test.cjs`:

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');
const { computeLayout } = require('../renderer/layout.cjs');

test('fits a wide Python frame without cropping and keeps stop inside HUD', () => {
  const layout = computeLayout(1920, 1080, 1280, 720);
  assert.deepEqual(layout.frame, { left: 0, top: 0, width: 1920, height: 1080 });
  assert.equal(layout.stop.left >= layout.frame.left, true);
  assert.equal(layout.stop.left + layout.stop.width <= layout.frame.left + layout.frame.width, true);
});

test('letterboxes the frame in a tall window', () => {
  const layout = computeLayout(900, 1200, 1280, 720);
  assert.equal(layout.frame.width, 900);
  assert.equal(layout.frame.height, 506.25);
  assert.equal(layout.frame.top, 346.875);
  assert.equal(layout.stop.top + layout.stop.height <= layout.frame.top + layout.frame.height, true);
});
```

- [ ] **Step 2: 安装依赖并确认测试因模块缺失而失败**

Run:

```powershell
Set-Location electron
npm install
npm test
```

Expected: npm 安装 Electron 44.0.0 和 electron-builder 26.15.3；测试 FAIL with missing `bridge-protocol.cjs` and `renderer/layout.cjs`。

- [ ] **Step 3: 实现纯协议和布局函数**

Create `electron/bridge-protocol.cjs`:

```javascript
const ALLOWED_COMMANDS = new Set([
  'quit',
  'cycle_mode',
  'toggle_pause',
  'emergency_stop',
]);

function commandLine(command) {
  if (!ALLOWED_COMMANDS.has(command)) {
    throw new Error(`Unsupported command: ${command}`);
  }
  return `${JSON.stringify({ type: 'command', command })}\n`;
}

function parseFrameLine(line) {
  try {
    const payload = JSON.parse(line);
    if (
      payload?.type !== 'frame'
      || !Number.isInteger(payload.sequence)
      || typeof payload.jpeg !== 'string'
    ) {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

module.exports = { commandLine, parseFrameLine };
```

Create `electron/renderer/layout.cjs`:

```javascript
function computeLayout(stageWidth, stageHeight, imageWidth, imageHeight) {
  if (stageWidth <= 0 || stageHeight <= 0 || imageWidth <= 0 || imageHeight <= 0) {
    return null;
  }
  const scale = Math.min(stageWidth / imageWidth, stageHeight / imageHeight);
  const width = imageWidth * scale;
  const height = imageHeight * scale;
  const left = (stageWidth - width) / 2;
  const top = (stageHeight - height) / 2;
  const panelWidth = Math.min(320 * scale, width);
  const inset = 16 * scale;
  const stopHeight = Math.max(44, 52 * scale);
  return {
    frame: { left, top, width, height },
    stop: {
      left: left + width - panelWidth + inset,
      top: top + height - stopHeight - inset,
      width: Math.max(120, panelWidth - inset * 2),
      height: stopHeight,
    },
  };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { computeLayout };
}

if (typeof window !== 'undefined') {
  window.computeLayout = computeLayout;
}
```

- [ ] **Step 4: 运行 Node 测试并确认通过**

Run:

```powershell
Set-Location electron
npm test
```

Expected: `4 tests passed`，退出码 0。

### Task 5: 实现 Electron 主进程和最小安全 IPC

**Files:**
- Create: `electron/main.cjs`
- Create: `electron/preload.cjs`

- [ ] **Step 1: 扩展协议测试以固定 Python 启动参数**

Append to `electron/test/bridge-protocol.test.cjs`:

```javascript
const path = require('node:path');
const { resolvePythonLaunch } = require('../bridge-protocol.cjs');

test('uses the project venv in development and the bundled executable when packaged', () => {
  const projectRoot = path.resolve('C:/repo');
  assert.deepEqual(resolvePythonLaunch({ projectRoot, packaged: false }), {
    executable: path.join(projectRoot, '.venv', 'Scripts', 'python.exe'),
    args: [path.join(projectRoot, 'main.py'), '--electron-bridge'],
    cwd: projectRoot,
  });
  assert.deepEqual(resolvePythonLaunch({
    projectRoot,
    packaged: true,
    resourcesPath: path.resolve('C:/app/resources'),
  }), {
    executable: path.resolve('C:/app/resources/RP-Hand/RP-Hand.exe'),
    args: ['--electron-bridge'],
    cwd: path.resolve('C:/app/resources/RP-Hand'),
  });
});
```

- [ ] **Step 2: 运行测试并确认 `resolvePythonLaunch` 缺失**

Run:

```powershell
Set-Location electron
npm test
```

Expected: FAIL with `resolvePythonLaunch is not a function`。

- [ ] **Step 3: 实现启动路径解析并导出**

Append to `electron/bridge-protocol.cjs` before `module.exports`:

```javascript
const path = require('node:path');

function resolvePythonLaunch({ projectRoot, packaged, resourcesPath }) {
  if (packaged) {
    const cwd = path.join(resourcesPath, 'RP-Hand');
    return {
      executable: path.join(cwd, 'RP-Hand.exe'),
      args: ['--electron-bridge'],
      cwd,
    };
  }
  return {
    executable: path.join(projectRoot, '.venv', 'Scripts', 'python.exe'),
    args: [path.join(projectRoot, 'main.py'), '--electron-bridge'],
    cwd: projectRoot,
  };
}
```

Change export to:

```javascript
module.exports = { commandLine, parseFrameLine, resolvePythonLaunch };
```

- [ ] **Step 4: 创建隔离 preload**

Create `electron/preload.cjs`:

```javascript
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('rpHand', {
  sendCommand: (command) => ipcRenderer.send('rp-hand:command', command),
  onFrame: (listener) => {
    const wrapped = (_event, frame) => listener(frame);
    ipcRenderer.on('rp-hand:frame', wrapped);
    return () => ipcRenderer.removeListener('rp-hand:frame', wrapped);
  },
  onProcessState: (listener) => {
    const wrapped = (_event, state) => listener(state);
    ipcRenderer.on('rp-hand:process-state', wrapped);
    return () => ipcRenderer.removeListener('rp-hand:process-state', wrapped);
  },
});
```

- [ ] **Step 5: 创建 Electron 主进程**

Create `electron/main.cjs`:

```javascript
const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('node:child_process');
const path = require('node:path');
const readline = require('node:readline');
const {
  commandLine,
  parseFrameLine,
  resolvePythonLaunch,
} = require('./bridge-protocol.cjs');

let mainWindow = null;
let pythonProcess = null;
let forceKillTimer = null;
let quitRequested = false;

function sendProcessState(state) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('rp-hand:process-state', state);
  }
}

function startPython() {
  const projectRoot = path.resolve(__dirname, '..');
  const launch = resolvePythonLaunch({
    projectRoot,
    packaged: app.isPackaged,
    resourcesPath: process.resourcesPath,
  });
  pythonProcess = spawn(launch.executable, launch.args, {
    cwd: launch.cwd,
    stdio: ['pipe', 'pipe', 'pipe'],
    windowsHide: true,
  });
  readline.createInterface({ input: pythonProcess.stdout }).on('line', (line) => {
    const frame = parseFrameLine(line);
    if (frame && mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('rp-hand:frame', frame);
    }
  });
  pythonProcess.stderr.setEncoding('utf8');
  pythonProcess.stderr.on('data', (chunk) => process.stderr.write(chunk));
  pythonProcess.on('error', (error) => sendProcessState({ running: false, error: error.message }));
  pythonProcess.on('exit', (code) => {
    pythonProcess = null;
    sendProcessState({ running: false, code });
    if (quitRequested) app.quit();
  });
  sendProcessState({ running: true });
}

function sendCommand(command) {
  if (!pythonProcess?.stdin?.writable) return;
  try {
    if (command === 'quit') quitRequested = true;
    pythonProcess.stdin.write(commandLine(command));
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
  }
}

function stopPython() {
  if (!pythonProcess) return;
  const child = pythonProcess;
  quitRequested = true;
  sendCommand('quit');
  forceKillTimer = setTimeout(() => {
    if (pythonProcess === child) child.kill();
  }, 2000);
  child.once('exit', () => {
    clearTimeout(forceKillTimer);
    forceKillTimer = null;
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 720,
    minWidth: 960,
    minHeight: 540,
    backgroundColor: '#000000',
    autoHideMenuBar: true,
    icon: path.resolve(__dirname, '..', 'assets', 'icon.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  mainWindow.once('ready-to-show', startPython);
  mainWindow.on('closed', () => { mainWindow = null; });
}

ipcMain.on('rp-hand:command', (_event, command) => sendCommand(command));
app.whenReady().then(createWindow);
app.on('before-quit', stopPython);
app.on('window-all-closed', () => app.quit());
```

- [ ] **Step 6: 运行协议测试和 Electron 语法检查**

Run:

```powershell
Set-Location electron
npm test
node --check main.cjs
node --check preload.cjs
```

Expected: Node 测试全部通过，两个语法检查退出码均为 0。

### Task 6: 实现与旧 HUD 完全一致的 renderer 和急停覆盖

**Files:**
- Create: `electron/renderer/index.html`
- Create: `electron/renderer/styles.css`
- Create: `electron/renderer/app.js`

- [ ] **Step 1: 创建只包含原画面和急停的页面**

Create `electron/renderer/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>RP-Hand</title>
    <link rel="stylesheet" href="styles.css">
  </head>
  <body>
    <main id="stage" aria-label="RP-Hand camera control view">
      <img id="frame" alt="Live hand tracking and RP-Hand status">
      <button id="emergency-stop" type="button">EMERGENCY STOP</button>
      <p id="process-state" role="status" aria-live="polite" hidden></p>
    </main>
    <script src="layout.cjs"></script>
    <script src="app.js"></script>
  </body>
</html>
```

- [ ] **Step 2: 创建无额外装饰的旧窗口样式**

Create `electron/renderer/styles.css`:

```css
:root {
  color-scheme: dark;
  font-family: Arial, Helvetica, sans-serif;
  background: #000;
}

* { box-sizing: border-box; }

html,
body,
#stage {
  width: 100%;
  height: 100%;
  margin: 0;
  overflow: hidden;
  background: #000;
}

#stage { position: relative; }

#frame {
  position: absolute;
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
  user-select: none;
}

#emergency-stop {
  position: absolute;
  z-index: 2;
  min-width: 120px;
  min-height: 44px;
  border: 2px solid #f04444;
  border-radius: 4px;
  background: rgba(28, 28, 28, 0.94);
  color: #fff;
  font: 700 14px/1 Arial, Helvetica, sans-serif;
  letter-spacing: 0;
  cursor: pointer;
}

#emergency-stop:hover,
#emergency-stop:focus-visible {
  background: #b51f2a;
  outline: 2px solid #fff;
  outline-offset: 2px;
}

#emergency-stop[data-latched="true"] {
  background: #b51f2a;
  cursor: not-allowed;
}

#process-state {
  position: absolute;
  inset: 50% auto auto 50%;
  transform: translate(-50%, -50%);
  color: #fff;
  background: rgba(0, 0, 0, 0.76);
  padding: 12px 16px;
}
```

- [ ] **Step 3: 创建帧、快捷键和锁定急停逻辑**

Create `electron/renderer/app.js`:

```javascript
const stage = document.getElementById('stage');
const frame = document.getElementById('frame');
const stopButton = document.getElementById('emergency-stop');
const processState = document.getElementById('process-state');
let emergencyLatched = false;

function updateLayout() {
  if (!frame.naturalWidth || !frame.naturalHeight) return;
  const layout = window.computeLayout(
    stage.clientWidth,
    stage.clientHeight,
    frame.naturalWidth,
    frame.naturalHeight,
  );
  if (!layout) return;
  Object.assign(stopButton.style, {
    left: `${layout.stop.left}px`,
    top: `${layout.stop.top}px`,
    width: `${layout.stop.width}px`,
    height: `${layout.stop.height}px`,
  });
}

function emergencyStop() {
  if (emergencyLatched) return;
  emergencyLatched = true;
  stopButton.dataset.latched = 'true';
  stopButton.setAttribute('aria-pressed', 'true');
  window.rpHand.sendCommand('emergency_stop');
}

stopButton.addEventListener('click', emergencyStop);
frame.addEventListener('load', updateLayout);
window.addEventListener('resize', updateLayout);
window.addEventListener('keydown', (event) => {
  if (event.repeat) return;
  const key = event.key.toLowerCase();
  if (key === 'q') window.rpHand.sendCommand('quit');
  if (key === 'm') window.rpHand.sendCommand('cycle_mode');
  if (key === 'e') emergencyStop();
  if (event.code === 'Space') {
    event.preventDefault();
    window.rpHand.sendCommand('toggle_pause');
  }
});

window.rpHand.onFrame(({ jpeg }) => {
  frame.src = `data:image/jpeg;base64,${jpeg}`;
  processState.hidden = true;
});

window.rpHand.onProcessState((state) => {
  if (state.running) return;
  stopButton.disabled = true;
  processState.textContent = state.error || `RP-Hand process exited (${state.code ?? 'unknown'})`;
  processState.hidden = false;
});
```

- [ ] **Step 4: 运行 Node 测试和 renderer 语法检查**

Run:

```powershell
Set-Location electron
npm test
node --check renderer/app.js
node --check renderer/layout.cjs
```

Expected: 全部测试通过，语法检查退出码 0。

### Task 7: 启动开发版并做非真手验收

**Files:**
- Verify: `electron/main.cjs`
- Verify: `main.py`

- [ ] **Step 1: 先运行完整自动化验证**

Run:

```powershell
Set-Location C:\gesture_hand_control_world_coords_portable_20260825
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m pytest -q
Set-Location electron
npm test
```

Expected: Python 与 Node 测试均为 0 failures。

- [ ] **Step 2: 在仿真驱动下启动 Electron**

Run:

```powershell
Set-Location C:\gesture_hand_control_world_coords_portable_20260825\electron
$env:RP_HAND_DRIVER='sim'
npm start
```

Expected: 出现单个 Electron 窗口；画面、骨架和右侧 HUD 与原 OpenCV 窗口一致；没有额外设置栏或功能按钮。

- [ ] **Step 3: 手动验证旧快捷键与新增急停**

Check:

```text
M      HUD Mode 在 mirror / gesture / rps 间循环
Space  HUD 在 SENDING / PAUSED 间切换
E      HUD 显示 EMERGENCY STOP，发送保持锁定
急停按钮  与 E 完全相同，点击第二次不会恢复
Q      Python 正常释放后 Electron 退出
```

Expected: 每项行为均走 `main.py` 原有分支；任务管理器中没有残留 Python 子进程。

- [ ] **Step 4: 对照检查没有引入控制限速**

Run:

```powershell
Set-Location C:\gesture_hand_control_world_coords_portable_20260825
rg -n "CommandLimiter|FeedbackMonitor|speed_limit|acceleration_limit|deadband" main.py electron_bridge.py electron
```

Expected: 无匹配；Electron 帧刷新是 15 FPS，但 `send_rate_hz` 和 `driver.set_joint_positions()` 路径没有变化。

### Task 8: 生成可双击运行的 Windows 安装包

**Files:**
- Create: `electron/build-python.ps1`
- Modify: `electron/package.json`
- Modify: `.gitignore`
- Verify: `RP-Hand.spec`

- [ ] **Step 1: 创建 Python 打包脚本**

Create `electron/build-python.ps1`:

```powershell
$ErrorActionPreference = 'Stop'
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Python virtual environment not found: $python"
}
Push-Location $projectRoot
try {
    & $python -m PyInstaller --noconfirm --clean RP-Hand.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}
```

- [ ] **Step 2: 为 electron-builder 添加 Windows 配置**

Add to `electron/package.json` after `devDependencies`:

```json
"build": {
  "appId": "com.roboparty.rphand",
  "productName": "RP-Hand",
  "directories": {
    "output": "dist"
  },
  "files": [
    "main.cjs",
    "preload.cjs",
    "bridge-protocol.cjs",
    "renderer/**/*"
  ],
  "extraResources": [
    {
      "from": "../dist/RP-Hand",
      "to": "RP-Hand"
    }
  ],
  "win": {
    "target": "nsis",
    "icon": "../assets/icon.ico"
  },
  "nsis": {
    "oneClick": false,
    "allowToChangeInstallationDirectory": true
  }
}
```

- [ ] **Step 3: 忽略依赖和构建产物**

Append to `.gitignore`:

```gitignore
electron/node_modules/
electron/dist/
dist/
build/
```

- [ ] **Step 4: 构建 Python 分发目录**

Run:

```powershell
Set-Location C:\gesture_hand_control_world_coords_portable_20260825\electron
npm run build:python
Test-Path ..\dist\RP-Hand\RP-Hand.exe
```

Expected: PyInstaller 退出码 0，`Test-Path` 输出 `True`。

- [ ] **Step 5: 构建 Windows 安装包**

Run:

```powershell
Set-Location C:\gesture_hand_control_world_coords_portable_20260825\electron
npm run dist:win
Get-ChildItem -LiteralPath .\dist -Filter '*.exe'
```

Expected: `electron/dist` 中出现 NSIS 安装程序。

- [ ] **Step 6: 安装后做最终验收**

Check:

```text
双击 RP-Hand 可以启动，不需要先打开终端
画面按原比例显示且 HUD 未重画
急停按钮可点击并锁定
Q 或关闭窗口后没有残留 RP-Hand.exe / Python 进程
程序目录包含 config.yaml 和 vendor/HCanbus.dll
```

Expected: 全部满足；真手连接测试必须由用户明确接好 CAN-FD 后再执行。

## 最终验证

- [ ] Run Python tests:

```powershell
Set-Location C:\gesture_hand_control_world_coords_portable_20260825
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m pytest -q
```

- [ ] Run Electron tests:

```powershell
Set-Location C:\gesture_hand_control_world_coords_portable_20260825\electron
npm test
```

- [ ] Run syntax/build checks:

```powershell
Set-Location C:\gesture_hand_control_world_coords_portable_20260825
.\.venv\Scripts\python.exe -m compileall -q main.py electron_bridge.py
Set-Location electron
node --check main.cjs
node --check preload.cjs
node --check renderer/app.js
```

- [ ] Confirm safety invariants:

```powershell
Set-Location C:\gesture_hand_control_world_coords_portable_20260825
rg -n "CommandLimiter|FeedbackMonitor|speed_limit|acceleration_limit|deadband" main.py electron_bridge.py electron
git diff --check
git status --short
```

Expected: 限速相关标识无匹配，`git diff --check` 无空白错误；状态中只包含本次 Electron GUI 与已确认的 SAFE-03 撤回改动。
