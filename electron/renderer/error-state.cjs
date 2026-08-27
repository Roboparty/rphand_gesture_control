const ERROR_COPY = {
  CONFIG_ERROR: {
    title: '配置文件读取失败',
    guidance: '请检查安装文件是否完整，然后重新启动。',
  },
  DRIVER_CONNECT_FAILED: {
    title: '灵巧手连接失败',
    guidance: '请检查 CAN-FD 连接和设备供电，并确认灵巧手周围无障碍物。',
  },
  CAMERA_OPEN_FAILED: {
    title: '无法打开摄像头',
    guidance: '请检查摄像头连接、系统权限或是否被其他程序占用。',
  },
  CAMERA_READ_FAILED: {
    title: '摄像头连接已中断',
    guidance: '请重新连接摄像头，确认设备可用后再重试。',
  },
  RUNTIME_ERROR: {
    title: 'RP-Hand 运行异常',
    guidance: '请检查设备连接后重新启动；如果问题持续，请保留错误码。',
  },
};

function buildFailureView(state) {
  const errorCode = state?.errorCode || 'RUNTIME_ERROR';
  const copy = ERROR_COPY[errorCode] || ERROR_COPY.RUNTIME_ERROR;
  const reason = state?.message || 'RP-Hand 后端未能正常运行';
  const detailParts = [errorCode];
  if (state?.exitCode !== undefined) detailParts.push(`退出码 ${state.exitCode}`);

  return {
    title: copy.title,
    message: `${reason}。${copy.guidance}`,
    detail: detailParts.join(' · '),
    retryable: Boolean(state?.retryable),
  };
}

if (typeof module !== 'undefined') {
  module.exports = { buildFailureView };
}
if (typeof window !== 'undefined') {
  window.rpHandErrorState = { buildFailureView };
}
