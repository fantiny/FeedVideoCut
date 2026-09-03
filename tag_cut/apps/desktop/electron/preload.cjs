// Context bridge (minimal — API calls happen from renderer via fetch)
const { contextBridge } = require('electron')

contextBridge.exposeInMainWorld('tagCut', {
  apiBase: 'http://localhost:8765',
})
