const frame = document.getElementById('frame');
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

function setProgress(track, width) {
  if (!track) return;
  track.firstElementChild.style.width = width;
  track.setAttribute('aria-valuenow', `${Number.parseInt(width, 10) || 0}`);
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
