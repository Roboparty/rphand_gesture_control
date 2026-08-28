// Electron 渲染层控制器：把 Python 运行状态投影到 HUD，并把用户操作发回后端。
const frame = document.getElementById('frame');
const detectionToggle = document.getElementById('detection-toggle');
const sendingToggle = document.getElementById('sending-toggle');
const retargetingSelect = document.getElementById('retargeting-select');
const recoveryButton = document.getElementById('recover-control');
const stopButton = document.getElementById('emergency-stop');
const processState = document.getElementById('process-state');
const startupScreen = document.getElementById('startup-screen');
const startupLabel = document.getElementById('startup-label');
const startupProgressElement = document.getElementById('startup-progress');
const startupProgressBar = document.getElementById('startup-progress-bar');
const startupCenter = document.querySelector('.startup-center');
const startupError = document.getElementById('startup-error');
const startupErrorTitle = document.getElementById('startup-error-title');
const startupErrorMessage = document.getElementById('startup-error-message');
const startupErrorDetail = document.getElementById('startup-error-detail');
const retryButton = document.getElementById('retry-startup');
const exitButton = document.getElementById('exit-app');
const modeState = document.getElementById('mode-state');
const sendingState = document.getElementById('sending-state');
const gestureState = document.getElementById('gesture-state');
const gestureLabel = document.getElementById('gesture-label');
const jointTelemetry = document.getElementById('joint-telemetry');
const safetyBanner = document.getElementById('safety-banner');
const inputTracks = new Map(
  [...document.querySelectorAll('[data-input]')].map((row) => [
    row.dataset.input,
    row.querySelector('.telemetry-track'),
  ]),
);
let emergencyLatched = false;
let emergencyRequested = false;
let pendingDetection = null;
let pendingSending = null;
let pendingRetargeting = null;
let startupTick = 0;
let startupValue = 8;
let startupFinished = false;
let startupTimer = null;
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
    stopStartupTimer();
    renderStartupProgress(100);
    startupScreen.dataset.state = 'ready';
    setTimeout(() => {
      startupScreen.hidden = true;
    }, reduceMotion ? 0 : 260);
  },
  fail(view) {
    startupFinished = false;
    stopStartupTimer();
    startupScreen.hidden = false;
    startupScreen.dataset.state = 'error';
    startupCenter.hidden = true;
    startupProgressElement.hidden = true;
    startupError.hidden = false;
    startupErrorTitle.textContent = view.title;
    startupErrorMessage.textContent = view.message;
    startupErrorDetail.textContent = view.detail;
    retryButton.disabled = !view.retryable;
    if (view.retryable) setTimeout(() => retryButton.focus(), 0);
  },
};

function stopStartupTimer() {
  if (startupTimer !== null) clearInterval(startupTimer);
  startupTimer = null;
}

function startStartupTimer() {
  stopStartupTimer();
  startupTimer = setInterval(() => {
    startupProgress.setAtLeast(window.rpHandStartup.nextSoftProgress(startupValue));
    if (!reduceMotion) {
      startupTick += 1;
      startupLabel.textContent = window.rpHandStartup.loadingLabel(startupTick);
    }
  }, 360);
}

function beginStartup() {
  startupFinished = false;
  startupTick = 0;
  startupValue = 8;
  startupScreen.hidden = false;
  startupScreen.dataset.state = 'loading';
  startupCenter.hidden = false;
  startupError.hidden = true;
  startupProgressElement.hidden = false;
  startupLabel.textContent = 'Loading';
  processState.hidden = true;
  retryButton.disabled = true;
  frame.removeAttribute('src');
  renderStartupProgress(8);
  setRuntimeControlsDisabled(true);
  startStartupTimer();
}

function completeStartupOnce() {
  startupProgress.setComplete();
}

function setProgress(track, width) {
  if (!track) return;
  track.firstElementChild.style.width = width;
  track.setAttribute('aria-valuenow', `${Number.parseInt(width, 10) || 0}`);
}

function setRuntimeControlsDisabled(disabled) {
  stopButton.disabled = disabled;
  recoveryButton.disabled = disabled;
  detectionToggle.disabled = disabled;
  sendingToggle.disabled = disabled;
  retargetingSelect.disabled = disabled;
}

function resetRuntimeDisplay() {
  emergencyLatched = false;
  emergencyRequested = false;
  pendingDetection = null;
  pendingSending = null;
  pendingRetargeting = null;
  sendingState.textContent = 'DISCONNECTED';
  sendingState.dataset.tone = 'danger';
  gestureState.textContent = 'Gesture: none';
  gestureLabel.textContent = '(未连接)';
  inputTracks.forEach((track) => setProgress(track, '0%'));
  jointTelemetry.replaceChildren();
  safetyBanner.hidden = true;
}

function createJointRow(joint) {
  const row = document.createElement('div');
  row.className = 'joint-row';
  row.dataset.joint = joint.name;

  const label = document.createElement('span');
  label.textContent = joint.name;
  label.title = joint.name;

  const track = document.createElement('span');
  track.className = 'joint-track';
  track.setAttribute('role', 'progressbar');
  track.setAttribute('aria-label', joint.name);
  track.setAttribute('aria-valuemin', '0');
  track.setAttribute('aria-valuemax', '100');
  track.append(document.createElement('span'));

  const output = document.createElement('output');
  row.append(label, track, output);
  return row;
}

function renderJoints(joints) {
  const currentNames = [...jointTelemetry.children].map((row) => row.dataset.joint);
  const nextNames = joints.map((joint) => joint.name);
  if (currentNames.join('\0') !== nextNames.join('\0')) {
    jointTelemetry.replaceChildren(...joints.map(createJointRow));
  }
  joints.forEach((joint, index) => {
    const row = jointTelemetry.children[index];
    setProgress(row.querySelector('.joint-track'), joint.width);
    row.querySelector('output').textContent = joint.value;
  });
}

function renderTelemetry(state) {
  if (!state?.telemetry) return;
  const view = window.rpHandTelemetry.buildTelemetryView(state);
  modeState.textContent = `Mode: ${view.mode}`;
  sendingState.textContent = view.status;
  sendingState.dataset.tone = view.statusTone;
  gestureState.textContent = view.gesture;
  gestureLabel.textContent = view.gestureLabel;
  Object.entries(view.inputs).forEach(([channel, width]) => {
    setProgress(inputTracks.get(channel), width);
  });
  renderJoints(view.joints);
  safetyBanner.textContent = view.banner;
  safetyBanner.hidden = view.banner.length === 0;
}

function applyRuntimeState(state) {
  if (!state) return;
  stopButton.disabled = false;
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
  retargetingSelect.disabled = stopped;
  if (pendingDetection === state.detection_enabled) {
    pendingDetection = null;
  }
  // pending 值用于即时反馈点击；收到后端确认后，再由真实运行状态接管控件。
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
  if (pendingRetargeting === state.retargeting_strategy) {
    pendingRetargeting = null;
  }
  if (
    pendingRetargeting === null
    && retargetingSelect.value !== state.retargeting_strategy
  ) {
    retargetingSelect.value = state.retargeting_strategy;
  }
  renderTelemetry(state);
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

async function retryStartup() {
  if (retryButton.disabled) return;
  // Restarting the backend can reconnect and initialize the physical hand.
  // Require a deliberate user action instead of silently auto-retrying.
  const confirmed = window.confirm(
    '请确认摄像头已连接，并确保灵巧手周围无障碍物。是否重新启动 RP-Hand Gesture？',
  );
  if (!confirmed) return;

  retryButton.disabled = true;
  try {
    const started = await window.rpHand.restartBackend();
    if (!started) retryButton.disabled = false;
  } catch {
    startupProgress.fail(window.rpHandErrorState.buildFailureView({
      status: 'failed',
      errorCode: 'RUNTIME_ERROR',
      message: '无法请求后端重新启动',
      retryable: true,
    }));
  }
}

stopButton.addEventListener('click', emergencyStop);
recoveryButton.addEventListener('click', recoverControl);
sendingToggle.addEventListener('click', toggleSending);
retryButton.addEventListener('click', retryStartup);
exitButton.addEventListener('click', () => window.rpHand.exitApp());
detectionToggle.addEventListener('click', () => {
  pendingDetection = detectionToggle.getAttribute('aria-checked') !== 'true';
  detectionToggle.setAttribute('aria-checked', pendingDetection ? 'true' : 'false');
  window.rpHand.sendCommand('toggle_detection');
});
retargetingSelect.addEventListener('change', () => {
  pendingRetargeting = retargetingSelect.value;
  window.rpHand.sendCommand(`retargeting_${retargetingSelect.value}`);
});
frame.addEventListener('load', completeStartupOnce);
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
  if (state.status === 'starting') {
    if (
      startupScreen.hidden
      || startupScreen.dataset.state === 'error'
      || startupFinished
    ) {
      beginStartup();
    }
    const phaseProgress = {
      process: 20,
      config: 30,
      driver: 48,
      camera: 70,
    };
    startupProgress.setAtLeast(phaseProgress[state.phase] || 20);
    return;
  }
  if (state.status === 'ready') {
    startupProgress.setAtLeast(88);
    return;
  }
  if (state.status === 'stopped') return;
  if (state.status !== 'failed') return;

  setRuntimeControlsDisabled(true);
  resetRuntimeDisplay();
  const view = window.rpHandErrorState.buildFailureView(state);
  processState.textContent = view.message;
  processState.hidden = true;
  startupProgress.fail(view);
});

beginStartup();
