const test = require('node:test');
const assert = require('node:assert/strict');

const {
  BackendLifecycle,
  ShutdownGate,
} = require('../backend-lifecycle.cjs');

test('a spawned backend is starting until Python explicitly reports ready', () => {
  const lifecycle = new BackendLifecycle();

  assert.deepEqual(lifecycle.started(), {
    status: 'starting',
    phase: 'process',
  });
  assert.deepEqual(lifecycle.accept({ type: 'ready' }), {
    status: 'ready',
  });
});

test('preserves a structured fatal error until the child process exits', () => {
  const lifecycle = new BackendLifecycle();
  lifecycle.started();

  assert.deepEqual(
    lifecycle.accept({
      type: 'fatal',
      code: 'CAMERA_OPEN_FAILED',
      message: '无法打开摄像头 0',
      retryable: true,
    }),
    {
      status: 'failed',
      errorCode: 'CAMERA_OPEN_FAILED',
      message: '无法打开摄像头 0',
      retryable: false,
      pendingExit: true,
    },
  );
  assert.deepEqual(lifecycle.exited({ code: 1, signal: null }), {
    status: 'failed',
    errorCode: 'CAMERA_OPEN_FAILED',
    message: '无法打开摄像头 0',
    retryable: true,
    pendingExit: false,
    exitCode: 1,
  });
});

test('classifies an unexpected exit without a fatal event as a runtime error', () => {
  const lifecycle = new BackendLifecycle();
  lifecycle.started();

  assert.deepEqual(lifecycle.exited({ code: 7, signal: null }), {
    status: 'failed',
    errorCode: 'RUNTIME_ERROR',
    message: 'RP-Hand Gesture 后端意外退出',
    retryable: true,
    pendingExit: false,
    exitCode: 7,
  });
});

test('does not present an expected application shutdown as a failure', () => {
  const lifecycle = new BackendLifecycle();
  lifecycle.started();

  assert.deepEqual(
    lifecycle.exited({ code: 0, signal: null, expected: true }),
    { status: 'stopped' },
  );
});

test('ignores protocol messages that arrive after final process close', () => {
  const lifecycle = new BackendLifecycle();
  lifecycle.started();
  lifecycle.exited({ code: 1, signal: null });

  assert.equal(
    lifecycle.accept({
      type: 'fatal',
      code: 'CAMERA_OPEN_FAILED',
      message: 'late fatal',
      retryable: true,
    }),
    null,
  );
});

test('defers application quit until backend cleanup is complete', () => {
  const gate = new ShutdownGate();

  assert.equal(gate.shouldDefer(false), false);
  assert.equal(gate.shouldDefer(true), true);
  assert.equal(gate.requested, true);

  gate.allowExit();

  assert.equal(gate.shouldDefer(true), false);
});
