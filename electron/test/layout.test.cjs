const test = require('node:test');
const assert = require('node:assert/strict');

const layout = require('../renderer/layout.cjs');
const { computeWindowSize } = layout;

test('keeps the initial 16:9 content inside the current work area', () => {
  assert.deepEqual(computeWindowSize(1152, 720), { width: 1056, height: 594 });
  assert.deepEqual(computeWindowSize(1920, 1080), { width: 1120, height: 630 });
});

test('does not expose the retired fixed-pixel HUD layout helper', () => {
  assert.equal(layout.computeLayout, undefined);
});
