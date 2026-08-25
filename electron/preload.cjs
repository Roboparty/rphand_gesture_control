const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('rpHand', {
  sendCommand: (command) => ipcRenderer.send('rp-hand:command', command),
  onFrame: (listener) => {
    const wrapped = (_event, frame) => listener(frame);
    ipcRenderer.on('rp-hand:frame', wrapped);
    return () => ipcRenderer.removeListener('rp-hand:frame', wrapped);
  },
  onProcessState: (listener) => {
    const wrapped = (_event, state) => listener(state);
    ipcRenderer.on('rp-hand:process-state', wrapped);
    return () => ipcRenderer.removeListener('rp-hand:process-state', wrapped);
  },
});
