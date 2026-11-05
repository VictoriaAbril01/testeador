import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, friendlyError } from '../services/api'
import type { Execution, Project } from '../services/types'

interface AppState {
  token: string
  connected: boolean
  connect: (key: string) => Promise<void>
  disconnect: () => void
  projects: Project[]
  projectsLoading: boolean
  projectsError: string | null
  refreshProjects: () => void
  runs: Execution[]
  rememberRun: (run: Execution) => void
  refreshRun: (id: string) => Promise<Execution>
}

const Context = createContext<AppState | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState('')
  const [projects, setProjects] = useState<Project[]>([])
  const [projectsLoading, setProjectsLoading] = useState(false)
  const [projectsError, setProjectsError] = useState<string | null>(null)
  const [projectsVersion, setProjectsVersion] = useState(0)
  const [runs, setRuns] = useState<Execution[]>([])

  const connect = useCallback(async (key: string) => {
    await api.projectsPage(key.trim(), 1)
    setProjects([])
    setRuns([])
    setToken(key.trim())
  }, [])

  const disconnect = useCallback(() => {
    setToken('')
    setProjects([])
    setRuns([])
    setProjectsError(null)
  }, [])

  useEffect(() => {
    if (!token) return
    const controller = new AbortController()
    setProjectsLoading(true)
    setProjectsError(null)
    api.allProjects(token, controller.signal).then((items) => {
      if (!controller.signal.aborted) setProjects(items)
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setProjectsError(friendlyError(error))
    }).finally(() => {
      if (!controller.signal.aborted) setProjectsLoading(false)
    })
    return () => controller.abort()
  }, [token, projectsVersion])

  const refreshProjects = useCallback(() => setProjectsVersion((value) => value + 1), [])
  const rememberRun = useCallback((run: Execution) => {
    setRuns((current) => [run, ...current.filter((item) => item.id !== run.id)].slice(0, 20))
  }, [])
  const refreshRun = useCallback(async (id: string) => {
    const run = await api.execution(token, id)
    rememberRun(run)
    return run
  }, [token, rememberRun])

  const value = useMemo(() => ({
    token, connected: Boolean(token), connect, disconnect, projects, projectsLoading,
    projectsError, refreshProjects, runs, rememberRun, refreshRun,
  }), [token, connect, disconnect, projects, projectsLoading, projectsError, refreshProjects, runs, rememberRun, refreshRun])

  return <Context.Provider value={value}>{children}</Context.Provider>
}

export function useAppState(): AppState {
  const state = useContext(Context)
  if (!state) throw new Error('AppProvider is missing')
  return state
}
