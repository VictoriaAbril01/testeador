import { useCallback, useEffect, useState } from 'react'
import { api } from '../services/api'
import type { Dashboard } from '../services/types'

const activeStatuses = ['queued', 'running', 'cancelling'] as const

export function useDashboardData(token: string) {
  const [data, setData] = useState<Dashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)
  const [version, setVersion] = useState(0)
  const reload = useCallback(() => setVersion((current) => current + 1), [])

  useEffect(() => {
    let stopped = false
    let controller: AbortController | null = null
    let timer: ReturnType<typeof setTimeout> | null = null
    let poll = false

    async function load(initial: boolean) {
      controller = new AbortController()
      if (initial) setLoading(true)
      try {
        const snapshot = await api.dashboard(token, controller.signal)
        if (stopped || controller.signal.aborted) return
        setData(snapshot)
        setError(null)
        poll = activeStatuses.some((status) => (snapshot.executions_by_status[status] ?? 0) > 0)
      } catch (reason) {
        if (!stopped && !controller.signal.aborted) setError(reason)
      } finally {
        if (!stopped && !controller.signal.aborted) {
          if (initial) setLoading(false)
          if (poll) timer = setTimeout(() => { void load(false) }, 5000)
        }
      }
    }

    void load(true)
    return () => {
      stopped = true
      if (timer) clearTimeout(timer)
      controller?.abort()
    }
  }, [token, version])

  return { data, loading, error, reload }
}
