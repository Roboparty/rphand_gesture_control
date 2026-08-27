// Electron 主进程：管理窗口、Python 控制后端，以及两者之间的 IPC 生命周期。
const {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  screen,
} = require('electron');
const { spawn } = require('node:child_process');
const path = require('node:path');
const readline = require('node:readline');

const {
  commandLine,
  parseBackendLine,
  resolvePythonLaunch,
} = require('./bridge-protocol.cjs');
const {
  BackendLifecycle,
  ShutdownGate,
} = require('./backend-lifecycle.cjs');
const { attachLogForwarder } = require('./log-forwarder.cjs');
const { terminateProcessTree } = require('./process-termination.cjs');
const { computeWindowSize } = require('./renderer/layout.cjs');

let mainWindow = null;
let pythonProcess = null;
let forceKillTimer = null;
let forceQuitTimer = null;
let quitRequested = false;
let detachPythonLogs = null;
const shutdownGate = new ShutdownGate();

function sendProcessState(state) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('rp-hand:process-state', state);
  }
}

function startPython() {
  // A retry must never create a second process that competes for the camera
  // or becomes a second owner of the physical hand driver.
  if (pythonProcess) return false;
  quitRequested = false;
  const lifecycle = new BackendLifecycle();
  sendProcessState(lifecycle.started());

  let child;
  try {
    const projectRoot = path.resolve(__dirname, '..');
    const driver = process.env.RP_HAND_DRIVER === 'sim' ? 'sim' : 'lhandpro';
    const launch = resolvePythonLaunch({
      projectRoot,
      packaged: app.isPackaged,
      resourcesPath: process.resourcesPath,
      driver,
    });
    child = spawn(launch.executable, launch.args, {
      cwd: launch.cwd,
      stdio: ['pipe', 'pipe', 'pipe'],
      windowsHide: true,
    });
  } catch (error) {
    lifecycle.accept({
      type: 'fatal',
      code: 'RUNTIME_ERROR',
      message: error.message,
      retryable: true,
    });
    sendProcessState(lifecycle.exited({ code: null, signal: null }));
    return false;
  }
  pythonProcess = child;
  // stdout 专用于逐行 JSON 帧协议；普通日志必须由 stderr 转发，避免污染协议。
  readline.createInterface({ input: child.stdout }).on('line', (line) => {
    if (pythonProcess !== child) return;
    const message = parseBackendLine(line);
    if (!message) return;
    if (message.type === 'frame') {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('rp-hand:frame', message);
      }
      return;
    }
    const state = lifecycle.accept(message);
    if (state) sendProcessState(state);
  });
  detachPythonLogs = attachLogForwarder(child.stderr, process.stderr);
  child.stdin.on('error', (error) => {
    if (pythonProcess !== child) return;
    process.stderr.write(`Python stdin: ${error.message}\n`);
    if (quitRequested) return;
    const state = lifecycle.accept({
      type: 'fatal',
      code: 'RUNTIME_ERROR',
      message: '与 RP-Hand Gesture 后端的控制通道已断开',
      retryable: true,
    });
    if (state) sendProcessState(state);
  });
  child.on('error', (error) => {
    if (pythonProcess !== child) return;
    const state = lifecycle.accept({
      type: 'fatal',
      code: 'RUNTIME_ERROR',
      message: error.message,
      retryable: true,
    });
    if (state) sendProcessState(state);
  });
  // `close` runs after stdout/stderr have closed, so the final fatal line is
  // parsed before retry becomes available. `exit` alone does not guarantee it.
  child.on('close', (code, signal) => {
    if (pythonProcess !== child) return;
    if (forceKillTimer !== null) clearTimeout(forceKillTimer);
    if (forceQuitTimer !== null) clearTimeout(forceQuitTimer);
    forceKillTimer = null;
    forceQuitTimer = null;
    detachPythonLogs?.();
    detachPythonLogs = null;
    pythonProcess = null;
    const state = lifecycle.exited({
      code,
      signal,
      expected: quitRequested,
    });
    if (state) sendProcessState(state);
    if (quitRequested || shutdownGate.requested) {
      shutdownGate.allowExit();
      app.quit();
    }
  });
  return true;
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
  if (forceKillTimer !== null) return;
  const child = pythonProcess;
  quitRequested = true;
  sendCommand('quit');
  // 先给后端时间释放摄像头、CAN-FD 和模型；超时后才强制结束进程。
  forceKillTimer = setTimeout(() => {
    if (pythonProcess !== child) return;
    terminateProcessTree(child, {}, (error, details) => {
      if (pythonProcess !== child) return;
      if (error) {
        forceKillTimer = null;
        process.stderr.write(`无法安全终止 RP-Hand Gesture 后端: ${error.message}\n`);
        dialog.showErrorBox(
          '无法安全退出 RP-Hand Gesture',
          '后端进程仍可能连接灵巧手。请断开设备后重试退出，或在任务管理器中结束 RP-Hand Gesture 后端。',
        );
        return;
      }
      if (!details.terminationConfirmed) return;

      // taskkill has confirmed the whole process tree is gone. `close` should
      // arrive next; this fallback only handles a broken Node child handle.
      forceQuitTimer = setTimeout(() => {
        if (pythonProcess !== child) return;
        detachPythonLogs?.();
        detachPythonLogs = null;
        pythonProcess = null;
        shutdownGate.allowExit();
        app.quit();
      }, 1000);
    });
  }, 2000);
}

function createWindow() {
  const { width, height } = computeWindowSize(
    screen.getPrimaryDisplay().workAreaSize.width,
    screen.getPrimaryDisplay().workAreaSize.height,
  );
  mainWindow = new BrowserWindow({
    width,
    height,
    minWidth: 640,
    minHeight: 360,
    useContentSize: true,
    center: true,
    backgroundColor: '#000000',
    autoHideMenuBar: true,
    show: false,
    icon: path.resolve(__dirname, '..', 'assets', 'icon.ico'),
    // 渲染页不获得 Node 权限，只能通过 preload 暴露的最小 IPC 接口通信。
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    startPython();
  });
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

ipcMain.on('rp-hand:command', (_event, command) => sendCommand(command));
ipcMain.handle('rp-hand:restart', () => {
  if (pythonProcess) return false;
  return startPython();
});
ipcMain.on('rp-hand:exit-app', () => app.quit());
app.whenReady().then(createWindow);
app.on('before-quit', (event) => {
  // Keep Electron alive until Python releases the camera and CAN-FD driver.
  // The second app.quit(), issued from the child's `close`, is allowed through.
  if (!shutdownGate.shouldDefer(Boolean(pythonProcess))) return;
  event.preventDefault();
  stopPython();
});
app.on('window-all-closed', () => app.quit());
