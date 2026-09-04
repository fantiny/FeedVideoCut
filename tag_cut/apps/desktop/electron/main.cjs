const { app, BrowserWindow, ipcMain, dialog } = require('electron')
const { spawn } = require('child_process')
const fs = require('fs')
const path = require('path')

let backendProcess = null
let mainWindow = null
const backendLogs = []

function tagCutDir() {
  // __dirname = tag_cut/apps/desktop/electron → tag_cut/
  return path.resolve(__dirname, '..', '..', '..')
}

function resolvePython(root) {
  const candidates = [
    process.env.TAG_CUT_PYTHON,
    path.join(root, '.venv', 'bin', 'python3'),
    path.join(root, '.venv', 'bin', 'python'),
  ].filter(Boolean)
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate
  }
  return 'python3'
}

function pushLog(line) {
  const text = String(line).trim()
  if (!text) return
  backendLogs.push(text)
  if (backendLogs.length > 80) backendLogs.shift()
  console.error('[backend]', text)
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('backend-status', {
      ok: false,
      logs: backendLogs.slice(-20),
    })
  }
}

function freePort(port) {
  try {
    const { execSync } = require('child_process')
    // macOS/Linux: kill whatever is listening on the API port so we don't talk to a stale backend
    const out = execSync(`lsof -tiTCP:${port} -sTCP:LISTEN`, { encoding: 'utf8' }).trim()
    if (!out) return
    for (const pid of out.split(/\s+/).filter(Boolean)) {
      try {
        process.kill(Number(pid), 'SIGTERM')
        pushLog(`freed port ${port}: killed pid ${pid}`)
      } catch (e) {
        pushLog(`could not kill pid ${pid}: ${e.message}`)
      }
    }
    // Give the OS a moment to release the port
    execSync('sleep 0.4')
  } catch {
    // nothing listening — ok
  }
}

function startBackend() {
  const root = tagCutDir()
  const python = resolvePython(root)
  freePort(8765)
  const args = [
    '-m', 'uvicorn',
    'services.app:app',
    '--host', '127.0.0.1',
    '--port', '8765',
    '--log-level', 'info',
  ]
  pushLog(`starting: ${python} ${args.join(' ')} (cwd=${root})`)

  backendProcess = spawn(python, args, {
    cwd: root,
    env: { ...process.env, PYTHONPATH: root },
  })

  backendProcess.on('error', (err) => {
    pushLog(`spawn error: ${err.message}`)
  })
  backendProcess.on('exit', (code, signal) => {
    pushLog(`exited code=${code} signal=${signal || ''}`)
    if (code !== 0) {
      pushLog('hint: cd tag_cut && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt')
    }
  })
  backendProcess.stderr.on('data', (d) => pushLog(d.toString()))
  backendProcess.stdout.on('data', (d) => pushLog(d.toString()))
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

  const devUrl = process.env.VITE_DEV_SERVER_URL
  if (devUrl) {
    mainWindow.loadURL(devUrl)
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }

  mainWindow.webContents.on('did-finish-load', () => {
    if (backendLogs.length) {
      mainWindow.webContents.send('backend-status', {
        ok: false,
        logs: backendLogs.slice(-20),
      })
    }
  })
}

app.whenReady().then(() => {
  startBackend()
  createWindow()
  ipcMain.handle('pick-directory', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      title: '选择 clip 保存目录',
      properties: ['openDirectory', 'createDirectory'],
    })
    if (result.canceled || !result.filePaths[0]) return null
    return result.filePaths[0]
  })
})

app.on('window-all-closed', () => {
  if (backendProcess) {
    backendProcess.kill()
    backendProcess = null
  }
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  if (backendProcess) {
    backendProcess.kill()
    backendProcess = null
  }
})
