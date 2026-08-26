const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const {
  commandLine,
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

test('preserves validated Python runtime state on a frame', () => {
  const payload = parseFrameLine(JSON.stringify({
    type: 'frame',
    sequence: 8,
    jpeg: 'YWJj',
    state: {
      mode: 'rps',
      detection_enabled: false,
      sending: true,
    },
  }));

  assert.deepEqual(payload.state, {
    mode: 'rps',
    detection_enabled: false,
    sending: true,
  });
  assert.equal(parseFrameLine(JSON.stringify({
    type: 'frame',
    sequence: 9,
    jpeg: 'YWJj',
    state: { mode: 'invalid', detection_enabled: true, sending: true },
  })), null);
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
