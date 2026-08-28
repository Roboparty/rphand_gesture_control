// Electron 与 Python 后端之间的行协议边界：校验命令、帧状态和启动路径。
// 所有跨进程输入都先在这里收窄，主进程和渲染进程不直接信任原始 JSON。
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
  'retargeting_stable',
  'retargeting_dexpilot',
]);

const VALID_MODES = new Set(['mirror', 'gesture', 'rps']);
const VALID_RETARGETING_STRATEGIES = new Set(['stable', 'dexpilot']);
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
const VALID_BACKEND_PHASES = new Set(['config', 'driver', 'camera', 'runtime']);
const VALID_FATAL_CODES = new Set([
  'CONFIG_ERROR',
  'DRIVER_CONNECT_FAILED',
  'CAMERA_OPEN_FAILED',
  'CAMERA_READ_FAILED',
  'RUNTIME_ERROR',
]);

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

function hasOnlyKeys(value, allowedKeys) {
  return Object.keys(value).every((key) => allowedKeys.has(key));
}

function parseBackendLine(line) {
  try {
    const payload = JSON.parse(line);
    if (!isRecord(payload) || typeof payload.type !== 'string') return null;

    if (payload.type === 'status') {
      if (
        !hasOnlyKeys(
          payload,
          new Set(['type', 'phase', 'state', 'camera_index', 'driver_type']),
        )
        || !VALID_BACKEND_PHASES.has(payload.phase)
        || payload.state !== 'starting'
        || (payload.camera_index !== undefined && !Number.isInteger(payload.camera_index))
        || (payload.driver_type !== undefined && typeof payload.driver_type !== 'string')
      ) {
        return null;
      }
      return payload;
    }

    if (payload.type === 'ready') {
      return hasOnlyKeys(payload, new Set(['type'])) ? payload : null;
    }

    if (payload.type === 'fatal') {
      if (
        !hasOnlyKeys(payload, new Set(['type', 'code', 'message', 'retryable']))
        || !VALID_FATAL_CODES.has(payload.code)
        || typeof payload.message !== 'string'
        || payload.message.length === 0
        || typeof payload.retryable !== 'boolean'
      ) {
        return null;
      }
      return payload;
    }

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
        || !VALID_RETARGETING_STRATEGIES.has(payload.state.retargeting_strategy)
        || !VALID_RETARGETING_STRATEGIES.has(payload.state.retargeting_effective)
        || typeof payload.state.retargeting_fallback !== 'string'
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

function parseFrameLine(line) {
  const payload = parseBackendLine(line);
  return payload?.type === 'frame' ? payload : null;
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

module.exports = {
  commandLine,
  parseBackendLine,
  parseFrameLine,
  resolvePythonLaunch,
};
