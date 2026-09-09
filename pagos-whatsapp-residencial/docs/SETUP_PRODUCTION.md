# Configuración de producción

Este documento describe lo que debe existir fuera de GitHub. No contiene valores reales.

## 1. Google Cloud

Crear o seleccionar un proyecto bajo la cuenta de la empresa y habilitar:

- Google Sheets API;
- Google Drive API.

Crear una cuenta de servicio dedicada. No subir el JSON al repositorio.

Variables requeridas:

- `GOOGLE_CLIENT_EMAIL`
- `GOOGLE_PRIVATE_KEY`

## 2. Google Sheets

Crear una hoja privada y compartirla únicamente con la cuenta de servicio con permisos de edición.

Guardar el ID como:

- `GOOGLE_SHEET_ID`

El backend crea/valida las pestañas operativas al iniciar el acceso de producción.

La base `Viviendas` debe usar **Etapa + Bloque + Casa** como identidad. No guardar teléfonos para resolver viviendas.

## 3. Google Drive

Crear un folder privado dedicado a comprobantes y compartirlo sólo con la cuenta de servicio.

Guardar su ID como:

- `GOOGLE_RECEIPT_FOLDER_ID`

No activar "cualquiera con el enlace".

## 4. Meta / WhatsApp Cloud API

Configurar una aplicación de Meta y un número autorizado para WhatsApp Cloud API.

Variables:

- `WHATSAPP_VERIFY_TOKEN` — valor aleatorio generado para verificar el webhook;
- `WHATSAPP_ACCESS_TOKEN` — token server-side;
- `WHATSAPP_PHONE_NUMBER_ID`;
- `META_APP_SECRET`;
- `WHATSAPP_GRAPH_VERSION` — versión configurada para el proyecto.

Webhook de producción:

```text
https://<dominio>/api/whatsapp/webhook
```

Suscribir únicamente los eventos necesarios.

El número que envía el comprobante se utiliza para responder y para correlacionar temporalmente una respuesta pendiente. **Nunca se usa para inferir Etapa/Bloque/Casa.**

## 5. Vercel

Crear un proyecto con:

- repositorio: `Jchernand3z19/Portafolio`;
- Root Directory: `pagos-whatsapp-residencial`;
- framework: Next.js;
- Node.js 22.

Separar variables de Preview y Production. Los secretos de producción no deben estar disponibles en previews públicas salvo necesidad explícita.

Variables de autenticación:

- `ADMIN_ACCESS_KEY` — clave larga y aleatoria;
- `AUTH_SESSION_SECRET` — secreto aleatorio independiente.

Regla de monto:

- `EXPECTED_PAYMENT_AMOUNT=150`

Variables opcionales de validación:

- `EXPECTED_BENEFICIARY`;
- `EXPECTED_ACCOUNT_LAST4`.

Configurar `APP_MODE=production` únicamente en producción. Mantener previews públicas en `demo` cuando no necesiten datos reales.

## 6. Viviendas

Cargar `Viviendas` con datos reales sólo en la Sheet privada.

Campos mínimos:

- `id`
- `stage`
- `block`
- `house`
- `monthly_fee`
- `active`

`responsible` es opcional. No hay campo de teléfono para resolución de pagos.

Para el MVP la cuota bancaria esperada es L150.00. El sistema conserva por separado la cuota de la vivienda y el monto extraído del comprobante; cualquier monto distinto de L150 queda en revisión humana.

## 7. Histórico inicial

Agosto 2026 es la base del histórico de depósitos:

- depósitos del 1 al 14 de agosto → julio 2026;
- depósitos del 15 al 31 de agosto → agosto 2026;
- desde septiembre, el sistema aplica el depósito al primer mes **no verificado como pagado** desde agosto;
- un comprobante sólo recibido o en revisión no hace avanzar el histórico;
- si llega otro comprobante mientras el primer mes sigue sin verificar, ambos quedan vinculados al mismo mes pendiente y el conflicto requiere revisión;
- los pagos en efectivo se incorporarán posteriormente mediante un flujo manual separado.

Antes de cargar datos reales, validar el histórico en una copia privada/controlada de la Sheet.

## 8. Verificación bancaria

El MVP **no necesita acceso a la banca en línea**.

El encargado:

1. revisa el movimiento por su cuenta en BAC;
2. compara banco, monto, fecha y referencia disponibles;
3. en el panel pulsa `Verificar` o `Verifiqué en banco` sólo si el caso es elegible.

Un monto menor o mayor de L150, un conflicto de mes o evidencia de reutilización del mismo movimiento permanecen en revisión aunque el movimiento exista en BAC. Primero debe resolverse la excepción correcta; el botón de verificación no la debe borrar.

No almacenar usuario, contraseña, PIN, token OTP ni códigos de BAC en Vercel, Google Sheets, GitHub o el navegador.

Una integración futura puede usar un archivo/API bancaria autorizada. Para verificación automática la fuente debe proporcionar un identificador estable del movimiento. El sistema persiste `bank_movement_id` y no permite que ese movimiento verifique dos pagos distintos, ni en la misma corrida ni en una posterior.

## 9. Validación antes de operar

- webhook challenge funciona;
- firma inválida retorna 401;
- archivo no imagen se rechaza;
- comprobante BAC sintético/de prueba controlada se procesa;
- retry del mismo `message_id` no duplica;
- comprobante con E/B/C completos valida la vivienda;
- comprobante que omite cualquiera de Etapa/Bloque/Casa pide los tres datos;
- respuesta `E1 B4 C18` asigna la vivienda sin repetir OCR;
- el teléfono remitente no asigna vivienda;
- monto exactamente L150 sigue a verificación bancaria;
- monto menor o mayor de L150 pasa a revisión y no puede verificarse por el atajo manual;
- depósito de septiembre con agosto no verificado se mantiene en agosto;
- depósito de septiembre con agosto ya `VERIFICADO` se aplica a septiembre;
- una vivienda sólo aparece pagada después de `VERIFICADO`;
- referencia repetida pasa a revisión y no se descarta automáticamente;
- archivo exacto reenviado no incrementa recaudación;
- panel permite verificación bancaria manual sólo para pagos elegibles;
- un conflicto de período no puede verificarse hasta corregirse;
- un `bank_movement_id` ya usado no verifica otro pago;
- panel requiere login;
- comprobante privado no abre sin sesión;
- Sheet y Drive no son públicos;
- `VERIFICADO` sólo aparece tras una confirmación bancaria explícita.
