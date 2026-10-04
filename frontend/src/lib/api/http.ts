/*
  Tiny fetch wrapper. Base path is relative ("/api/v1"): in dev, Vite proxies it
  to the FastAPI backend (see vite.config.ts); in a same-origin deploy it just works.
*/

export const API_BASE = '/api/v1'

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let detail: unknown
  let message = `${res.status} ${res.statusText}`
  try {
    const body = await res.json()
    detail = body
    // FastAPI conventionally returns { detail: string | object }.
    if (body && typeof body.detail === 'string') {
      message = body.detail
    } else if (Array.isArray(body?.detail)) {
      // pydantic validation errors
      message = body.detail
        .map((e: { loc?: unknown[]; msg?: string }) =>
          [e.loc?.slice(1).join('.'), e.msg].filter(Boolean).join(': '),
        )
        .join('; ')
    }
  } catch {
    // non-JSON error body; keep the status line
  }
  return new ApiError(res.status, message, detail)
}

interface RequestOptions {
  method?: string
  body?: unknown
  // when true, `body` is a FormData and must not be JSON-encoded
  form?: boolean
  signal?: AbortSignal
}

export async function request<T>(
  path: string,
  opts: RequestOptions = {},
): Promise<T> {
  const { method = 'GET', body, form = false, signal } = opts
  const headers: Record<string, string> = {}
  let payload: BodyInit | undefined

  if (form) {
    payload = body as FormData
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: payload,
    signal,
  })

  if (!res.ok) throw await parseError(res)
  if (res.status === 204) return undefined as T
  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
}
