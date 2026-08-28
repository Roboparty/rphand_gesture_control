const test = require('node:test');
const assert = require('node:assert/strict');

const { buildTelemetryView } = require('../renderer/telemetry-state.cjs');

test('converts normalized runtime telemetry into renderer display values', () => {
  const view = buildTelemetryView({
    mode: 'mirror',
    retargeting_strategy: 'dexpilot',
    retargeting_effective: 'stable',
    retargeting_fallback: '掌宽过小',
    sending: true,
    safety_state: 'tracking',
    telemetry: {
      detected: true,
      driver_connected: true,
      gesture: 'pinch',
      gesture_label: '捏合',
      inputs: {
        thumb: 0.804,
        index: 1,
        middle: 0,
        ring: 0.25,
        pinky: 0.5,
        thumb_spread: 0.6,
      },
      joints: [
        { name: 'thumb_bend', value: 8039.6, ratio: 0.804 },
      ],
      banner: 'SAFE POSE',
    },
  });

  assert.equal(view.mode, 'mirror');
  assert.equal(view.retargetingStrategy, 'dexpilot');
  assert.equal(view.retargetingEffective, 'stable');
  assert.equal(view.retargetingFallback, '掌宽过小');
  assert.equal(view.status, 'SENDING');
  assert.equal(view.statusTone, 'success');
  assert.equal(view.gesture, 'Gesture: pinch');
  assert.equal(view.gestureLabel, '(捏合)');
  assert.equal(view.inputs.thumb, '80%');
  assert.equal(view.inputs.thumb_spread, '60%');
  assert.deepEqual(view.joints, [
    { name: 'thumb_bend', value: '8040', width: '80%' },
  ]);
  assert.equal(view.banner, 'SAFE POSE');
});

test('reports paused or disconnected output without changing control state', () => {
  const view = buildTelemetryView({
    mode: 'mirror',
    retargeting_strategy: 'stable',
    retargeting_effective: 'stable',
    retargeting_fallback: '',
    sending: false,
    safety_state: 'safe_hold',
    telemetry: {
      detected: false,
      driver_connected: false,
      gesture: 'none',
      gesture_label: '未识别',
      inputs: {
        thumb: 0,
        index: 0,
        middle: 0,
        ring: 0,
        pinky: 0,
        thumb_spread: 0,
      },
      joints: [],
      banner: '',
    },
  });

  assert.equal(view.status, 'PAUSED');
  assert.equal(view.statusTone, 'danger');
  assert.equal(view.detected, false);
});
