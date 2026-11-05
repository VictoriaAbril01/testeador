# Motor Black Box (Fase 4)

## Alcance implementado

`tester/runner.py` usa Chromium con un contexto aislado por ejecución, timeouts y cierre de recursos en `finally`. Descubre enlaces de páginas visibles sin pulsar botones ni enviar formularios generales. `tester/discovery/dom.py` registra títulos, encabezados, menús, enlaces, formularios, botones, campos, etiquetas y selectores estables cuando existen. Solo asigna un módulo si la página declara `data-module`; en los demás casos queda sin identificar.

El login opcional utiliza los selectores configurados y únicamente permite el POST del formulario seleccionado. Exige un selector o patrón literal de URL para confirmar la sesión. No intenta resolver CAPTCHA, MFA ni otros controles. Una ejecución sin credenciales visita la URL base directamente.

El motor guarda pasos ordenados con acción, pantalla, módulo si consta, elemento, resultado y fecha; las peticiones bloqueadas también dejan un paso de auditoría. Observa excepciones JavaScript, respuestas HTTP 4xx/5xx, fallos de petición y navegación y tiempos agotados. Puede comparar respuestas con reglas exactas `expected_statuses` al invocarlo desde Python; la API aún no ofrece un campo para configurarlas. `tester/analyzers/rules.py` clasifica señales técnicas y deja 5xx/JavaScript como pendientes de confirmación funcional. Un enlace visitado que devuelve 404 se marca como enlace roto detectado. La página sin errores de la aplicación de prueba no genera hallazgos.

`workers/jobs.py` toma una ejecución `pending`, descifra credenciales únicamente en memoria del worker, ejecuta el motor y guarda páginas, pasos y hallazgos en PostgreSQL. El estado termina en `completed` o `failed`, con un motivo genérico seguro. RQ transporta solo el UUID de la ejecución. El worker del perfil `blackbox` se inicia explícitamente; la API encola nuevas solicitudes solo con `TESTLAB_QUEUE_ENABLED=true`. Las solicitudes anteriores no se encolan automáticamente.

## Política de seguridad

- Solo acepta orígenes HTTP(S) explícitos, por esquema, host y puerto. Resuelve todos los hosts antes de arrancar Chromium, rechaza respuestas DNS mixtas con direcciones privadas y fija los hosts autorizados a IPs revisadas en Chromium.
- Intercepta cada salto de petición, incluso redirecciones, mediante el protocolo de depuración de Chromium. Playwright `route()` por sí solo no vuelve a interceptar una redirección; por eso no se usa como límite de seguridad.
- Rechaza destinos privados por defecto, incluidas direcciones de loopback. Una ejecución interna requiere un worker separado con acceso de red concedido expresamente, `TESTLAB_PRIVATE_WORKER=true` y CIDRs privados concretos en `TESTLAB_PRIVATE_CIDRS`. El worker de Compose no recibe esas variables.
- Permite solo GET/HEAD durante el descubrimiento. La única excepción es el POST del formulario de login configurado. Omite navegación con parámetros, rutas potencialmente destructivas y enlaces fuera del alcance. Los límites de páginas, profundidad, solicitudes y tiempo son obligatorios. La navegación es secuencial, así que nunca supera `max_concurrency`.
- Desactiva service workers, descargas, WebSockets, workers JavaScript y apertura de ventanas adicionales; esas vías no forman parte del recorrido autorizado. El navegador no lee valores de campos en el inventario; las URLs registradas omiten query y fragmento. Los mensajes de excepciones JavaScript no se guardan porque podrían contener secretos.

El interceptor y la fijación DNS reducen SSRF, pero un despliegue contra plataformas no confiables también debe imponer una política de salida de red fuera del proceso del navegador. El worker público de Compose comparte red con los servicios de datos y **no debe recibir permisos de destinos privados**. No se debe habilitar una red interna en él cambiando solo variables de entorno.

## Límites conocidos

- El descubrimiento sigue enlaces visibles; no explora acciones que cambien datos ni flujos SPA que solo se abren mediante botones.
- La API no configura todavía reglas de respuestas esperadas ni ofrece porcentaje de progreso. El listado global, los archivos privados y el reporte HTML se añadieron en la Fase 5; otros formatos siguen pendientes.
- El motor registra señales observables. Un HTTP 500 o una excepción JavaScript no demuestran por sí solos un fallo funcional confirmado.
- La política actual solo fija hosts con IPv4; destinos públicos únicamente IPv6 se rechazan de forma segura.
- Si el proceso del worker se interrumpe de forma abrupta, la fila puede quedar en `running` hasta una reconciliación manual; aún no existe un mecanismo de recuperación de ejecuciones huérfanas.

## Verificación realizada

La aplicación FastAPI local de `tests/integration/test_blackbox_browser.py` incluye login, varias páginas, un error JavaScript, HTTP 500, enlace 404, redirecciones fuera de alcance, una ruta destructiva, intentos de WebSocket y worker JavaScript, y una página sana. Las pruebas reales de Chromium comprueban navegación, aislamiento, detecciones, pasos, persistencia, bloqueo de destinos, límite de solicitudes, páginas y tiempo. El contenedor del worker arrancó Chromium y creó un contexto aislado correctamente. Consulta [testing.md](testing.md) para los comandos.

