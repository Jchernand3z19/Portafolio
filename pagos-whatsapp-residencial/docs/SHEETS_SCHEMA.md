# Esquema operativo de Google Sheets

La hoja de cálculo es **privada**. El backend valida/crea las pestañas necesarias y escribe con `valueInputOption=RAW` para evitar formula injection desde texto OCR.

## `Pagos`

| Columna | Uso |
| --- | --- |
| `id` | ID interno determinístico del comprobante |
| `created_at` / `updated_at` | auditoría temporal |
| `source_message_id` | idempotencia de WhatsApp |
| `phone` | remitente del mensaje; dato privado |
| `media_id` | identificador temporal de media de Meta |
| `receipt_file_id` | ID privado de Google Drive |
| `bank` | banco detectado |
| `depositor` | depositante/remitente extraído |
| `transaction_date` / `transaction_time` | fecha/hora del comprobante |
| `amount` | monto declarado |
| `detail` | detalle/concepto |
| `reference` | referencia/transacción bancaria |
| `beneficiary` | beneficiario extraído |
| `destination_account_masked` | sólo últimos cuatro dígitos |
| `block` / `house` | vivienda operativa |
| `period` | `YYYY-MM` aplicado a cartera |
| `status` | estado de la máquina de pagos |
| `file_hash` | SHA-256 del archivo |
| `duplicate_of` | pago original relacionado |
| `review_reason` | motivo interno de revisión |
| `verification_source` | fuente bancaria usada para verificar |
| `verified_at` | fecha/hora de verificación |

## `Viviendas`

| Columna | Uso |
| --- | --- |
| `id` | ID interno |
| `block` / `house` | clave operativa principal |
| `responsible` | responsable opcional |
| `phone` | teléfono asociado opcional |
| `monthly_fee` | cuota mensual |
| `active` | vivienda activa/inactiva |
| `start_date` / `end_date` | vigencia para períodos históricos |

El nombre del depositante **no** se utiliza como dueño de la vivienda.

## `Conversaciones`

| Columna | Uso |
| --- | --- |
| `id` | ID del contexto |
| `phone` | teléfono |
| `payment_id` | comprobante esperando vivienda |
| `created_at` | creación |
| `expires_at` | expiración |

Sólo debe existir un contexto vigente por teléfono.

## `Mensajes`

| Columna | Uso |
| --- | --- |
| `message_id` | ID de WhatsApp |
| `received_at` | recepción |
| `kind` | image/document/text/other |
| `outcome` | processed/ignored/rejected |

## `Conciliacion`

Reservada para trazabilidad de corridas de conciliación y fuentes bancarias autorizadas. El servicio actual no necesita almacenar movimientos brutos para ejecutar una conciliación en memoria.

## `Configuracion`

Reservada para parámetros operativos no secretos. **Nunca** guardar tokens, contraseñas, llaves privadas ni secretos de Meta/Google en esta hoja.

## Reglas

- No publicar la Sheet.
- No usar fórmulas provenientes de OCR.
- No almacenar el texto OCR completo salvo necesidad futura explícita.
- Cuenta destino: conservar sólo versión enmascarada.
- Comprobantes: Drive privado, no celdas con URLs públicas.
- Secretos: únicamente variables de entorno de Vercel.
