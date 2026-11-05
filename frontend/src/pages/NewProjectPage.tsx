import { useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowLeft, ArrowRight, Globe2, ShieldCheck } from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import { Field, Notice, PageHeading, Panel } from '../components/UI'
import { useAppState } from '../hooks/useAppState'
import { api, canonicalOrigin, friendlyError, validateHttpUrl } from '../services/api'
import type { EnvironmentName } from '../services/types'

export function NewProjectPage() {
  const { token, refreshProjects } = useAppState()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [origin, setOrigin] = useState('')
  const [environment, setEnvironment] = useState<EnvironmentName>('staging')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) { setError('Escribe un nombre para el proyecto.'); return }
    const urlError = validateHttpUrl(baseUrl)
    const originError = validateHttpUrl(origin, true)
    if (urlError || originError) { setError(urlError ?? originError ?? 'URL no válida.'); return }
    if (canonicalOrigin(baseUrl) !== canonicalOrigin(origin)) { setError('El origen autorizado debe coincidir con el origen de la URL base.'); return }
    setBusy(true); setError('')
    try {
      const project = await api.createProject(token, { name: name.trim(), description: description.trim(), base_url: baseUrl.trim(), environment, modality: 'blackbox', authorized_origins: [origin.trim()] })
      refreshProjects()
      navigate(`/projects/${project.id}`)
    } catch (reason) { setError(friendlyError(reason)) }
    finally { setBusy(false) }
  }

  return <div className="page-stack narrow-page"><PageHeading eyebrow="PROYECTOS / NUEVO" title="Registrar plataforma" description="Define una URL y autoriza explícitamente el origen que podrá utilizarse." actions={<Link to="/projects" className="button button-secondary"><ArrowLeft size={16} /> Volver</Link>} />
    <form onSubmit={submit}><Panel title="Datos del proyecto" subtitle="Modalidad Black Box"><div className="form-grid"><Field label="Nombre" required><input value={name} onChange={(event) => setName(event.target.value)} maxLength={200} placeholder="Ej. Portal de clientes" required /></Field><Field label="Entorno" required><select value={environment} onChange={(event) => setEnvironment(event.target.value as EnvironmentName)}><option value="development">Desarrollo</option><option value="staging">Staging</option><option value="production">Producción</option><option value="other">Otro</option></select></Field><div className="form-full"><Field label="Descripción" hint="Opcional"><textarea value={description} onChange={(event) => setDescription(event.target.value)} maxLength={5000} rows={3} placeholder="Objetivo y contexto de esta plataforma" /></Field></div></div></Panel>
      <Panel title="URL y alcance" subtitle="El origen autorizado debe pertenecer a la URL base"><div className="form-stack"><Field label="URL base" required hint="HTTP o HTTPS; puede incluir una ruta. Sin usuario, parámetros ni fragmentos."><input type="url" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://staging.ejemplo.com/" required /></Field><div className="origin-field"><Field label="Origen autorizado" required hint="Solo esquema, host y puerto; sin ruta."><input type="url" value={origin} onChange={(event) => setOrigin(event.target.value)} placeholder="https://staging.ejemplo.com/" required /></Field><button type="button" className="button button-secondary" onClick={() => { if (!validateHttpUrl(baseUrl)) setOrigin(canonicalOrigin(baseUrl)) }}><Globe2 size={16} /> Usar origen de URL</button></div><Notice><ShieldCheck size={17} /> Confirma que tienes autorización para probar este origen. La API rechaza URLs fuera del alcance declarado.</Notice></div></Panel>
      {error && <div className="form-error" role="alert">{error}</div>}<div className="form-actions"><Link to="/projects" className="button button-secondary">Cancelar</Link><button className="button button-primary" type="submit" disabled={busy}>{busy ? 'Guardando…' : 'Registrar proyecto'} <ArrowRight size={17} /></button></div></form></div>
}
