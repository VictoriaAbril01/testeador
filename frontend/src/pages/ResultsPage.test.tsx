import { afterEach, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { AppProvider } from '../hooks/useAppState'
import { ResultsPage } from './ResultsPage'
import { api } from '../services/api'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

it('muestra historial vacío de API y valida el ID antes de consultar', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => Promise.resolve({ ok: true,
    json: async () => url.includes('/history') ? { total: 0, limit: 20, offset: 0, items: [] } : [],
  })))
  render(<MemoryRouter><AppProvider><ResultsPage /></AppProvider></MemoryRouter>)
  expect(await screen.findByText('No hay ejecuciones registradas')).toBeTruthy()
  fireEvent.change(screen.getByLabelText('ID de ejecución'), { target: { value: 'invalido' } })
  fireEvent.click(screen.getByText('Consultar'))
  expect(screen.getByRole('alert').textContent).toContain('UUID completo')
})

it('pagina el historial desde la API y conserva el filtro en la consulta', async () => {
  const run = { id: '11111111-1111-4111-8111-111111111111', project_id: '22222222-2222-4222-8222-222222222222',
    project_name: 'Portal', modality: 'blackbox', status: 'completed', requested_at: '2026-10-13T12:00:00Z',
    started_at: '2026-10-13T12:00:00Z', finished_at: '2026-10-13T12:01:00Z', finding_count: 2,
    retest_of_run_id: null, retry_of_run_id: null } as const
  const history = vi.spyOn(api, 'executionHistory').mockImplementation(async (_token, options) => ({
    total: 21, limit: 20, offset: options.offset, items: [run],
  }))
  vi.spyOn(api, 'incidents').mockResolvedValue([])
  render(<MemoryRouter><AppProvider><ResultsPage /></AppProvider></MemoryRouter>)
  expect(await screen.findByText('Portal · blackbox')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
  expect(await screen.findByText('Página 2 de 2')).toBeTruthy()
  expect(history).toHaveBeenLastCalledWith('', expect.objectContaining({ offset: 20, limit: 20 }), expect.any(AbortSignal))
  fireEvent.change(screen.getByLabelText('Filtrar estado'), { target: { value: 'completed' } })
  expect(await screen.findByText('Página 1 de 2')).toBeTruthy()
  expect(history).toHaveBeenLastCalledWith('', expect.objectContaining({ offset: 0, status: 'completed' }), expect.any(AbortSignal))
})
