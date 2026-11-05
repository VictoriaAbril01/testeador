# Instalación local

## Requisitos

Git, Docker Engine, Docker Compose v2, Python 3.13 y Node.js 24 o superior para desarrollo local. Docker debe estar iniciado.

## Preparar variables locales

En PowerShell, desde la raíz del repositorio:

```powershell
Copy-Item .env.example .env
```

Edita `.env` y establece un valor único y no vacío para `POSTGRES_PASSWORD`. `.env` está ignorado por Git. Si Windows tiene ocupado o reservado el puerto 5432, cambia `POSTGRES_PORT` a otro puerto local libre, por ejemplo `55432`.

Configura también `TESTLAB_API_KEY` con un valor aleatorio de al menos 32 caracteres y `TESTLAB_FERNET_KEY` con una clave Fernet válida. Puedes generar ambos sin imprimirlos en pantalla desde PowerShell:

```powershell
$apiKey = py -3.13 -c "import secrets; print(secrets.token_urlsafe(32))"
$fernetKey = py -3.13 -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
$lines = Get-Content .env
$lines = $lines -replace '^TESTLAB_API_KEY=.*$', "TESTLAB_API_KEY=$apiKey"
$lines = $lines -replace '^TESTLAB_FERNET_KEY=.*$', "TESTLAB_FERNET_KEY=$fernetKey"
Set-Content .env -Value $lines -Encoding utf8
```

Conserva ambas claves fuera del repositorio. Si pierdes la clave Fernet, no podrás descifrar credenciales existentes. No reutilices las claves de este equipo en otro despliegue.

## Iniciar servicios de datos

```powershell
docker compose config
docker compose up -d --build --wait api postgres redis
docker compose ps
```

PostgreSQL se expone solo en `127.0.0.1` para herramientas locales. Redis no publica un puerto en el host. El volumen privado `evidence_data` comparte archivos de evidencia entre API y worker; no está expuesto por el servidor web.
La API se expone solo en `127.0.0.1:8000` por defecto; si está ocupado, configura `API_PORT` en `.env`.

## Comprobar servicios

```powershell
docker compose exec -T postgres pg_isready -U testlab -d testlab
docker compose exec -T redis redis-cli ping
Invoke-RestMethod http://127.0.0.1:8000/health
```

Si cambias `POSTGRES_USER` o `POSTGRES_DB`, ajusta la primera comprobación. PostgreSQL debe responder `accepting connections`, Redis `PONG` y la API `status: ok`. La documentación interactiva está en `http://127.0.0.1:8000/docs`.

## Detener servicios

```powershell
docker compose down
```

Los volúmenes conservan los datos al detener servicios. No uses `down --volumes` si deseas conservarlos.

## Instalar dependencias locales y aplicar migraciones

Desde la raíz del repositorio, con PostgreSQL saludable:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e './backend[dev]'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

La configuración de Alembic lee el `.env` local y se conecta al puerto indicado por `POSTGRES_PORT`. También acepta `DATABASE_URL` con el driver `postgresql+psycopg` para otros entornos. Ejecuta migraciones solo contra una base de datos cuya estructura puedas modificar.

Para ejecutar la API sin Docker, desde la raíz:

```powershell
$env:PYTHONPATH = "backend;."
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Consulta [api.md](api.md) para la autenticación y las rutas. El motor Black Box se documenta en [blackbox.md](blackbox.md). Consulta [testing.md](testing.md) para verificar cada componente.

## Iniciar el frontend

Con la API activa en `127.0.0.1:8000`, abre otra terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Abre `http://127.0.0.1:5173` e introduce el valor local de `TESTLAB_API_KEY`. Vite redirige las peticiones `/api` y `/health` a FastAPI. La clave permanece solo en memoria de la pestaña. Para servir el build de producción localmente, ejecuta `npm run build` y `npm run preview`; el proxy de vista previa usa la misma dirección de API. Para un despliegue separado se necesita un proxy del mismo origen o una configuración CORS autorizada en FastAPI.

## Activar el worker Black Box

El worker público de Compose se inicia explícitamente con el perfil `blackbox`. Para encolar **solo las nuevas ejecuciones** de la API, establece `TESTLAB_QUEUE_ENABLED=true` en `.env` después de revisar el alcance de los proyectos y arranca ambos servicios:

```powershell
docker compose --profile blackbox up -d --build --wait api worker
docker compose --profile blackbox ps
```

El worker público rechaza loopback, redes privadas y destinos fuera de los orígenes autorizados. No intentes probar servicios internos desde este contenedor: requieren un worker separado con acceso de red concedido y CIDRs explícitos. Para dejar de encolar nuevas ejecuciones, vuelve a establecer `TESTLAB_QUEUE_ENABLED=false` y recrea la API. Las solicitudes ya encoladas no se cancelan por ese cambio. Configura `TESTLAB_EVIDENCE_RETENTION_DAYS` entre 1 y 365 si necesitas otro plazo. Consulta [blackbox.md](blackbox.md) para límites y [evidence-reports.md](evidence-reports.md) para retención y reportes.

Para pruebas locales del motor sin Redis, instala las dependencias de navegador en el entorno Python y usa Chrome instalado o descarga Chromium de Playwright:

```powershell
.\.venv\Scripts\python.exe -m pip install -e './backend[dev,blackbox]'
.\.venv\Scripts\python.exe -m playwright install chromium
```
