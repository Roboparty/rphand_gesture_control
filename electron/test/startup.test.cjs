const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const rendererDir = path.resolve(__dirname, '../renderer');
const html = fs.readFileSync(path.join(rendererDir, 'index.html'), 'utf8');
const css = fs.readFileSync(path.join(rendererDir, 'styles.css'), 'utf8');
const appJs = fs.readFileSync(path.join(rendererDir, 'app.js'), 'utf8');
const { loadingLabel, nextSoftProgress } = require('../renderer/startup-state.cjs');

test('cycles the loading label from zero to three dots', () => {
  assert.equal(loadingLabel(0), 'Loading');
  assert.equal(loadingLabel(1), 'Loading.');
  assert.equal(loadingLabel(2), 'Loading..');
  assert.equal(loadingLabel(3), 'Loading...');
  assert.equal(loadingLabel(4), 'Loading');
});

test('soft progress advances monotonically but waits below completion', () => {
  assert.equal(nextSoftProgress(8) > 8, true);
  assert.equal(nextSoftProgress(91.9) <= 92, true);
  assert.equal(nextSoftProgress(92), 92);
});

test('renders a branded runner splash until the first frame is ready', () => {
  assert.match(html, /id="startup-screen"/);
  assert.match(html, /roboparty\.svg/);
  assert.match(css, /atom01-loading-runner-16\.webp/);
  assert.match(html, /role="progressbar"/);
  assert.match(appJs, /frame\.addEventListener\('load', completeStartupOnce\)/);
  assert.match(appJs, /startupProgress\.setComplete\(\)/);
});

test('keeps startup motion accessible when reduced motion is requested', () => {
  assert.match(css, /@media\s*\(prefers-reduced-motion:\s*reduce\)/);
  assert.match(css, /\.startup-runner-strip[\s\S]*?animation:\s*none/);
});
