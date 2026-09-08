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
- `WHATSAPP_GRAPH_VERSION` — por defecto `v26.0` en esta versión del proyecto.

Webhook de producción:

```text
https://<dominio>/api/whatsapp/webhook
```

Suscribir únicamente los eventos necesarios.

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

Variables opcionales de validación:

- `EXPECTED_BENEFICIARY`;
- `EXPECTED_ACCOUNT_LAST4`.

Configurar `APP_MODE=production` únicamente en producción. Mantener previews de portafolio en `demo` cuando no necesiten datos reales.

## 6. Viviendas

Cargar `Viviendas` con datos reales sólo en la Sheet privada. La clave operativa es bloque + casa.

Campos mínimos:

- `id`
- `block`
- `house`
- `monthly_fee`
- `active`

Teléfono y responsable son opcionales.

## 7. Validación antes de operar

- webhook challenge funciona;
- firma inválida retorna 401;
- archivo no imagen se rechaza;
- comprobante BAC sintético/de prueba controlada se procesa;
- retry del mismo `message_id` no duplica;
- comprobante sin vivienda pregunta bloque/casa;
- respuesta asigna la vivienda sin repetir OCR;
- duplicado no incrementa recaudación;
- panel requiere login;
- comprobante privado no abre sin sesión;
- Sheet y Drive no son públicos;
- `VERIFICADO` sólo aparece después de conciliación.
