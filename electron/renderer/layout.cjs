function computeWindowSize(workWidth, workHeight) {
  const width = Math.round(Math.max(
    640,
    Math.min(1120, workWidth - 96, ((workHeight - 96) * 16) / 9),
  ));
  return { width, height: Math.round((width * 9) / 16) };
}

function computeLayout(stageWidth, stageHeight, imageWidth, imageHeight) {
  if (stageWidth <= 0 || stageHeight <= 0 || imageWidth <= 0 || imageHeight <= 0) {
    return null;
  }
  const scale = Math.min(stageWidth / imageWidth, stageHeight / imageHeight);
  const width = imageWidth * scale;
  const height = imageHeight * scale;
  const left = (stageWidth - width) / 2;
  const top = (stageHeight - height) / 2;
  const panelWidth = Math.min(320 * scale, width);
  const inset = 16 * scale;
  const stopHeight = Math.max(44, 52 * scale);
  return {
    frame: { left, top, width, height },
    stop: {
      left: left + width - panelWidth + inset,
      top: top + height - stopHeight - inset,
      width: Math.max(120, panelWidth - inset * 2),
      height: stopHeight,
    },
  };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { computeLayout, computeWindowSize };
}

if (typeof window !== 'undefined') {
  window.computeLayout = computeLayout;
  window.computeWindowSize = computeWindowSize;
}
