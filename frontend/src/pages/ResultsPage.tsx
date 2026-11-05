import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowRight, Search } from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { EmptyState, ErrorState, LoadingState, PageHeading, Panel, StatusBadge, formatDate, shortId } from '../components/UI'
import { useAppState } from '../hooks/useAppState'
import { useResource } from '../hooks/useResource'
import { api, friendlyError } from '../services/api'
import type { ExecutionHistory, ExecutionStatus, Finding } from '../services/types'

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export function ResultsPage() {
  const { token, projects } = useAppState()
  const [params, setParams] = useSearchParams()
  const projectId = params.get('project_id') ?? ''
  const status = params.get('status') ?? ''
  const offset = Math.max(0, Number(params.get('offset') ?? 0) || 0)
  const pageSize = 20
  const load = useCallback((signal: AbortSignal): Promise<ExecutionHistory> =>
    api.executionHistory(token, { limit: pageSize, offset, projectId, status: status as ExecutionStatus }, signal),
  [token, offset, projectId, status])
  const runs = useResource(load)
  const changeFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    next.delete('offset')
    setParams(next)
  }
  const changePage = (nextOffset: number) => {
    const next = new URLSearchParams(params)
    next.set('offset', String(nextOffset))
    setParams(next)
  }
  const incidents = useResource(useCallback(async (signal: AbortSignal): Promise<Finding[]> => {
    const result: Finding[] = []
    while (true) {
      const page = await api.incidents(token, 100, result.length, signal)
      result.push(...page)
      if (page.length < 100) return result
    }
  }, [token]))
  const [moduleFilter, setModuleFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const visible = incidents.data?.filter((item) => (!moduleFilter || item.module_name === moduleFilter) &&
    (!typeFilter || item.error_type === typeFilter) && (!statusFilter || item.validation_status === statusFilter)) ?? []
  const navigate = useNavigate()
  const [id, setId] = useState('')
  const [error, setError] = useState('')
  function submit(event: FormEvent) {
    event.preventDefault()
    if (!uuid.test(id.trim())) { setError('Introduce un identificador UUID completo de ejecución.'); return }
    navigate(`/executions/${id.trim()}`)
  }
  return <div className="page-stack"><PageHeading eyebrow="EJECUCIONES / RESULTADOS" title="Resultados" description="Historial de ejecuciones registrado en TestLab." />
    <Panel title="Buscar ejecución" subtitle="Introduce el ID completo que aparece en su detalle"><form className="search-form" onSubmit={submit}><div className="search-input"><Search size={18} /><input aria-label="ID de ejecución" value={id} onChange={(event) => { setId(event.target.value); setError('') }} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" /></div><button className="button button-primary" type="submit">Consultar <ArrowRight size={16} /></button></form>{error && <div className="form-error" role="alert">{error}</div>}</Panel>
    <Panel title="Historial de ejecuciones" subtitle={runs.data ? `${runs.data.total} registros en PostgreSQL` : undefined}>
      <div className="filter-row">
        <label>Proyecto<select aria-label="Filtrar proyecto" value={projectId} onChange={(event) => changeFilter('project_id', event.target.value)}><option value="">Todos</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
        <label>Estado<select aria-label="Filtrar estado" value={status} onChange={(event) => changeFilter('status', event.target.value)}><option value="">Todos</option>{(['pending', 'queued', 'running', 'cancelling', 'completed', 'failed', 'cancelled'] as ExecutionStatus[]).map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <button className="button button-secondary" onClick={runs.reload}>Actualizar</button>
      </div>
      {runs.loading ? <LoadingState /> : runs.error ? <ErrorState message={friendlyError(runs.error)} onRetry={runs.reload} /> : runs.data?.items.length ? <>
        <div className="list-rows">{runs.data.items.map((run) => <Link className="list-row" key={run.id} to={`/executions/${run.id}`}><span className="list-main"><b>{run.project_name} · {run.modality}</b><small>ID: {run.id}</small><small>Inicio: {formatDate(run.started_at)} · Fin: {formatDate(run.finished_at)} · {run.finding_count} hallazgos</small>{run.retry_of_run_id && <small>Reintento de #{shortId(run.retry_of_run_id)}</small>}{run.retest_of_run_id && <small>Retest de #{shortId(run.retest_of_run_id)}</small>}</span><StatusBadge status={run.status} /><ArrowRight size={16} /></Link>)}</div>
        <div className="filter-row"><button className="button button-secondary" disabled={offset === 0} onClick={() => changePage(Math.max(0, offset - pageSize))}>Anterior</button><span>Página {Math.floor(offset / pageSize) + 1} de {Math.ceil(runs.data.total / pageSize)}</span><button className="button button-secondary" disabled={offset + pageSize >= runs.data.total} onClick={() => changePage(offset + pageSize)}>Siguiente</button></div>
      </> : <EmptyState title="No hay ejecuciones registradas" description="Crea una ejecución para ver aquí su historial o cambia los filtros." actionLabel="Nueva ejecución" actionTo="/executions/new" />}
    </Panel>
    <Panel title="Incidencias" subtitle="Hallazgos persistidos de todas las ejecuciones">{incidents.loading ? <LoadingState /> : incidents.error ? <ErrorState message={friendlyError(incidents.error)} onRetry={incidents.reload} /> : incidents.data?.length ? <><div className="filter-row"><label>Módulo<select value={moduleFilter} onChange={(event) => setModuleFilter(event.target.value)}><option value="">Todos</option>{[...new Set(incidents.data.map((item) => item.module_name).filter((value): value is string => Boolean(value)))].map((value) => <option key={value}>{value}</option>)}</select></label><label>Tipo<select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="">Todos</option>{[...new Set(incidents.data.map((item) => item.error_type))].map((value) => <option key={value}>{value}</option>)}</select></label><label>Estado<select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="">Todos</option>{[...new Set(incidents.data.map((item) => item.validation_status))].map((value) => <option key={value}>{value}</option>)}</select></label></div>{visible.length ? <div className="list-rows">{visible.map((item) => <Link className="list-row" key={item.id} to={`/executions/${item.run_id}/findings/${item.id}`}><span className="list-main"><b>{item.error_type} · {item.validation_status}</b><small>{item.module_name ?? 'Sin módulo'} · {item.page_name ?? 'Sin pantalla'} · {formatDate(item.created_at)}</small></span><ArrowRight size={16} /></Link>)}</div> : <EmptyState title="Sin coincidencias" description="Ajusta los filtros para ver otras incidencias." />}</> : <EmptyState title="Sin incidencias" description="Aún no se han registrado hallazgos." />}</Panel></div>
}
