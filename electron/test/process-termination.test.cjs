const test = require('node:test');
const assert = require('node:assert/strict');

const { terminateProcessTree } = require('../process-termination.cjs');

test('uses taskkill to terminate the complete backend tree on Windows', async () => {
  const calls = [];
  const result = await new Promise((resolve) => {
    terminateProcessTree(
      { pid: 4321 },
      {
        platform: 'win32',
        execFileImpl: (...args) => {
          calls.push(args.slice(0, 3));
          args[3](null);
        },
      },
      (error, details) => resolve({ error, details }),
    );
  });

  assert.deepEqual(calls, [[
    'taskkill',
    ['/PID', '4321', '/T', '/F'],
    { windowsHide: true },
  ]]);
  assert.equal(result.error, null);
  assert.deepEqual(result.details, { terminationConfirmed: true });
});

test('does not claim safe termination when taskkill fails', async () => {
  const failure = new Error('access denied');
  const result = await new Promise((resolve) => {
    terminateProcessTree(
      { pid: 4321 },
      {
        platform: 'win32',
        execFileImpl: (_file, _args, _options, callback) => callback(failure),
      },
      (error, details) => resolve({ error, details }),
    );
  });

  assert.equal(result.error, failure);
  assert.deepEqual(result.details, { terminationConfirmed: false });
});
