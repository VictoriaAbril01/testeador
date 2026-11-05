# TestLab

TestLab es una plataforma en desarrollo para ejecutar pruebas autorizadas y registrar incidencias con evidencia y pasos de reproducción. La primera versión funcional se centrará en pruebas Black Box. Los modos White Box e híbrido se incorporarán en fases posteriores.

## Estado

**Fase 5: evidencias, incidencias y reportes implementados y probados localmente.** React, TypeScript y Vite ofrecen proyectos, ejecuciones, incidencias, validación y retest básico. Chromium navega dentro del alcance autorizado; el worker guarda páginas, pasos, hallazgos y archivos privados. La cola está desactivada por defecto. La cancelación de ejecuciones y el análisis White Box siguen pendientes.

## Empezar

Sigue [docs/installation.md](docs/installation.md) para preparar el entorno y comprobar PostgreSQL y Redis. Consulta [docs/roadmap.md](docs/roadmap.md) para el alcance de las siguientes fases.

## Documentación

- [Requisitos y alcance](docs/requirements.md)
- [Arquitectura y seguridad](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Instalación](docs/installation.md)
- [API disponible](docs/api.md)
- [Verificación](docs/testing.md)
- [Frontend y límites de la API](docs/frontend.md)
- [Motor Black Box y seguridad](docs/blackbox.md)
- [Evidencias, reproducción, retest y reporte HTML](docs/evidence-reports.md)

Solo deben probarse sistemas para los que exista autorización y un alcance definido.
