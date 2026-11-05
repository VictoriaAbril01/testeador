# Arquitectura

## Componentes

- `frontend/`: React, TypeScript y Vite. Interfaz modular para proyectos, ejecuciones e incidencias; usa un cliente HTTP centralizado, rutas declarativas y estado de sesión en memoria.
- `backend/`: FastAPI, validación Pydantic, autorización de operador, cifrado Fernet, modelos SQLAlchemy y conexión PostgreSQL.
- `tester/`: motor Black Box modular de política de destinos, descubrimiento DOM, escenarios tipados, análisis, evidencias, reproducción y reportes HTML basados en reglas.
- `workers/`: trabajo de RQ sobre Redis que ejecuta el motor y persiste páginas, pasos, hallazgos y archivos privados.
- `database/migrations/`: esquema y evoluciones administrados por Alembic.
- `tests/`: pruebas unitarias, de integración y end to end.
- `docs/` y `scripts/`: documentación y utilidades reproducibles.

API, worker y motor comparten este repositorio como procesos separados. PostgreSQL almacena datos transaccionales; Redis transporta trabajos. Los archivos de evidencia permanecen en un volumen privado compartido por API y worker, con metadatos, límites y vencimiento en PostgreSQL. Consulta [evidence-reports.md](evidence-reports.md).

El esquema contiene `projects`, `environments`, `authorized_targets`, `credentials`, `test_runs`, `discovered_pages`, `test_steps`, `findings`, `rule_evaluations`, `evidence` y `finding_validations`. La migración de entornos conserva los proyectos existentes. `projects.environment` y `projects.base_url` siguen como valores iniciales por compatibilidad. `credentials` almacena únicamente bytes cifrados; `evidence` guarda metadatos y rutas relativas, no binarios. Los hallazgos tienen una huella única por ejecución; la misma huella permite consultar ocurrencias posteriores del mismo proyecto. `test_runs.retest_of_run_id` une cada retest con su ejecución origen y `scenario_urls` registra los destinos que se repetirán. `findings.scenario` guarda página, URL, regla, tipo de recurso y requisito de login observados; `test_steps.page_url` y `rule_evaluations` prueban qué ruta y regla se ejecutaron realmente. Los hallazgos anteriores a la migración de cobertura tienen escenario nulo y sus ausencias en retest son inconclusas.

La API exige una clave de operador en todas las rutas de datos. Esta es una política de un solo operador y una sola instancia: no distingue propietarios de proyectos. El acceso multiusuario y los roles requieren un diseño posterior. La API valida URLs y orígenes explícitos sin hacer peticiones a las plataformas. El worker valida DNS/IP y cada salto de redirección antes de navegar. Las ejecuciones creadas por la API se encolan solo con `TESTLAB_QUEUE_ENABLED=true`; de otro modo permanecen `pending`.

El dashboard consulta un resumen agregado de PostgreSQL mediante `GET /api/v1/dashboard`; el historial usa `GET /api/v1/executions/history` con filtros validados y paginación. React no usa su lista temporal de ejecuciones para estos datos. La clave de operador solo vive en memoria: tras recargar, el usuario vuelve a introducirla y las consultas recuperan los registros persistidos. El frontend consulta periódicamente únicamente mientras hay trabajos activos y limpia sus intervalos al desmontar la vista.

## Flujo implementado

1. El usuario define proyecto, entorno, destino y alcance autorizado.
2. La API valida la configuración y registra una ejecución auditable.
3. Un worker toma el trabajo, aplica límites y ejecuta el motor pertinente.
4. El motor produce observaciones, capturas con texto oculto y metadatos sanitizados.
5. El analizador basado en reglas convierte observaciones en incidencias; la reproducción usa únicamente acciones registradas.
6. La API permite revisar evidencias, validar incidencias, consultar historial, comparar retests y descargar HTML.

La comparación de retest exige estado `completed`, visita real de la página, paso de navegación exitoso, login repetido si correspondía y evaluación de la misma regla sobre la misma URL y tipo de recurso. Una regla que vuelve a coincidir indica persistencia; una evaluación sin coincidencia queda pendiente de confirmación manual. Sin cobertura, el resultado es inconcluso; un retest `failed` se muestra como fallo técnico. Solo una evaluación cubierta sin coincidencia permite la transición manual a `retested`.

El ciclo de ejecución usa `pending → queued → running → completed/failed`, con `running → cancelling → cancelled` para cancelación cooperativa. Una solicitud aún no encolada puede pasar de `pending` a `cancelled`; el worker reclama `pending` o `queued` bajo bloqueo de fila y rechaza estados terminales. Cada trabajo RQ usa el UUID de la ejecución como `job_id`; la API acepta una cabecera opcional `Idempotency-Key`, guarda únicamente su huella y rechaza el mismo identificador si cambia la configuración. Un reintento explícito crea otra fila con `retry_of_run_id`; la reconciliación nunca reencola automáticamente.

El worker actualiza `heartbeat_at` mientras el navegador está activo y consulta `cancellation_requested` cada medio segundo. La API reconcilia Redis y PostgreSQL cada cinco segundos. Espera 45 segundos antes de declarar perdido un trabajo sin cola, o interrumpida una ejecución cuando tanto la señal de PostgreSQL como la de RQ están vencidas. Si Redis no responde, conserva el estado hasta disponer de evidencia; si RQ termina y PostgreSQL sigue activo tras la gracia, marca `failed` con un mensaje técnico. Un timeout duro de RQ puede impedir el cierre normal de Chromium y se trata como interrupción técnica para reconciliar. La salida de red externa y el aislamiento privado continúan sujetos a los límites anteriores.

La interfaz del analizador separará la recolección de observaciones de su interpretación. Un analizador futuro podrá usar IA sin alterar el contrato de ejecución ni el almacenamiento de evidencias. No se instalarán SDK ni servicios de IA en el MVP.

## Límites de seguridad

La primera versión Black Box se limita por defecto a destinos públicos expresamente autorizados. Antes de navegar, el worker resuelve DNS, rechaza direcciones fuera de política y fija hosts autorizados a IPs revisadas. Cada petición y salto de redirección pasa por un interceptor de Chromium que verifica esquema, host, puerto, método y límites. Los destinos privados requieren un despliegue separado con acceso de red expresamente concedido, además de CIDRs concretos. El worker público de Compose no admite destinos privados. Para un despliegue frente a plataformas no confiables se requiere además un control de salida de red externo al navegador.

Las credenciales de prueba se cifrarán antes de persistirse; la clave se obtendrá fuera del repositorio. No se registrarán contraseñas, tokens ni cookies en texto plano. Los workers tendrán límites de tiempo, solicitudes y concurrencia, y la navegación será no destructiva por defecto. El análisis White Box aislará repositorios y no ejecutará scripts de terceros sin autorización. Cada ejecución dejará un registro de auditoría. No se desactivarán TLS ni los controles de autenticación.

## Decisiones por cerrar antes de cada implementación

- Para los modelos y migraciones se eligió Python 3.13; el equipo también dispone de Python 3.14. La compatibilidad de las dependencias de API, navegador y worker se verificará al introducirlas.
- Autenticación multiusuario y roles antes de habilitar colaboración o acceso de distintos propietarios; la Fase 2 usa una clave de operador para todos los proyectos.
- Política concreta de acciones permitidas y aprobación de cambios de datos antes del motor Black Box.
- Almacenamiento, sanitización y retención de capturas y trazas antes de guardar evidencias.
- Política para redes privadas y separación de workers internos y externos antes de habilitar esos destinos.
