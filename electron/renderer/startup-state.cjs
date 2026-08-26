const SOFT_PROGRESS_LIMIT = 92;

function loadingLabel(tick) {
  return `Loading${'.'.repeat(Math.abs(tick) % 4)}`;
}

function nextSoftProgress(current) {
  const value = Math.max(0, Number(current) || 0);
  if (value >= SOFT_PROGRESS_LIMIT) return SOFT_PROGRESS_LIMIT;
  const step = Math.max(0.5, (SOFT_PROGRESS_LIMIT - value) * 0.08);
  return Math.min(SOFT_PROGRESS_LIMIT, value + step);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { loadingLabel, nextSoftProgress };
}

if (typeof window !== 'undefined') {
  window.rpHandStartup = { loadingLabel, nextSoftProgress };
}
