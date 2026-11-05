import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Activity, ArrowRight, FlaskConical, KeyRound, LockKeyhole, ShieldCheck } from 'lucide-react'
import { api, friendlyError } from '../services/api'
import { useAppState } from '../hooks/useAppState'

export function ConnectionPage() {
  const { connect } = useAppState()
  const [key, setKey] = useState('')
  const [health, setHealth] = useState<'checking' | 'online' | 'offline'>('checking')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    api.health().then(() => { if (active) setHealth('online') }).catch(() => { if (active) setHealth('offline') })
    return () => { active = false }
  }, [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!key.trim()) { setError('Introduce la clave de operador para continuar.'); return }
    setBusy(true); setError('')
    try { await connect(key); setKey('') }
    catch (reason) { setError(friendlyError(reason)) }
    finally { setBusy(false) }
  }

  return <div className="login-shell"><div className="login-aside"><div className="login-brand"><span className="brand-mark"><FlaskConical size={24} /></span><b>TestLab</b></div><div className="login-hero"><span className="hero-kicker"><Activity size={16} /> CONSOLA DE CALIDAD</span><h1>Pruebas más claras.<br /><em>Hallazgos con contexto.</em></h1><p>Organiza plataformas autorizadas, configura accesos de prueba y consulta resultados en un solo espacio.</p><div className="login-highlights"><span><ShieldCheck size={19} /> Alcance explícito</span><span><LockKeyhole size={19} /> Credenciales protegidas</span></div></div><div className="login-foot">TESTLAB / ENTORNO LOCAL</div></div><div className="login-main"><div className="login-status"><span className={`health-dot health-${health}`} />{health === 'online' ? 'API disponible' : health === 'offline' ? 'API no disponible' : 'Comprobando API'}</div><div className="login-form-wrap"><div className="login-symbol"><KeyRound size={27} /></div><p className="eyebrow">ACCESO AL ESPACIO</p><h2>Conecta tu operador</h2><p className="login-description">Introduce la clave configurada en <code>TESTLAB_API_KEY</code>. Se conserva solo en memoria mientras esta pestaña permanezca abierta.</p><form onSubmit={submit}><label className="field"><span className="field-label">Clave de operador</span><input type="password" value={key} onChange={(event) => setKey(event.target.value)} placeholder="Introduce tu clave" autoComplete="off" required /></label>{error && <div className="form-error" role="alert">{error}</div>}<button className="button button-primary button-wide" disabled={busy} type="submit">{busy ? 'Conectando…' : 'Entrar a TestLab'} <ArrowRight size={18} /></button></form><p className="login-note">La clave no se guarda en el navegador ni aparece en los reportes. Si la API está desconectada, revisa Docker Compose.</p></div><p className="login-bottom">© TestLab · Automatización QA responsable</p></div></div>
}
