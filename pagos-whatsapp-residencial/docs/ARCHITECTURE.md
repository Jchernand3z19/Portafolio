# Arquitectura

## Principios

1. **Recibido no significa verificado.** OCR identifica una transacción declarada; una revisión bancaria humana o futura conciliación bancaria confirma el dinero.
2. **Fail closed.** Firma inválida, MIME inconsistente, vivienda desconocida o datos conflictivos no se aceptan silenciosamente.
3. **Datos privados server-side.** Meta, Google Sheets y Google Drive nunca se consultan desde el navegador público.
4. **Demo y producción separados.** La demo usa fixtures sintéticos; producción exige variables de entorno y recursos privados.
5. **Parser por banco.** La lógica bancaria vive detrás de `ReceiptParser`.
6. **Excepciones visibles.** Sin identificar, duplicados y revisión tienen estados y bandejas propias.
7. **Vivienda estable.** Sólo `Etapa + Bloque + Casa` identifica una vivienda. Ni teléfono ni depositante participan en esa identidad.

## Componentes

```text
WhatsApp Cloud API
        │
        ▼
/api/whatsapp/webhook
  ├─ valida challenge / HMAC
  ├─ valida payload
  └─ descarga media autorizada
        │
        ▼
Receipt file guard
  ├─ tamaño
  ├─ MIME declarado
  └─ magic bytes + SHA-256
        │
        ▼
Sharp → Tesseract.js
        │
        ▼
ReceiptParser registry
        │
        └─ bac/
        │
        ▼
Payment processor
  ├─ Etapa/Bloque/Casa por detalle
  ├─ pregunta E/B/C si falta cualquiera
  ├─ contexto temporal por remitente WhatsApp
  ├─ reglas de mes desde agosto 2026
  ├─ duplicados / conflictos / revisión
  ├─ validación beneficiario/cuenta
  └─ recibido ≠ verificado
        │
        ├──────────────► Google Drive privado (imagen)
        │
        ▼
Google Sheets privado
        │
        ├─ panel administrativo
        │    ├─ corregir E/B/C o mes
        │    ├─ revisar excepciones
        │    └─ verificar tras revisar banco
        └─ futura conciliación bancaria
```

## Idempotencia y posibles duplicados

Se aplican varias capas:

- `message_id` de WhatsApp identifica retries técnicos y se ignora silenciosamente;
- SHA-256 detecta el mismo archivo exacto reenviado;
- el mismo archivo desde otro remitente se manda a revisión;
- `banco + referencia` es una señal de correlación/riesgo, **no** se considera un identificador global único;
- referencia repetida con otra vivienda, monto o fecha incompatible produce revisión/conflicto;
- `banco + vivienda + monto + fecha` es señal débil y sólo manda a revisión;
- el dashboard sólo excluye registros explícitamente marcados `DUPLICADO` o `RECHAZADO`; no elimina pagos por referencia de forma silenciosa.

Google Sheets no ofrece una restricción UNIQUE ni transacciones ACID. El MVP evita presentarse como exactly-once a nivel de almacenamiento. Para alto volumen se recomienda introducir un datastore transaccional como fuente primaria y mantener Sheets como salida operativa.

## Resolución de vivienda

Único orden válido:

1. buscar `Etapa + Bloque + Casa` completos en el comprobante;
2. validar que esa combinación exista y esté activa en la base maestra;
3. si falta cualquiera de los tres, preguntar por WhatsApp: `E1 B4 C18`;
4. usar el número remitente sólo para relacionar esa respuesta con el comprobante pendiente;
5. actualizar el mismo pago sin volver a ejecutar OCR.

No existe resolución teléfono → vivienda. Si ya existe un comprobante pendiente de E/B/C para el mismo remitente, un segundo comprobante sin vivienda no crea otro contexto ambiguo: queda `EN_REVISION`.

## Mes de servicio

La fecha del depósito y el mes pagado son campos distintos.

- Agosto 2026 es la base histórica.
- 01–14 agosto → julio.
- 15–31 agosto → agosto.
- Desde septiembre se asigna el primer mes pendiente a partir de agosto.
- Si todos los meses hasta la fecha del depósito ya están ocupados, el sistema no adelanta silenciosamente a un mes futuro; mantiene el mes del depósito y expone el conflicto para revisión/corrección.

## Archivos

Producción conserva la imagen en un folder privado de Google Drive compartido sólo con la cuenta de servicio. La hoja guarda únicamente `receipt_file_id`; el navegador obtiene la imagen a través de una ruta autenticada y `Cache-Control: private, no-store`.

No se generan enlaces públicos de Drive.

## Autenticación

El panel de producción usa:

- clave administrativa definida por ambiente;
- comparación temporalmente segura;
- cookie de sesión firmada HMAC;
- `HttpOnly`, `SameSite=Strict`, `Secure` en producción;
- comprobación de mismo origen para acciones mutables.

La demo pública no reutiliza datos de producción.

## Verificación y conciliación

En el MVP el encargado revisa BAC independientemente y usa el botón del panel para cambiar un pago elegible a `VERIFICADO`. La aplicación no necesita ni debe almacenar usuario, contraseña, PIN o códigos bancarios.

`reconcilePendingPayments` queda preparado para una futura fuente autorizada. Requiere una coincidencia consistente de banco, referencia y monto; una discrepancia de fecha va a revisión. Además, un mismo movimiento bancario no puede verificar dos pagos diferentes.

La fuente de movimientos se mantiene abstracta para incorporar posteriormente un archivo bancario, notificación oficial o API autorizada.
