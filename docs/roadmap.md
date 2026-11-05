# Roadmap de TestLab

Estado actualizado: 13 de octubre de 2026. Cada fase requiere autorización separada. Marca una tarea como terminada solo cuando exista una implementación verificable; actualiza este archivo al cerrar cada fase o al cambiar su alcance.

## Fase 1 — Fundamentos: terminada

- [x] Inicializar el repositorio Git y crear la estructura base de carpetas.
- [x] Documentar requisitos, arquitectura, seguridad, instalación y verificación.
- [x] Configurar PostgreSQL y Redis para desarrollo local con Docker Compose.
- [x] Validar Compose y comprobar que ambos servicios respondan y estén saludables.
- [x] Ignorar `.env` y proporcionar `.env.example` sin secretos reales.

**Entregado:** infraestructura local y documentación. Aún no existe funcionalidad de aplicación.

## V0.1 — Flujo Black Box de extremo a extremo

El usuario autorizó y se implementó la Fase 5 de evidencias y reportes. La [auditoría integral del MVP](mvp-audit.md) comprobó el flujo completo y encontró requisitos parciales en las Fases 2 a 5; por ello **ninguna se considera cerrada sin reservas**. La cancelación por API y la reconciliación conservadora de workers se implementaron en el incremento 2 de la Fase 5.1; permanecen los problemas P1 y los límites de recuperación descritos en la auditoría.

1. [x] Modelos SQLAlchemy y migración inicial de PostgreSQL para las entidades solicitadas.
2. [x] API de proyectos, validación de URL y alcance explícito; autorización de operador único.
3. [x] Navegación y descubrimiento básicos con Playwright, límites de seguridad, credenciales cifradas y login configurable.
4. [x] Observación y clasificación de errores JavaScript, HTTP y navegación, más tiempos básicos.
5. [x] Persistencia y consulta de ejecuciones, páginas, pasos y hallazgos sin duplicados; reproducción manual basada en acciones registradas.
6. [x] Ejecución asíncrona, cancelación y timeouts con Redis y RQ. El incremento 2 agregó cancelación cooperativa y reconciliación conservadora; quedan los límites de interrupción forzada documentados en la auditoría.
7. [x] Evidencias sanitizadas, almacenamiento privado, límites, retención y pasos de reproducción manual.
8. [x] Integración del frontend con proyectos, historial de ejecuciones, hallazgos, evidencias, validación, retest y reporte HTML.
9. [x] Pruebas end to end del motor contra una aplicación local controlada.
10. [x] Documentación de operación y resultados de las Fases 2 a 5.

La V0.1 sigue **incompleta** por los problemas P1 y límites de recuperación de [mvp-audit.md](mvp-audit.md). El flujo de incidencias, evidencia privada, validación y reporte HTML funciona bajo las limitaciones allí descritas.

## Fase 5.1 — Estabilización del MVP: en curso

1. [x] **Retesting confiable:** escenario original, acciones y reglas evaluadas persistidas; comparación conservadora y bloqueo de `retested` sin cobertura. Suite local: 39 pruebas Python, 4 frontend, migración y build aprobados. Los hallazgos anteriores a la migración quedan inconclusos. Detalle en [mvp-audit.md](mvp-audit.md#fase-51--incremento-1-retesting-confiable).
2. [x] **Workers y ejecución:** estados `queued`/`cancelling`, cancelación cooperativa, idempotencia, heartbeat, reconciliación sin reejecución automática y reintento explícito. Migraciones `a10e312cb840` y `b9de73015c21`; pruebas de PostgreSQL, Redis y RQ real. Detalle en [mvp-audit.md](mvp-audit.md#fase-51--incremento-2-workers-y-recuperacion).
3. [x] **Capturas y evidencias:** espera de renderizado observable, redacción visual con contexto, validación PNG, clasificación válida/sospechosa/no disponible y estado asociado a la incidencia. Prueba visual local inspeccionada; detalle en [mvp-audit.md](mvp-audit.md#fase-51--incremento-3-capturas-y-evidencias).
4. [x] Dashboard e historial consultan PostgreSQL mediante FastAPI; conteos, filtros, paginación y actualización periódica de trabajos activos. Verificado en Chrome tras recarga y reinicio de Vite, sin reiniciar PostgreSQL.
5. [x] Regresión integral de la Fase 5.1: 57 pruebas Python, 10 frontend, TypeScript, build, Alembic y recorrido automatizado desde Chrome por frontend, API, PostgreSQL, Redis/RQ, worker, analizadores, evidencias y reporte. El historial sobrevivió a la recarga. El piloto RECAF aún requiere CA confiable, despliegue interno dedicado, confirmar compatibilidad de login y autorización específica. Detalle en [mvp-audit.md](mvp-audit.md#fase-51--incremento-5-regresion-integral-y-preparacion-del-piloto).

## Fase 2 — Backend: implementada; pendientes de auditoría

- [x] Fijar Python 3.13 para modelos y migraciones; verificar las dependencias restantes al introducirlas.
- [x] Proteger proyectos, credenciales y resultados con una clave de operador de entorno. El acceso multiusuario queda pendiente.
- [x] Crear FastAPI, configuración por variables de entorno, manejo centralizado de errores y `/health`.
- [x] Configurar conexión PostgreSQL mediante SQLAlchemy y Alembic para migraciones.
- [x] Crear modelos y migraciones para proyectos, entornos, destinos autorizados, credenciales, ejecuciones, páginas, pasos, hallazgos y evidencias.
- [x] Implementar los endpoints solicitados, configuración cifrada de credenciales, validación Pydantic y pruebas de API y persistencia.
- [x] Documentar los contratos HTTP reales en `docs/api.md` y exponer OpenAPI.

## Fase 3 — Frontend: implementada; pendientes de auditoría

- [x] Configurar React, TypeScript, Vite y pruebas con Vitest.
- [x] Crear acceso de operador, dashboard, proyectos, configuración opcional de credenciales, modalidades, ejecución y consulta de resultados.
- [x] Consumir la API real, validar formularios, manejar carga y errores, y verificar el flujo en Chrome.
- [x] Mostrar las modalidades White Box e híbrida como no disponibles; Black Box ejecuta trabajos si la cola está habilitada y deja solicitudes `pending` si está deshabilitada.

**Pendiente:** porcentaje de progreso y edición de URL/entorno de proyectos. El dashboard persistido se corrigió en el incremento 4 de la Fase 5.1. La cancelación de ejecuciones se incorporó en el incremento 2; el listado global de incidencias y las evidencias se incorporaron en la Fase 5.

## Fase 4 — Motor Black Box: criterios principales probados; pendientes de auditoría

- [x] Validar alcance, URLs, DNS, direcciones de destino y cada salto de redirección; bloquear destinos no autorizados.
- [x] Aplicar límites de páginas, profundidad, solicitudes y tiempo; navegación secuencial y no destructiva por defecto.
- [x] Implementar autenticación de formulario configurable, navegación y descubrimiento con Playwright.
- [x] Detectar errores JavaScript, HTTP 4xx/5xx, reglas de estado configuradas programáticamente y fallos observables de navegación.
- [x] Registrar páginas, pasos, observaciones y estado final desde el worker.
- [x] Capturas y otros archivos de evidencia sanitizados: implementados en la Fase 5 con política de retención.

## Fase 5 — Evidencias, reproducción y reportes: implementada; pendientes de auditoría

- [x] Registrar navegación, pasos ejecutados y URLs repetibles del escenario.
- [x] Generar instrucciones de reproducción manual basadas únicamente en acciones observadas e indicar datos faltantes.
- [x] Guardar capturas con contenido oculto, logs de consola sin texto libre, metadatos HTTP, trazas y pasos como archivos privados con límites, retención y descarga autorizada.
- [x] Agrupar incidencias equivalentes por huella sin eliminar registros ni evidencias de otras ejecuciones.
- [x] Validación manual con transiciones, actor, fecha, notas e historial.
- [x] Retest básico de navegación registrada y comparación sin marcar automáticamente un error como corregido.
- [x] Reporte HTML descargable e interfaz para incidencias, filtros, evidencias, validación, historial y retest.
- [x] Pruebas unitarias, de API, PostgreSQL y navegador real; tipos, build y pruebas frontend.

**Pendiente:** ampliar la protección visual a patrones de páginas desconocidas, mejorar la huella de errores y los pasos de reproducción, y distinguir observaciones de incidencias en el reporte. La cobertura del retest se corrigió en el primer incremento de la Fase 5.1 y las capturas en el tercero. Evidencia y prioridades: [mvp-audit.md](mvp-audit.md).

## Fase 6 — White Box: pendiente

- [ ] Aislar repositorios autorizados sin ejecutar su código por defecto.
- [ ] Identificar lenguajes, frameworks, dependencias y pruebas existentes.
- [ ] Integrar analizadores estáticos compatibles y reportar archivos y líneas solo con evidencia.

## Fase 7 — Híbrido: pendiente

- [ ] Correlacionar hallazgos dinámicos con código cuando haya evidencia verificable.
- [ ] Distinguir errores confirmados, posibles causas y hallazgos pendientes.
- [ ] Generar reportes unificados.

## Fase 8 — Optimización: pendiente

- [ ] Ampliar el retest a escenarios de interacción autorizados y políticas de verificación explícitas; el retest básico de navegación quedó implementado en la Fase 5.
- [ ] Revisar rendimiento, aislamiento y controles de seguridad.

## Decisiones abiertas

- Usuarios, roles y separación de proyectos antes de admitir más de un operador; rotación de la clave de cifrado antes de un despliegue compartido.
- Acciones que cambian datos más allá del login de prueba, y autorización explícita de cada una antes de habilitarlas.
- La reconciliación y cancelación API básicas quedaron implementadas en el incremento 2 de la Fase 5.1. Persisten límites de recuperación cuando Redis está indisponible o un proceso no puede cerrar recursos tras un apagado forzado.
- Evaluar cifrado del volumen privado y controles por usuario antes de permitir varios operadores o distribuir reportes fuera de QA.
- Diseño separado para destinos de red privada antes de habilitarlos.

Los requisitos y los límites de seguridad se detallan en [requirements.md](requirements.md) y [architecture.md](architecture.md).
