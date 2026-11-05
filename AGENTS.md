# Reglas permanentes de TestLab

Estas instrucciones se aplican a todo el repositorio. Lee `docs/roadmap.md`, `docs/requirements.md` y `docs/architecture.md` antes de proponer o implementar una fase.

## Forma de trabajo

- Trabaja en fases pequeñas. Antes de cada fase, revisa archivos, documentación y estado de Git; evita repetir trabajo terminado.
- Explica objetivo, archivos afectados, implementación y criterios de aceptación, y espera autorización para comenzar una fase nueva. La autorización de una fase no autoriza la siguiente. Ejecuta únicamente el alcance aprobado.
- Al terminar, ejecuta las verificaciones pertinentes, corrige los fallos propios, actualiza la documentación y `docs/roadmap.md`, y comunica lo terminado, lo pendiente y cómo verificarlo manualmente.
- Mantén el roadmap fiel al estado real: distingue tareas terminadas, pendientes y decisiones abiertas. No marques funcionalidades documentadas o simuladas como implementadas.
- No borres trabajo existente, ejecutes comandos destructivos de Git ni subas cambios a remotos sin autorización.

## Arquitectura y desarrollo

- Conserva la estructura modular acordada: `frontend/` (React, TypeScript, Vite), `backend/` (FastAPI, SQLAlchemy, Alembic), `tester/` (motores y análisis), `workers/` (Redis, RQ), `database/migrations/`, `tests/` y `docs/`. Consulta al usuario antes de cambiar la arquitectura principal.
- La primera versión funcional cubre Black Box; White Box e híbrido corresponden a fases posteriores. No añadas microservicios ni dependencias de IA durante el MVP.
- Separa recolección de observaciones y análisis mediante una interfaz; comienza con reglas. Prefiere código legible, tipado, validación de entradas, manejo explícito de errores y pruebas relevantes.
- No atribuyas lenguaje de backend, archivo, línea o causa raíz sin evidencia. Distingue defectos confirmados, hipótesis y hallazgos pendientes.

## Seguridad

- Prueba únicamente destinos y repositorios expresamente autorizados. Aplica límites de alcance, tiempo, solicitudes y concurrencia; la navegación debe ser no destructiva por defecto.
- El worker Black Box debe validar URL, DNS, dirección de destino y cada salto de redirección. No omitas la interceptación de Chromium ni la fijación DNS; el worker público rechaza redes privadas. Los destinos internos requieren un despliegue separado con permisos de red explícitos.
- Exige autorización explícita para acciones que cambien datos. Aísla el análisis de repositorios y no ejecutes código desconocido o instaladores de terceros por defecto.
- Cifra credenciales de prueba antes de persistirlas; mantén claves fuera del repositorio. Nunca registres contraseñas, tokens o cookies en texto plano. No desactives TLS ni autenticación para facilitar pruebas.

La descripción completa del producto, los contratos conceptuales y las decisiones abiertas permanecen en `docs/`.
