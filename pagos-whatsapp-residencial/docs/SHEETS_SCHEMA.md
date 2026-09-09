# Esquema operativo de Google Sheets

La hoja de cálculo es **privada**. El backend valida/crea las pestañas necesarias y escribe con `valueInputOption=RAW` para evitar formula injection desde texto OCR.

## Vista operativa esperada

La información que necesita el encargado se presenta como:

`Etapa | Bloque | Casa | Cuota | Estado | Banco | Referencia | Fecha depósito | Mes pagado | Teléfono WhatsApp`

El teléfono es el número que envió el comprobante por WhatsApp. **Nunca identifica la vivienda.**

La cuota esperada del MVP es **L150.00**. El monto del comprobante se conserva como dato bancario independiente: si es menor o mayor de L150, el pago queda en `EN_REVISION` y no se considera pagado/verificado automáticamente.

## `Pagos`

| Columna | Uso |
| --- | --- |
| `id` | ID interno determinístico del comprobante |
| `created_at` / `updated_at` | auditoría temporal |
| `source_message_id` | idempotencia de WhatsApp |
| `phone` | remitente de WhatsApp; dato privado, no identidad de vivienda |
| `media_id` | identificador temporal de media de Meta |
| `receipt_file_id` | ID privado de Google Drive |
| `bank` | banco detectado |
| `depositor` | depositante/remitente extraído |
| `transaction_date` / `transaction_time` | fecha/hora del depósito según comprobante |
| `amount` | monto declarado por el comprobante; se compara contra la cuota esperada |
| `detail` | detalle/concepto |
| `reference` | referencia/transacción bancaria; señal de comparación, no ID global único |
| `beneficiary` | beneficiario extraído |
| `destination_account_masked` | sólo últimos cuatro dígitos |
| `stage` / `block` / `house` | identidad operativa de la vivienda |
| `period` | mes de servicio pagado `YYYY-MM` |
| `status` | estado de la máquina de pagos |
| `file_hash` | SHA-256 del archivo |
| `duplicate_of` | pago original relacionado |
| `duplicate_reason` | señal exacta que originó duplicado/conflicto |
| `review_reason` | motivo interno de revisión, por ejemplo monto menor/mayor a L150 |
| `verification_source` | fuente usada para verificar |
| `verified_at` | fecha/hora de verificación |
| `bank_movement_id` | identificador estable del movimiento bancario usado por una fuente de conciliación automática; no se reutiliza en otro pago |

## `Viviendas`

| Columna | Uso |
| --- | --- |
| `id` | ID interno |
| `stage` / `block` / `house` | clave operativa principal y única |
| `responsible` | dato administrativo opcional |
| `monthly_fee` | cuota mensual esperada |
| `active` | vivienda activa/inactiva |
| `start_date` / `end_date` | vigencia para períodos históricos |

**No existe columna de teléfono en `Viviendas`.** Una casa puede estar alquilada y el pago puede enviarlo cualquier tercero. Ni el remitente de WhatsApp ni el nombre del depositante se utilizan para determinar la vivienda.

## `Conversaciones`

| Columna | Uso |
| --- | --- |
| `id` | ID del contexto temporal |
| `phone` | remitente de WhatsApp |
| `payment_id` | comprobante esperando Etapa/Bloque/Casa |
| `created_at` | creación |
| `expires_at` | expiración |

El teléfono se usa únicamente para relacionar una respuesta posterior `E1 B4 C18` con el comprobante pendiente de esa conversación. No crea una asociación permanente teléfono → vivienda. Sólo debe existir un contexto vigente por remitente para evitar respuestas ambiguas.

## `Mensajes`

| Columna | Uso |
| --- | --- |
| `message_id` | ID de WhatsApp |
| `received_at` | recepción |
| `kind` | image/document/text/other |
| `outcome` | processed/ignored/rejected |

## `Conciliacion`

Reservada para trazabilidad de futuras corridas de conciliación y fuentes bancarias autorizadas. Una misma transacción/movimiento bancario nunca puede verificar dos pagos distintos.

Para conciliación automática segura, la fuente debe aportar un identificador estable de movimiento. Si no existe `bank_movement_id`, el sistema no verifica automáticamente y manda el caso a revisión. Cuando un movimiento se usa, su ID queda persistido en `Pagos` y no puede volver a verificar otro pago en una corrida posterior.

## `Configuracion`

Reservada para parámetros operativos no secretos. **Nunca** guardar tokens, contraseñas, llaves privadas ni secretos de Meta/Google/BAC en esta hoja.

## Mes pagado

Agosto 2026 es el punto de inicio del histórico:

- depósitos del 1 al 14 de agosto de 2026 → julio 2026;
- depósitos del 15 al 31 de agosto de 2026 → agosto 2026;
- desde septiembre, el sistema busca el primer mes **no verificado como pagado** desde agosto;
- un comprobante `PENDIENTE_VERIFICACION` o `EN_REVISION` no hace avanzar el histórico; si llega otro, se mantiene el mismo primer mes pendiente y el conflicto se revisa;
- si todos los meses hasta el mes del depósito ya están `VERIFICADO`, no se avanza silenciosamente a un mes futuro: el caso queda visible para revisión/corrección.

## Estado operativo

- `PENDIENTE_VERIFICACION`: el comprobante fue recibido y parece válido, pero el banco aún no fue confirmado.
- `VERIFICADO`: el encargado confirmó el movimiento bancario o una futura fuente bancaria confiable lo confirmó.
- `EN_REVISION`: existe una excepción que requiere decisión humana; incluye montos diferentes de L150.
- `DUPLICADO`: no debe volver a contabilizarse.

Una vivienda se considera **pagada** para el período únicamente cuando existe un pago `VERIFICADO` para ese E/B/C y mes.

## Reglas

- No publicar la Sheet.
- No usar fórmulas provenientes de OCR.
- No almacenar el texto OCR completo salvo necesidad futura explícita.
- Cuenta destino: conservar sólo versión enmascarada.
- Comprobantes: Drive privado, no celdas con URLs públicas.
- Secretos: únicamente variables de entorno de Vercel.
- Una referencia bancaria repetida no se descarta automáticamente como duplicado.
- Un monto distinto de L150 se conserva y se manda a revisión; no se corrige ni se descarta automáticamente.
- Un `bank_movement_id` ya utilizado no puede verificar otro pago.
- Si una hoja existente tiene encabezados inesperados, el backend falla de forma cerrada en lugar de sobrescribir datos.
