// Convert validated Python protocol messages into one small GUI lifecycle.
// Keeping this state out of main.cjs makes failure and shutdown semantics testable.
class BackendLifecycle {
  constructor() {
    this.lastFailure = null;
    this.finalized = false;
  }

  started() {
    this.lastFailure = null;
    this.finalized = false;
    return { status: 'starting', phase: 'process' };
  }

  accept(message) {
    // ChildProcess `close` is the final boundary for one backend run. Ignore
    // any stale callback after that boundary so it cannot disable retry again.
    if (this.finalized) return null;
    if (message.type === 'status') {
      const state = {
        status: 'starting',
        phase: message.phase,
      };
      if (message.camera_index !== undefined) state.cameraIndex = message.camera_index;
      if (message.driver_type !== undefined) state.driverType = message.driver_type;
      return state;
    }
    if (message.type === 'ready') return { status: 'ready' };
    if (message.type !== 'fatal') return null;

    this.lastFailure = {
      errorCode: message.code,
      message: message.message,
      retryable: message.retryable,
    };
    // A fatal event is emitted before Python finishes releasing hardware.
    // Show the reason immediately, but do not enable retry until process exit.
    return {
      status: 'failed',
      errorCode: message.code,
      message: message.message,
      retryable: false,
      pendingExit: true,
    };
  }

  exited({ code, signal, expected = false }) {
    if (this.finalized) return null;
    this.finalized = true;
    if (expected) {
      this.lastFailure = null;
      return { status: 'stopped' };
    }

    const failure = this.lastFailure || {
      errorCode: 'RUNTIME_ERROR',
      message: 'RP-Hand 后端意外退出',
      retryable: true,
    };
    const state = {
      status: 'failed',
      ...failure,
      pendingExit: false,
    };
    if (code !== null && code !== undefined) state.exitCode = code;
    if (signal) state.signal = signal;
    return state;
  }
}

class ShutdownGate {
  constructor() {
    this.requested = false;
    this.allowed = false;
  }

  shouldDefer(hasBackend) {
    if (this.allowed || !hasBackend) return false;
    this.requested = true;
    return true;
  }

  allowExit() {
    this.allowed = true;
  }
}

module.exports = { BackendLifecycle, ShutdownGate };
