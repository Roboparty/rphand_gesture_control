const test = require('node:test');
const assert = require('node:assert/strict');

const { computeLayout, computeWindowSize } = require('../renderer/layout.cjs');

test('keeps the initial 16:9 content inside the current work area', () => {
  assert.deepEqual(computeWindowSize(1152, 720), { width: 1056, height: 594 });
  assert.deepEqual(computeWindowSize(1920, 1080), { width: 1120, height: 630 });
});

test('fits a wide Python frame without cropping and keeps stop inside HUD', () => {
  const layout = computeLayout(1920, 1080, 1280, 720);

  assert.deepEqual(layout.frame, {
    left: 0,
    top: 0,
    width: 1920,
    height: 1080,
  });
  assert.equal(layout.stop.left >= layout.frame.left, true);
  assert.equal(
    layout.stop.left + layout.stop.width <= layout.frame.left + layout.frame.width,
    true,
  );
});

test('letterboxes the frame in a tall window', () => {
  const layout = computeLayout(900, 1200, 1280, 720);

  assert.equal(layout.frame.width, 900);
  assert.equal(layout.frame.height, 506.25);
  assert.equal(layout.frame.top, 346.875);
  assert.equal(
    layout.stop.top + layout.stop.height <= layout.frame.top + layout.frame.height,
    true,
  );
});
