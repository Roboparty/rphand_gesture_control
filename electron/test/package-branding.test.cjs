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
