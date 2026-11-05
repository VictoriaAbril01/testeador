import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, canonicalOrigin, friendlyError, validateHttpUrl } from './api'

afterEach(() => vi.unstubAllGlobals())

describe('validación de alcance', () => {
  it('rechaza esquemas inseguros, secretos y rutas en orígenes', () => {
    expect(validateHttpUrl('file:///tmp/example')).toBeTruthy()
    expect(validateHttpUrl('https://user:pass@example.com')).toBeTruthy()
    expect(validateHttpUrl('https://example.com/?token=abc')).toBeTruthy()
    expect(validateHttpUrl('https://example.com/login', true)).toBeTruthy()
    expect(validateHttpUrl('https://example.com/login')).toBeNull()
    expect(canonicalOrigin('https://example.com/login')).toBe('https://example.com:443')
  })
})

describe('cliente HTTP', () => {
  it('envía la clave solo como cabecera y consulta proyectos reales', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    expect(await api.projectsPage('secret-key', 1)).toEqual([])
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/projects?limit=1&offset=0')
    expect(options.headers.Authorization).toBe('Bearer secret-key')
    expect(JSON.stringify(options)).not.toContain('localStorage')
  })

  it('maneja errores de red sin mostrar datos enviados', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('password=secret-value')))
    await expect(api.createProject('operator-key', { name: 'A', base_url: 'https://example.com', environment: 'staging', modality: 'blackbox', authorized_origins: ['https://example.com'] })).rejects.toMatchObject({ code: 'network_error', status: 0 })
    const error = await api.health().catch((reason: unknown) => reason)
    expect(error).toBeInstanceOf(ApiError)
    expect(friendlyError(error)).not.toContain('secret-value')
  })
})
