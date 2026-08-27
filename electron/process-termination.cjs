const { execFile } = require('node:child_process');

function terminateProcessTree(
  child,
  {
    platform = process.platform,
    execFileImpl = execFile,
  } = {},
  callback,
) {
  if (!Number.isInteger(child?.pid) || child.pid <= 0) {
    callback(new Error('RP-Hand 后端进程 ID 无效'), {
      terminationConfirmed: false,
    });
    return;
  }

  if (platform === 'win32') {
    // /T includes descendants and /F waits for taskkill to confirm termination.
    execFileImpl(
      'taskkill',
      ['/PID', String(child.pid), '/T', '/F'],
      { windowsHide: true },
      (error) => callback(error || null, {
        terminationConfirmed: !error,
      }),
    );
    return;
  }

  try {
    const signalled = child.kill('SIGKILL');
    callback(
      signalled ? null : new Error('无法向 RP-Hand 后端发送终止信号'),
      { terminationConfirmed: false },
    );
  } catch (error) {
    callback(error, { terminationConfirmed: false });
  }
}

module.exports = { terminateProcessTree };
