# API de TestLab — Fases 2 a 5

La especificación OpenAPI se genera desde el código en `http://127.0.0.1:8000/openapi.json`; la interfaz está en `http://127.0.0.1:8000/docs`. `/health` es público y comprueba la conexión a PostgreSQL.

Todas las rutas `/api/v1/*` requieren `Authorization: Bearer <TESTLAB_API_KEY>`. La Fase 2 usa un único operador local: la clave autoriza el acceso a todos los proyectos y resultados. No hay todavía usuarios, roles ni separación entre organizaciones. Despliega la API solo detrás de TLS si se accede fuera del equipo local.

Ejemplo de consulta local en PowerShell, sin imprimir la clave:

```powershell
$keyLine = Get-Content .env | Where-Object { $_ -match '^TESTLAB_API_KEY=' } | Select-Object -First 1
$apiKey = $keyLine.Substring('TESTLAB_API_KEY='.Length)
Invoke-RestMethod http://127.0.0.1:8000/api/v1/projects -Headers @{ Authorization = "Bearer $apiKey" }
```

## Proyectos

| Método y ruta | Descripción |
| --- | --- |
| `POST /api/v1/projects` | Crea un proyecto, su entorno inicial y sus orígenes autorizados explícitos. |
| `GET /api/v1/projects?limit=50&offset=0` | Lista proyectos con paginación. |
| `GET /api/v1/projects/{id}` | Consulta un proyecto. |
| `POST /api/v1/projects/{id}/credentials` | Configura o reemplaza credenciales de formulario cifradas. La respuesta omite usuario y contraseña. |

Ejemplo de registro:

```json
{
  "name": "Plataforma de pruebas",
  "base_url": "https://example.test/app",
  "environment": "staging",
  "modality": "blackbox",
  "authorized_origins": ["https://example.test"]
}
```

El origen de `base_url` debe figurar explícitamente en `authorized_origins`. Se aceptan HTTP y HTTPS sin usuario, contraseña, query ni fragmento. El registro no provoca ninguna petición al destino. El login configurado también debe pertenecer a un origen autorizado. DNS, IP y redirecciones se validan en el worker antes de navegar.

La configuración de credenciales solicita `login_url`, selectores de usuario, contraseña y envío, una condición de éxito (`success_selector` o `success_url_pattern`), `username` y `password`. Ambos valores se cifran con Fernet antes de guardarse; la clave se obtiene de `TESTLAB_FERNET_KEY` fuera de PostgreSQL. No existe una ruta para leer secretos descifrados.

## Ejecuciones y resultados

| Método y ruta | Descripción |
| --- | --- |
| `POST /api/v1/executions` | Valida proyecto y alcance; crea `pending` y pasa a `queued` si se encola. Admite cabecera opcional `Idempotency-Key` (8–128 caracteres). |
| `GET /api/v1/executions?limit=50&offset=0&project_id=...` | Historial de ejecuciones persistidas. |
| `GET /api/v1/dashboard` | Conteos globales de proyectos, ejecuciones por estado y hallazgos, cinco ejecuciones recientes y cinco proyectos recientes con su última ejecución. |
| `GET /api/v1/executions/history?limit=20&offset=0&project_id=...&status=...` | Historial paginado con total, proyecto, modalidad, fechas, hallazgos y vínculo de retest/reintento. `limit` 1–100, `offset` 0–100000; filtros validados. |
| `GET /api/v1/executions/{id}` | Consulta estado y límites de una ejecución. |
| `POST /api/v1/executions/{id}/cancel` | Cancela inmediatamente `pending`/`queued` o solicita cancelación cooperativa de `running`, que pasa a `cancelling`. Repetir la solicitud es seguro. |
| `GET /api/v1/executions/{id}/cancellation` | Consulta solicitud, estado y fin efectivo de la cancelación. |
| `POST /api/v1/executions/{id}/retry` | Reintento explícito de una ejecución `failed`/`cancelled`; crea un UUID nuevo y registra `retry_of_run_id`. Acepta `Idempotency-Key`. |
| `GET /api/v1/executions/{id}/findings?limit=50&offset=0` | Lista hallazgos persistidos. |
| `GET /api/v1/executions/{id}/steps?limit=50&offset=0` | Lista pasos persistidos. |
| `GET /api/v1/executions/{id}/rule-evaluations?limit=100&offset=0` | Lista reglas efectivamente evaluadas, página, URL, tipo de recurso y resultado, incluso cuando no hubo error. |
| `GET /api/v1/executions/{id}/report` | Descarga un reporte HTML escapado y sin archivos de evidencia embebidos. |
| `POST /api/v1/executions/{id}/retest` | Crea una nueva ejecución con límites y URLs de navegación registradas anteriormente. Requiere ejecución terminada y pasos navegables. |
| `GET /api/v1/executions/{id}/comparison` | Compara escenarios, reglas reevaluadas, resultados, evidencias y fechas. Devuelve `persisting`, `not_observed_pending_verification`, `inconclusive`, `technical_failure`, `unknown` o `new` según la cobertura y el estado. |

El dashboard cuenta como pendientes de confirmación los hallazgos con `validation_status` `detected` o `pending_confirmation`. Sus listas recientes tienen máximo cinco elementos; el historial devuelve `{total, limit, offset, items}` y cada elemento incluye `finding_count`, `retry_of_run_id` y `retest_of_run_id`. Los filtros de historial se aplican en PostgreSQL antes de paginar. Las respuestas resumidas omiten credenciales y rutas privadas de evidencias.

## Incidencias y evidencias

| Método y ruta | Descripción |
| --- | --- |
| `GET /api/v1/findings` | Lista incidencias con filtros opcionales `project_id`, `module`, `error_type`, `validation_status`, `limit` y `offset`. |
| `GET /api/v1/findings/{id}` | Detalle con proyecto, ejecución, entorno y huella del hallazgo. |
| `GET /api/v1/findings/{id}/history` | Hallazgos equivalentes del mismo proyecto, incluidos otros runs. |
| `GET /api/v1/findings/{id}/evidence` | Metadatos de archivos vigentes, sin rutas privadas. |
| `GET /api/v1/evidence/{id}` | Descarga autorizada de PNG o JSON; no se cachea. |
| `DELETE /api/v1/evidence/{id}` | Elimina el archivo privado y su fila de metadatos. |
| `GET /api/v1/findings/{id}/validations` | Historial de validaciones manuales. |
| `POST /api/v1/findings/{id}/validations` | Cambia el estado con cuerpo `{"status":"confirmed","notes":"..."}` y registra actor `operator`, fecha y observaciones. |

Estados disponibles: `detected`, `pending_confirmation`, `confirmed`, `not_reproducible`, `false_positive`, `fixed` y `retested`. La API valida transiciones; `fixed` y `retested` requieren notas. `retested` exige además un retest completo del run original con la página visitada, navegación registrada, login repetido si era necesario y la misma regla evaluada sin coincidencia. Una ausencia sin esa cobertura devuelve 409. El operador único no permite identificar personas distintas. Una sola ejecución limpia no cambia automáticamente el estado de la incidencia anterior.

`GET /findings/{id}` expone `scenario` con página, URL, regla y tipo de recurso saneados, o `null` para hallazgos históricos sin trazabilidad suficiente. Cada paso expone `page_url`. Las evaluaciones están paginadas; `matched` indica si la regla detectó su condición y `observed_status` registra el estado HTTP cuando corresponde. Un retest histórico sin escenario original se considera `inconclusive` aunque no aparezca la huella.

Una captura nueva puede acompañarse de un artefacto privado `screenshot_status`. Su fila en `GET /findings/{id}/evidence` incluye `capture_status` (`valid`, `suspicious`, `invalid` o `unavailable`), `capture_reason`, `page_url` saneada, `captured_at` y dimensiones cuando existen. `screenshot` solo aparece si se guardó un PNG decodificable; una página blanca legítima puede conservarse como `suspicious`. Las filas antiguas no reciben este estado retroactivamente. La descarga del PNG y del JSON de estado exige la misma autorización.

La huella combina tipo, URL sin query ni fragmento, mensaje observado, módulo y elemento cuando exista. Es única dentro de una ejecución y sirve para agrupar el historial por proyecto sin descartar evidencias de ejecuciones distintas. Los pasos de reproducción se derivan de navegación y login registrados. Cuando no existe recorrido suficiente, se indica la carencia. `expected_result` solo se llena al aplicar una regla de estado configurada.

Ejemplo de creación:

```json
{
  "project_id": "00000000-0000-0000-0000-000000000000",
  "max_pages": 20,
  "max_depth": 3,
  "max_requests": 200,
  "max_concurrency": 1,
  "page_timeout_ms": 15000,
  "execution_timeout_ms": 120000
}
```

`pending` significa **registro creado**; `queued`, trabajo aceptado por RQ; `running`, navegador activo; `cancelling`, solicitud recibida mientras termina el navegador; `cancelled`, detención concluida. `completed` permite hallazgos de la plataforma probada; `failed` indica problema técnico o interrupción. Una cola no disponible devuelve `failed` con un mensaje genérico. Una clave de idempotencia repetida con los mismos datos devuelve el mismo UUID; con datos distintos devuelve 409. Los errores de dominio tienen forma `{"error":{"code":"...","message":"..."}}`. Las peticiones inválidas devuelven 422 sin repetir datos sensibles. No existe porcentaje de progreso.
