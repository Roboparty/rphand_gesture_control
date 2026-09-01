const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');

const { resolveWindowIcon } = require('../window-icon.cjs');

test('uses the system-installed icon for a packaged Linux application', () => {
  assert.equal(
    resolveWindowIcon({
      packaged: true,
      platform: 'linux',
      projectRoot: '/workspace',
      executablePath: '/opt/RP-Hand-Gesture/rp-hand-gesture',
    }),
    '/usr/share/icons/hicolor/256x256/apps/rp-hand-gesture.png',
  );
});

test('uses the executable icon for a packaged Windows application', () => {
  const executablePath = 'C:\\Program Files\\RP-Hand Gesture\\RP-Hand Gesture.exe';

  assert.equal(
    resolveWindowIcon({
      packaged: true,
      platform: 'win32',
      projectRoot: 'C:\\project',
      executablePath,
    }),
    executablePath,
  );
});

test('uses repository assets while running from source', () => {
  assert.equal(
    resolveWindowIcon({
      packaged: false,
      platform: 'linux',
      projectRoot: '/workspace',
      executablePath: '/usr/bin/electron',
    }),
    path.resolve('/workspace', 'assets', 'icon.png'),
  );
});
