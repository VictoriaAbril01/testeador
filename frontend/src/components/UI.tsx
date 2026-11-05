import type { ReactNode } from 'react'
import { AlertCircle, ArrowRight, Inbox, LoaderCircle, RefreshCw } from 'lucide-react'
import { Link } from 'react-router'
import type { ExecutionStatus, Finding } from '../services/types'

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('es-MX', {
    timeZone: 'America/Mexico_City', dateStyle: 'medium', timeStyle: 'short',
  }).format(new Date(value))
}

export function shortId(id: string): string { return id.slice(0, 8) }

const statusLabels: Record<ExecutionStatus, string> = {
  pending: 'Pendiente', queued: 'En cola', running: 'En curso', cancelling: 'Cancelando', completed: 'Completada',
  failed: 'Fallida', cancelled: 'Cancelada',
}

export function StatusBadge({ status }: { status: ExecutionStatus }) {
  return <span className={`badge badge-${status}`}><span className="badge-dot" />{statusLabels[status]}</span>
}

export function SeverityBadge({ severity }: { severity: Finding['severity'] }) {
  const labels = { info: 'Info', low: 'Baja', medium: 'Media', high: 'Alta', critical: 'Crítica' }
  return <span className={`severity severity-${severity}`}>{labels[severity]}</span>
}

export function PageHeading({ eyebrow, title, description, actions }: {
  eyebrow?: string; title: string; description?: string; actions?: ReactNode
}) {
  return <div className="page-heading">
    <div><p className="eyebrow">{eyebrow ?? 'TESTLAB / ESPACIO DE TRABAJO'}</p><h1>{title}</h1>{description && <p className="page-description">{description}</p>}</div>
    {actions && <div className="heading-actions">{actions}</div>}
  </div>
}

export function Panel({ title, subtitle, action, children, className = '' }: {
  title?: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string
}) {
  return <section className={`panel ${className}`}>
    {(title || action) && <div className="panel-header"><div>{title && <h2>{title}</h2>}{subtitle && <p>{subtitle}</p>}</div>{action}</div>}
    {children}
  </section>
}

export function LoadingState({ label = 'Cargando datos…' }: { label?: string }) {
  return <div className="state-box"><LoaderCircle size={24} className="spin" /><strong>{label}</strong></div>
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="state-box state-error"><AlertCircle size={25} /><strong>No se pudieron cargar los datos</strong><p>{message}</p>{onRetry && <button className="button button-secondary" onClick={onRetry}><RefreshCw size={16} /> Reintentar</button>}</div>
}

export function EmptyState({ title, description, actionLabel, actionTo }: {
  title: string; description: string; actionLabel?: string; actionTo?: string
}) {
  return <div className="state-box state-empty"><span className="empty-icon"><Inbox size={27} /></span><strong>{title}</strong><p>{description}</p>{actionLabel && actionTo && <Link className="text-link" to={actionTo}>{actionLabel}<ArrowRight size={15} /></Link>}</div>
}

export function Field({ label, hint, required, children }: { label: string; hint?: string; required?: boolean; children: ReactNode }) {
  return <label className="field"><span className="field-label">{label}{required && <span className="required"> *</span>}</span>{children}{hint && <small>{hint}</small>}</label>
}

export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'warning' | 'success' }) {
  return <div className={`notice notice-${tone}`}><AlertCircle size={18} aria-hidden="true" /><div>{children}</div></div>
}
