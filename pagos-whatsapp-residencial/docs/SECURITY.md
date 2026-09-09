# Seguridad y privacidad

## Modelo de amenaza resumido

El sistema procesa documentos bancarios y datos de contacto. Las amenazas prioritarias son:

- webhook falso;
- archivo malicioso o con MIME suplantado;
- reenvío/retry que contabilice dos veces;
- comprobante editado o reutilizado;
- asignación incorrecta de vivienda;
- filtración de PII o secretos en GitHub/logs;
- acceso público al panel o comprobantes;
- formula injection en Google Sheets;
- conflicto de referencia que revele información de otra vivienda;
- reutilización de un mismo movimiento bancario para verificar dos pagos.

## Controles implementados

### Webhook

- `GET` sólo acepta token de verificación correcto.
- `POST` valida `X-Hub-Signature-256` con HMAC-SHA256 sobre el body crudo.
- payload acotado con Zod antes de procesarlo.
- mensajes normales no se convierten en pagos; un texto sólo se interpreta como vivienda si existe contexto pendiente.

### Vivienda y teléfono

- la identidad de vivienda es únicamente `Etapa + Bloque + Casa`;
- si falta cualquiera de los tres valores se solicitan los tres de nuevo (`E1 B4 C18`);
- el número de WhatsApp se conserva como remitente del pago y como clave temporal de conversación, nunca como vínculo vivienda → teléfono;
- `Viviendas` no guarda teléfono para resolver pagos;
- el depositante extraído por OCR tampoco determina la vivienda.

Esto evita asignaciones incorrectas cuando una vivienda está alquilada o paga un familiar, propietario u otra persona.

### Archivos

- formatos del MVP: JPEG/PNG;
- límite configurable de bytes;
- MIME declarado y magic bytes deben coincidir;
- SHA-256 antes de OCR;
- Sharp recibe el binario sólo después de las validaciones iniciales;
- PDF no se procesa en esta fase.

### Duplicados e idempotencia

- `message_id`: retry técnico, silencioso;
- hash: mismo archivo exacto;
- mismo archivo exacto desde otro remitente: revisión;
- banco + referencia: señal de correlación, **no** duplicado automático;
- referencia repetida con vivienda/monto/fecha incompatibles: revisión/conflicto;
- señal débil banco + vivienda + monto + fecha: sólo revisión;
- el dashboard excluye únicamente filas explícitamente marcadas `DUPLICADO` o `RECHAZADO`; no canonicaliza por referencia.

### Fraude y verificación

OCR no autentica una imagen. Estados como `PENDIENTE_VERIFICACION`, `NO_ENCONTRADO` y `EN_REVISION` impiden convertir una captura legible en dinero confirmado.

En el MVP, `VERIFICADO` sólo se obtiene cuando el encargado revisa el movimiento directamente en el banco y ejecuta la acción de verificación del panel. El sistema no almacena usuario, contraseña, PIN ni códigos de BAC.

Una futura conciliación puede usar una fuente bancaria autorizada. Su lógica impide que un mismo movimiento bancario verifique dos pagos distintos.

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
- rutas de comprobantes con `Cache-Control: private, no-store`;
- los casos de revisión requieren una acción explícita y separada para confirmar tras revisar el banco o marcar duplicado.

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

Los fixtures actuales usan nombres, teléfonos y referencias deliberadamente ficticios.

## Límites conocidos

Google Sheets no garantiza unicidad transaccional ante escrituras concurrentes desde múltiples instancias. El MVP tiene idempotencia de aplicación y controles de revisión; para crecimiento o alta concurrencia debe introducirse un datastore transaccional con índices únicos y mantener Sheets como salida operativa.

El envío de respuesta por WhatsApp no usa todavía un outbox durable. Si Meta acepta el comprobante pero falla el envío de la respuesta, el pago permanece seguro y no se duplica, pero el mensaje al usuario puede necesitar reintento operativo. Un outbox durable es una mejora prioritaria antes de escalar.

## Rotación y respuesta a incidentes

Ante sospecha de filtración:

1. revocar/rotar token de Meta;
2. rotar credenciales o clave de servicio de Google según corresponda;
3. rotar `ADMIN_ACCESS_KEY` y `AUTH_SESSION_SECRET`;
4. revisar logs sin descargar PII innecesaria;
5. invalidar despliegues anteriores si contienen configuración comprometida;
6. revisar historial Git antes de asumir que borrar un archivo lo eliminó del repositorio.
