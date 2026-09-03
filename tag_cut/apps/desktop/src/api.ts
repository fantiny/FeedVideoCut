const BASE = 'http://localhost:8765'

export async function health() {
  const r = await fetch(`${BASE}/health`)
  return r.json()
}

export async function createJob(batchPath: string, layers?: string[]) {
  const r = await fetch(`${BASE}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ batch_path: batchPath, video_glob: '**/*.mp4', layers }),
  })
  return r.json()
}

export async function getJob(jobId: string) {
  const r = await fetch(`${BASE}/jobs/${jobId}`)
  return r.json()
}

export async function listMaterials(batchId: string) {
  const r = await fetch(`${BASE}/materials/${batchId}`)
  return r.json()
}

export async function getMaterial(batchId: string, matId: string) {
  const r = await fetch(`${BASE}/materials/${batchId}/${matId}`)
  return r.json()
}

export async function patchShot(shotId: string, patch: { is_rejected?: boolean; label_overrides?: object[] }) {
  const r = await fetch(`${BASE}/shots/${shotId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  return r.json()
}

export async function triggerExport(batchId: string) {
  const r = await fetch(`${BASE}/exports/${batchId}`, { method: 'POST' })
  return r.json()
}
