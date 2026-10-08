const trimTrailingSlashes = (value: string) => value.replace(/\/+$/, '')

function resolveApiBaseUrl() {
  const origin = import.meta.env.VITE_API_ORIGIN?.trim()
  const prefix = import.meta.env.VITE_API_PREFIX?.trim()
  const legacy = import.meta.env.VITE_API_BASE_URL?.trim()
  const normalizedPrefix = prefix ? `/${prefix.replace(/^\/+/, '')}` : '/api/v1'

  if (origin || prefix) {
    return `${origin ? trimTrailingSlashes(origin) : ''}${trimTrailingSlashes(normalizedPrefix)}`
  }
  if (legacy) {
    try {
      const parsed = new URL(legacy)
      return parsed.pathname === '/' || parsed.pathname === '' ? `${trimTrailingSlashes(legacy)}/api/v1` : trimTrailingSlashes(legacy)
    } catch {
      return trimTrailingSlashes(legacy)
    }
  }
  return '/api/v1'
}

export const API_BASE_URL = resolveApiBaseUrl()
export const UNAUTHORIZED_EVENT = 'spectwin:unauthorized'

let accessToken: string | null = null

export function setAccessToken(token: string | null) {
  accessToken = token
}

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(message: string, status: number, detail: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

function detailMessage(body: unknown, status: number): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length) {
      const first = detail[0] as { msg?: string; loc?: unknown[] }
      const field = Array.isArray(first.loc) ? first.loc.filter((part) => part !== 'body').join('.') : ''
      return field ? `${field}: ${first.msg ?? 'invalid value'}` : first.msg ?? 'Invalid request'
    }
  }
  if (status === 0) return 'Cannot reach the server. Check that the backend is running.'
  if (status >= 500) return 'The server hit an error. Please try again.'
  return 'Request failed'
}

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  query?: Record<string, string | undefined>
  auth?: boolean
}

async function send(path: string, { method = 'GET', body, query, auth = true }: RequestOptions): Promise<Response> {
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin)
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined) url.searchParams.set(key, value)
  }
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth && accessToken) headers.Authorization = `Bearer ${accessToken}`

  let response: Response
  try {
    response = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  } catch {
    throw new ApiError(detailMessage(null, 0), 0, null)
  }
  if (response.status === 401 && auth) {
    window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT))
  }
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null)
    throw new ApiError(detailMessage(errorBody, response.status), response.status, errorBody)
  }
  return response
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await send(path, options)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export async function requestText(path: string, options: RequestOptions = {}): Promise<{ text: string; filename: string | null }> {
  const response = await send(path, options)
  const disposition = response.headers.get('content-disposition')
  const match = disposition ? /filename="?([^";]+)"?/i.exec(disposition) : null
  return { text: await response.text(), filename: match?.[1] ?? null }
}

export function errorMessage(caught: unknown, fallback = 'Something went wrong'): string {
  return caught instanceof Error && caught.message ? caught.message : fallback
}
