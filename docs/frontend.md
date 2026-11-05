# Frontend de TestLab (Fases 3 y 5)

## Pantallas

La aplicación React incluye acceso de operador, dashboard, proyectos, configuración opcional de acceso, modalidades, ejecuciones e incidencias. **Resultados** consulta el historial persistido de ejecuciones y el listado global de incidencias; este último puede filtrarse por módulo, tipo y estado. El detalle de incidencia muestra proyecto, entorno, pasos de reproducción, capturas, JSON de evidencia, validación e historial de la misma huella. Las ejecuciones completadas con navegación registrada permiten retest y descarga de reporte HTML.

El flujo disponible es: **registrar proyecto → configurar acceso opcional → crear ejecución Black Box → consultar su estado → revisar hallazgos y pasos**. El motor y el worker procesan la solicitud solo cuando la cola está habilitada. Sin ella, la fila permanece `pending`. White Box e híbrido se presentan como modalidades futuras, sin controles funcionales ni datos simulados.

## Estructura y componentes

- `src/services/api.ts` concentra `fetch`, cabeceras de autorización, errores y llamadas tipadas. `types.ts` refleja los contratos de respuesta.
- `src/hooks/useAppState.tsx` mantiene la clave de operador en memoria. El historial se consulta desde PostgreSQL; ningún secreto se guarda en `localStorage`, `sessionStorage` o logs.
- `src/hooks/useResource.ts` maneja carga, cancelación y reintento de consultas.
- `src/components/UI.tsx` comparte paneles, encabezados, campos, avisos y estados de carga, vacío y error.
- `src/layouts/AppLayout.tsx` organiza navegación responsiva. `src/pages/` separa cada flujo.

## Endpoints consumidos

| Función | Endpoint |
| --- | --- |
| Estado de API | `GET /health` |
| Proyectos | `GET /api/v1/projects`, `GET /api/v1/projects/{id}`, `POST /api/v1/projects` |
| Acceso opcional | `POST /api/v1/projects/{id}/credentials` |
| Ejecuciones | `POST/GET /api/v1/executions`, `GET /api/v1/executions/{id}`, `POST /api/v1/executions/{id}/retest`, `GET /api/v1/executions/{id}/comparison` |
| Resultados | `GET /api/v1/executions/{id}/findings`, `GET /api/v1/executions/{id}/steps`, `GET /api/v1/findings`, `GET /api/v1/findings/{id}`, `GET /api/v1/findings/{id}/history` |
| Evidencia y validación | `GET /api/v1/findings/{id}/evidence`, `GET /api/v1/evidence/{id}`, `GET/POST /api/v1/findings/{id}/validations` |
| Reporte | `GET /api/v1/executions/{id}/report` |

En desarrollo, Vite reenvía `/api` y `/health` a `127.0.0.1:8000`. En producción, servir la interfaz y la API bajo el mismo origen mediante un proxy. `VITE_API_BASE_URL` solo sirve si la API permite el origen del frontend; no debe contener secretos.

## Límites actuales

- El dashboard conserva sus tarjetas de sesión; **Resultados** sí consulta el historial global y las incidencias de la API.
- No hay porcentaje de progreso ni edición de proyecto/entorno. La API devuelve el error final de ejecución, pero no una traza interna.
- La clave de operador en memoria se pierde al recargar. Esto evita persistir secretos, pero requiere volver a introducirla.
- La política de DNS, IP y redirecciones se aplica en el worker, no en el navegador de la interfaz. El worker público no admite destinos privados.

Consulta [api.md](api.md) para el contrato completo y [roadmap.md](roadmap.md) para las fases pendientes.
