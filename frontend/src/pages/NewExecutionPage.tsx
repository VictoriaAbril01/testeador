import { useState } from 'react'
import type { FormEvent } from 'react'
import { useRef } from 'react'
import { ArrowLeft, ArrowRight, Play } from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { Field, Notice, PageHeading, Panel } from '../components/UI'
import { useAppState } from '../hooks/useAppState'
import { api, friendlyError } from '../services/api'
import type { ExecutionInput } from '../services/types'

const defaults = { max_pages: 20, max_depth: 3, max_requests: 200, max_concurrency: 1, page_timeout_ms: 15000, execution_timeout_ms: 120000 }
const limits: Array<{ key: keyof typeof defaults; label: string; min: number; max: number; hint: string }> = [
  { key: 'max_pages', label: 'Máximo de páginas', min: 1, max: 1000, hint: '1 a 1000' },
  { key: 'max_depth', label: 'Profundidad máxima', min: 0, max: 20, hint: '0 a 20' },
  { key: 'max_requests', label: 'Máximo de solicitudes', min: 1, max: 10000, hint: '1 a 10000' },
  { key: 'max_concurrency', label: 'Concurrencia máxima', min: 1, max: 10, hint: '1 a 10' },
  { key: 'page_timeout_ms', label: 'Tiempo por página (ms)', min: 1000, max: 120000, hint: '1000 a 120000' },
  { key: 'execution_timeout_ms', label: 'Tiempo total (ms)', min: 1000, max: 3600000, hint: '1000 a 3600000' },
]

export function NewExecutionPage() {
  const { token, projects, projectsLoading, projectsError, rememberRun } = useAppState()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [projectId, setProjectId] = useState(params.get('project') ?? '')
  const [values, setValues] = useState(defaults)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const requestKey = useRef(crypto.randomUUID())
  const lastPayload = useRef('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    if (!projectId) { setError('Selecciona un proyecto.'); return }
    if (limits.some(({ key, min, max }) => !Number.isInteger(values[key]) || values[key] < min || values[key] > max)) { setError('Revisa los límites de la ejecución.'); return }
    const input: ExecutionInput = { project_id: projectId, ...values }
    const serialized = JSON.stringify(input)
    if (serialized !== lastPayload.current) { requestKey.current = crypto.randomUUID(); lastPayload.current = serialized }
    setBusy(true); setError('')
    try { const run = await api.createExecution(token, input, requestKey.current); rememberRun(run); navigate(`/executions/${run.id}`) }
    catch (reason) { setError(friendlyError(reason)) }
    finally { setBusy(false) }
  }

  return <div className="page-stack narrow-page"><PageHeading eyebrow="EJECUCIONES / NUEVA" title="Nueva ejecución" description="Registra una solicitud Black Box para un proyecto autorizado." actions={<Link to="/projects" className="button button-secondary"><ArrowLeft size={16} /> Proyectos</Link>} />
    <Notice tone="warning">La ejecución se encola solo si el worker está habilitado. Sin él, permanecerá pendiente. La navegación requiere destinos autorizados y límites válidos.</Notice>
    <form onSubmit={submit}><Panel title="Proyecto" subtitle="Solo proyectos Black Box activos"><Field label="Plataforma" required><select value={projectId} onChange={(event) => setProjectId(event.target.value)} required><option value="">{projectsLoading ? 'Cargando proyectos…' : 'Selecciona un proyecto'}</option>{projects.filter((project) => project.is_active && project.modality === 'blackbox').map((project) => <option key={project.id} value={project.id}>{project.name} · {project.environment}</option>)}</select></Field>{projectsError && <div className="form-error" role="alert">{projectsError}</div>}{!projectsLoading && !projects.length && <p className="muted small">No hay proyectos. <Link to="/projects/new" className="text-link">Registra uno primero <ArrowRight size={14} /></Link></p>}</Panel>
      <Panel title="Límites de seguridad" subtitle="La API valida estos valores al registrar la solicitud"><div className="form-grid">{limits.map(({ key, label, min, max, hint }) => <Field key={key} label={label} hint={hint} required><input type="number" min={min} max={max} step={1} value={values[key]} onChange={(event) => setValues((current) => ({ ...current, [key]: event.target.valueAsNumber }))} required /></Field>)}</div></Panel>
      {error && <div className="form-error" role="alert">{error}</div>}<div className="form-actions"><Link to="/projects" className="button button-secondary">Cancelar</Link><button className="button button-primary" type="submit" disabled={busy || projectsLoading || !projects.length}>{busy ? 'Creando…' : 'Crear ejecución'} <Play size={17} /></button></div></form></div>
}

