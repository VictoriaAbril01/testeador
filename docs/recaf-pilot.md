# Preparación del piloto interno RECAF

Estado al 13 de octubre de 2026: **sin ejecución contra RECAF**. Solo se hizo una conexión TCP y un handshake TLS con validación desde un contenedor basado en la imagen del worker; no se envió HTTP ni credenciales. TCP a `192.168.10.172:5173` respondió. TLS rechazó la cadena con `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`. No se desactivó la verificación.

## Configuración prevista

| Campo | Valor |
| --- | --- |
| Origen autorizado | `https://192.168.10.172:5173` |
| URL de login | `https://192.168.10.172:5173/auth/login` |
| URL base del proyecto | `https://192.168.10.172:5173/admin`, **solo tras confirmar que es la página inicial autenticada** |
| Usuario | `#login_email` |
| Contraseña | `#login_password` |
| Botón | `button[type="submit"]` |
| Patrón de éxito | `/admin` |
| Páginas/profundidad/solicitudes/concurrencia | `5 / 1 / 30 / 1` |
| Timeout por página/total | `15000 / 60000` ms |
| Red privada del worker dedicado | `TESTLAB_PRIVATE_WORKER=true`, `TESTLAB_PRIVATE_CIDRS=192.168.10.172/32` |

El motor abre la URL de login y luego la URL base. Por eso la base propuesta es `/admin` y no `/auth/login`. El login consume una de las cinco páginas: el recorrido puede dejar módulos sin visitar y un retest sin cobertura debe quedar inconcluso. No se ha verificado si `/admin` es navegable tras autenticar ni si el formulario usa un POST HTML nativo. El worker actual admite un POST del formulario configurado al mismo origen; un login basado exclusivamente en `fetch`/XHR necesitaría una revisión específica antes de probarse. No se debe inferir compatibilidad solo por los selectores.

## Condiciones previas

1. Obtener del administrador la CA emisora o un certificado válido para la **IP** `192.168.10.172`, con su cadena completa. La CA debe instalarse en una imagen dedicada del worker; repetir el handshake con verificación en esa misma imagen. Si el certificado solo cubre un nombre DNS, acordar ese nombre, su resolución y un origen autorizado nuevo. No usar `ignoreHTTPSErrors`, `--ignore-certificate-errors`, `verify=False` ni desactivar TLS de forma global.
2. Desplegar **un worker interno separado** del worker público, con acceso explícito solo al destino autorizado y a PostgreSQL/Redis requeridos. Mantener el worker público sin rangos privados. Confirmar el control de salida de red del host o infraestructura; `TESTLAB_PRIVATE_CIDRS` limita el navegador, pero no sustituye un firewall externo.
3. Confirmar con el propietario de RECAF que el entorno y la cuenta de prueba están autorizados, que `/admin` es la página inicial tras el login y que el formulario es compatible con el POST HTML admitido. Resolver CAPTCHA/MFA manualmente fuera del motor; no intentar superarlos.
4. Aportar usuario y contraseña de **cuenta de prueba** únicamente en el formulario de TestLab, nunca en archivos del repositorio, líneas de comando o logs. La API los cifra con la clave externa `TESTLAB_FERNET_KEY`.
5. Mantener la cola desactivada y no crear una ejecución RECAF hasta recibir la autorización específica para ese ensayo.

## Secuencia manual tras resolver las condiciones y recibir autorización

1. Detener el worker público antes de habilitar la cola para RECAF. Iniciar la API con `TESTLAB_QUEUE_ENABLED=true` y el worker interno dedicado con el CIDR `/32` anterior, certificado confiable y política de salida de red confirmada. Verificar `/health`, PostgreSQL, Redis y un solo consumidor de la cola `testlab`. La API y el worker deben compartir la misma clave de cifrado y el mismo almacenamiento privado de evidencias.
2. Abrir TestLab. Registrar un proyecto Black Box de entorno **staging** o el entorno de prueba acordado: URL base `/admin` y origen autorizado exacto `https://192.168.10.172:5173`. Configurar acceso con la URL y selectores de la tabla. Introducir las credenciales solo en la pantalla de acceso.
3. Crear **una** ejecución con límites `5`, `1`, `30`, `1`, `15000`, `60000`; conservar su UUID. No iniciar otra mientras la primera esté activa. La navegación por defecto es GET/HEAD; solo el POST del login configurado está permitido. Redirecciones y destinos ajenos al origen se bloquean.
4. Esperar `queued → running → completed` o registrar `failed/cancelled` como fallo técnico. Revisar páginas y pasos antes de interpretar hallazgos; un recorrido incompleto no valida ausencia de errores. Abrir cada captura desde TestLab, revisar su contenido antes de compartirla y descargar el HTML solo mediante acceso autenticado.
5. Desactivar de nuevo el encolado y retirar el worker interno al terminar. Conservar ejecuciones y evidencias según su política de retención; no borrar datos históricos.

Estas instrucciones **no autorizan la ejecución**. El handshake TLS fallido y la compatibilidad de login no comprobada impiden declarar RECAF listo para el primer ensayo.
