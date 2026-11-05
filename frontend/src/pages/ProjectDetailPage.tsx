import { useCallback } from 'react'
import { ArrowLeft, ArrowRight, Globe2, KeyRound, Play } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { EmptyState, ErrorState, LoadingState, Notice, PageHeading, Panel, formatDate } from '../components/UI'
import { useAppState } from '../hooks/useAppState'
import { useResource } from '../hooks/useResource'
import { api, friendlyError } from '../services/api'

export function ProjectDetailPage() {
  const { id = '' } = useParams()
  const { token } = useAppState()
  const load = useCallback((signal: AbortSignal) => api.project(token, id, signal), [token, id])
  const { data: project, loading, error, reload } = useResource(load)
  return <div className="page-stack"><PageHeading eyebrow="PROYECTOS / DETALLE" title={project?.name ?? 'Detalle del proyecto'} description="URL, entorno y alcance registrados en la API." actions={<Link to="/projects" className="button button-secondary"><ArrowLeft size={16} /> Proyectos</Link>} />
    {loading ? <LoadingState /> : error ? <ErrorState message={friendlyError(error)} onRetry={reload} /> : project ? <><div className="detail-grid"><Panel title="Plataforma"><dl className="detail-list"><div><dt>Nombre</dt><dd>{project.name}</dd></div><div><dt>Descripción</dt><dd>{project.description || 'Sin descripción'}</dd></div><div><dt>Modalidad</dt><dd>Black Box</dd></div><div><dt>Estado</dt><dd>{project.is_active ? 'Activo' : 'Inactivo'}</dd></div><div><dt>Creado</dt><dd>{formatDate(project.created_at)}</dd></div></dl></Panel><Panel title="Acceso y entorno"><dl className="detail-list"><div><dt>Entorno</dt><dd>{project.environment}</dd></div><div><dt>URL base</dt><dd className="break-all">{project.base_url}</dd></div><div><dt>Orígenes autorizados</dt><dd>{project.authorized_origins.map((origin) => <code key={origin} className="origin-pill">{origin}</code>)}</dd></div></dl><Notice>La API no ofrece edición de URL o entorno. Para otro entorno, registra un proyecto nuevo con su origen autorizado.</Notice></Panel></div><div className="action-grid"><Link className="action-card" to={`/projects/${project.id}/access`}><span className="stat-icon blue"><KeyRound size={21} /></span><b>Configurar acceso</b><p>Añade credenciales opcionales para un formulario de inicio de sesión.</p><ArrowRight size={18} /></Link><Link className="action-card" to={`/executions/new?project=${project.id}`}><span className="stat-icon teal"><Play size={21} /></span><b>Crear ejecución</b><p>Registra una solicitud Black Box con límites definidos.</p><ArrowRight size={18} /></Link></div><Panel title="Entornos registrados">{project.environments.length ? <div className="list-rows">{project.environments.map((env) => <div className="list-row" key={env.id}><span className="list-icon"><Globe2 size={17} /></span><span className="list-main"><b>{env.name}</b><small>{env.base_url}</small></span><span className="mini-tag active">{env.is_active ? 'Activo' : 'Inactivo'}</span></div>)}</div> : <EmptyState title="Sin entornos" description="No hay entornos asociados a este proyecto." />}</Panel></> : null}
  </div>
}
