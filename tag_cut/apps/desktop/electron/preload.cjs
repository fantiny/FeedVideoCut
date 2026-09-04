const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('tagCut', {
  apiBase: 'http://127.0.0.1:8765',
  onBackendStatus: (callback) => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('backend-status', listener)
    return () => ipcRenderer.removeListener('backend-status', listener)
  },
  pickDirectory: () => ipcRenderer.invoke('pick-directory'),
})
