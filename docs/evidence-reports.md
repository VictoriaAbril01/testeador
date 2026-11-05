# Fase 5: evidencias, incidencias y retest

## Registro y reproducción

El worker convierte observaciones de Chromium en hallazgos mediante reglas. Guarda tipo, severidad, módulo y pantalla solo cuando existen en el registro observado. Las instrucciones manuales se construyen desde los pasos `navigate` y `submit_login`; si falta una navegación, se advierte. La clasificación técnica sigue pendiente de confirmación humana salvo los casos que el analizador identifica expresamente. Las incidencias equivalentes se agrupan por huella dentro del mismo proyecto, conservando filas y evidencias separadas por ejecución.

El historial de validación guarda cada transición, actor `operator`, fecha y notas. La clave de operador único permite auditar una cuenta operativa, pero no distinguir personas. Los estados `fixed` y `retested` requieren una explicación manual; `retested` exige además un retest completo que haya visitado la página original, repetido el login si aplicaba y evaluado de nuevo la misma regla, URL y tipo de recurso sin detectar el error. Si falta alguno de esos datos, el resultado es inconcluso y se rechaza la transición. TestLab nunca la asigna automáticamente por una ejecución sin error.

## Archivos privados

PostgreSQL guarda UUID, tipo, ruta relativa, tamaño, SHA-256 y vencimiento. Los archivos se escriben bajo `TESTLAB_EVIDENCE_ROOT`: por defecto `artifacts/private` fuera de directorios públicos; en Compose, un volumen `evidence_data` compartido solo entre API y worker en `/var/lib/testlab/evidence`. Las rutas usan UUID validados. La API requiere la clave de operador y entrega los archivos con `Cache-Control: no-store`; nunca devuelve la ruta interna en JSON. Cada archivo está limitado a 1 MB y cada ejecución a 20 MB. Las capturas usan un viewport 1280×720, esperan una señal observable de renderizado con límite de tiempo, ocultan todos los glifos, controles editables y medios, y conservan bloques de color y siluetas de títulos/enlaces para ubicar la pantalla. El PNG se decodifica y clasifica como válido o sospechoso; una imagen vacía, corrupta o excesiva no se ofrece como captura. Cada incidencia con intento de captura recibe un archivo privado `screenshot_status` con URL saneada, fecha, dimensiones, estado y motivo; `unavailable` indica que no existe PNG utilizable. Una página genuinamente uniforme puede clasificarse como sospechosa y conservarse. Playwright no guarda cookies, cabeceras ni cuerpos de respuesta. Los pasos de login sustituyen selectores configurados por nombres genéricos. Los logs de consola guardan tipo y página, sustituyendo el mensaje libre por una descripción genérica. Los metadatos HTTP contienen método, URL saneada, estado y tipo de recurso.

La retención predeterminada es 30 días (`TESTLAB_EVIDENCE_RETENTION_DAYS`, válido de 1 a 365). La API ejecuta limpieza al iniciar y cada hora; el worker también la ejecuta antes de cada trabajo. Para mantenimiento manual: `python -m workers.cleanup` con `PYTHONPATH=backend;.`. `DELETE /api/v1/evidence/{id}` elimina un archivo concreto. El reporte HTML menciona IDs y tamaños de evidencias, sin incluir archivos ni enlaces públicos. Aunque se oculta el contenido visual sensible conocido, revisa una captura antes de compartirla fuera del entorno de QA: una página puede codificar datos inesperados en estilos o disposición.

## Retest y reporte

El retest usa el mismo proyecto, límites y las URLs intentadas que constan en una ejecución `completed`; el worker vuelve a aplicar alcance, DNS y límites. La autenticación configurada se repite con una sesión nueva. No reejecuta clics de negocio ni acciones de escritura. La comparación ofrece huella, resultado previo y actual, número de evidencias y fecha de ambas ejecuciones. Una regla reevaluada sobre la página cubierta sin detectar el error se presenta como `not_observed_pending_verification`; sin cobertura queda `inconclusive`. Un retest `failed` produce `technical_failure`, mientras que `pending` y `running` producen `unknown`. Los hallazgos anteriores a la migración de cobertura quedan inconclusos. El reporte HTML descargable incluye resumen, tipos, módulos, incidencias, estados, pasos y referencias privadas de evidencias. La estructura de `tester/reports/` permite añadir otros formatos en otra fase.

## Verificación manual

1. Arranca API, worker y frontend con la cola activada en un entorno de prueba autorizado. La base de datos aplica la migración al arrancar la API.
2. Crea una ejecución Black Box y espera `completed`; en **Resultados** verás el historial y las incidencias filtrables.
3. Abre una incidencia: comprueba contexto, pasos, archivos PNG/JSON y validaciones. Descarga un JSON y verifica que no incluya cookies, cabeceras ni cuerpos.
4. Cambia el estado a `confirmed` con notas y revisa la entrada en el historial. Intenta repetir la misma transición: la API debe devolver 409.
5. Descarga el reporte HTML desde la ejecución y ábrelo localmente. Debe contener resumen y hallazgos, sin imágenes embebidas ni scripts.
6. En una ejecución completa con pasos de navegación, pulsa **Repetir escenario**. Consulta su comparación al terminar y confirma que un error ausente dice «No observado; requiere verificación»; valida manualmente si corresponde.

La suite automatizada usa una aplicación FastAPI local controlada con páginas sana, error JavaScript, HTTP 500 y enlace 404. No evalúes plataformas ajenas sin autorización expresa.
