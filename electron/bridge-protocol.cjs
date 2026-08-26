const path = require('node:path');

const ALLOWED_COMMANDS = new Set([
  'quit',
  'cycle_mode',
  'toggle_pause',
  'emergency_stop',
  'recover_control',
  'toggle_detection',
  'mode_mirror',
  'mode_gesture',
  'mode_rps',
]);

const VALID_MODES = new Set(['mirror', 'gesture', 'rps']);
const VALID_SAFETY_STATES = new Set([
  'waiting',
  'tracking',
  'grace',
  'safe_return',
  'safe_hold',
  'stopped',
]);
const INPUT_CHANNELS = [
  'thumb',
  'index',
  'middle',
  'ring',
  'pinky',
  'thumb_spread',
];

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function isUnitNumber(value) {
  return Number.isFinite(value) && value >= 0 && value <= 1;
}

function isValidTelemetry(telemetry) {
  if (
    !isRecord(telemetry)
    || typeof telemetry.detected !== 'boolean'
    || typeof telemetry.driver_connected !== 'boolean'
    || typeof telemetry.gesture !== 'string'
    || typeof telemetry.gesture_label !== 'string'
    || typeof telemetry.banner !== 'string'
    || !isRecord(telemetry.inputs)
    || !Array.isArray(telemetry.joints)
  ) {
    return false;
  }
  if (!INPUT_CHANNELS.every((channel) => isUnitNumber(telemetry.inputs[channel]))) {
    return false;
  }
  return telemetry.joints.every((joint) => (
    isRecord(joint)
    && typeof joint.name === 'string'
    && joint.name.length > 0
    && Number.isFinite(joint.value)
    && isUnitNumber(joint.ratio)
  ));
}

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
    if (
      payload.state !== undefined
      && (
        payload.state === null
        || typeof payload.state !== 'object'
        || !VALID_MODES.has(payload.state.mode)
        || typeof payload.state.detection_enabled !== 'boolean'
        || typeof payload.state.sending !== 'boolean'
        || !VALID_SAFETY_STATES.has(payload.state.safety_state)
        || !isValidTelemetry(payload.state.telemetry)
      )
    ) {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

function resolvePythonLaunch({
  projectRoot,
  packaged,
  resourcesPath,
  driver = 'lhandpro',
}) {
  if (!['sim', 'lhandpro'].includes(driver)) {
    throw new Error(`Unsupported driver: ${driver}`);
  }
  const driverArgs = ['--electron-bridge', '--driver', driver];
  if (packaged) {
    const cwd = path.join(resourcesPath, 'RP-Hand');
    return {
      executable: path.join(cwd, 'RP-Hand.exe'),
      args: driverArgs,
      cwd,
    };
  }
  return {
    executable: path.join(projectRoot, '.venv', 'Scripts', 'python.exe'),
    args: [path.join(projectRoot, 'main.py'), ...driverArgs],
    cwd: projectRoot,
  };
}

module.exports = { commandLine, parseFrameLine, resolvePythonLaunch };
