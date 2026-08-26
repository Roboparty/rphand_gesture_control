const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const rendererDir = path.resolve(__dirname, '../renderer');
const html = fs.readFileSync(path.join(rendererDir, 'index.html'), 'utf8');
const css = fs.readFileSync(path.join(rendererDir, 'styles.css'), 'utf8');
const appJs = fs.readFileSync(path.join(rendererDir, 'app.js'), 'utf8');

test('exposes an accessible detection switch and native mode selector', () => {
  assert.match(html, /id="detection-toggle"/);
  assert.match(html, /role="switch"/);
  assert.match(html, /aria-checked="true"/);
  assert.match(html, /<select[^>]+id="mode-select"/);
  assert.match(html, /value="mirror"/);
  assert.match(html, /value="gesture"/);
  assert.match(html, /value="rps"/);
});

test('keeps every interactive control at least 44 pixels tall', () => {
  assert.match(css, /#detection-toggle[\s\S]*?min-height:\s*44px/);
  assert.match(css, /#mode-select[\s\S]*?min-height:\s*44px/);
  assert.match(css, /#emergency-stop[\s\S]*?min-height:\s*44px/);
  assert.match(css, /#recover-control[\s\S]*?min-height:\s*44px/);
});

test('requires confirmation and a stopped backend before control recovery', () => {
  assert.match(html, /id="recover-control"/);
  assert.match(html, /id="recover-control"[\s\S]*?disabled/);
  assert.match(appJs, /window\.confirm/);
  assert.match(appJs, /sendCommand\('recover_control'\)/);
  assert.match(appJs, /state\.safety_state\s*===\s*'stopped'/);
});

test('keeps emergency and quit shortcuts available while a control has focus', () => {
  const emergencyBranch = appJs.indexOf("if (key === 'e')");
  const quitBranch = appJs.indexOf("if (key === 'q')");
  const interactiveGuard = appJs.indexOf("event.target.closest('button, select, input, textarea, a')");

  assert.notEqual(emergencyBranch, -1);
  assert.notEqual(quitBranch, -1);
  assert.notEqual(interactiveGuard, -1);
  assert.equal(emergencyBranch < interactiveGuard, true);
  assert.equal(quitBranch < interactiveGuard, true);
});

test('prevents stale frames from reverting optimistic GUI control state', () => {
  assert.match(appJs, /pendingDetection/);
  assert.match(appJs, /pendingMode/);
});

test('exposes an independent sending switch synchronized with runtime state', () => {
  assert.match(html, /id="sending-toggle"/);
  assert.match(html, /id="sending-toggle"[\s\S]*?role="switch"/);
  assert.match(appJs, /pendingSending/);
  assert.match(appJs, /state\.sending/);
  assert.match(appJs, /sendCommand\('toggle_pause'\)/);
});

test('uses the same sending toggle for the button and Space shortcut', () => {
  assert.match(appJs, /sendingToggle\.addEventListener\('click', toggleSending\)/);
  assert.match(appJs, /event\.code === 'Space'[\s\S]*?toggleSending\(\)/);
});

test('keeps controls readable and contained in a narrow HUD panel', () => {
  assert.match(css, /container-type:\s*inline-size/);
  assert.match(css, /@container\s*\(max-width:\s*190px\)/);
  assert.match(css, /#mode-select[\s\S]*?max-width:\s*100%/);
  assert.match(css, /\.switch-track[\s\S]*?background:\s*#667085/);
  assert.match(css, /#mode-select[\s\S]*?border:\s*1px solid #667085/);
});

test('keeps the sending switch at least 44 pixels tall', () => {
  assert.match(css, /#sending-toggle[\s\S]*?min-height:\s*44px/);
});
