const stage = document.getElementById('stage');
const frame = document.getElementById('frame');
const controlPanel = document.getElementById('control-panel');
const detectionToggle = document.getElementById('detection-toggle');
const modeSelect = document.getElementById('mode-select');
const stopButton = document.getElementById('emergency-stop');
const processState = document.getElementById('process-state');
let emergencyLatched = false;
let pendingDetection = null;
let pendingMode = null;

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
  if (pendingDetection === state.detection_enabled) {
    pendingDetection = null;
  }
  if (pendingDetection === null) {
    detectionToggle.setAttribute(
      'aria-checked',
      state.detection_enabled ? 'true' : 'false',
    );
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
  emergencyLatched = true;
  stopButton.dataset.latched = 'true';
  stopButton.setAttribute('aria-pressed', 'true');
  window.rpHand.sendCommand('emergency_stop');
}

stopButton.addEventListener('click', emergencyStop);
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
window.addEventListener('resize', updateLayout);
window.addEventListener('keydown', (event) => {
  if (event.repeat) return;
  const key = event.key.toLowerCase();
  if (key === 'q') window.rpHand.sendCommand('quit');
  if (key === 'e') emergencyStop();
  if (key === 'q' || key === 'e') return;
  if (event.target.closest('button, select, input, textarea, a')) return;
  if (key === 'm') window.rpHand.sendCommand('cycle_mode');
  if (event.code === 'Space') {
    event.preventDefault();
    window.rpHand.sendCommand('toggle_pause');
  }
});

window.rpHand.onFrame(({ jpeg, state }) => {
  frame.src = `data:image/jpeg;base64,${jpeg}`;
  applyRuntimeState(state);
  processState.hidden = true;
});

window.rpHand.onProcessState((state) => {
  if (state.running) return;
  stopButton.disabled = true;
  detectionToggle.disabled = true;
  modeSelect.disabled = true;
  processState.textContent = state.error
    || `RP-Hand process exited (${state.code ?? 'unknown'})`;
  processState.hidden = false;
});
