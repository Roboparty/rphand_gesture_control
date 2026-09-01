const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const electronRoot = path.resolve(__dirname, '..');

test('packages the desktop application as RP-Hand Gesture', () => {
  const packageJson = JSON.parse(
    fs.readFileSync(path.join(electronRoot, 'package.json'), 'utf8'),
  );

  assert.equal(packageJson.build.productName, 'RP-Hand Gesture');
  assert.equal(packageJson.version, '1.1.1');
  assert.equal(packageJson.license, 'MIT');
  assert.equal(
    packageJson.homepage,
    'https://github.com/Roboparty/rphand_gesture_control',
  );
  assert.equal(
    packageJson.build.artifactName,
    '${productName} Setup ${version}.${ext}',
  );
});

test('uses RP-Hand Gesture as the desktop window title', () => {
  const html = fs.readFileSync(
    path.join(electronRoot, 'renderer', 'index.html'),
    'utf8',
  );

  assert.match(html, /<title>RP-Hand Gesture<\/title>/);
});

test('defines a reproducible Linux deb package with CAN-FD USB access', () => {
  const packageJson = JSON.parse(
    fs.readFileSync(path.join(electronRoot, 'package.json'), 'utf8'),
  );

  assert.equal(packageJson.scripts['dist:linux'],
    'npm test && npm run build:python:linux && electron-builder --linux deb --x64 --config.productName=RP-Hand-Gesture');
  assert.equal(packageJson.build.linux.target, 'deb');
  assert.equal(packageJson.build.linux.desktop.entry.Name, 'RP-Hand Gesture');
  assert.equal(
    packageJson.build.linux.artifactName,
    'RP-Hand-Gesture-${version}-${arch}.${ext}',
  );
  assert.equal(packageJson.build.deb.packageName, 'rp-hand-gesture');
  assert.ok(packageJson.build.deb.depends.includes('libgl1'));
  assert.ok(packageJson.build.deb.depends.includes('libusb-1.0-0'));
  assert.equal(
    packageJson.build.deb.afterInstall,
    '../packaging/linux/after-install.sh',
  );
  assert.equal(
    packageJson.build.deb.afterRemove,
    '../packaging/linux/after-remove.sh',
  );
});

test('packages the Linux icon at a standard hicolor size', () => {
  const packageJson = JSON.parse(
    fs.readFileSync(path.join(electronRoot, 'package.json'), 'utf8'),
  );
  const iconPath = path.resolve(
    electronRoot,
    packageJson.build.linux.icon,
  );
  const png = fs.readFileSync(iconPath);

  assert.equal(packageJson.build.linux.icon, '../assets/icon-linux-256.png');
  assert.equal(png.toString('ascii', 1, 4), 'PNG');
  assert.equal(png.readUInt32BE(16), 256);
  assert.equal(png.readUInt32BE(20), 256);
});

test('configures the Electron sandbox with the permissions Chromium requires', () => {
  const afterInstall = fs.readFileSync(
    path.resolve(electronRoot, '..', 'packaging', 'linux', 'after-install.sh'),
    'utf8',
  );

  assert.match(afterInstall, /chown root:root "\$\{sandbox_path\}"/);
  assert.match(afterInstall, /chmod 4755 "\$\{sandbox_path\}"/);
  assert.match(
    afterInstall,
    /sandbox_path="\/opt\/RP-Hand-Gesture\/chrome-sandbox"/,
  );
});

test('installs and removes the rp-hand-gesture command launcher', () => {
  const afterInstall = fs.readFileSync(
    path.resolve(electronRoot, '..', 'packaging', 'linux', 'after-install.sh'),
    'utf8',
  );
  const afterRemove = fs.readFileSync(
    path.resolve(electronRoot, '..', 'packaging', 'linux', 'after-remove.sh'),
    'utf8',
  );

  assert.match(
    afterInstall,
    /app_path="\/opt\/RP-Hand-Gesture\/rp-hand-gesture"/,
  );
  assert.match(
    afterInstall,
    /launcher_path="\/usr\/bin\/rp-hand-gesture"/,
  );
  assert.match(afterInstall, /ln -sfn "\$\{app_path\}" "\$\{launcher_path\}"/);
  assert.match(
    afterRemove,
    /launcher_path="\/usr\/bin\/rp-hand-gesture"/,
  );
  assert.match(afterRemove, /rm -f "\$\{launcher_path\}"/);
});
