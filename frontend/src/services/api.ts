import type { CredentialInput, CredentialReceipt, Dashboard, Evidence, Execution, ExecutionHistory, ExecutionInput, ExecutionStatus, Finding, Project, ProjectInput, RetestComparison, Step, Validation, ValidationStatus } from './types'

const configuredBase = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? ''

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly fields: Array<{ field: string; code: string }> = [],
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

interface ErrorBody {
  error?: { code?: string; message?: string; fields?: Array<{ field: string; code: string }> }
  detail?: string
}

async function request<T>(path: string, token?: string, body?: unknown, signal?: AbortSignal, method?: string, extraHeaders?: Record<string, string>): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${configuredBase}${path}`, {
      method: method ?? (body === undefined ? 'GET' : 'POST'),
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...extraHeaders,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
      cache: 'no-store',
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'network_error', 'No se pudo conectar con la API de TestLab.')
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as ErrorBody
    const code = payload.error?.code ?? 'request_failed'
    const message = payload.error?.message ?? payload.detail ?? `La solicitud falló (${response.status}).`
    throw new ApiError(response.status, code, message, payload.error?.fields ?? [])
  }
  return response.json() as Promise<T>
}

async function download(path: string, token: string): Promise<Blob> {
  let response: Response
  try {
    response = await fetch(`${configuredBase}${path}`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' })
  } catch {
    throw new ApiError(0, 'network_error', 'No se pudo conectar con la API de TestLab.')
  }
  if (!response.ok) throw new ApiError(response.status, 'download_failed', `La descarga falló (${response.status}).`)
  return response.blob()
}

export function friendlyError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'La clave de operador no es válida. Vuelve a conectarte.'
    if (error.status === 404) return 'El recurso solicitado ya no existe o el identificador no es correcto.'
    if (error.status === 503) return 'La API o la base de datos no están disponibles. Inténtalo de nuevo.'
    if (error.status === 422) {
      const fields = error.fields.map((item) => item.field.replace(/^body\./, '')).filter(Boolean)
      return fields.length ? `Revisa los datos enviados: ${fields.join(', ')}.` : 'Revisa los datos del formulario y el alcance autorizado.'
    }
    if (error.code === 'network_error') return error.message
    return error.message
  }
  return 'Ocurrió un error inesperado. Inténtalo de nuevo.'
}

export function validateHttpUrl(value: string, originOnly = false): string | null {
  try {
    const url = new URL(value.trim())
    if (!['http:', 'https:'].includes(url.protocol)) return 'Usa una URL HTTP o HTTPS.'
    if (url.username || url.password || url.search || url.hash) return 'La URL no debe incluir credenciales, parámetros ni fragmentos.'
    if (originOnly && url.pathname !== '/') return 'El origen autorizado no debe incluir una ruta.'
    return null
  } catch {
    return 'Introduce una URL válida.'
  }
}

export function canonicalOrigin(value: string): string {
  const url = new URL(value.trim())
  const port = url.port || (url.protocol === 'https:' ? '443' : '80')
  return `${url.protocol}//${url.hostname}:${port}`
}

export const api = {
  health: (signal?: AbortSignal) => request<{ status: string }>('/health', undefined, undefined, signal),
  dashboard: (token: string, signal?: AbortSignal) => request<Dashboard>('/api/v1/dashboard', token, undefined, signal),
  projectsPage: (token: string, limit = 100, offset = 0, signal?: AbortSignal) =>
    request<Project[]>(`/api/v1/projects?limit=${limit}&offset=${offset}`, token, undefined, signal),
  async allProjects(token: string, signal?: AbortSignal): Promise<Project[]> {
    const projects: Project[] = []
    while (true) {
      const page = await this.projectsPage(token, 100, projects.length, signal)
      projects.push(...page)
      if (page.length < 100) return projects
    }
  },
  project: (token: string, id: string, signal?: AbortSignal) =>
    request<Project>(`/api/v1/projects/${encodeURIComponent(id)}`, token, undefined, signal),
  createProject: (token: string, data: ProjectInput) => request<Project>('/api/v1/projects', token, data),
  configureCredentials: (token: string, id: string, data: CredentialInput) =>
    request<CredentialReceipt>(`/api/v1/projects/${encodeURIComponent(id)}/credentials`, token, data),
  createExecution: (token: string, data: ExecutionInput, key?: string) => request<Execution>('/api/v1/executions', token, data, undefined, undefined,
    key ? { 'Idempotency-Key': key } : undefined),
  executions: (token: string, limit = 100, offset = 0, signal?: AbortSignal) =>
    request<Execution[]>(`/api/v1/executions?limit=${limit}&offset=${offset}`, token, undefined, signal),
  executionHistory: (token: string, options: { limit: number; offset: number; projectId?: string; status?: ExecutionStatus }, signal?: AbortSignal) => {
    const params = new URLSearchParams({ limit: String(options.limit), offset: String(options.offset) })
    if (options.projectId) params.set('project_id', options.projectId)
    if (options.status) params.set('status', options.status)
    return request<ExecutionHistory>(`/api/v1/executions/history?${params}`, token, undefined, signal)
  },
  execution: (token: string, id: string, signal?: AbortSignal) =>
    request<Execution>(`/api/v1/executions/${encodeURIComponent(id)}`, token, undefined, signal),
  cancelExecution: (token: string, id: string) => request<Execution>(`/api/v1/executions/${encodeURIComponent(id)}/cancel`, token, {}),
  retryExecution: (token: string, id: string, key?: string) => request<Execution>(`/api/v1/executions/${encodeURIComponent(id)}/retry`, token, {}, undefined, undefined,
    key ? { 'Idempotency-Key': key } : undefined),
  findings: (token: string, id: string, limit = 100, offset = 0, signal?: AbortSignal) =>
    request<Finding[]>(`/api/v1/executions/${encodeURIComponent(id)}/findings?limit=${limit}&offset=${offset}`, token, undefined, signal),
  steps: (token: string, id: string, limit = 100, offset = 0, signal?: AbortSignal) =>
    request<Step[]>(`/api/v1/executions/${encodeURIComponent(id)}/steps?limit=${limit}&offset=${offset}`, token, undefined, signal),
  finding: (token: string, id: string, signal?: AbortSignal) =>
    request<Finding>(`/api/v1/findings/${encodeURIComponent(id)}`, token, undefined, signal),
  incidents: (token: string, limit = 100, offset = 0, signal?: AbortSignal) =>
    request<Finding[]>(`/api/v1/findings?limit=${limit}&offset=${offset}`, token, undefined, signal),
  evidence: (token: string, id: string, signal?: AbortSignal) =>
    request<Evidence[]>(`/api/v1/findings/${encodeURIComponent(id)}/evidence`, token, undefined, signal),
  evidenceFile: (token: string, id: string) => download(`/api/v1/evidence/${encodeURIComponent(id)}`, token),
  validations: (token: string, id: string, signal?: AbortSignal) =>
    request<Validation[]>(`/api/v1/findings/${encodeURIComponent(id)}/validations`, token, undefined, signal),
  validate: (token: string, id: string, status: ValidationStatus, notes: string) =>
    request<Validation>(`/api/v1/findings/${encodeURIComponent(id)}/validations`, token, { status, notes }),
  history: (token: string, id: string, signal?: AbortSignal) =>
    request<Finding[]>(`/api/v1/findings/${encodeURIComponent(id)}/history`, token, undefined, signal),
  retest: (token: string, id: string, key?: string) => request<Execution>(`/api/v1/executions/${encodeURIComponent(id)}/retest`, token, {}, undefined, undefined,
    key ? { 'Idempotency-Key': key } : undefined),
  comparison: (token: string, id: string, signal?: AbortSignal) =>
    request<RetestComparison>(`/api/v1/executions/${encodeURIComponent(id)}/comparison`, token, undefined, signal),
  report: (token: string, id: string) => download(`/api/v1/executions/${encodeURIComponent(id)}/report`, token),
}
