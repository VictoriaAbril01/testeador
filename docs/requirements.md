# Requisitos y alcance

## Objetivo

Reducir el trabajo manual de detección y reproducción de fallos mediante ejecuciones autorizadas, evidencias y un registro de incidencias verificable. No se empleará IA en el MVP.

## Primera versión funcional (fases 1 a 5)

1. Registrar proyectos, entornos y destinos explícitamente autorizados.
2. Configurar una ejecución Black Box con límites de tiempo, solicitudes y concurrencia.
3. Navegar con Playwright dentro del alcance permitido y registrar los pasos realizados.
4. Observar errores de JavaScript, respuestas HTTP inesperadas y fallos de navegación o validación que puedan comprobarse.
5. Guardar evidencias sanitizadas y generar instrucciones para reproducir cada incidencia.
6. Consultar ejecuciones e incidencias y actualizar el estado de validación manual.

La exploración será no destructiva por defecto. Un usuario deberá autorizar explícitamente cualquier acción que pueda cambiar datos. Los destinos fuera del alcance configurado se rechazarán, incluidas las redirecciones.

## Fases posteriores

- White Box: análisis estático de repositorios autorizados, sin ejecutar su código por defecto.
- Híbrido: correlación de observaciones dinámicas con archivos y líneas solo cuando haya evidencia.
- Retesting y comparación de ejecuciones.

## Contratos conceptuales

Una **ejecución** tendrá identificador, proyecto, entorno, modalidad, alcance autorizado, configuración de límites, inicio y fin, estado y registro de auditoría. Una **incidencia** tendrá identificador, ejecución, tipo, descripción, resultado esperado y observado, pasos de reproducción, fecha y estado de validación. Según la evidencia disponible podrá incluir módulo, pantalla, URL, elemento, datos de prueba sin secretos, HTTP sanitizado, captura, trazas, tecnología y confianza. Archivo y línea solo se incluirán cuando exista evidencia verificable.

Estados de validación previstos: detectado automáticamente, pendiente de confirmación, confirmado manualmente, no reproducible, falso positivo, corregido y verificado mediante retest. El modelo y sus transiciones se implementarán en la fase correspondiente.

## Criterios de calidad

- Ningún reporte afirmará conocer el backend, archivo, línea o causa raíz sin evidencia.
- Contraseñas, tokens y cookies no aparecerán en logs, capturas exportadas ni respuestas HTTP guardadas.
- Los fallos de red, tiempo de espera y bloqueo de alcance quedarán diferenciados de defectos confirmados del producto probado.
- La arquitectura admitirá un analizador basado en reglas y una implementación futura mediante una interfaz, sin dependencia de IA durante el MVP.
