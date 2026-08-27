const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const {
  commandLine,
  parseBackendLine,
  parseFrameLine,
  resolvePythonLaunch,
} = require('../bridge-protocol.cjs');

test('serializes the existing controls and the new explicit GUI controls', () => {
  assert.equal(commandLine('quit'), '{"type":"command","command":"quit"}\n');
  assert.equal(
    commandLine('emergency_stop'),
    '{"type":"command","command":"emergency_stop"}\n',
  );
  assert.equal(
    commandLine('recover_control'),
    '{"type":"command","command":"recover_control"}\n',
  );
  assert.equal(
    commandLine('toggle_detection'),
    '{"type":"command","command":"toggle_detection"}\n',
  );
  assert.equal(
    commandLine('mode_gesture'),
    '{"type":"command","command":"mode_gesture"}\n',
  );
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

test('accepts validated lifecycle events from Python', () => {
  assert.deepEqual(
    parseBackendLine('{"type":"status","phase":"camera","state":"starting","camera_index":0}'),
    {
      type: 'status',
      phase: 'camera',
      state: 'starting',
      camera_index: 0,
    },
  );
  assert.deepEqual(parseBackendLine('{"type":"ready"}'), { type: 'ready' });
  assert.deepEqual(
    parseBackendLine('{"type":"fatal","code":"CAMERA_OPEN_FAILED","message":"camera 0","retryable":true}'),
    {
      type: 'fatal',
      code: 'CAMERA_OPEN_FAILED',
      message: 'camera 0',
      retryable: true,
    },
  );
  assert.equal(
    parseBackendLine('{"type":"fatal","code":"UNKNOWN","message":"bad","retryable":true}'),
    null,
  );
  assert.equal(parseBackendLine('{"type":"ready","extra":true}'), null);
});

test('preserves validated Python runtime state on a frame', () => {
  const telemetry = {
    detected: true,
    driver_connected: true,
    gesture: 'pinch',
    gesture_label: '捏合',
    inputs: {
      thumb: 0.8,
      index: 0.9,
      middle: 0,
      ring: 0,
      pinky: 0,
      thumb_spread: 0.6,
    },
    joints: [
      { name: 'thumb_bend', value: 8000, ratio: 0.8 },
    ],
    banner: '',
  };
  const payload = parseFrameLine(JSON.stringify({
    type: 'frame',
    sequence: 8,
    jpeg: 'YWJj',
    state: {
      mode: 'rps',
      detection_enabled: false,
      sending: true,
      safety_state: 'stopped',
      telemetry,
    },
  }));

  assert.deepEqual(payload.state, {
    mode: 'rps',
    detection_enabled: false,
    sending: true,
    safety_state: 'stopped',
    telemetry,
  });
  assert.equal(parseFrameLine(JSON.stringify({
    type: 'frame',
    sequence: 9,
    jpeg: 'YWJj',
    state: {
      mode: 'invalid',
      detection_enabled: true,
      sending: true,
      safety_state: 'tracking',
    },
  })), null);
  assert.equal(parseFrameLine(JSON.stringify({
    type: 'frame',
    sequence: 10,
    jpeg: 'YWJj',
    state: {
      mode: 'mirror',
      detection_enabled: true,
      sending: true,
      safety_state: 'invalid',
    },
  })), null);
});

test('rejects malformed Electron telemetry instead of rendering unsafe values', () => {
  const base = {
    type: 'frame',
    sequence: 11,
    jpeg: 'YWJj',
    state: {
      mode: 'mirror',
      detection_enabled: true,
      sending: true,
      safety_state: 'tracking',
      telemetry: {
        detected: true,
        driver_connected: true,
        gesture: 'unknown',
        gesture_label: '未知',
        inputs: {
          thumb: 0,
          index: 0,
          middle: 0,
          ring: 0,
          pinky: 0,
          thumb_spread: 0,
        },
        joints: [],
        banner: '',
      },
    },
  };

  const invalidRatio = structuredClone(base);
  invalidRatio.state.telemetry.joints = [
    { name: 'thumb_bend', value: 12000, ratio: 1.2 },
  ];
  assert.equal(parseFrameLine(JSON.stringify(invalidRatio)), null);

  const missingFinger = structuredClone(base);
  delete missingFinger.state.telemetry.inputs.ring;
  assert.equal(parseFrameLine(JSON.stringify(missingFinger)), null);
});

test('launches the physical hand driver from Electron by default', () => {
  const projectRoot = path.resolve('C:/repo');

  assert.deepEqual(resolvePythonLaunch({ projectRoot, packaged: false }), {
    executable: path.join(projectRoot, '.venv', 'Scripts', 'python.exe'),
    args: [
      path.join(projectRoot, 'main.py'),
      '--electron-bridge',
      '--driver',
      'lhandpro',
    ],
    cwd: projectRoot,
  });
  assert.deepEqual(
    resolvePythonLaunch({
      projectRoot,
      packaged: true,
      resourcesPath: path.resolve('C:/app/resources'),
    }),
    {
      executable: path.resolve('C:/app/resources/RP-Hand/RP-Hand.exe'),
      args: ['--electron-bridge', '--driver', 'lhandpro'],
      cwd: path.resolve('C:/app/resources/RP-Hand'),
    },
  );
});

test('allows Electron development to explicitly use the simulator', () => {
  const projectRoot = path.resolve('C:/repo');

  assert.deepEqual(
    resolvePythonLaunch({ projectRoot, packaged: false, driver: 'sim' }).args,
    [path.join(projectRoot, 'main.py'), '--electron-bridge', '--driver', 'sim'],
  );
});
