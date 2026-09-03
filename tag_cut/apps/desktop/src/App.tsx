import React, { useState, useEffect, useCallback } from 'react'
import * as api from './api'

// ── Types ────────────────────────────────────────────────────────────────────

interface Job {
  job_id: string
  status: string
  batch_id?: string
  progress?: { layer: string; done: number; total: number }[]
  error?: string
}

interface Material {
  material_id: string
  file_name: string
}

interface Shot {
  shot_id: string
  start_time: number
  end_time: number
  is_rejected: boolean
  quality_grade?: string
  keyframe_mid?: string
  labels?: { layer: string; value: string }[]
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

function useBackendReady(): boolean {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      while (!cancelled) {
        try {
          await api.health()
          if (!cancelled) setReady(true)
          return
        } catch {
          await new Promise(r => setTimeout(r, 1000))
        }
      }
    }
    poll()
    return () => { cancelled = true }
  }, [])
  return ready
}

// ── LoadingScreen ─────────────────────────────────────────────────────────────

function LoadingScreen() {
  const [dots, setDots] = useState('.')
  useEffect(() => {
    const t = setInterval(() => setDots(d => d.length >= 3 ? '.' : d + '.'), 500)
    return () => clearInterval(t)
  }, [])
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', background: C.bg, color: C.text }}>
      <div style={{ fontSize: 32, marginBottom: 16 }}>🎬</div>
      <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>tag_cut</div>
      <div style={{ color: C.muted, fontSize: 14 }}>正在启动后台服务{dots}</div>
    </div>
  )
}

// ── BatchPicker ───────────────────────────────────────────────────────────────

interface BatchPickerProps {
  onJobCreated: (job: Job) => void
}

function BatchPicker({ onJobCreated }: BatchPickerProps) {
  const [batchPath, setBatchPath] = useState('../input/8月第60条信息流')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleAnalyse = async () => {
    setLoading(true)
    setError('')
    try {
      const job = await api.createJob(batchPath)
      if (job.detail) throw new Error(job.detail)
      onJobCreated(job)
    } catch (e: any) {
      setError(e.message || '提交失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={s.panel}>
      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 12, color: C.accent }}>批次选择</div>
      <label style={s.label}>批次路径</label>
      <input
        style={{ ...s.input, marginBottom: 10 }}
        value={batchPath}
        onChange={e => setBatchPath(e.target.value)}
        placeholder="../input/8月第60条信息流"
      />
      <button
        style={{ ...s.btn, opacity: loading ? 0.6 : 1 }}
        onClick={handleAnalyse}
        disabled={loading}
      >
        {loading ? '提交中…' : '开始分析'}
      </button>
      {error && <div style={{ color: C.reject, fontSize: 12, marginTop: 8 }}>{error}</div>}
    </div>
  )
}

// ── JobProgress ───────────────────────────────────────────────────────────────

interface JobProgressProps {
  job: Job
  onJobUpdate: (job: Job) => void
}

function JobProgress({ job, onJobUpdate }: JobProgressProps) {
  useEffect(() => {
    if (job.status === 'done' || job.status === 'error') return
    const interval = setInterval(async () => {
      try {
        const updated = await api.getJob(job.job_id)
        onJobUpdate(updated)
      } catch {}
    }, 2000)
    return () => clearInterval(interval)
  }, [job.job_id, job.status, onJobUpdate])

  const statusColor = job.status === 'done' ? C.accent : job.status === 'error' ? C.reject : '#f4a261'

  return (
    <div style={s.panel}>
      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 10, color: C.accent }}>任务进度</div>
      <div style={{ fontSize: 12, marginBottom: 8 }}>
        <span style={{ color: C.muted }}>ID: </span>
        <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{job.job_id.slice(0, 16)}…</span>
      </div>
      <div style={{ fontSize: 13, marginBottom: 8 }}>
        <span style={{ color: C.muted }}>状态: </span>
        <span style={{ color: statusColor, fontWeight: 600 }}>{job.status}</span>
      </div>
      {job.error && <div style={{ color: C.reject, fontSize: 12, marginBottom: 8 }}>{job.error}</div>}
      {job.progress && job.progress.map(p => (
        <div key={p.layer} style={{ marginBottom: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: C.muted, marginBottom: 3 }}>
            <span>{p.layer}</span>
            <span>{p.done}/{p.total}</span>
          </div>
          <div style={{ height: 4, background: '#2a2a2a', borderRadius: 2 }}>
            <div style={{
              height: '100%',
              width: `${p.total > 0 ? (p.done / p.total) * 100 : 0}%`,
              background: C.accent,
              borderRadius: 2,
              transition: 'width 0.3s',
            }} />
          </div>
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
      .then(data => setMaterials(Array.isArray(data) ? data : data.materials || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [batchId])

  return (
    <div style={s.panel}>
      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 10, color: C.accent }}>素材列表</div>
      {loading && <div style={{ color: C.muted, fontSize: 12 }}>加载中…</div>}
      {materials.map(m => (
        <div
          key={m.material_id}
          onClick={() => onSelect(m.material_id)}
          style={{
            padding: '8px 10px',
            borderRadius: 6,
            cursor: 'pointer',
            fontSize: 12,
            marginBottom: 4,
            background: selectedId === m.material_id ? C.accent + '22' : 'transparent',
            border: selectedId === m.material_id ? `1px solid ${C.accent}` : `1px solid transparent`,
            color: selectedId === m.material_id ? C.text : C.muted,
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
}

function ShotViewer({ batchId, matId }: ShotViewerProps) {
  const [shots, setShots] = useState<Shot[]>([])
  const [loading, setLoading] = useState(true)

  const loadShots = useCallback(() => {
    setLoading(true)
    api.getMaterial(batchId, matId)
      .then(data => setShots(Array.isArray(data) ? data : data.shots || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [batchId, matId])

  useEffect(() => { loadShots() }, [loadShots])

  const toggleReject = async (shot: Shot) => {
    try {
      await api.patchShot(shot.shot_id, { is_rejected: !shot.is_rejected })
      setShots(prev => prev.map(s => s.shot_id === shot.shot_id ? { ...s, is_rejected: !s.is_rejected } : s))
    } catch {}
  }

  if (loading) return <div style={{ color: C.muted, fontSize: 12, padding: 16 }}>加载镜头中…</div>

  return (
    <div style={{ overflowY: 'auto', flex: 1 }}>
      {shots.map(shot => (
        <div key={shot.shot_id} style={{
          ...s.panel,
          border: shot.is_rejected ? `1px solid ${C.reject}44` : `1px solid ${C.border}`,
          opacity: shot.is_rejected ? 0.6 : 1,
        }}>
          <div style={{ display: 'flex', gap: 12 }}>
            {/* Keyframe */}
            <div style={{ flexShrink: 0 }}>
              {shot.keyframe_mid ? (
                <img
                  src={`http://localhost:8765${shot.keyframe_mid}`}
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

            {/* Info */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                <div style={{ fontSize: 11, color: C.muted }}>
                  {shot.start_time.toFixed(2)}s — {shot.end_time.toFixed(2)}s
                  <span style={{ marginLeft: 8, color: C.text }}>{(shot.end_time - shot.start_time).toFixed(2)}s</span>
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

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 4 }}>
                {shot.quality_grade && (
                  <span style={{ ...s.tag, color: C.accent, borderColor: C.accent + '44' }}>
                    质量: {shot.quality_grade}
                  </span>
                )}
                {shot.labels && shot.labels.map((lbl, i) => (
                  <span key={i} style={s.tag}>{lbl.layer}: {lbl.value}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
      ))}
      {shots.length === 0 && <div style={{ color: C.muted, fontSize: 12, padding: 16 }}>暂无镜头数据</div>}
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
      setMsg(res.output_path || res.message || '导出成功')
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
  const ready = useBackendReady()
  const [job, setJob] = useState<Job | null>(null)
  const [selectedMatId, setSelectedMatId] = useState<string | null>(null)

  const handleJobUpdate = useCallback((updated: Job) => {
    setJob(updated)
  }, [])

  if (!ready) return <LoadingScreen />

  const batchId = job?.batch_id ?? ''
  const jobDone = job?.status === 'done'

  return (
    <div style={{ display: 'flex', height: '100vh', background: C.bg, color: C.text, overflow: 'hidden' }}>
      {/* Left column */}
      <div style={{ width: 320, minWidth: 260, display: 'flex', flexDirection: 'column', borderRight: `1px solid ${C.border}`, padding: 12, overflowY: 'auto' }}>
        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 16, padding: '4px 0', color: C.accent }}>
          🎬 tag_cut
        </div>

        <BatchPicker onJobCreated={j => { setJob(j); setSelectedMatId(null) }} />

        {job && (
          <JobProgress job={job} onJobUpdate={handleJobUpdate} />
        )}

        {job && jobDone && batchId && (
          <MaterialList
            batchId={batchId}
            selectedId={selectedMatId}
            onSelect={setSelectedMatId}
          />
        )}
      </div>

      {/* Right column */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 12, overflow: 'hidden' }}>
        {selectedMatId && batchId ? (
          <>
            <div style={{ fontWeight: 700, fontSize: 13, color: C.accent, marginBottom: 8 }}>镜头时间线</div>
            <ShotViewer batchId={batchId} matId={selectedMatId} />
            <ExportButton batchId={batchId} />
          </>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, color: C.muted, fontSize: 14 }}>
            {job ? (jobDone ? '← 选择左侧素材查看镜头' : '分析进行中，请稍候…') : '← 输入批次路径并开始分析'}
          </div>
        )}
      </div>
    </div>
  )
}
