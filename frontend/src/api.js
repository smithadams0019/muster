// Thin fetch client for the Muster API. One function per route. No caching,
// no retry policy, no business logic — the store decides what a response
// means; this file only knows how to ask for it.

const BASE = import.meta.env.VITE_MUSTER_API || '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = ''
    try {
      const body = await res.json()
      detail = body?.detail ? ` — ${body.detail}` : ''
    } catch {
      // response wasn't JSON; fall through with no detail
    }
    throw new Error(`${options.method || 'GET'} ${path} failed: ${res.status}${detail}`)
  }
  if (res.status === 204) return null
  return res.json()
}

export function getWorld() {
  return request('/world')
}

export function getSchedule(siteId) {
  return request(`/schedule/${encodeURIComponent(siteId)}`)
}

export function draftWeek(siteId) {
  return request(`/draft/${encodeURIComponent(siteId)}`, { method: 'POST' })
}

export function reportDisruption(body) {
  return request('/disruptions', { method: 'POST', body: JSON.stringify(body) })
}

export function getDecisions() {
  return request('/decisions')
}

export function answerDecision(id, body) {
  return request(`/decisions/${encodeURIComponent(id)}/answer`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function getConsent() {
  return request('/consent')
}

export function answerConsent(id, body) {
  return request(`/consent/${encodeURIComponent(id)}/answer`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function getReceipts() {
  return request('/receipts')
}

export function getTimeline() {
  return request('/timeline')
}

export function getAutonomy() {
  return request('/autonomy')
}

export function setAutonomy(level) {
  return request('/autonomy', { method: 'PUT', body: JSON.stringify({ level }) })
}

export function receiptsCsvUrl() {
  return `${BASE}/receipts.csv`
}
