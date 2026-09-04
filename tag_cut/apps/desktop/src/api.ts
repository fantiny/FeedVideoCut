const BASE =
  (typeof window !== 'undefined' && window.tagCut?.apiBase) ||
  'http://127.0.0.1:8765'

async function jsonOrThrow(r: Response) {
  if (!r.ok) {
    const text = await r.text()
    let detail = text || `HTTP ${r.status}`
    try {
      const j = JSON.parse(text)
      if (j?.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch { /* keep raw */ }
    if (r.status === 404 && /not found/i.test(detail)) {
      throw new Error('接口不存在：后台可能是旧版本。请完全退出 Electron 后重新打开。')
    }
    throw new Error(detail)
  }
  return r.json()
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`${BASE}${path}`, init)
  } catch (e: any) {
    const msg = String(e?.message || e)
    if (/failed to fetch|networkerror|load failed|network request failed/i.test(msg)) {
      throw new Error(
        '无法连接后台服务。请完全退出 Electron 后重新打开（仅刷新页面不够）；若刚更新过功能，旧进程可能还在占用 8765 端口。',
      )
    }
    throw e
  }
}

export async function health() {
  const r = await apiFetch('/health')
  return jsonOrThrow(r)
}

export async function lookupBatch(batchPath: string, batchId?: string) {
  const qs = new URLSearchParams({ path: batchPath })
  if (batchId) qs.set('batch_id', batchId)
  const r = await apiFetch(`/batches/lookup?${qs}`)
  return jsonOrThrow(r)
}

export async function listBatches() {
  const r = await apiFetch('/batches')
  return jsonOrThrow(r)
}

export async function deleteBatch(batchId: string) {
  const r = await apiFetch(`/batches/${encodeURIComponent(batchId)}`, { method: 'DELETE' })
  return jsonOrThrow(r)
}

export async function createJob(
  batchPath: string,
  layers?: string[],
  force = false,
  batchId?: string,
) {
  const r = await apiFetch('/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      batch_path: batchPath,
      video_glob: '**/*.mp4',
      layers,
      force,
      batch_id: batchId || undefined,
    }),
  })
  return jsonOrThrow(r)
}

export async function getJob(jobId: string) {
  const r = await apiFetch(`/jobs/${jobId}`)
  return jsonOrThrow(r)
}

export async function listMaterials(batchId: string) {
  const r = await apiFetch(`/materials/${encodeURIComponent(batchId)}`)
  return jsonOrThrow(r)
}

export async function getMaterial(batchId: string, matId: string) {
  const r = await apiFetch(`/materials/${encodeURIComponent(batchId)}/${encodeURIComponent(matId)}`)
  return jsonOrThrow(r)
}

export async function patchShot(shotId: string, patch: { is_rejected?: boolean; label_overrides?: object[] }) {
  const r = await apiFetch(`/shots/${encodeURIComponent(shotId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  return jsonOrThrow(r)
}

export async function triggerExport(batchId: string) {
  const r = await apiFetch(`/exports/${encodeURIComponent(batchId)}`, { method: 'POST' })
  return jsonOrThrow(r)
}

export function clipPreviewUrl(shotId: string) {
  return `${BASE}/shots/${encodeURIComponent(shotId)}/preview`
}

export async function exportClip(shotId: string, outputDir: string, filename?: string) {
  const r = await apiFetch(`/shots/${encodeURIComponent(shotId)}/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ output_dir: outputDir, filename }),
  })
  return jsonOrThrow(r)
}

export async function listYoloModels() {
  const r = await apiFetch('/models/yolo')
  return jsonOrThrow(r)
}

export async function probeYoloEnv() {
  const r = await apiFetch('/models/yolo/env')
  return jsonOrThrow(r)
}

export async function downloadYoloModel(modelId: string, force = false) {
  const r = await apiFetch(`/models/yolo/${encodeURIComponent(modelId)}/download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ force }),
  })
  return jsonOrThrow(r)
}

export async function getYoloDownloadStatus(modelId: string) {
  const r = await apiFetch(`/models/yolo/${encodeURIComponent(modelId)}/download`)
  return jsonOrThrow(r)
}

export async function activateYoloModel(modelId: string) {
  const r = await apiFetch('/models/yolo/activate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_id: modelId }),
  })
  return jsonOrThrow(r)
}

export async function searchTags(params: {
  q?: string
  batch_id?: string
  label_type?: string
  layer?: string
  limit?: number
}) {
  const qs = new URLSearchParams()
  if (params.q) qs.set('q', params.q)
  if (params.batch_id) qs.set('batch_id', params.batch_id)
  if (params.label_type) qs.set('label_type', params.label_type)
  if (params.layer) qs.set('layer', params.layer)
  if (params.limit) qs.set('limit', String(params.limit))
  // Prefer /tags/query — some environments block paths named /search
  const r = await apiFetch(`/tags/query?${qs}`)
  return jsonOrThrow(r)
}

export async function searchFacets(batchId?: string) {
  const qs = new URLSearchParams()
  if (batchId) qs.set('batch_id', batchId)
  const r = await apiFetch(`/tags/facets?${qs}`)
  return jsonOrThrow(r)
}

export async function getTaxonomy() {
  const r = await apiFetch('/taxonomy')
  return jsonOrThrow(r)
}
