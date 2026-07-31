// 与后端通信的 API 封装（开发环境由 vite 代理转发 /api 到 :8000）
const BASE = ''

export async function getSamples() {
  const r = await fetch(`${BASE}/api/samples`)
  return r.json()
}

export async function generate(config, files) {
  const fd = new FormData()
  fd.append('config', JSON.stringify(config))
  for (const f of files) {
    fd.append('files', f, f.name)
  }
  const r = await fetch(`${BASE}/api/generate`, { method: 'POST', body: fd })
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${r.status}`)
  }
  return r.json()
}

export async function getTask(id) {
  const r = await fetch(`${BASE}/api/tasks/${id}`)
  return r.json()
}

export function downloadUrl(id) {
  return `${BASE}/api/download/${id}`
}
