import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { ErrorState, LoadingState, Notice, PageHeading, Panel, SeverityBadge, formatDate, shortId } from '../components/UI'
import { useAppState } from '../hooks/useAppState'
import { useResource } from '../hooks/useResource'
import { api, friendlyError } from '../services/api'
import type { Evidence, ValidationStatus } from '../services/types'

const transitions: Record<ValidationStatus, ValidationStatus[]> = {
  detected: ['pending_confirmation', 'confirmed', 'not_reproducible', 'false_positive'],
  pending_confirmation: ['confirmed', 'not_reproducible', 'false_positive'],
  confirmed: ['fixed', 'not_reproducible', 'false_positive'],
  not_reproducible: ['pending_confirmation', 'confirmed', 'false_positive'],
  false_positive: ['pending_confirmation', 'confirmed'],
  fixed: ['retested', 'confirmed'],
  retested: ['confirmed', 'fixed'],
}
const labels: Record<ValidationStatus, string> = {
  detected: 'Detectado automáticamente', pending_confirmation: 'Pendiente de confirmación', confirmed: 'Confirmado',
  not_reproducible: 'No reproducible', false_positive: 'Falso positivo', fixed: 'Corregido manualmente',
  retested: 'Verificado mediante retest',
}

function EvidenceItem({ item, token }: { item: Evidence; token: string }) {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState('')
  useEffect(() => () => { if (url) URL.revokeObjectURL(url) }, [url])
  async function open() {
    setError('')
    try {
      const blob = await api.evidenceFile(token, item.id)
      const next = URL.createObjectURL(blob)
      setUrl((previous) => { if (previous) URL.revokeObjectURL(previous); return next })
      if (item.kind !== 'screenshot') {
        const link = document.createElement('a'); link.href = next; link.download = `evidence-${item.id}.json`; link.click()
      }
    } catch (reason) { setError(friendlyError(reason)) }
  }
  if (item.kind === 'screenshot_status') {
    const status = item.capture_status === 'valid' ? 'Captura válida' : item.capture_status === 'suspicious' ? 'Captura sospechosa: revisa si muestra contenido útil' : 'Captura no disponible'
    return <li><b>{status}</b> · {item.page_url ?? 'Página no registrada'} · {item.captured_at ? formatDate(item.captured_at) : 'Fecha no registrada'}{item.width && item.height ? ` · ${item.width}×${item.height}` : ''}{item.capture_reason && <small> ({item.capture_reason})</small>}</li>
  }
  return <li><b>{item.kind}</b> · {item.size_bytes} bytes · caduca {formatDate(item.expires_at)} <button className="button button-secondary" onClick={open}>{item.kind === 'screenshot' ? 'Ver captura' : 'Descargar JSON'}</button>{error && <span role="alert">{error}</span>}{url && item.kind === 'screenshot' && <img className="evidence-preview" src={url} alt="Captura de la página con texto y campos ocultos" onError={() => setError('No se pudo mostrar la imagen descargada.')} />}</li>
}

export function FindingDetailPage() {
  const { id = '', findingId = '' } = useParams()
  const { token, projects } = useAppState()
  const finding = useResource(useCallback((signal: AbortSignal) => api.finding(token, findingId, signal), [token, findingId]))
  const run = useResource(useCallback((signal: AbortSignal) => api.execution(token, id, signal), [token, id]))
  const evidence = useResource(useCallback((signal: AbortSignal) => api.evidence(token, findingId, signal), [token, findingId]))
  const validations = useResource(useCallback((signal: AbortSignal) => api.validations(token, findingId, signal), [token, findingId]))
  const history = useResource(useCallback((signal: AbortSignal) => api.history(token, findingId, signal), [token, findingId]))
  const [status, setStatus] = useState<ValidationStatus>('pending_confirmation')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const choices = transitions[(finding.data?.validation_status as ValidationStatus) ?? 'detected'] ?? transitions.detected
  useEffect(() => { setStatus(choices[0]) }, [finding.data?.validation_status])
  const project = projects.find((item) => item.id === run.data?.project_id)
  async function saveValidation() {
    setSaving(true); setSaveError('')
    try { await api.validate(token, findingId, status, notes); finding.reload(); validations.reload(); setNotes('') }
    catch (error) { setSaveError(friendlyError(error)) }
    finally { setSaving(false) }
  }

  return <div className="page-stack"><PageHeading eyebrow="RESULTADOS / INCIDENCIA" title={finding.data?.error_type ?? 'Detalle de incidencia'} description="Observación y validación registrada en TestLab." actions={<Link to={`/executions/${id}`} className="button button-secondary"><ArrowLeft size={16} /> Ejecución</Link>} />
    {finding.loading ? <LoadingState /> : finding.error ? <ErrorState message={friendlyError(finding.error)} onRetry={finding.reload} /> : finding.data ? <>
      <div className="detail-grid"><Panel title="Clasificación"><dl className="detail-list"><div><dt>ID</dt><dd className="break-all">{finding.data.id}</dd></div><div><dt>Tipo</dt><dd>{finding.data.error_type}</dd></div><div><dt>Severidad</dt><dd><SeverityBadge severity={finding.data.severity} /></dd></div><div><dt>Validación</dt><dd>{finding.data.validation_status}</dd></div><div><dt>Detectado</dt><dd>{formatDate(finding.data.created_at)}</dd></div></dl></Panel><Panel title="Contexto"><dl className="detail-list"><div><dt>Proyecto</dt><dd>{project?.name ?? (run.data ? `#${shortId(run.data.project_id)}` : 'Cargando')}</dd></div><div><dt>Ejecución</dt><dd>#{shortId(id)}</dd></div><div><dt>Entorno</dt><dd>{project?.environment ?? 'No cargado'}</dd></div><div><dt>Módulo</dt><dd>{finding.data.module_name ?? 'No identificado'}</dd></div><div><dt>Pantalla</dt><dd>{finding.data.page_name ?? 'No registrada'}</dd></div><div><dt>Campo/componente</dt><dd>{finding.data.element ?? 'No registrado'}</dd></div><div><dt>URL</dt><dd className="break-all">{finding.data.url ?? 'No registrada'}</dd></div></dl></Panel></div>
      <Panel title="Descripción"><p>{finding.data.description}</p><div className="result-columns"><div><h3>Resultado esperado</h3><p>{finding.data.expected_result ?? 'No hay regla de resultado esperado configurada.'}</p></div><div><h3>Resultado observado</h3><p>{finding.data.observed_result}</p></div></div></Panel>
      <Panel title="Reproducción manual">{finding.data.reproduction_steps?.length ? <ol className="repro-list">{finding.data.reproduction_steps.map((step, index) => <li key={index}>{String(step)}</li>)}</ol> : <p className="muted">La ejecución no registró suficientes acciones para generar pasos.</p>}</Panel>
      <Panel title="Evidencias">{evidence.loading ? <LoadingState /> : evidence.error ? <ErrorState message={friendlyError(evidence.error)} onRetry={evidence.reload} /> : evidence.data?.length ? <ul className="evidence-list">{evidence.data.map((item) => <EvidenceItem item={item} token={token} key={item.id} />)}</ul> : <p className="muted">Sin archivos disponibles o ya vencieron.</p>}</Panel>
      <Panel title="Confirmación manual"><p>La clave de operador identifica al validador como «operator».</p><div className="filter-row"><label>Estado<select value={status} onChange={(event) => setStatus(event.target.value as ValidationStatus)}>{choices.map((choice) => <option value={choice} key={choice}>{labels[choice]}</option>)}</select></label><label>Observaciones<textarea value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={2000} /></label></div><button className="button button-primary" disabled={saving} onClick={saveValidation}>Guardar validación</button>{saveError && <Notice tone="warning">{saveError}</Notice>}</Panel>
      <Panel title="Historial de validaciones">{validations.loading ? <LoadingState /> : validations.error ? <ErrorState message={friendlyError(validations.error)} onRetry={validations.reload} /> : validations.data?.length ? <div className="list-rows">{validations.data.map((item) => <div className="list-row" key={item.id}><span className="list-main"><b>{item.from_status} → {item.to_status}</b><small>{item.actor} · {formatDate(item.validated_at)}</small><small>{item.notes ?? 'Sin observaciones'}</small></span></div>)}</div> : <p className="muted">Sin validaciones manuales.</p>}</Panel>
      <Panel title="Historial del error en el proyecto">{history.loading ? <LoadingState /> : history.error ? <ErrorState message={friendlyError(history.error)} onRetry={history.reload} /> : history.data?.length ? <div className="list-rows">{history.data.map((item) => <Link className="list-row" to={`/executions/${item.run_id}/findings/${item.id}`} key={item.id}><span className="list-main"><b>#{shortId(item.run_id)} · {item.validation_status}</b><small>{formatDate(item.created_at)} · {item.observed_result}</small></span></Link>)}</div> : <p className="muted">Sin otras observaciones equivalentes.</p>}</Panel>
    </> : null}
  </div>
}
