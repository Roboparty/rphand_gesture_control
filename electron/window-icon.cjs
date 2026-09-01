const path = require('node:path');

const LINUX_ICON_PATH = '/usr/share/icons/hicolor/256x256/apps/rp-hand-gesture.png';

function resolveWindowIcon({
  packaged,
  platform,
  projectRoot,
  executablePath,
}) {
  if (packaged && platform === 'linux') return LINUX_ICON_PATH;
  if (packaged && platform === 'win32') return executablePath;

  const extension = platform === 'win32' ? 'ico' : 'png';
  return path.resolve(projectRoot, 'assets', `icon.${extension}`);
}

module.exports = { resolveWindowIcon };
