import React, { useState, useEffect, useCallback } from 'react'
import * as api from './api'

// ── Types ────────────────────────────────────────────────────────────────────

interface Job {
  id: string
  batch_id?: string
  batch_path?: string
  status: string
  videos?: string[]
  progress?: { layer: string; status: string; error?: string | null }[]
  error?: string | null
}

interface Material {
  id: string
  file_name: string
}

interface Shot {
  id: string
  start_time: number
  end_time: number
  is_rejected?: boolean
  quality_grade?: string | null
  key_frames?: { start?: string | null; mid?: string | null; end?: string | null }
  labels?: { layer: string; label_type?: string; label_value?: unknown }[]
}

function jobId(job: Job): string {
  return job.id || ''
}

function batchIdOf(job: Job): string {
  if (job.batch_id) return job.batch_id
  const p = (job.batch_path || '').replace(/\\/g, '/')
  const parts = p.split('/').filter(Boolean)
  return parts[parts.length - 1] || ''
}

function labelText(value: unknown): string {
  if (value == null) return ''
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return value.map(labelText).join('/')
  if (typeof value === 'object' && 'class_name' in (value as object)) {
    return String((value as { class_name: string }).class_name)
  }
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

/** Prefer business-facing dims over raw object_detection dumps. */
const FEATURED_LABEL_TYPES = [
  'shot_scale', 'camera_move', 'lighting',
  'has_person', 'has_dog', 'has_product', 'dog_breed',
  'behavior', 'audio_texture', 'audio_role',
  'subject_role', 'relation_hint',
  'category_code', 'emotion', 'hook_role', 'applicable_types',
  'content_intent',
]

function featuredLabels(labels: Shot['labels'] | undefined, limit = 16) {
  if (!labels?.length) return []
  const ranked = [...labels].sort((a, b) => {
    const ia = FEATURED_LABEL_TYPES.indexOf(a.label_type || '')
    const ib = FEATURED_LABEL_TYPES.indexOf(b.label_type || '')
    const ra = ia === -1 ? 999 : ia
    const rb = ib === -1 ? 999 : ib
    return ra - rb
  })
  const picked = ranked.filter(l => FEATURED_LABEL_TYPES.includes(l.label_type || ''))
  const pool = picked.length ? picked : ranked
  return pool.slice(0, limit)
}

// ── Colors ───────────────────────────────────────────────────────────────────

const C = {
  bg: '#0f0f0f',
  panel: '#1a1a1a',
  panel2: '#222',
  border: '#333',
  accent: '#2a9d8f',
  accentHover: '#21867a',
  text: '#e8e8e8',
  muted: '#888',
  reject: '#e76f51',
  danger: '#c0392b',
}

const s = {
  panel: {
    background: C.panel,
    border: `1px solid ${C.border}`,
    borderRadius: 8,
    padding: 16,
    marginBottom: 12,
  } as React.CSSProperties,
  btn: {
    background: C.accent,
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    padding: '8px 16px',
    cursor: 'pointer',
    fontSize: 13,
    fontWeight: 600,
  } as React.CSSProperties,
  input: {
    background: '#111',
    color: C.text,
    border: `1px solid ${C.border}`,
    borderRadius: 6,
    padding: '8px 10px',
    fontSize: 13,
    width: '100%',
  } as React.CSSProperties,
  label: {
    fontSize: 11,
    color: C.muted,
    marginBottom: 4,
    display: 'block',
  } as React.CSSProperties,
  tag: {
    display: 'inline-block',
    background: '#2a2a2a',
    border: `1px solid ${C.border}`,
    borderRadius: 4,
    padding: '2px 6px',
    fontSize: 11,
    marginRight: 4,
    marginBottom: 4,
  } as React.CSSProperties,
}

// ── useBackendReady ───────────────────────────────────────────────────────────

function useBackendReady(): { ready: boolean; logs: string[] } {
  const [ready, setReady] = useState(false)
  const [logs, setLogs] = useState<string[]>([])
  useEffect(() => {
    let cancelled = false
    const onStatus = (window as any).tagCut?.onBackendStatus
    const unsub = onStatus?.((payload: { logs?: string[] }) => {
      if (!cancelled && payload?.logs) setLogs(payload.logs)
    })
    const poll = async () => {
      while (!cancelled) {
        try {
          const h = await api.health()
          if (!cancelled) {
            const features = Array.isArray(h?.features) ? h.features : []
            if (features.length && !features.includes('search')) {
              setLogs(prev => [...prev, '后台版本过旧（无搜索接口），请完全退出后重启 Electron'])
            }
            setReady(true)
          }
          return
        } catch {
          await new Promise(r => setTimeout(r, 1000))
        }
      }
    }
    poll()
    return () => {
      cancelled = true
      if (typeof unsub === 'function') unsub()
    }
  }, [])
  return { ready, logs }
}

// ── LoadingScreen ─────────────────────────────────────────────────────────────

function LoadingScreen({ logs }: { logs: string[] }) {
  const [dots, setDots] = useState('.')
  useEffect(() => {
    const t = setInterval(() => setDots(d => d.length >= 3 ? '.' : d + '.'), 500)
    return () => clearInterval(t)
  }, [])
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', background: C.bg, color: C.text, padding: 24 }}>
      <div style={{ fontSize: 32, marginBottom: 16 }}>🎬</div>
      <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>tag_cut</div>
      <div style={{ color: C.muted, fontSize: 14 }}>正在启动后台服务{dots}</div>
      {logs.length > 0 && (
        <pre style={{
          marginTop: 20,
          maxWidth: 720,
          maxHeight: 280,
          overflow: 'auto',
          background: '#111',
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          padding: 12,
          fontSize: 11,
          color: '#f4a261',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
        }}>
          {logs.join('\n')}
        </pre>
      )}
    </div>
  )
}

// ── BatchPicker ───────────────────────────────────────────────────────────────

interface BatchPickerProps {
  onCacheLoaded: (info: { batchId: string; batchPath: string; materialCount: number; shotCount: number }) => void
  onJobCreated: (job: Job) => void
  onBatchesChanged?: () => void
}

function BatchPicker({ onCacheLoaded, onJobCreated, onBatchesChanged }: BatchPickerProps) {
  const [batchPath, setBatchPath] = useState('../input/8月第60条信息流')
  const [batchAlias, setBatchAlias] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [hint, setHint] = useState('')

  const aliasOrUndefined = batchAlias.trim() || undefined

  const openBatch = async () => {
    setLoading(true)
    setError('')
    setHint('')
    try {
      const info = await api.lookupBatch(batchPath, aliasOrUndefined)
      if (info.exists && info.material_count > 0) {
        onCacheLoaded({
          batchId: info.batch_id,
          batchPath: info.batch_path,
          materialCount: info.material_count,
          shotCount: info.shot_count || 0,
        })
        setHint(`已加载「${info.batch_id}」：${info.material_count} 条素材 / ${info.shot_count || 0} 个镜头`)
        onBatchesChanged?.()
        return
      }
      const job = await api.createJob(batchPath, undefined, false, aliasOrUndefined)
      if (!job?.id) throw new Error('任务创建失败：未返回 id')
      onJobCreated(job)
      setHint(`尚无缓存，开始分析到子目录「${job.batch_id || aliasOrUndefined || '…'}」…`)
      onBatchesChanged?.()
    } catch (e: any) {
      setError(e.message || '打开失败')
    } finally {
      setLoading(false)
    }
  }

  const regenerate = async () => {
    const name = aliasOrUndefined || batchPath.split(/[/\\]/).filter(Boolean).slice(-1)[0] || '该批次'
    if (!window.confirm(`将清除子目录「${name}」的分析结果并重新生成，其他批次不受影响。是否继续？`)) return
    setLoading(true)
    setError('')
    setHint('')
    try {
      const job = await api.createJob(batchPath, undefined, true, aliasOrUndefined)
      if (!job?.id) throw new Error('任务创建失败：未返回 id')
      onJobCreated(job)
      setHint('正在重新生成…')
      onBatchesChanged?.()
    } catch (e: any) {
      setError(e.message || '重新生成失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={s.panel}>
      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 12, color: C.accent }}>打开输入批次</div>
      <label style={s.label}>输入目录路径</label>
      <input
        style={{ ...s.input, marginBottom: 8 }}
        value={batchPath}
        onChange={e => setBatchPath(e.target.value)}
        placeholder="../input/8月第60条信息流"
      />
      <label style={s.label}>结果子目录名（可选，默认用文件夹名；不同批次请用不同名字）</label>
      <input
        style={{ ...s.input, marginBottom: 10 }}
        value={batchAlias}
        onChange={e => setBatchAlias(e.target.value)}
        placeholder="例如 batch_aug60"
      />
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button
          style={{ ...s.btn, opacity: loading ? 0.6 : 1, flex: 1 }}
          onClick={openBatch}
          disabled={loading}
        >
          {loading ? '处理中…' : '打开批次'}
        </button>
        <button
          style={{
            ...s.btn,
            background: 'transparent',
            color: C.text,
            border: `1px solid ${C.border}`,
            opacity: loading ? 0.6 : 1,
          }}
          onClick={regenerate}
          disabled={loading}
        >
          重新生成
        </button>
      </div>
      {hint && <div style={{ color: C.accent, fontSize: 12, marginTop: 8 }}>{hint}</div>}
      {error && <div style={{ color: C.reject, fontSize: 12, marginTop: 8 }}>{error}</div>}
    </div>
  )
}

// ── BatchLibrary ──────────────────────────────────────────────────────────────

interface BatchSummary {
  batch_id: string
  material_count: number
  shot_count: number
  source_path?: string
  updated_at?: string
  data_dir?: string
}

interface BatchLibraryProps {
  selectedId: string
  refreshKey: number
  onSelect: (batchId: string) => void
  onDeleted: (batchId: string) => void
}

function BatchLibrary({ selectedId, refreshKey, onSelect, onDeleted }: BatchLibraryProps) {
  const [batches, setBatches] = useState<BatchSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const reload = useCallback(() => {
    setLoading(true)
    setError('')
    api.listBatches()
      .then(data => setBatches(Array.isArray(data?.batches) ? data.batches : []))
      .catch((e: any) => setError(e.message || '加载批次列表失败'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { reload() }, [reload, refreshKey])

  const handleDelete = async (b: BatchSummary, ev: React.MouseEvent) => {
    ev.stopPropagation()
    if (!window.confirm(
      `确认删除批次「${b.batch_id}」？\n将删除分析结果目录（约 ${b.material_count} 条素材 / ${b.shot_count} 镜头），不会删除 input 原片。`,
    )) return
    try {
      await api.deleteBatch(b.batch_id)
      onDeleted(b.batch_id)
      reload()
    } catch (e: any) {
      setError(e.message || '删除失败')
    }
  }

  return (
    <div style={s.panel}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ fontWeight: 700, fontSize: 13, color: C.accent }}>已有批次</div>
        <button
          onClick={reload}
          style={{ background: 'transparent', border: `1px solid ${C.border}`, color: C.muted, borderRadius: 4, padding: '2px 8px', fontSize: 11, cursor: 'pointer' }}
        >
          刷新
        </button>
      </div>
      {loading && <div style={{ color: C.muted, fontSize: 12 }}>加载中…</div>}
      {error && <div style={{ color: C.reject, fontSize: 12, marginBottom: 6 }}>{error}</div>}
      {!loading && batches.length === 0 && (
        <div style={{ color: C.muted, fontSize: 12 }}>暂无已分析批次（结果保存在 data/&lt;批次名&gt;/）</div>
      )}
      {batches.map(b => {
        const active = selectedId === b.batch_id
        return (
          <div
            key={b.batch_id}
            onClick={() => onSelect(b.batch_id)}
            style={{
              padding: '8px 10px',
              borderRadius: 6,
              cursor: 'pointer',
              marginBottom: 6,
              background: active ? C.accent + '22' : C.panel2,
              border: active ? `1px solid ${C.accent}` : `1px solid ${C.border}`,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'flex-start' }}>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: C.text, wordBreak: 'break-all' }}>{b.batch_id}</div>
                <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>
                  {b.material_count} 素材 · {b.shot_count} 镜头
                </div>
                {b.source_path && (
                  <div style={{ fontSize: 10, color: C.muted, marginTop: 2, wordBreak: 'break-all', opacity: 0.8 }}>
                    {b.source_path}
                  </div>
                )}
              </div>
              <button
                onClick={ev => handleDelete(b, ev)}
                style={{
                  background: 'transparent',
                  border: `1px solid ${C.reject}66`,
                  color: C.reject,
                  borderRadius: 4,
                  padding: '2px 6px',
                  fontSize: 11,
                  cursor: 'pointer',
                  flexShrink: 0,
                }}
              >
                删除
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── JobProgress ───────────────────────────────────────────────────────────────

interface JobProgressProps {
  job: Job
  onJobUpdate: (job: Job) => void
}

function JobProgress({ job, onJobUpdate }: JobProgressProps) {
  const id = jobId(job)
  useEffect(() => {
    if (!id) return
    if (job.status === 'done' || job.status === 'failed' || job.status === 'error') return
    const interval = setInterval(async () => {
      try {
        const updated = await api.getJob(id)
        onJobUpdate(updated)
      } catch {}
    }, 2000)
    return () => clearInterval(interval)
  }, [id, job.status, onJobUpdate])

  const statusColor = job.status === 'done' ? C.accent : (job.status === 'failed' || job.status === 'error') ? C.reject : '#f4a261'
  const progress = job.progress || []
  const recent = progress.slice(-12)
  const videoCount = job.videos?.length ?? 0
  const doneLayers = progress.filter(p => p.status === 'done').length

  return (
    <div style={s.panel}>
      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 10, color: C.accent }}>任务进度</div>
      <div style={{ fontSize: 12, marginBottom: 8 }}>
        <span style={{ color: C.muted }}>ID: </span>
        <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{id ? `${id.slice(0, 16)}…` : '—'}</span>
      </div>
      <div style={{ fontSize: 13, marginBottom: 8 }}>
        <span style={{ color: C.muted }}>状态: </span>
        <span style={{ color: statusColor, fontWeight: 600 }}>{job.status}</span>
        {videoCount > 0 && (
          <span style={{ color: C.muted, marginLeft: 8 }}>{videoCount} 条视频</span>
        )}
      </div>
      {job.error && <div style={{ color: C.reject, fontSize: 12, marginBottom: 8 }}>{job.error}</div>}
      {progress.length > 0 && (
        <div style={{ fontSize: 11, color: C.muted, marginBottom: 8 }}>
          阶段完成 {doneLayers}/{progress.length}
        </div>
      )}
      {recent.map((p, i) => (
        <div key={`${p.layer}-${i}`} style={{ fontSize: 11, color: p.status === 'failed' ? C.reject : C.muted, marginBottom: 4, wordBreak: 'break-all' }}>
          {p.status === 'done' ? '✓' : p.status === 'failed' ? '✗' : '•'} {p.layer.split('/').slice(-1)[0]} {p.status}
          {p.error ? ` (${p.error})` : ''}
        </div>
      ))}
    </div>
  )
}

// ── MaterialList ──────────────────────────────────────────────────────────────

interface MaterialListProps {
  batchId: string
  selectedId: string | null
  onSelect: (id: string) => void
}

function MaterialList({ batchId, selectedId, onSelect }: MaterialListProps) {
  const [materials, setMaterials] = useState<Material[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.listMaterials(batchId)
      .then(data => {
        const list = Array.isArray(data) ? data : data.materials || []
        setMaterials(list)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [batchId])

  return (
    <div style={s.panel}>
      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 10, color: C.accent }}>素材列表</div>
      {loading && <div style={{ color: C.muted, fontSize: 12 }}>加载中…</div>}
      {materials.map(m => (
        <div
          key={m.id}
          onClick={() => onSelect(m.id)}
          style={{
            padding: '8px 10px',
            borderRadius: 6,
            cursor: 'pointer',
            fontSize: 12,
            marginBottom: 4,
            background: selectedId === m.id ? C.accent + '22' : 'transparent',
            border: selectedId === m.id ? `1px solid ${C.accent}` : `1px solid transparent`,
            color: selectedId === m.id ? C.text : C.muted,
            wordBreak: 'break-all',
          }}
        >
          {m.file_name}
        </div>
      ))}
      {!loading && materials.length === 0 && (
        <div style={{ color: C.muted, fontSize: 12 }}>暂无素材</div>
      )}
    </div>
  )
}

// ── ShotViewer ────────────────────────────────────────────────────────────────

interface ShotViewerProps {
  batchId: string
  matId: string
  focusShotId?: string | null
}

function ShotViewer({ batchId, matId, focusShotId }: ShotViewerProps) {
  const [shots, setShots] = useState<Shot[]>([])
  const [loading, setLoading] = useState(true)
  const [previewId, setPreviewId] = useState<string | null>(null)
  const [exportingId, setExportingId] = useState<string | null>(null)
  const [clipMsg, setClipMsg] = useState<Record<string, { ok: boolean; text: string }>>({})

  const loadShots = useCallback(() => {
    setLoading(true)
    setPreviewId(null)
    api.getMaterial(batchId, matId)
      .then(data => {
        const rawShots: Shot[] = Array.isArray(data) ? data : (data.shots || [])
        const labels = Array.isArray(data?.labels) ? data.labels : []
        const byShot: Record<string, Shot['labels']> = {}
        for (const lb of labels) {
          const sid = lb.shot_id
          if (!sid) continue
          if (!byShot[sid]) byShot[sid] = []
          byShot[sid]!.push(lb)
        }
        setShots(rawShots.map(sh => ({ ...sh, labels: byShot[sh.id] || [] })))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [batchId, matId])

  useEffect(() => { loadShots() }, [loadShots])

  useEffect(() => {
    if (focusShotId) {
      setPreviewId(focusShotId)
      requestAnimationFrame(() => {
        document.getElementById(`shot-${focusShotId}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      })
    }
  }, [focusShotId, shots])

  const toggleReject = async (shot: Shot) => {
    try {
      await api.patchShot(shot.id, { is_rejected: !shot.is_rejected })
      setShots(prev => prev.map(s => s.id === shot.id ? { ...s, is_rejected: !s.is_rejected } : s))
    } catch {}
  }

  const saveClip = async (shot: Shot) => {
    let dir: string | null = null
    try {
      dir = (await window.tagCut?.pickDirectory?.()) ?? null
    } catch {
      dir = null
    }
    if (!dir) {
      dir = window.prompt(
        '保存 clip 的目录（绝对路径）',
        localStorage.getItem('tag_cut_clip_dir') || '',
      )
    }
    if (!dir) return
    localStorage.setItem('tag_cut_clip_dir', dir)
    setExportingId(shot.id)
    setClipMsg(prev => ({ ...prev, [shot.id]: { ok: true, text: '正在导出…' } }))
    try {
      const res = await api.exportClip(shot.id, dir)
      setClipMsg(prev => ({ ...prev, [shot.id]: { ok: true, text: `已保存 ${res.path}` } }))
    } catch (e: any) {
      setClipMsg(prev => ({ ...prev, [shot.id]: { ok: false, text: e.message || '导出失败' } }))
    } finally {
      setExportingId(null)
    }
  }

  if (loading) return <div style={{ color: C.muted, fontSize: 12, padding: 16 }}>加载镜头中…</div>

  const miniBtn = (opts: { label: string; onClick: () => void; disabled?: boolean; danger?: boolean }) => (
    <button
      onClick={opts.onClick}
      disabled={opts.disabled}
      style={{
        background: opts.danger ? 'transparent' : C.accent,
        color: opts.danger ? C.muted : '#fff',
        border: `1px solid ${opts.danger ? C.border : C.accent}`,
        borderRadius: 4,
        padding: '4px 8px',
        cursor: opts.disabled ? 'wait' : 'pointer',
        fontSize: 11,
        opacity: opts.disabled ? 0.6 : 1,
      }}
    >
      {opts.label}
    </button>
  )

  return (
    <div style={{ overflowY: 'auto', flex: 1 }}>
      {shots.map(shot => {
        const mid = shot.key_frames?.mid
        const imgSrc = mid
          ? (mid.startsWith('http') ? mid : `http://127.0.0.1:8765${mid}`)
          : ''
        const start = Number(shot.start_time) || 0
        const end = Number(shot.end_time) || 0
        const isPreview = previewId === shot.id
        const note = clipMsg[shot.id]
        return (
        <div
          key={shot.id}
          id={`shot-${shot.id}`}
          style={{
          ...s.panel,
          border: focusShotId === shot.id
            ? `1px solid ${C.accent}`
            : shot.is_rejected ? `1px solid ${C.reject}44` : `1px solid ${C.border}`,
          opacity: shot.is_rejected ? 0.6 : 1,
          boxShadow: focusShotId === shot.id ? `0 0 0 1px ${C.accent}55` : undefined,
        }}>
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flexShrink: 0 }}>
              {imgSrc ? (
                <img
                  src={imgSrc}
                  alt="keyframe"
                  style={{ width: 120, height: 68, objectFit: 'cover', borderRadius: 4, background: '#111' }}
                  onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                />
              ) : (
                <div style={{ width: 120, height: 68, background: '#111', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', color: C.muted, fontSize: 11 }}>
                  无缩略图
                </div>
              )}
            </div>

            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6, gap: 8 }}>
                <div style={{ fontSize: 11, color: C.muted }}>
                  {start.toFixed(2)}s — {end.toFixed(2)}s
                  <span style={{ marginLeft: 8, color: C.text }}>{(end - start).toFixed(2)}s</span>
                </div>
                <button
                  onClick={() => toggleReject(shot)}
                  style={{
                    background: shot.is_rejected ? C.reject : 'transparent',
                    color: shot.is_rejected ? '#fff' : C.muted,
                    border: `1px solid ${shot.is_rejected ? C.reject : C.border}`,
                    borderRadius: 4,
                    padding: '2px 8px',
                    cursor: 'pointer',
                    fontSize: 11,
                  }}
                >
                  {shot.is_rejected ? '已排除' : '排除'}
                </button>
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
                {shot.quality_grade && (
                  <span style={{ ...s.tag, color: C.accent, borderColor: C.accent + '44' }}>
                    质量: {shot.quality_grade}
                  </span>
                )}
                {featuredLabels(shot.labels).map((lbl, i) => (
                  <span key={i} style={s.tag} title={lbl.layer}>
                    {lbl.label_type || lbl.layer}: {labelText(lbl.label_value)}
                  </span>
                ))}
              </div>

              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {miniBtn({
                  label: isPreview ? '关闭预览' : '预览 clip',
                  onClick: () => setPreviewId(isPreview ? null : shot.id),
                })}
                {miniBtn({
                  label: exportingId === shot.id ? '导出中…' : '另存 mp4',
                  onClick: () => saveClip(shot),
                  disabled: exportingId === shot.id,
                })}
              </div>
              {note && (
                <div style={{ fontSize: 11, marginTop: 6, color: note.ok ? C.accent : C.reject, wordBreak: 'break-all' }}>
                  {note.text}
                </div>
              )}
            </div>
          </div>

          {isPreview && (
            <video
              key={shot.id}
              src={api.clipPreviewUrl(shot.id)}
              controls
              autoPlay
              style={{ width: '100%', maxHeight: 360, marginTop: 12, background: '#000', borderRadius: 6 }}
            />
          )}
        </div>
        )
      })}
      {shots.length === 0 && <div style={{ color: C.muted, fontSize: 12, padding: 16 }}>暂无镜头数据</div>}
    </div>
  )
}

// ── ModelsPanel ───────────────────────────────────────────────────────────────

interface YoloModelRow {
  id: string
  filename: string
  family: string
  size_class: string
  approx_mb: number
  description: string
  downloaded: boolean
  active: boolean
  supported: boolean
  recommended: boolean
  badge: string
  reasons: string[]
  download?: { status?: string; bytes?: number; total?: number; error?: string }
}

function ModelsPanel() {
  const [models, setModels] = useState<YoloModelRow[]>([])
  const [env, setEnv] = useState<Record<string, unknown> | null>(null)
  const [recommendedId, setRecommendedId] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [msg, setMsg] = useState('')
  const [open, setOpen] = useState(false)

  const reload = useCallback(() => {
    api.listYoloModels()
      .then(data => {
        setModels(Array.isArray(data?.models) ? data.models : [])
        setEnv(data?.environment || null)
        setRecommendedId(data?.recommended_id || '')
      })
      .catch((e: any) => setMsg(e.message || '加载模型列表失败'))
  }, [])

  useEffect(() => { reload() }, [reload])

  useEffect(() => {
    if (!busyId) return
    const t = setInterval(() => {
      api.getYoloDownloadStatus(busyId)
        .then(st => {
          if (st.status === 'done') {
            setBusyId(null)
            setMsg(`${busyId} 下载完成`)
            reload()
          } else if (st.status === 'failed') {
            setBusyId(null)
            setMsg(st.error || '下载失败')
            reload()
          }
        })
        .catch(() => {})
    }, 1200)
    return () => clearInterval(t)
  }, [busyId, reload])

  const probe = async () => {
    setMsg('正在检测本机环境…')
    try {
      const data = await api.probeYoloEnv()
      setModels(Array.isArray(data?.models) ? data.models : [])
      setEnv(data?.environment || null)
      setRecommendedId(data?.recommended_id || '')
      const e = data?.environment || {}
      setMsg(`环境：${e.cpu || ''} · ${e.ram_gb || '?'}GB · ${e.accelerator || 'cpu'} · 推荐 ${data?.recommended_id || '—'}`)
    } catch (e: any) {
      setMsg(e.message || '环境检测失败')
    }
  }

  const download = async (id: string) => {
    setBusyId(id)
    setMsg(`开始下载 ${id}…`)
    try {
      await api.downloadYoloModel(id)
    } catch (e: any) {
      setBusyId(null)
      setMsg(e.message || '下载失败')
    }
  }

  const activate = async (id: string) => {
    try {
      await api.activateYoloModel(id)
      setMsg(`已切换为 ${id}（下次分析生效）`)
      reload()
    } catch (e: any) {
      setMsg(e.message || '切换失败')
    }
  }

  const badgeStyle = (m: YoloModelRow): React.CSSProperties => {
    if (m.badge === 'recommended') return { color: C.accent, borderColor: C.accent + '66' }
    if (m.badge === 'supported') return { color: '#8ab4f8', borderColor: '#8ab4f866' }
    return { color: C.reject, borderColor: C.reject + '66' }
  }

  const badgeText = (m: YoloModelRow) => {
    if (m.badge === 'recommended') return '推荐'
    if (m.badge === 'supported') return '支持'
    return '不推荐'
  }

  return (
    <div style={s.panel}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: open ? 10 : 0 }}>
        <div style={{ fontWeight: 700, fontSize: 13, color: C.accent }}>YOLO 模型</div>
        <button
          onClick={() => setOpen(o => !o)}
          style={{ background: 'transparent', border: `1px solid ${C.border}`, color: C.muted, borderRadius: 4, padding: '2px 8px', fontSize: 11, cursor: 'pointer' }}
        >
          {open ? '收起' : '展开'}
        </button>
      </div>
      {open && (
        <>
          <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
            <button style={{ ...s.btn, padding: '4px 10px', fontSize: 11 }} onClick={probe}>检测本机环境</button>
            <button
              style={{ ...s.btn, padding: '4px 10px', fontSize: 11, background: 'transparent', color: C.text, border: `1px solid ${C.border}` }}
              onClick={reload}
            >
              刷新
            </button>
          </div>
          {env && (
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 8, lineHeight: 1.4 }}>
              {(env as any).cpu} · {(env as any).ram_gb}GB · {(env as any).accelerator}
              {recommendedId ? ` · 推荐 ${recommendedId}` : ''}
            </div>
          )}
          {models.map(m => (
            <div key={m.id} style={{
              padding: 8,
              marginBottom: 6,
              borderRadius: 6,
              background: C.panel2,
              border: m.active ? `1px solid ${C.accent}` : `1px solid ${C.border}`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 6, alignItems: 'flex-start' }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>
                    {m.id}
                    {m.active && <span style={{ color: C.accent, marginLeft: 6, fontSize: 10 }}>当前</span>}
                  </div>
                  <div style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>{m.description}</div>
                  <div style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>
                    ~{m.approx_mb}MB · {m.downloaded ? '已下载' : '未下载'}
                    {(m.reasons || []).length ? ` · ${m.reasons[0]}` : ''}
                  </div>
                </div>
                <span style={{ ...s.tag, ...badgeStyle(m), margin: 0 }}>{badgeText(m)}</span>
              </div>
              <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                <button
                  style={{ ...s.btn, padding: '3px 8px', fontSize: 11, opacity: busyId === m.id ? 0.6 : 1 }}
                  disabled={busyId === m.id}
                  onClick={() => download(m.id)}
                >
                  {busyId === m.id ? '下载中…' : m.downloaded ? '重新下载' : '下载'}
                </button>
                <button
                  style={{
                    ...s.btn, padding: '3px 8px', fontSize: 11,
                    background: 'transparent', color: C.text, border: `1px solid ${C.border}`,
                    opacity: (!m.downloaded || m.active) ? 0.5 : 1,
                  }}
                  disabled={!m.downloaded || m.active}
                  onClick={() => activate(m.id)}
                >
                  设为当前
                </button>
              </div>
            </div>
          ))}
          {msg && <div style={{ fontSize: 11, color: C.muted, marginTop: 4, wordBreak: 'break-all' }}>{msg}</div>}
        </>
      )}
    </div>
  )
}

// ── TagSearchPanel ────────────────────────────────────────────────────────────

interface SearchHit {
  batch_id: string
  material_id: string
  material_name: string
  shot_id: string
  start_time: number
  end_time: number
  matched_labels: { label_type?: string; label_value?: unknown; layer?: string }[]
  keyframe_mid?: string | null
}

interface TagSearchPanelProps {
  batchId: string
  onOpenHit: (hit: SearchHit) => void
}

function TagSearchPanel({ batchId, onOpenHit }: TagSearchPanelProps) {
  const [q, setQ] = useState('')
  const [labelType, setLabelType] = useState('')
  const [scopeAll, setScopeAll] = useState(false)
  const [types, setTypes] = useState<string[]>([])
  const [hits, setHits] = useState<SearchHit[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.searchFacets(scopeAll ? undefined : (batchId || undefined))
      .then(data => {
        const list = Array.isArray(data?.label_types) ? data.label_types.map((t: any) => t.type) : []
        setTypes(list)
      })
      .catch(() => {})
  }, [batchId, scopeAll])

  const runSearch = async () => {
    if (!q.trim() && !labelType) {
      setError('请输入关键词或选择标签类型')
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await api.searchTags({
        q: q.trim() || undefined,
        batch_id: scopeAll ? undefined : (batchId || undefined),
        label_type: labelType || undefined,
        limit: 80,
      })
      setHits(Array.isArray(data?.hits) ? data.hits : [])
      if (!(data?.hits?.length)) setError('无匹配片段')
    } catch (e: any) {
      setError(e.message || '搜索失败')
      setHits([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={s.panel}>
      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 10, color: C.accent }}>按标签搜索片段</div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
        <input
          style={{ ...s.input, flex: 1, minWidth: 160 }}
          value={q}
          onChange={e => setQ(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') runSearch() }}
          placeholder="关键词：种草 / 第一口 / 特写 / V03…"
        />
        <select
          style={{ ...s.input, width: 160 }}
          value={labelType}
          onChange={e => setLabelType(e.target.value)}
        >
          <option value="">全部标签类型</option>
          {types.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <label style={{ fontSize: 11, color: C.muted, display: 'flex', alignItems: 'center', gap: 4 }}>
          <input type="checkbox" checked={scopeAll} onChange={e => setScopeAll(e.target.checked)} />
          搜全部批次
        </label>
        <button style={{ ...s.btn, opacity: loading ? 0.6 : 1 }} onClick={runSearch} disabled={loading}>
          {loading ? '搜索中…' : '搜索'}
        </button>
      </div>
      {error && <div style={{ color: hits.length ? C.muted : C.reject, fontSize: 12, marginBottom: 6 }}>{error}</div>}
      <div style={{ maxHeight: 220, overflowY: 'auto' }}>
        {hits.map(h => (
          <div
            key={`${h.batch_id}-${h.shot_id}`}
            onClick={() => onOpenHit(h)}
            style={{
              display: 'flex', gap: 10, padding: 8, marginBottom: 6, borderRadius: 6,
              background: C.panel2, border: `1px solid ${C.border}`, cursor: 'pointer',
            }}
          >
            {h.keyframe_mid ? (
              <img
                src={h.keyframe_mid.startsWith('http') ? h.keyframe_mid : `http://127.0.0.1:8765${h.keyframe_mid}`}
                alt=""
                style={{ width: 72, height: 40, objectFit: 'cover', borderRadius: 4, background: '#111' }}
              />
            ) : (
              <div style={{ width: 72, height: 40, background: '#111', borderRadius: 4 }} />
            )}
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: 12, fontWeight: 600, wordBreak: 'break-all' }}>
                {h.material_name || h.material_id}
                <span style={{ color: C.muted, fontWeight: 400, marginLeft: 6 }}>
                  {Number(h.start_time).toFixed(2)}–{Number(h.end_time).toFixed(2)}s
                </span>
              </div>
              <div style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>
                {h.batch_id} · {(h.matched_labels || []).slice(0, 4).map(l =>
                  `${l.label_type}:${labelText(l.label_value)}`
                ).join(' · ')}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── ExportButton ──────────────────────────────────────────────────────────────

interface ExportButtonProps {
  batchId: string
}

function ExportButton({ batchId }: ExportButtonProps) {
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [msg, setMsg] = useState('')

  const handleExport = async () => {
    setStatus('loading')
    try {
      const res = await api.triggerExport(batchId)
      setMsg(res.index_csv || res.index_json || res.output_path || res.message || '导出成功')
      setStatus('done')
    } catch (e: any) {
      setMsg(e.message || '导出失败')
      setStatus('error')
    }
  }

  return (
    <div style={{ padding: '12px 0' }}>
      <button
        style={{ ...s.btn, background: status === 'loading' ? C.accentHover : C.accent, width: '100%' }}
        onClick={handleExport}
        disabled={status === 'loading'}
      >
        {status === 'loading' ? '导出中…' : '导出索引'}
      </button>
      {msg && (
        <div style={{ fontSize: 11, marginTop: 6, color: status === 'error' ? C.reject : C.accent, wordBreak: 'break-all' }}>
          {msg}
        </div>
      )}
    </div>
  )
}

// ── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  const { ready, logs } = useBackendReady()
  const [job, setJob] = useState<Job | null>(null)
  const [batchId, setBatchId] = useState('')
  const [selectedMatId, setSelectedMatId] = useState<string | null>(null)
  const [focusShotId, setFocusShotId] = useState<string | null>(null)
  const [fromCache, setFromCache] = useState(false)
  const [batchListKey, setBatchListKey] = useState(0)

  const bumpBatchList = useCallback(() => setBatchListKey(k => k + 1), [])

  const handleJobUpdate = useCallback((updated: Job) => {
    setJob(updated)
    if (updated.status === 'done') {
      setBatchId(batchIdOf(updated))
      setFromCache(false)
      setBatchListKey(k => k + 1)
    }
  }, [])

  const handleCacheLoaded = useCallback((info: { batchId: string; batchPath: string; materialCount: number; shotCount: number }) => {
    setJob(null)
    setBatchId(info.batchId)
    setSelectedMatId(null)
    setFocusShotId(null)
    setFromCache(true)
  }, [])

  const handleJobCreated = useCallback((j: Job) => {
    setJob(j)
    setBatchId(batchIdOf(j))
    setSelectedMatId(null)
    setFocusShotId(null)
    setFromCache(false)
  }, [])

  const handleSelectBatch = useCallback((id: string) => {
    setJob(null)
    setBatchId(id)
    setSelectedMatId(null)
    setFocusShotId(null)
    setFromCache(true)
  }, [])

  const handleDeletedBatch = useCallback((id: string) => {
    setBatchId(prev => {
      if (prev === id) {
        setSelectedMatId(null)
        setFocusShotId(null)
        setJob(null)
        setFromCache(false)
        return ''
      }
      return prev
    })
  }, [])

  const handleSearchHit = useCallback((hit: SearchHit) => {
    setJob(null)
    setBatchId(hit.batch_id)
    setSelectedMatId(hit.material_id)
    setFocusShotId(hit.shot_id)
    setFromCache(true)
    setBatchListKey(k => k + 1)
  }, [])

  if (!ready) return <LoadingScreen logs={logs} />

  const jobDone = job?.status === 'done'
  const showMaterials = Boolean(batchId && (fromCache || jobDone))
  const analyzing = Boolean(job && !jobDone && job.status !== 'failed' && job.status !== 'error')

  return (
    <div style={{ display: 'flex', height: '100vh', background: C.bg, color: C.text, overflow: 'hidden' }}>
      <div style={{ width: 320, minWidth: 260, display: 'flex', flexDirection: 'column', borderRight: `1px solid ${C.border}`, padding: 12, overflowY: 'auto' }}>
        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 16, padding: '4px 0', color: C.accent }}>
          🎬 tag_cut
        </div>

        <BatchLibrary
          selectedId={batchId}
          refreshKey={batchListKey}
          onSelect={handleSelectBatch}
          onDeleted={handleDeletedBatch}
        />

        <BatchPicker
          onCacheLoaded={handleCacheLoaded}
          onJobCreated={handleJobCreated}
          onBatchesChanged={bumpBatchList}
        />

        <ModelsPanel />

        {job && (
          <JobProgress job={job} onJobUpdate={handleJobUpdate} />
        )}

        {fromCache && !job && batchId && (
          <div style={{ ...s.panel, fontSize: 12, color: C.muted }}>
            当前批次 <span style={{ color: C.text }}>{batchId}</span>（独立子目录，切换其他批次不会覆盖）。要覆盖本批次请点「重新生成」。
          </div>
        )}

        {showMaterials && (
          <MaterialList
            batchId={batchId}
            selectedId={selectedMatId}
            onSelect={(id) => { setSelectedMatId(id); setFocusShotId(null) }}
          />
        )}
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 12, overflow: 'hidden' }}>
        <TagSearchPanel batchId={batchId} onOpenHit={handleSearchHit} />
        {selectedMatId && batchId ? (
          <>
            <div style={{ fontWeight: 700, fontSize: 13, color: C.accent, marginBottom: 8 }}>
              镜头时间线 · {batchId}
            </div>
            <ShotViewer batchId={batchId} matId={selectedMatId} focusShotId={focusShotId} />
            <ExportButton batchId={batchId} />
          </>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, color: C.muted, fontSize: 14, textAlign: 'center', padding: 24 }}>
            {analyzing
              ? '分析进行中，请稍候…'
              : showMaterials
                ? '← 选择左侧素材，或上方按标签搜索片段'
                : '← 从「已有批次」切换，或打开输入目录开始分析。每个批次结果在 data/&lt;批次名&gt;/ 独立存放。'}
          </div>
        )}
      </div>
    </div>
  )
}
