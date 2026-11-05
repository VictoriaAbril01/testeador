import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { useDashboardData } from './useDashboardData'
import { api } from '../services/api'
import type { Dashboard } from '../services/types'

const base: Dashboard = {
  total_projects: 1, total_executions: 1, executions_by_status: { queued: 1 },
  total_findings: 0, findings_pending_confirmation: 0, recent_executions: [], recent_projects: [],
}

afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks() })

it.each(['completed', 'failed', 'cancelled'] as const)('detiene el sondeo al llegar a %s', async (terminal) => {
  vi.useFakeTimers()
  const dashboard = vi.spyOn(api, 'dashboard')
    .mockResolvedValueOnce(base)
    .mockResolvedValueOnce({ ...base, executions_by_status: { running: 1 } })
    .mockResolvedValueOnce({ ...base, executions_by_status: { [terminal]: 1 } })
  const view = renderHook(() => useDashboardData('operator-key'))
  await act(async () => { await Promise.resolve() })
  expect(view.result.current.data?.executions_by_status.queued).toBe(1)
  await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
  expect(view.result.current.data?.executions_by_status.running).toBe(1)
  await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
  expect(view.result.current.data?.executions_by_status[terminal]).toBe(1)
  await act(async () => { await vi.advanceTimersByTimeAsync(15000) })
  expect(dashboard).toHaveBeenCalledTimes(3)
  view.unmount()
  await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
  expect(dashboard).toHaveBeenCalledTimes(3)
})
