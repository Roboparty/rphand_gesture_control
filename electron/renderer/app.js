const stage = document.getElementById('stage');
const frame = document.getElementById('frame');
const controlPanel = document.getElementById('control-panel');
const detectionToggle = document.getElementById('detection-toggle');
const sendingToggle = document.getElementById('sending-toggle');
const modeSelect = document.getElementById('mode-select');
const recoveryButton = document.getElementById('recover-control');
const stopButton = document.getElementById('emergency-stop');
const processState = document.getElementById('process-state');
const startupScreen = document.getElementById('startup-screen');
const startupLabel = document.getElementById('startup-label');
const startupProgressElement = document.getElementById('startup-progress');
const startupProgressBar = document.getElementById('startup-progress-bar');
let emergencyLatched = false;
let emergencyRequested = false;
let pendingDetection = null;
let pendingSending = null;
let pendingMode = null;
let startupTick = 0;
let startupValue = 8;
let startupFinished = false;
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function renderStartupProgress(value) {
  startupValue = Math.min(Math.max(value, 0), 100);
  startupProgressBar.style.width = `${startupValue}%`;
  startupProgressElement.setAttribute('aria-valuenow', `${Math.round(startupValue)}`);
}

const startupProgress = {
  setAtLeast(value) {
    if (!startupFinished) renderStartupProgress(Math.max(startupValue, value));
  },
  setComplete() {
    if (startupFinished) return;
    startupFinished = true;
    clearInterval(startupTimer);
    renderStartupProgress(100);
    startupScreen.dataset.state = 'ready';
    setTimeout(() => {
      startupScreen.hidden = true;
    }, reduceMotion ? 0 : 260);
  },
  fail(message) {
    clearInterval(startupTimer);
    startupScreen.dataset.state = 'error';
    startupLabel.textContent = message || '启动失败';
  },
};

const startupTimer = setInterval(() => {
  startupProgress.setAtLeast(window.rpHandStartup.nextSoftProgress(startupValue));
  if (!reduceMotion) {
    startupTick += 1;
    startupLabel.textContent = window.rpHandStartup.loadingLabel(startupTick);
  }
}, 360);

function completeStartupOnce() {
  startupProgress.setComplete();
}

function updateLayout() {
  if (!frame.naturalWidth || !frame.naturalHeight) return;
  const layout = window.computeLayout(
    stage.clientWidth,
    stage.clientHeight,
    frame.naturalWidth,
    frame.naturalHeight,
  );
  if (!layout) return;
  Object.assign(controlPanel.style, {
    left: `${layout.controls.left}px`,
    top: `${layout.controls.top}px`,
    width: `${layout.controls.width}px`,
    height: `${layout.controls.height}px`,
    visibility: 'visible',
  });
  Object.assign(stopButton.style, {
    left: `${layout.stop.left}px`,
    top: `${layout.stop.top}px`,
    width: `${layout.stop.width}px`,
    height: `${layout.stop.height}px`,
    visibility: 'visible',
  });
}

function applyRuntimeState(state) {
  if (!state) return;
  const stopped = state.safety_state === 'stopped';
  if (stopped) {
    emergencyRequested = false;
    emergencyLatched = true;
  } else if (!emergencyRequested) {
    emergencyLatched = false;
  }
  stopButton.dataset.latched = emergencyLatched ? 'true' : 'false';
  stopButton.setAttribute('aria-pressed', emergencyLatched ? 'true' : 'false');
  recoveryButton.disabled = !stopped;
  detectionToggle.disabled = stopped;
  sendingToggle.disabled = stopped;
  modeSelect.disabled = stopped;
  if (pendingDetection === state.detection_enabled) {
    pendingDetection = null;
  }
  if (pendingDetection === null) {
    detectionToggle.setAttribute(
      'aria-checked',
      state.detection_enabled ? 'true' : 'false',
    );
  }
  if (stopped) {
    pendingSending = null;
  } else if (pendingSending === state.sending) {
    pendingSending = null;
  }
  if (pendingSending === null) {
    sendingToggle.setAttribute('aria-checked', state.sending ? 'true' : 'false');
  }
  if (pendingMode === state.mode) {
    pendingMode = null;
  }
  if (pendingMode === null && modeSelect.value !== state.mode) {
    modeSelect.value = state.mode;
  }
}

function emergencyStop() {
  if (emergencyLatched) return;
  emergencyRequested = true;
  emergencyLatched = true;
  stopButton.dataset.latched = 'true';
  stopButton.setAttribute('aria-pressed', 'true');
  window.rpHand.sendCommand('emergency_stop');
}

function recoverControl() {
  if (!emergencyLatched || recoveryButton.disabled) return;
  const confirmed = window.confirm(
    '请确认灵巧手周围无障碍物。恢复后将保持识别与发送关闭，并先安全回张。',
  );
  if (confirmed) window.rpHand.sendCommand('recover_control');
}

function toggleSending() {
  if (sendingToggle.disabled) return;
  pendingSending = sendingToggle.getAttribute('aria-checked') !== 'true';
  sendingToggle.setAttribute('aria-checked', pendingSending ? 'true' : 'false');
  window.rpHand.sendCommand('toggle_pause');
}

stopButton.addEventListener('click', emergencyStop);
recoveryButton.addEventListener('click', recoverControl);
sendingToggle.addEventListener('click', toggleSending);
detectionToggle.addEventListener('click', () => {
  pendingDetection = detectionToggle.getAttribute('aria-checked') !== 'true';
  detectionToggle.setAttribute('aria-checked', pendingDetection ? 'true' : 'false');
  window.rpHand.sendCommand('toggle_detection');
});
modeSelect.addEventListener('change', () => {
  pendingMode = modeSelect.value;
  window.rpHand.sendCommand(`mode_${modeSelect.value}`);
});
frame.addEventListener('load', updateLayout);
frame.addEventListener('load', completeStartupOnce);
window.addEventListener('resize', updateLayout);
window.addEventListener('keydown', (event) => {
  if (event.repeat) return;
  const key = event.key.toLowerCase();
  if (key === 'q') window.rpHand.sendCommand('quit');
  if (key === 'e') emergencyStop();
  if (key === 'r') recoverControl();
  if (key === 'q' || key === 'e' || key === 'r') return;
  if (event.target.closest('button, select, input, textarea, a')) return;
  if (event.code === 'Space') {
    event.preventDefault();
    toggleSending();
  }
});

window.rpHand.onFrame(({ jpeg, state }) => {
  frame.src = `data:image/jpeg;base64,${jpeg}`;
  startupProgress.setAtLeast(96);
  applyRuntimeState(state);
  processState.hidden = true;
});

window.rpHand.onProcessState((state) => {
  if (state.running) {
    startupProgress.setAtLeast(24);
    return;
  }
  stopButton.disabled = true;
  recoveryButton.disabled = true;
  detectionToggle.disabled = true;
  sendingToggle.disabled = true;
  modeSelect.disabled = true;
  processState.textContent = state.error
    || `RP-Hand process exited (${state.code ?? 'unknown'})`;
  processState.hidden = false;
  if (!startupFinished) startupProgress.fail(processState.textContent);
});
