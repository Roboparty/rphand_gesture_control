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
    visibility: 'visible',
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
  processState.textContent = state.error
    || `RP-Hand process exited (${state.code ?? 'unknown'})`;
  processState.hidden = false;
});
