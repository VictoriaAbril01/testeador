import { ArrowRight, Bug, FolderKanban, Play, RefreshCw } from 'lucide-react'
import { Link } from 'react-router'
import { EmptyState, ErrorState, LoadingState, PageHeading, Panel, StatusBadge, formatDate, shortId } from '../components/UI'
import { useAppState } from '../hooks/useAppState'
import { useDashboardData } from '../hooks/useDashboardData'
import { friendlyError } from '../services/api'
import type { ExecutionStatus } from '../services/types'

const statuses: ExecutionStatus[] = ['pending', 'queued', 'running', 'cancelling', 'completed', 'failed', 'cancelled']
const labels: Record<ExecutionStatus, string> = {
  pending: 'Pendientes', queued: 'En cola', running: 'En curso', cancelling: 'Cancelando',
  completed: 'Completadas', failed: 'Fallidas', cancelled: 'Canceladas',
}

export function DashboardPage() {
  const { token } = useAppState()
  const { data, loading, error, reload } = useDashboardData(token)
  return <div className="page-stack">
    <PageHeading eyebrow="RESUMEN / ESPACIO DE TRABAJO" title="Tu espacio de pruebas" description="Resumen persistido de proyectos, ejecuciones y hallazgos." actions={<><button className="button button-secondary" onClick={reload}><RefreshCw size={16} /> Actualizar</button><Link className="button button-primary" to="/executions/new"><Play size={16} /> Nueva ejecución</Link></>} />
    {loading && !data ? <LoadingState /> : error ? <ErrorState message={friendlyError(error)} onRetry={reload} /> : data ? <>
      <div className="stats-grid">
        <div className="stat-card"><span className="stat-icon teal"><FolderKanban size={21} /></span><span className="stat-label">Proyectos registrados</span><strong>{data.total_projects}</strong><span className="stat-note">Total en PostgreSQL</span></div>
        <div className="stat-card"><span className="stat-icon blue"><Play size={21} /></span><span className="stat-label">Ejecuciones</span><strong>{data.total_executions}</strong><span className="stat-note">Historial persistido</span></div>
        <div className="stat-card"><span className="stat-icon rose"><Bug size={21} /></span><span className="stat-label">Hallazgos detectados</span><strong>{data.total_findings}</strong><span className="stat-note">{data.findings_pending_confirmation} pendientes de confirmación</span></div>
        <div className="stat-card"><span className="stat-icon amber"><RefreshCw size={21} /></span><span className="stat-label">En cola o en curso</span><strong>{(data.executions_by_status.queued ?? 0) + (data.executions_by_status.running ?? 0) + (data.executions_by_status.cancelling ?? 0)}</strong><span className="stat-note">Actualización automática cada 5 s</span></div>
      </div>
      <Panel title="Ejecuciones por estado"><div className="filter-row">{statuses.map((status) => <Link key={status} to={`/results?status=${status}`} className="mini-tag">{labels[status]}: {data.executions_by_status[status] ?? 0}</Link>)}</div></Panel>
      <div className="dashboard-grid">
        <Panel title="Ejecuciones recientes" subtitle="Últimos registros de la base de datos" action={<Link to="/results" className="text-link">Ver historial <ArrowRight size={15} /></Link>}>
          {data.recent_executions.length ? <div className="list-rows">{data.recent_executions.map((run) => <Link className="list-row" key={run.id} to={`/executions/${run.id}`}><span className="list-icon"><Play size={17} /></span><span className="list-main"><b>#{shortId(run.id)} · {run.project_name}</b><small>{run.modality} · {run.finding_count} hallazgos · {formatDate(run.requested_at)}</small></span><StatusBadge status={run.status} /></Link>)}</div> : <EmptyState title="No hay ejecuciones" description="Las ejecuciones creadas aparecerán aquí incluso después de recargar." actionLabel="Crear ejecución" actionTo="/executions/new" />}
        </Panel>
        <Panel title="Proyectos" subtitle="Última ejecución por proyecto" action={<Link to="/projects" className="text-link">Ver todos <ArrowRight size={15} /></Link>}>
          {data.recent_projects.length ? <div className="list-rows">{data.recent_projects.map((project) => <Link className="list-row" key={project.id} to={`/projects/${project.id}`}><span className="list-icon"><FolderKanban size={17} /></span><span className="list-main"><b>{project.name}</b><small>{project.latest_execution ? `Última ejecución: ${formatDate(project.latest_execution.requested_at)}` : 'Sin ejecuciones'}</small></span>{project.latest_execution && <StatusBadge status={project.latest_execution.status} />}</Link>)}</div> : <EmptyState title="No hay proyectos" description="Registra una plataforma y su origen autorizado para comenzar." actionLabel="Registrar proyecto" actionTo="/projects/new" />}
        </Panel>
      </div>
    </> : null}
  </div>
}
