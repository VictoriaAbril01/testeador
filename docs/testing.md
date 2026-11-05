# Verificación

## Infraestructura local (Fase 1)

```powershell
docker compose config --quiet
docker compose up -d --wait postgres redis
docker compose ps
docker compose exec -T postgres pg_isready -U testlab -d testlab
docker compose exec -T redis redis-cli ping
git status --short
```

Ejecuta estos comandos después de configurar `.env` según [installation.md](installation.md). Ambos contenedores deben figurar como saludables. El último comando permite comprobar los archivos nuevos y que `.env` no aparezca entre los archivos rastreables.

## Backend, modelos y migraciones (Fase 2)

Después de instalar las dependencias y aplicar la migración según [installation.md](installation.md):

```powershell
.\.venv\Scripts\python.exe -m alembic check
$env:PYTHONPATH = (Resolve-Path backend).Path
.\.venv\Scripts\python.exe -m pytest tests -q
```

`alembic check` debe indicar que no hay nuevas operaciones. Las pruebas comprueban tablas, claves foráneas, unicidad, límites, registro y consulta de proyectos, validación de URLs, cifrado de credenciales, creación y lectura de ejecuciones, transiciones de estado, autorización y respuestas de error sin secretos. Sus filas de prueba se revierten al terminar.

La migración y las pruebas se ejecutaron en la base local configurada en `.env`. Para probar el contenedor y OpenAPI:

```powershell
docker compose up -d --build --wait api
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/openapi.json
```

Las pruebas del motor, worker y evidencias se ejecutan en la suite completa.

## Frontend (Fase 3)

Con Node.js instalado, desde `frontend/`:

```powershell
npm ci
npm run typecheck
npm run build
npm test
```

Las cuatro pruebas verifican validación de URL, cabeceras HTTP, protección de errores de red y estado vacío del historial. En Chrome se comprobó el acceso a FastAPI, alta real de proyecto, creación de ejecución pendiente, consulta de pasos, modalidades, navegación móvil y visualización de fallo de red. La prueba de navegador de Fase 3 dejó dos proyectos y dos ejecuciones pendientes identificados por el prefijo `Verificación fase 3`.

Para comprobarlo manualmente, inicia API y Vite según [installation.md](installation.md). Introduce la clave de operador, registra un proyecto con URL `https://example.test/` y confirma explícitamente su origen, configura un acceso solo si dispones de credenciales de prueba, crea una ejecución y abre sus resultados. Con la cola desactivada debe aparecer `Pendiente`, sin pasos ni hallazgos inventados. Guarda el UUID de la ejecución si quieres volver a consultarla tras recargar. En DevTools, revisa la consola y la pestaña Network; detén temporalmente la API o bloquea `/api/v1/projects` para observar el estado de error y el botón de reintento. La interfaz se adapta a ancho móvil mediante el menú lateral.

## Motor Black Box (Fase 4)

La prueba de navegador usa el Chrome instalado en `C:/Program Files/Google/Chrome/Application/chrome.exe`, PostgreSQL migrado y un servidor FastAPI local en loopback. Las escrituras de la prueba de persistencia se revierten al terminar:

```powershell
.\.venv\Scripts\python.exe -m pip install -e './backend[dev,blackbox]'
.\.venv\Scripts\python.exe -m pytest tests -q
docker compose --profile blackbox build api worker
docker compose --profile blackbox up -d --wait api worker
docker compose --profile blackbox exec -T worker python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(); print(b.version); b.close(); p.stop()"
```

La suite comprobó login, varias páginas, error JavaScript, HTTP 500, enlace 404, página sana, redirecciones fuera de alcance y a una ruta destructiva, límites de páginas/solicitudes/tiempo, reglas de estado HTTP, cierre de navegador y persistencia de pasos y hallazgos. Al cerrar la Fase 4 había **24 pruebas Python y 4 frontend aprobadas**.

Para una comprobación manual end to end de una plataforma propia, usa un destino de prueba expresamente autorizado y público, activa el worker según [installation.md](installation.md), crea una ejecución desde la interfaz y actualiza su detalle. Espera `running` y después `completed` o `failed`; revisa hallazgos y pasos. Para destinos internos, usa únicamente el despliegue separado descrito en [blackbox.md](blackbox.md).

## Fase 5 — Evidencias y reportes

```powershell
$env:PYTHONPATH = "backend;."
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m pytest -q
Set-Location frontend
npm run typecheck
npm run build
npm test
```

Resultado: **29 pruebas Python y 4 pruebas frontend aprobadas**, migración aplicada y Alembic sin diferencias. La suite incluye captura PNG real en Chromium, asociación de archivos, sanitización de metadatos, reproducción, huella y agrupación, API de validación, historial, comparación de retest, autorización de evidencia y reporte HTML escapado. También se comprobó en Chrome el acceso del frontend a la API y la carga de historial e incidencias sin errores de página. API y worker recreados en Compose, ambos saludables; `/health` y OpenAPI respondieron correctamente. Queda una advertencia de deprecación de `starlette.testclient` procedente de una dependencia. Para el recorrido manual completo, sigue [evidence-reports.md](evidence-reports.md).

## Fase 5.1 — Incremento de retesting

Tras aplicar `alembic upgrade head`, ejecuta `python -m pytest tests/unit/test_retest_coverage.py tests/integration/test_api.py tests/integration/test_blackbox_browser.py -q` con `PYTHONPATH=backend;.`. La suite comprueba que un retest sin página, navegación, login requerido o regla evaluada queda `inconclusive`; que una regla reevaluada distingue error persistente de ausencia pendiente de validación; y que `failed` se informa como fallo técnico. La prueba Chromium/worker comprueba persistencia de escenarios y evaluaciones positivas y negativas. En el incremento 1 aprobaron **39 pruebas Python** y **4 frontend** al ejecutar la suite completa; Alembic quedó en `88a1b7c52d10 (head)` sin diferencias, y TypeScript/build aprobaron.

Para un ensayo manual nuevo, usa una aplicación local expresamente autorizada con worker privado separado según [blackbox.md](blackbox.md). Tras la ejecución original, `GET /api/v1/findings/{id}` debe incluir `scenario`. El retest debe guardar `page_url` en pasos y evaluaciones en `GET /api/v1/executions/{id}/rule-evaluations`. Solo cuando la misma regla se evaluó sin coincidencia, `/comparison` puede devolver `not_observed_pending_verification` y la transición manual `fixed` → `retested` puede aceptarse. Los registros anteriores a la migración no se completan por inferencia y darán `inconclusive`.

## Fase 5.1 — Incremento 2: workers y recuperación

Aplica `alembic upgrade head` antes de reiniciar API y worker. Comprueba `alembic check`, `pytest -q` y las pruebas frontend (`npm run typecheck`, `npm run build`, `npm test`). La prueba `tests/integration/test_queue_redis.py` requiere un Redis aislado indicado por `TESTLAB_TEST_REDIS_URL`; nunca uses la base Redis de desarrollo para esta prueba. `tests/integration/test_blackbox_browser.py` ejecuta RQ y Chromium contra una aplicación local controlada.

Para la verificación manual, inicia API y worker y crea una ejecución Black Box sobre un destino de prueba expresamente autorizado. Debe pasar por `queued` y `running` antes de finalizar. `POST /api/v1/executions/{id}/cancel` cancela de inmediato un trabajo pendiente o en cola; durante la ejecución, `GET /api/v1/executions/{id}/cancellation` mostrará `cancelling` hasta que el navegador se cierre y el estado sea `cancelled`. Repetir la misma solicitud de creación con la misma cabecera `Idempotency-Key` debe devolver el mismo UUID; usar esa clave para otra carga devuelve 409. `POST /api/v1/executions/{id}/retry` solo acepta ejecuciones `failed` o `cancelled`, devuelve otro UUID y enlaza `retry_of_run_id`. Al reiniciar el worker, una ejecución interrumpida debe pasar a `failed` tras la ventana de reconciliación, sin reejecución automática.

La recuperación ante apagado forzado y fallos de Redis no se ensayó en un entorno de producción. Un trabajo interrumpido conserva el fallo técnico; el operador decide si inicia un reintento explícito.

## Fase 5.1 — Incremento 3: capturas y evidencias

La prueba `tests/integration/test_blackbox_browser.py::test_screenshots_follow_rendered_page_redirect_and_spa` ejecuta Chromium contra páginas locales visual, SPA, redirigida y blanca uniforme. Con `-s` imprime la ruta temporal de `visual-evidence.png` para inspeccionarla: debe mostrar un bloque azul y otro naranja, sin texto legible ni campo de contraseña. La prueba comprueba además el píxel naranja, dimensiones, decodificación y asociación con la URL final. La suite verifica PNG vacío/corrupto, JavaScript, HTTP 500, enlace 404, fallo de navegación, cancelación con evidencia previa, acceso autenticado y estado de captura en API/reporte.

Resultado local del incremento: **52 pruebas Python aprobadas** con Redis aislado y RQ real; **4 pruebas frontend**, TypeScript y build aprobados; `alembic check` sin diferencias. Se abrió visualmente el PNG generado y se confirmó su contenido. Sigue una advertencia `StarletteDeprecationWarning` procedente de una dependencia.

Las imágenes de Docker de API y worker se reconstruyeron con Pillow y se iniciaron con `docker compose --profile blackbox up -d --no-build --wait api worker`; ambos servicios quedaron saludables y `/health` respondió `ok`. El Redis aislado de pruebas se detuvo al terminar; no se vació el Redis ni se borraron datos de desarrollo.

Para comprobarlo en la interfaz, ejecuta una prueba Black Box autorizada contra un entorno de prueba con contenido visual. En el detalle de una incidencia, abre **Evidencias**: `Captura válida`, `Captura sospechosa` o `Captura no disponible` indica fecha y página; **Ver captura** aparece solo cuando existe un PNG. La descarga requiere la clave de operador. El reporte HTML conserva el ID del archivo privado y el estado de captura; el HTML descargado no incrusta ni enlaza archivos sin autorización. Usa solo cuentas y datos de prueba y revisa cualquier PNG antes de compartirlo: un diseño desconocido puede codificar información en colores o disposición.

## Fase 5.1 — Incremento 4: dashboard persistido

Con PostgreSQL y la API de Compose activos, `GET /api/v1/dashboard` devuelve conteos y últimos registros de PostgreSQL; `GET /api/v1/executions/history?limit=20&offset=0` devuelve la primera página. Ambas rutas requieren la clave de operador. Para repetir la prueba automatizada de navegador, compila el frontend y ejecuta `npm run preview -- --port 5174` en `frontend/`; luego, desde la raíz con `PYTHONPATH=backend;.`, ejecuta `.\.venv\Scripts\python.exe scripts/verify_dashboard_browser.py`. El script lee la clave desde `.env`, compara los tres conteos principales con la API, recarga Chrome, vuelve a introducir la clave y abre el historial. Para comprobar un reinicio, detén y vuelve a iniciar solo Vite y repite el script; PostgreSQL debe permanecer encendido y conservar los mismos datos.

Pruebas realizadas: PostgreSQL aislado migrado hasta `b9de73015c21`; módulo `tests/integration/test_dashboard.py` con base vacía, varios proyectos, estados, transición, filtros, paginación y autorización; suite Python completa **55 aprobadas** antes de añadir la prueba de transición; **10 pruebas frontend**, `npm run typecheck`, `npm run build` y `alembic check` aprobados. La prueba de Chrome pasó dos veces, antes y después del reinicio de Vite, con **4 proyectos, 5 ejecuciones, 6 hallazgos y 0 errores de página**. La clave se mantiene solo en memoria: tras la recarga debe introducirse de nuevo, pero el historial reaparece desde PostgreSQL. No se borraron datos de desarrollo. La repetición posterior de la suite completa se interrumpió por una demora prolongada en las pruebas existentes de Chromium; el módulo nuevo pasó 4/4 por separado. El Redis y PostgreSQL aislados de la suite de pruebas son recursos temporales independientes.

## Fase 5.1 — Incremento 5: regresión integral

Se usaron PostgreSQL y Redis **aislados** del Compose de desarrollo. La suite de dashboard comprueba conteos absolutos desde cero: ejecútala en una base de pruebas recién creada y migrada. Las pruebas de API se revierten mediante transacciones, pero el recorrido completo desde Chrome conserva filas en su propia base. Reutilizar esa base para `pytest tests` produjo 3 fallos de conteos; en una base nueva terminaron **57/57** sin borrar datos históricos. Usa un Redis de pruebas con `TESTLAB_TEST_REDIS_URL`.

Comandos principales ejecutados desde la raíz, sustituyendo puertos y contraseñas por los de tu entorno aislado:

```powershell
$env:POSTGRES_PORT = '15433'
$env:POSTGRES_PASSWORD = '<clave de PostgreSQL de pruebas>'
$env:PYTHONPATH = 'backend;.'
$env:TESTLAB_TEST_REDIS_URL = 'redis://127.0.0.1:16379/0'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m pytest tests -vv --durations=10
Set-Location frontend
npm test -- --run
npm run typecheck
npm run build
```

Resultado: **57 pruebas Python aprobadas en 88,36 s**, **10 frontend aprobadas**, TypeScript y build correctos, Alembic sin diferencias. La ejecución detallada identifica cada caso; la prueba Chromium más lenta tardó 6,67 s. La ejecución completa inicial de 56 pruebas terminó en 88,07 s. No se reprodujo el bloqueo anterior; tampoco se atribuyó una causa sin evidencia. La advertencia `StarletteDeprecationWarning` de la dependencia permanece. Las pruebas del navegador y del runner establecen límites de navegación/espera y verifican cierre tras cancelación.

Para repetir el flujo local desde la **interfaz**, primero compila el frontend y prepara PostgreSQL de pruebas en `127.0.0.1:15432`, migrado, y Redis de pruebas en `127.0.0.1:16379`; deben estar libres los puertos 18000, 18991 y 5175. Desde la raíz:

```powershell
$env:PYTHONPATH = 'backend;.'
.\.venv\Scripts\python.exe scripts/run_local_ui_regression.py
```

El guion inicia una aplicación local controlada con login ficticio, página sana, JavaScript erróneo, HTTP 500 y enlace 404; crea una API, un worker RQ privado **limitado a loopback** y Vite preview. Recorre Chrome desde registro hasta reporte y retest; recarga y luego reinicia solo Vite, dejando PostgreSQL activo, y comprueba de nuevo el acceso y el historial persistido. Resultado observado: ejecución `completed`, tres clases de hallazgo, seis evidencias, diez pasos, comparación `persisting` para los tres errores, `reload: passed` y `frontend_restart: passed`. La página sana no generó incidencia. El ensayo usa una clave de API y una clave de cifrado efímeras; deja los registros de prueba en esa base aislada. No lo apuntes al PostgreSQL de desarrollo. El guion termina los procesos que inicia y no contacta destinos externos.

Para verificar manualmente el mismo comportamiento, usa solo la aplicación local de prueba y un worker privado autorizado a `127.0.0.1/32`. En la interfaz registra el proyecto con origen exacto, configura el login ficticio, inicia la ejecución, espera su estado final y revisa que los tres hallazgos, la captura protegida, los pasos y el HTML estén disponibles. Recarga la página, introduce de nuevo la clave de operador y confirma que historial, UUID y hallazgos reaparecen. Inicia un retest y compara las rutas y reglas realmente reevaluadas; una página omitida debe dar `inconclusive`, nunca verificada. La suite también comprueba cancelación, recuperación, reintento, idempotencia y filtros; el recorrido UI automatizado ejercita el camino de ejecución y retest, no todas las ramas de fallo desde botones.

La guía [recaf-pilot.md](recaf-pilot.md) contiene la plantilla exacta de límites, origen y selectores para RECAF, los requisitos previos y la secuencia manual **solo después de una autorización específica**. Por ahora únicamente se comprobó TCP y handshake TLS: el certificado no fue aceptado por el worker. No se realizó navegación HTTP ni se usaron credenciales reales.

