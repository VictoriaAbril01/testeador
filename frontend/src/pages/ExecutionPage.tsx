import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, Bug, Download, RefreshCw } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router'
import { EmptyState, ErrorState, LoadingState, Notice, PageHeading, Panel, SeverityBadge, StatusBadge, formatDate, shortId } from '../components/UI'
import { useAppState } from '../hooks/useAppState'
import { useResource } from '../hooks/useResource'
import { api, friendlyError } from '../services/api'
import type { Finding, RetestComparison, Step } from '../services/types'

async function allPages<T>(getPage: (offset: number, signal: AbortSignal) => Promise<T[]>, signal: AbortSignal): Promise<T[]> {
  const result: T[] = []
  while (true) {
    const page = await getPage(result.length, signal)
    result.push(...page)
    if (page.length < 100) return result
  }
}

export function ExecutionPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const { token, projects, rememberRun } = useAppState()
  const run = useResource(useCallback((signal: AbortSignal) => api.execution(token, id, signal), [token, id]))
  const findings = useResource(useCallback((signal: AbortSignal) => allPages<Finding>((offset, abort) => api.findings(token, id, 100, offset, abort), signal), [token, id]))
  const steps = useResource(useCallback((signal: AbortSignal) => allPages<Step>((offset, abort) => api.steps(token, id, 100, offset, abort), signal), [token, id]))
  const comparison = useResource(useCallback((signal: AbortSignal): Promise<RetestComparison | null> =>
    run.data?.retest_of_run_id ? api.comparison(token, id, signal) : Promise.resolve(null), [token, id, run.data?.retest_of_run_id]))
  const [tab, setTab] = useState<'findings' | 'steps'>('findings')
  const [moduleFilter, setModuleFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [actionError, setActionError] = useState('')
  const [busy, setBusy] = useState(false)
  const retestKey = useRef(crypto.randomUUID())
  const retryKey = useRef(crypto.randomUUID())
  useEffect(() => { if (run.data) rememberRun(run.data) }, [run.data, rememberRun])
  const status = run.data?.status
  useEffect(() => {
    if (status !== 'queued' && status !== 'running' && status !== 'cancelling') return
    const timer = setInterval(() => run.reload(), 5000)
    return () => clearInterval(timer)
  }, [status, run.reload])
  const previousStatus = useRef(status)
  useEffect(() => {
    if (previousStatus.current && ['queued', 'running', 'cancelling'].includes(previousStatus.current) &&
      status && !['queued', 'running', 'cancelling'].includes(status)) {
      findings.reload(); steps.reload(); comparison.reload()
    }
    previousStatus.current = status
  }, [status, findings.reload, steps.reload, comparison.reload])
  const refresh = () => { run.reload(); findings.reload(); steps.reload(); comparison.reload() }
  const project = projects.find((item) => item.id === run.data?.project_id)
  const filtered = findings.data?.filter((item) => (!moduleFilter || item.module_name === moduleFilter) &&
    (!typeFilter || item.error_type === typeFilter) && (!statusFilter || item.validation_status === statusFilter)) ?? []
  const canRetest = run.data?.status === 'completed' && steps.data?.some((step) => step.action === 'navigate' && step.status.startsWith('HTTP'))

  async function startRetest() {
    if (busy) return
    setBusy(true); setActionError('')
    try { const next = await api.retest(token, id, retestKey.current); rememberRun(next); navigate(`/executions/${next.id}`) }
    catch (error) { setActionError(friendlyError(error)) }
    finally { setBusy(false) }
  }
  async function getReport() {
    setBusy(true); setActionError('')
    try {
      const blob = await api.report(token, id)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a'); link.href = url; link.download = `testlab-${id}.html`; link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (error) { setActionError(friendlyError(error)) }
    finally { setBusy(false) }
  }

  async function cancelRun() {
    if (busy) return
    setBusy(true); setActionError('')
    try { const changed = await api.cancelExecution(token, id); rememberRun(changed); refresh() }
    catch (error) { setActionError(friendlyError(error)) }
    finally { setBusy(false) }
  }

  async function retryRun() {
    if (busy) return
    setBusy(true); setActionError('')
    try { const next = await api.retryExecution(token, id, retryKey.current); rememberRun(next); navigate(`/executions/${next.id}`) }
    catch (error) { setActionError(friendlyError(error)) }
    finally { setBusy(false) }
  }

  return <div className="page-stack"><PageHeading eyebrow="EJECUCIONES / DETALLE" title={`Ejecución #${shortId(id)}`} description="Estado y resultados registrados en la API." actions={<><Link to="/results" className="button button-secondary"><ArrowLeft size={16} /> Resultados</Link><button className="button button-primary" onClick={refresh}><RefreshCw size={16} /> Actualizar</button></>} />
    {actionError && <Notice tone="warning">{actionError}</Notice>}
    {run.loading ? <LoadingState /> : run.error ? <ErrorState message={friendlyError(run.error)} onRetry={refresh} /> : run.data ? <>
      <div className="run-summary"><div><span className="summary-label">ESTADO ACTUAL</span><StatusBadge status={run.data.status} /></div><div><span className="summary-label">PROYECTO</span><strong>{project?.name ?? `#${shortId(run.data.project_id)}`}</strong></div><div><span className="summary-label">SOLICITADA</span><strong>{formatDate(run.data.requested_at)}</strong></div><div><span className="summary-label">FINALIZADA</span><strong>{formatDate(run.data.finished_at)}</strong></div></div>
      <Notice tone="warning">La API no proporciona porcentaje de progreso. {run.data.status === 'pending' ? 'Solicitud registrada; se encolará solo si la cola está habilitada.' : run.data.status === 'cancelling' ? 'La cancelación está solicitada; el navegador todavía puede estar cerrándose.' : 'Actualiza para consultar el estado registrado.'}</Notice>
      {run.data.error_message && <Notice tone="warning">Error de ejecución: {run.data.error_message}</Notice>}
      <div className="detail-grid"><Panel title="Límites"><dl className="detail-list"><div><dt>Páginas</dt><dd>{run.data.max_pages}</dd></div><div><dt>Profundidad</dt><dd>{run.data.max_depth}</dd></div><div><dt>Solicitudes</dt><dd>{run.data.max_requests}</dd></div><div><dt>Tiempo por página</dt><dd>{run.data.page_timeout_ms} ms</dd></div></dl></Panel><Panel title="Seguimiento"><dl className="detail-list"><div><dt>Iniciada</dt><dd>{formatDate(run.data.started_at)}</dd></div><div><dt>Finalizada</dt><dd>{formatDate(run.data.finished_at)}</dd></div><div><dt>ID completo</dt><dd className="break-all"><code>{run.data.id}</code></dd></div></dl></Panel></div>
      <div className="action-row"><button className="button button-secondary" onClick={getReport} disabled={busy}><Download size={16} /> Descargar reporte HTML</button>{['pending', 'queued', 'running'].includes(run.data.status) && <button className="button button-secondary" onClick={cancelRun} disabled={busy}>Solicitar cancelación</button>}{['failed', 'cancelled'].includes(run.data.status) && <button className="button button-secondary" onClick={retryRun} disabled={busy}><RefreshCw size={16} /> Reintentar explícitamente</button>}{canRetest && <button className="button button-primary" onClick={startRetest} disabled={busy}><RefreshCw size={16} /> Repetir escenario</button>}</div>
      {run.data.retest_of_run_id && <Panel title="Comparación del retest">{comparison.loading ? <LoadingState /> : comparison.error ? <ErrorState message={friendlyError(comparison.error)} onRetry={comparison.reload} /> : comparison.data ? <><p>Anterior: <Link to={`/executions/${comparison.data.previous_run_id}`}>#{shortId(comparison.data.previous_run_id)}</Link> ({formatDate(comparison.data.previous_finished_at)}) · Actual: {formatDate(comparison.data.current_finished_at)}</p>{!comparison.data.complete && <Notice tone="warning">La ejecución actual no está completa; la comparación aún no permite concluir ausencia de errores.</Notice>}<div className="list-rows">{comparison.data.findings.map((item) => <div className="list-row" key={item.fingerprint}><span className="list-main"><b>{item.assessment === 'persisting' ? 'Persistente' : item.assessment === 'not_observed_pending_verification' ? 'No observado tras reevaluar; requiere verificación manual' : item.assessment === 'technical_failure' ? 'Retest fallido por problema técnico' : item.assessment === 'inconclusive' ? 'Inconcluso: falta cobertura del escenario o de la regla' : item.assessment === 'new' ? 'Nuevo' : 'Pendiente de resultado'}</b><small>Antes: {item.previous_result ?? 'Sin registro'} · Ahora: {item.current_result ?? 'Sin registro'}</small><small>Evidencias: {item.previous_evidence_count} anteriores / {item.current_evidence_count} actuales</small></span></div>)}</div></> : null}</Panel>}
      <Panel><div className="tabs" role="tablist" aria-label="Resultados de ejecución"><button className={tab === 'findings' ? 'tab active' : 'tab'} role="tab" aria-selected={tab === 'findings'} onClick={() => setTab('findings')}><Bug size={17} /> Hallazgos {findings.data && `(${findings.data.length})`}</button><button className={tab === 'steps' ? 'tab active' : 'tab'} role="tab" aria-selected={tab === 'steps'} onClick={() => setTab('steps')}>Pasos {steps.data && `(${steps.data.length})`}</button></div>
        {tab === 'findings' ? findings.loading ? <LoadingState /> : findings.error ? <ErrorState message={friendlyError(findings.error)} onRetry={findings.reload} /> : findings.data?.length ? <><div className="filter-row"><label>Módulo<select value={moduleFilter} onChange={(event) => setModuleFilter(event.target.value)}><option value="">Todos</option>{[...new Set(findings.data.map((item) => item.module_name).filter((value): value is string => Boolean(value)))].map((value) => <option key={value}>{value}</option>)}</select></label><label>Tipo<select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="">Todos</option>{[...new Set(findings.data.map((item) => item.error_type))].map((value) => <option key={value}>{value}</option>)}</select></label><label>Estado<select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="">Todos</option>{[...new Set(findings.data.map((item) => item.validation_status))].map((value) => <option key={value}>{value}</option>)}</select></label></div>{filtered.length ? <div className="finding-list">{filtered.map((finding) => <Link to={`/executions/${id}/findings/${finding.id}`} key={finding.id} className="finding-row"><span className="list-main"><b>{finding.error_type}</b><small>{finding.module_name ?? 'Módulo sin registrar'} · {finding.page_name ?? 'Pantalla sin registrar'} · {finding.validation_status}</small><small>{finding.description}</small></span><SeverityBadge severity={finding.severity} /></Link>)}</div> : <EmptyState title="Sin coincidencias" description="Cambia los filtros para ver otros hallazgos." />}</> : <EmptyState title="Sin hallazgos registrados" description="La ejecución aún no ha registrado incidencias." /> : steps.loading ? <LoadingState /> : steps.error ? <ErrorState message={friendlyError(steps.error)} onRetry={steps.reload} /> : steps.data?.length ? <div className="list-rows">{steps.data.map((step) => <div className="list-row" key={step.id}><span className="step-number">{step.step_number}</span><span className="list-main"><b>{step.action}</b><small>{step.module_name ?? 'Sin módulo'} · {step.page_name ?? 'Sin pantalla'} · {step.target ?? 'Sin destino'}</small></span><span className="mini-tag">{step.status}</span></div>)}</div> : <EmptyState title="Sin pasos registrados" description="La ejecución aún no ha registrado pasos." />}</Panel>
    </> : null}
  </div>
}
