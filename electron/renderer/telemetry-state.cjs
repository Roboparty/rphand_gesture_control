// 把 Python 遥测状态整理成只含显示信息的视图模型，DOM 层无需理解控制协议。
const INPUT_CHANNELS = [
  'thumb',
  'index',
  'middle',
  'ring',
  'pinky',
  'thumb_spread',
];

function percentage(value) {
  const normalized = Math.min(Math.max(Number(value) || 0, 0), 1);
  return `${Math.round(normalized * 100)}%`;
}

function buildTelemetryView(state) {
  const telemetry = state.telemetry;
  let status = 'PAUSED';
  if (state.sending && !telemetry.driver_connected) status = 'DISCONNECTED';
  else if (state.sending) status = 'SENDING';

  return {
    mode: state.mode,
    status,
    statusTone: state.sending && telemetry.driver_connected ? 'success' : 'danger',
    detected: telemetry.detected,
    gesture: `Gesture: ${telemetry.gesture}`,
    gestureLabel: `(${telemetry.gesture_label})`,
    inputs: Object.fromEntries(
      INPUT_CHANNELS.map((channel) => [channel, percentage(telemetry.inputs[channel])]),
    ),
    joints: telemetry.joints.map((joint) => ({
      name: joint.name,
      value: `${Math.round(joint.value)}`,
      width: percentage(joint.ratio),
    })),
    banner: telemetry.banner,
  };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { buildTelemetryView, percentage };
}

if (typeof window !== 'undefined') {
  window.rpHandTelemetry = { buildTelemetryView, percentage };
}
