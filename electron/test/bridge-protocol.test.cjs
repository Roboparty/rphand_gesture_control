const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const {
  commandLine,
  parseBackendLine,
  parseFrameLine,
  resolveBackendEnvironment,
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
  assert.equal(
    commandLine('retargeting_dexpilot'),
    '{"type":"command","command":"retargeting_dexpilot"}\n',
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
      retargeting_strategy: 'dexpilot',
      retargeting_effective: 'stable',
      retargeting_fallback: '掌宽过小',
      detection_enabled: false,
      sending: true,
      safety_state: 'stopped',
      telemetry,
    },
  }));

  assert.deepEqual(payload.state, {
    mode: 'rps',
    retargeting_strategy: 'dexpilot',
    retargeting_effective: 'stable',
    retargeting_fallback: '掌宽过小',
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
      retargeting_strategy: 'stable',
      retargeting_effective: 'stable',
      retargeting_fallback: '',
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
      retargeting_strategy: 'stable',
      retargeting_effective: 'stable',
      retargeting_fallback: '',
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
      retargeting_strategy: 'stable',
      retargeting_effective: 'stable',
      retargeting_fallback: '',
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

  const unknownStrategy = structuredClone(base);
  unknownStrategy.state.retargeting_strategy = 'unknown';
  assert.equal(parseFrameLine(JSON.stringify(unknownStrategy)), null);
});

test('launches the physical hand driver from Electron by default', () => {
  const projectRoot = path.resolve('C:/repo');

  assert.deepEqual(resolvePythonLaunch({
    projectRoot,
    packaged: false,
    platform: 'win32',
  }), {
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
      platform: 'win32',
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
    resolvePythonLaunch({
      projectRoot,
      packaged: false,
      platform: 'win32',
      driver: 'sim',
    }).args,
    [path.join(projectRoot, 'main.py'), '--electron-bridge', '--driver', 'sim'],
  );
});

test('uses native Linux backend paths for packaged and development launches', () => {
  const projectRoot = path.resolve('/repo');
  const resourcesPath = path.resolve('/opt/RP-Hand Gesture/resources');

  assert.deepEqual(
    resolvePythonLaunch({
      projectRoot,
      packaged: true,
      resourcesPath,
      platform: 'linux',
    }),
    {
      executable: path.join(resourcesPath, 'RP-Hand', 'RP-Hand'),
      args: ['--electron-bridge', '--driver', 'lhandpro'],
      cwd: path.join(resourcesPath, 'RP-Hand'),
    },
  );
  assert.deepEqual(
    resolvePythonLaunch({
      projectRoot,
      packaged: false,
      platform: 'linux',
      driver: 'sim',
    }),
    {
      executable: path.join(projectRoot, '.venv', 'bin', 'python'),
      args: [
        path.join(projectRoot, 'main.py'),
        '--electron-bridge',
        '--driver',
        'sim',
      ],
      cwd: projectRoot,
    },
  );
});

test('selects bundled libcanbus only for packaged Linux backends', () => {
  const baseEnvironment = { PATH: '/usr/bin' };

  assert.deepEqual(
    resolveBackendEnvironment({
      environment: baseEnvironment,
      packaged: true,
      platform: 'linux',
    }),
    { PATH: '/usr/bin', SDK_CANFD_DRIVER: 'libcanbus' },
  );
  assert.deepEqual(
    resolveBackendEnvironment({
      environment: { ...baseEnvironment, SDK_CANFD_DRIVER: 'socketcan' },
      packaged: true,
      platform: 'linux',
    }),
    { PATH: '/usr/bin', SDK_CANFD_DRIVER: 'socketcan' },
  );
  assert.deepEqual(
    resolveBackendEnvironment({
      environment: baseEnvironment,
      packaged: true,
      platform: 'win32',
    }),
    baseEnvironment,
  );
});
