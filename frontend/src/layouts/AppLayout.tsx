import { useState } from 'react'
import { Activity, ArrowUpRight, CircleHelp, FlaskConical, FolderKanban, LayoutDashboard, Layers3, LogOut, Menu, PlayCircle, Search, X } from 'lucide-react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'
import { useAppState } from '../hooks/useAppState'

const nav = [
  { to: '/', label: 'Resumen', icon: LayoutDashboard, end: true },
  { to: '/projects', label: 'Proyectos', icon: FolderKanban },
  { to: '/executions/new', label: 'Nueva ejecución', icon: PlayCircle },
  { to: '/results', label: 'Resultados', icon: Activity },
  { to: '/modalities', label: 'Modalidades', icon: Layers3 },
]

export function AppLayout() {
  const { disconnect, projects } = useAppState()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  return <div className="app-shell">
    {menuOpen && <button className="mobile-overlay" aria-label="Cerrar menú" onClick={() => setMenuOpen(false)} />}
    <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
      <div className="sidebar-top"><Link to="/" className="brand" onClick={() => setMenuOpen(false)}><span className="brand-mark"><FlaskConical size={23} strokeWidth={2.2} /></span><span><b>TestLab</b><small>QA Workspace</small></span></Link><button className="icon-button mobile-close" onClick={() => setMenuOpen(false)} aria-label="Cerrar menú"><X size={20} /></button></div>
      <div className="workspace-switch"><span className="workspace-avatar">TL</span><span><b>Espacio local</b><small>Operador único</small></span><span className="workspace-chevron">⌄</span></div>
      <p className="nav-caption">NAVEGACIÓN</p>
      <nav className="side-nav" aria-label="Navegación principal">
        {nav.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} onClick={() => setMenuOpen(false)} className={({ isActive }) => `nav-item ${isActive ? 'nav-active' : ''}`}><Icon size={19} strokeWidth={1.9} /><span>{label}</span></NavLink>)}
      </nav>
      <div className="sidebar-bottom"><div className="sidebar-help"><CircleHelp size={19} /><div><b>¿Cómo funciona?</b><p>La API registra proyectos y ejecuciones. Black Box se ejecuta en un worker cuando la cola está habilitada.</p><Link to="/modalities" onClick={() => setMenuOpen(false)}>Ver alcance <ArrowUpRight size={13} /></Link></div></div><button className="disconnect-button" onClick={disconnect}><LogOut size={18} /> Desconectar operador</button></div>
    </aside>
    <div className="main-column">
      <header className="topbar"><div className="topbar-left"><button className="icon-button mobile-menu" onClick={() => setMenuOpen(true)} aria-label="Abrir menú"><Menu size={22} /></button><span className="breadcrumb">TestLab</span><span className="breadcrumb-sep">/</span><span className="breadcrumb-current">{nav.find((item) => item.to === location.pathname)?.label ?? 'Detalle'}</span></div><div className="topbar-right"><Link to="/results" className="topbar-search"><Search size={16} /><span>Buscar ejecución</span></Link><span className="topbar-divider" /><span className="api-indicator"><span /> Clave activa</span><span className="topbar-avatar">QA</span></div></header>
      <main className="content"><Outlet /></main>
      <footer className="app-footer"><span>TestLab v0.1 · Fase 3</span><span>{projects.length} {projects.length === 1 ? 'proyecto' : 'proyectos'} cargados en esta sesión</span></footer>
    </div>
  </div>
}

