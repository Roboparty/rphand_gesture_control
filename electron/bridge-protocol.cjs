const path = require('node:path');

const ALLOWED_COMMANDS = new Set([
  'quit',
  'cycle_mode',
  'toggle_pause',
  'emergency_stop',
]);

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
    return payload;
  } catch {
    return null;
  }
}

function resolvePythonLaunch({ projectRoot, packaged, resourcesPath }) {
  if (packaged) {
    const cwd = path.join(resourcesPath, 'RP-Hand');
    return {
      executable: path.join(cwd, 'RP-Hand.exe'),
      args: ['--electron-bridge'],
      cwd,
    };
  }
  return {
    executable: path.join(projectRoot, '.venv', 'Scripts', 'python.exe'),
    args: [path.join(projectRoot, 'main.py'), '--electron-bridge'],
    cwd: projectRoot,
  };
}

module.exports = { commandLine, parseFrameLine, resolvePythonLaunch };
