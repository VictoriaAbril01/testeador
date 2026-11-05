import { useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowLeft, ArrowRight, LockKeyhole } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { Field, Notice, PageHeading, Panel } from '../components/UI'
import { useAppState } from '../hooks/useAppState'
import { api, canonicalOrigin, friendlyError, validateHttpUrl } from '../services/api'

export function AccessPage() {
  const { id = '' } = useParams()
  const { token, projects } = useAppState()
  const project = projects.find((item) => item.id === id)
  const [loginUrl, setLoginUrl] = useState('')
  const [usernameSelector, setUsernameSelector] = useState('')
  const [passwordSelector, setPasswordSelector] = useState('')
  const [submitSelector, setSubmitSelector] = useState('')
  const [successSelector, setSuccessSelector] = useState('')
  const [successUrlPattern, setSuccessUrlPattern] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const urlError = validateHttpUrl(loginUrl)
    if (urlError) { setError(urlError); return }
    if (project && !project.authorized_origins.includes(canonicalOrigin(loginUrl))) { setError('La URL de acceso debe pertenecer a un origen autorizado.'); return }
    if (!successSelector.trim() && !successUrlPattern.trim()) { setError('Configura un selector de éxito o un patrón de URL.'); return }
    setBusy(true); setError(''); setSaved(false)
    try {
      await api.configureCredentials(token, id, { login_url: loginUrl.trim(), username_selector: usernameSelector.trim(), password_selector: passwordSelector.trim(), submit_selector: submitSelector.trim(), success_selector: successSelector.trim() || undefined, success_url_pattern: successUrlPattern.trim() || undefined, username, password })
      setUsername(''); setPassword(''); setSaved(true)
    } catch (reason) { setError(friendlyError(reason)) }
    finally { setBusy(false) }
  }

  return <div className="page-stack narrow-page"><PageHeading eyebrow="PROYECTOS / ACCESO" title="Configurar acceso" description={`Credenciales opcionales de formulario${project ? ` para ${project.name}` : ''}.`} actions={<Link className="button button-secondary" to={`/projects/${id}`}><ArrowLeft size={16} /> Proyecto</Link>} />
    <Notice tone="warning">El worker usa estas credenciales solo para el formulario configurado. Se cifran en el servidor. La API no permite consultar si ya existe una configuración previa.</Notice>
    {saved && <Notice tone="success">Configuración guardada. Los campos de usuario y contraseña se han vaciado.</Notice>}
    <form onSubmit={submit} autoComplete="off"><Panel title="Formulario de inicio de sesión" subtitle="Introduce selectores CSS de la página autorizada"><div className="form-stack"><Field label="URL de acceso" required><input type="url" value={loginUrl} onChange={(event) => setLoginUrl(event.target.value)} placeholder="https://staging.ejemplo.com/login" required /></Field><div className="form-grid"><Field label="Selector de usuario" required><input value={usernameSelector} onChange={(event) => setUsernameSelector(event.target.value)} placeholder="input[name=email]" required /></Field><Field label="Selector de contraseña" required><input value={passwordSelector} onChange={(event) => setPasswordSelector(event.target.value)} placeholder="input[type=password]" required /></Field><Field label="Selector del botón" required><input value={submitSelector} onChange={(event) => setSubmitSelector(event.target.value)} placeholder="button[type=submit]" required /></Field><Field label="Selector de éxito"><input value={successSelector} onChange={(event) => setSuccessSelector(event.target.value)} placeholder="[data-test=dashboard]" /></Field></div><Field label="Patrón de URL de éxito" hint="Opcional si indicas un selector de éxito."><input value={successUrlPattern} onChange={(event) => setSuccessUrlPattern(event.target.value)} placeholder="/dashboard" /></Field></div></Panel>
      <Panel title="Credenciales" subtitle="Enviadas directamente a la API mediante la conexión local"><div className="form-grid"><Field label="Usuario" required><input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="off" required /></Field><Field label="Contraseña" required><input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" required /></Field></div><p className="muted small"><LockKeyhole size={14} /> La contraseña no se guarda en localStorage ni se muestra después de guardar.</p></Panel>
      {error && <div className="form-error" role="alert">{error}</div>}<div className="form-actions"><Link to={`/projects/${id}`} className="button button-secondary">Volver</Link><button type="submit" className="button button-primary" disabled={busy}>{busy ? 'Guardando…' : 'Guardar acceso'} <ArrowRight size={17} /></button></div></form></div>
}

