# Seguridad y privacidad

## Modelo de amenaza resumido

El sistema procesa documentos bancarios y datos de contacto. Las amenazas prioritarias son:

- webhook falso;
- archivo malicioso o con MIME suplantado;
- reenvío/retry que contabilice dos veces;
- comprobante editado;
- filtración de PII o secretos en GitHub/logs;
- acceso público al panel o comprobantes;
- formula injection en Google Sheets;
- conflicto de referencia que revele información de otra vivienda.

## Controles implementados

### Webhook

- `GET` sólo acepta token de verificación correcto.
- `POST` valida `X-Hub-Signature-256` con HMAC-SHA256 sobre el body crudo.
- payload acotado con Zod antes de procesarlo.
- mensajes normales no se convierten en pagos; un texto sólo se interpreta como vivienda si existe contexto pendiente.

### Archivos

- formatos del MVP: JPEG/PNG;
- límite configurable de bytes;
- MIME declarado y magic bytes deben coincidir;
- SHA-256 antes de OCR;
- Sharp recibe el binario sólo después de las validaciones iniciales;
- PDF no se procesa en esta fase.

### Duplicados e idempotencia

- `message_id`: retry técnico;
- hash: mismo archivo;
- banco + referencia: misma transacción declarada;
- señal débil monto/fecha no deduplica automáticamente;
- una referencia asociada a otro remitente/vivienda produce revisión sin revelar datos del original;
- el agregado del dashboard canonicaliza pagos para evitar doble conteo.

### Fraude

OCR no autentica una imagen. Estados como `PENDIENTE_VERIFICACION`, `NO_ENCONTRADO` y `EN_REVISION` impiden convertir una captura legible en dinero confirmado.

`VERIFICADO` se obtiene mediante conciliación con una fuente bancaria confiable.

### Google

- Sheets y Drive son privados;
- archivos se crean en un folder privado;
- no se generan permisos públicos ni links públicos;
- el navegador recibe comprobantes únicamente por una ruta autenticada;
- `valueInputOption=RAW` evita ejecutar contenido OCR como fórmula;
- cuenta destino se guarda enmascarada.

### Panel

- clave administrativa por ambiente;
- comparación temporalmente segura;
- sesión HMAC con expiración;
- cookie HttpOnly + SameSite Strict + Secure en producción;
- comprobación de mismo origen en escrituras;
- rutas de comprobantes con `Cache-Control: private, no-store`.

### Logs

No registrar:

- body completo del webhook;
- OCR completo;
- access tokens;
- llaves privadas;
- comprobantes;
- teléfonos/referencias sin enmascarar.

El logger estructurado incluye únicamente campos mínimos y utilidades de masking.

## Repositorio público

Nunca versionar:

- `.env*` con valores;
- service-account JSON;
- credenciales descargadas;
- comprobantes reales;
- exports de Sheets/Drive de producción;
- teléfonos, nombres o referencias bancarias reales.

Los fixtures actuales usan nombres y números deliberadamente ficticios.

## Límites conocidos

Google Sheets no garantiza unicidad transaccional ante escrituras concurrentes desde múltiples instancias. El MVP tiene idempotencia de aplicación y deduplicación de agregado; para crecimiento o alta concurrencia debe introducirse un datastore transaccional con índices únicos y mantener Sheets como salida operativa.

El envío de respuesta por WhatsApp no usa todavía un outbox durable. Si Meta acepta el comprobante pero falla el envío de la respuesta, el pago permanece seguro y no se duplica, pero el mensaje al usuario puede necesitar reintento operativo. Un outbox durable es una mejora prioritaria antes de escalar.

## Rotación y respuesta a incidentes

Ante sospecha de filtración:

1. revocar/rotar token de Meta;
2. rotar credenciales o clave de servicio de Google según corresponda;
3. rotar `ADMIN_ACCESS_KEY` y `AUTH_SESSION_SECRET`;
4. revisar logs sin descargar PII innecesaria;
5. invalidar despliegues anteriores si contienen configuración comprometida;
6. revisar historial Git antes de asumir que borrar un archivo lo eliminó del repositorio.
