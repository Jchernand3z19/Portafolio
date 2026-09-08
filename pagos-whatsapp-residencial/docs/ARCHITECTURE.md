# Arquitectura

## Principios

1. **Recibido no significa verificado.** OCR identifica una transacción declarada; conciliación bancaria confirma dinero.
2. **Fail closed.** Firma inválida, MIME inconsistente, vivienda desconocida o referencia conflictiva no se aceptan silenciosamente.
3. **Datos privados server-side.** Meta, Google Sheets y Google Drive nunca se consultan desde el navegador público.
4. **Demo y producción separados.** La demo usa fixtures sintéticos; producción exige variables de entorno y recursos privados.
5. **Parser por banco.** La lógica bancaria vive detrás de `ReceiptParser`.
6. **Excepciones visibles.** Sin identificar, duplicados y revisión tienen estados y bandejas propias.

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
  ├─ vivienda por detalle
  ├─ vivienda por teléfono
  ├─ contexto pendiente
  ├─ duplicados / conflictos
  ├─ validación beneficiario/cuenta
  └─ período
        │
        ├──────────────► Google Drive privado (imagen)
        │
        ▼
Google Sheets privado
        │
        ├─ panel administrativo
        └─ conciliación bancaria
```

## Idempotencia

Se aplican varias capas:

- `message_id` de WhatsApp identifica retries técnicos;
- SHA-256 detecta el mismo archivo reenviado;
- `banco + referencia` detecta la misma transacción aun con archivo distinto;
- `banco + teléfono + monto + fecha` es señal débil y sólo manda a revisión;
- el dashboard vuelve a canonicalizar referencias/hash y excluye `DUPLICADO` para que una fila repetida no incremente recaudación.

Google Sheets no ofrece una restricción UNIQUE ni transacciones ACID. Por eso el MVP evita presentar el backend como exactamente-once a nivel de almacenamiento. Para alto volumen se recomienda introducir un datastore transaccional como fuente primaria y mantener Sheets como salida operativa.

## Resolución de vivienda

Orden:

1. bloque/casa extraído del comprobante;
2. vivienda activa asociada al teléfono si existe exactamente una;
3. pregunta por WhatsApp.

Si ya existe un comprobante sin identificar para el mismo teléfono, un segundo comprobante sin vivienda no crea otro contexto ambiguo: queda `EN_REVISION`.

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

## Conciliación

`reconcilePendingPayments` requiere una coincidencia única de banco, referencia y monto. Una discrepancia de fecha va a revisión. La ausencia de movimiento produce `NO_ENCONTRADO`.

La fuente de movimientos se mantiene abstracta para incorporar posteriormente archivo bancario, notificación oficial o API autorizada.
