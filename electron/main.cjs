const { app, BrowserWindow, ipcMain, screen } = require('electron');
const { spawn } = require('node:child_process');
const path = require('node:path');
const readline = require('node:readline');

const {
  commandLine,
  parseFrameLine,
  resolvePythonLaunch,
} = require('./bridge-protocol.cjs');
const { attachLogForwarder } = require('./log-forwarder.cjs');
const { computeWindowSize } = require('./renderer/layout.cjs');

let mainWindow = null;
let pythonProcess = null;
let forceKillTimer = null;
let quitRequested = false;
let detachPythonLogs = null;

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
  detachPythonLogs = attachLogForwarder(pythonProcess.stderr, process.stderr);
  pythonProcess.on('error', (error) => {
    sendProcessState({ running: false, error: error.message });
  });
  pythonProcess.on('exit', (code) => {
    detachPythonLogs?.();
    detachPythonLogs = null;
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
app.whenReady().then(createWindow);
app.on('before-quit', stopPython);
app.on('window-all-closed', () => app.quit());
