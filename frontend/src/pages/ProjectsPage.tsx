import { ArrowRight, Plus, RefreshCw } from 'lucide-react'
import { Link } from 'react-router'
import { EmptyState, ErrorState, LoadingState, PageHeading, Panel, formatDate } from '../components/UI'
import { useAppState } from '../hooks/useAppState'

export function ProjectsPage() {
  const { projects, projectsLoading, projectsError, refreshProjects } = useAppState()
  return <div className="page-stack"><PageHeading eyebrow="GESTIÓN / PROYECTOS" title="Proyectos" description="Plataformas y entornos configurados para pruebas autorizadas." actions={<><button className="button button-secondary" onClick={refreshProjects}><RefreshCw size={16} /> Actualizar</button><Link className="button button-primary" to="/projects/new"><Plus size={17} /> Nuevo proyecto</Link></>} />
    <Panel>{projectsLoading ? <LoadingState label="Consultando proyectos…" /> : projectsError ? <ErrorState message={projectsError} onRetry={refreshProjects} /> : projects.length ? <div className="project-list">{projects.map((project) => <Link to={`/projects/${project.id}`} key={project.id} className="project-row"><span className="project-monogram">{project.name.slice(0, 2).toUpperCase()}</span><span className="project-row-main"><b>{project.name}</b><small>{project.base_url}</small></span><span className="project-row-meta"><span className="mini-tag active">{project.environment}</span><small>{formatDate(project.created_at)}</small></span><ArrowRight size={18} /></Link>)}</div> : <EmptyState title="No hay proyectos registrados" description="Crea el primero para configurar la URL, el entorno y el acceso." actionLabel="Registrar plataforma" actionTo="/projects/new" />}</Panel>
  </div>
}
