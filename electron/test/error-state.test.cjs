const test = require('node:test');
const assert = require('node:assert/strict');

const { buildFailureView } = require('../renderer/error-state.cjs');

test('turns a camera failure into actionable Chinese copy', () => {
  assert.deepEqual(
    buildFailureView({
      status: 'failed',
      errorCode: 'CAMERA_OPEN_FAILED',
      message: '无法打开摄像头 0',
      retryable: true,
      exitCode: 1,
    }),
    {
      title: '无法打开摄像头',
      message: '无法打开摄像头 0。请检查摄像头连接、系统权限或是否被其他程序占用。',
      detail: 'CAMERA_OPEN_FAILED · 退出码 1',
      retryable: true,
    },
  );
});

test('falls back to a safe generic runtime failure message', () => {
  const view = buildFailureView({ status: 'failed', retryable: false });

  assert.equal(view.title, 'RP-Hand Gesture 运行异常');
  assert.equal(view.retryable, false);
  assert.match(view.message, /重新启动/);
});
