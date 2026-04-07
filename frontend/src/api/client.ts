/**
 * Thin HTTP layer — all backend calls go through here (single place for base URL & errors).
 */
async function parseError(res: Response): Promise<string> {
  const t = await res.text()
  try {
    const j = JSON.parse(t) as { detail?: string | unknown }
    if (typeof j.detail === 'string') return j.detail
    return t || res.statusText
  } catch {
    return t || res.statusText
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}
