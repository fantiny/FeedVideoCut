const { app, BrowserWindow, ipcMain } = require('electron')
const { spawn } = require('child_process')
const path = require('path')

let backendProcess = null
let mainWindow = null

function startBackend() {
  // __dirname is tag_cut/apps/desktop/electron/, so ../../.. is tag_cut/
  const tagCutDir = path.resolve(__dirname, '..', '..', '..')
  backendProcess = spawn('python3', [
    '-m', 'uvicorn', 'services.app:app',
    '--port', '8765',
    '--log-level', 'warning',
  ], {
    cwd: tagCutDir,
    env: { ...process.env, PYTHONPATH: tagCutDir },
  })
  backendProcess.stderr.on('data', d => console.error('[backend]', d.toString()))
  backendProcess.stdout.on('data', d => console.log('[backend]', d.toString()))
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    title: 'tag_cut — 视频拆解打标',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs'),
    },
  })

  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }
}

app.whenReady().then(() => {
  startBackend()
  createWindow()
})

app.on('window-all-closed', () => {
  if (backendProcess) backendProcess.kill()
  if (process.platform !== 'darwin') app.quit()
})
