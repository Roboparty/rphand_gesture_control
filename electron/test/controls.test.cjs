const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const rendererDir = path.resolve(__dirname, '../renderer');
const html = fs.readFileSync(path.join(rendererDir, 'index.html'), 'utf8');
const css = fs.readFileSync(path.join(rendererDir, 'styles.css'), 'utf8');
const appJs = fs.readFileSync(path.join(rendererDir, 'app.js'), 'utf8');

test('exposes stable and experimental retargeting strategies in the GUI', () => {
  assert.match(html, /id="detection-toggle"/);
  assert.match(html, /role="switch"/);
  assert.match(html, /aria-checked="true"/);
  assert.match(html, /<label for="retargeting-select">映射算法<\/label>/);
  assert.match(html, /id="retargeting-select"/);
  assert.match(html, /value="stable"[^>]*>轻量映射（稳定）/);
  assert.match(html, /value="dexpilot"[^>]*>DexPilot 6DOF（实验）/);
  assert.match(
    appJs,
    /sendCommand\(`retargeting_\$\{retargetingSelect\.value\}`\)/,
  );
  assert.doesNotMatch(appJs, /sendCommand\('cycle_mode'\)/);
});

test('keeps every interactive control at least 44 pixels tall', () => {
  assert.match(css, /#detection-toggle[\s\S]*?min-height:\s*44px/);
  assert.match(css, /#retargeting-select[\s\S]*?min-height:\s*44px/);
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
  assert.match(appJs, /pendingRetargeting/);
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
  assert.match(css, /#retargeting-select[\s\S]*?max-width:\s*100%/);
  assert.match(css, /\.switch-track[\s\S]*?background:\s*#667085/);
  assert.match(css, /#retargeting-select[\s\S]*?border:\s*1px solid #667085/);
});

test('keeps the sending switch at least 44 pixels tall', () => {
  assert.match(css, /#sending-toggle[\s\S]*?min-height:\s*44px/);
});

test('owns telemetry and controls in a layout independent of camera pixels', () => {
  assert.match(html, /id="video-region"/);
  assert.match(html, /id="runtime-sidebar"/);
  assert.match(html, /id="telemetry-panel"/);
  assert.match(html, /data-input="thumb"/);
  assert.match(html, /id="joint-telemetry"/);
  assert.match(css, /#stage\s*\{[\s\S]*?display:\s*grid/);
  assert.match(css, /#runtime-sidebar\s*\{[\s\S]*?overflow-y:\s*auto/);
  assert.doesNotMatch(appJs, /computeLayout|naturalWidth|naturalHeight/);
  assert.doesNotMatch(appJs, /controlPanel\.style|stopButton\.style/);
});
