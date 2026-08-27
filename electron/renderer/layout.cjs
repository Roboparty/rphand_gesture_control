// 在工作区内计算初始 16:9 窗口，并保留桌面边缘余量与最小可用尺寸。
function computeWindowSize(workWidth, workHeight) {
  const width = Math.round(Math.max(
    640,
    Math.min(1120, workWidth - 96, ((workHeight - 96) * 16) / 9),
  ));
  return { width, height: Math.round((width * 9) / 16) };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { computeWindowSize };
}

if (typeof window !== 'undefined') {
  window.computeWindowSize = computeWindowSize;
}
