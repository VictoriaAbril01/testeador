import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { AppProvider } from '../hooks/useAppState'
import { api } from '../services/api'
import type { Dashboard } from '../services/types'
import { DashboardPage } from './DashboardPage'

const empty: Dashboard = {
  total_projects: 0, total_executions: 0, executions_by_status: {}, total_findings: 0,
  findings_pending_confirmation: 0, recent_executions: [], recent_projects: [],
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

it('carga el resumen persistido, muestra vacíos y reintenta la consulta', async () => {
  const dashboard = vi.spyOn(api, 'dashboard').mockResolvedValueOnce(empty).mockResolvedValueOnce({
    ...empty, total_projects: 2, total_executions: 1, total_findings: 3,
  })
  render(<MemoryRouter><AppProvider><DashboardPage /></AppProvider></MemoryRouter>)
  expect(await screen.findByText('No hay proyectos')).toBeTruthy()
  expect(screen.getByText('No hay ejecuciones')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Actualizar' }))
  expect(await screen.findByText('2')).toBeTruthy()
  expect(dashboard).toHaveBeenCalledTimes(2)
})

it('muestra fallo de conexión y permite reintentar', async () => {
  const dashboard = vi.spyOn(api, 'dashboard').mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(empty)
  render(<MemoryRouter><AppProvider><DashboardPage /></AppProvider></MemoryRouter>)
  expect(await screen.findByText('No se pudieron cargar los datos')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
  expect(await screen.findByText('No hay proyectos')).toBeTruthy()
  expect(dashboard).toHaveBeenCalledTimes(2)
})
