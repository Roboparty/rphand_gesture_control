// 把 Python 的诊断输出转发到 Electron 日志，同时隔离日志目标自身的故障。
function attachLogForwarder(source, destination) {
  if (!source) return () => {};

  source.setEncoding?.('utf8');
  const ignoreDestinationError = () => {};
  const forwardChunk = (chunk) => {
    if (!destination?.writable || destination.destroyed) return;
    try {
      destination.write(chunk);
    } catch {
      // A diagnostic stream must never terminate the control application.
    }
  };

  destination?.on?.('error', ignoreDestinationError);
  source.on('data', forwardChunk);

  return () => {
    source.removeListener?.('data', forwardChunk);
    destination?.removeListener?.('error', ignoreDestinationError);
  };
}

module.exports = { attachLogForwarder };
