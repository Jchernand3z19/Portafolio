# Pagos residenciales por WhatsApp

Plataforma de automatización de cobros residenciales por WhatsApp con OCR, validación de transacciones, conciliación, control de cartera y dashboard administrativo.

> **Importante:** un comprobante leído por OCR no demuestra que el dinero exista. El sistema separa explícitamente `comprobante recibido` de `pago verificado`; sólo una fuente bancaria confiable puede llevar un pago a `VERIFICADO`.

## Objetivo

Automatizar el flujo operativo de una empresa residencial que recibe comprobantes bancarios por WhatsApp:

`Vecino → WhatsApp → archivo → validación → OCR → parser bancario → vivienda → duplicados → registro → conciliación → dashboard → respuesta`

El MVP inicia con **BAC Honduras**, pero los parsers están desacoplados para incorporar Ficohsa, Atlántida, Banpaís, Occidente y otros sin reescribir la lógica central.

## Capacidades implementadas

- Webhook de WhatsApp Cloud API con verificación y firma `X-Hub-Signature-256`.
- Retry técnico de Meta detectado antes de volver a descargar media o ejecutar OCR cuando el `message_id` ya fue procesado.
- Descarga server-side de media; JPG/JPEG y PNG con validación de MIME, magic bytes y tamaño antes de OCR.
- OCR local/server-side con Tesseract.js + modelo español y preprocesamiento Sharp.
- Parser BAC para banco, depositante, fecha, hora, monto, detalle, referencia, beneficiario y cuenta destino enmascarada.
- Normalización de vivienda: `B4 C18`, `Bloque 4 Casa 18`, `B4-C18`, `B 4 C 18` y variantes.
- Normalización de identidad telefónica para comparar formatos equivalentes como `+504...` y `504...`.
- Resolución por comprobante → teléfono de vivienda → pregunta automática por WhatsApp.
- Contexto pendiente único por teléfono para evitar asignaciones ambiguas.
- Idempotencia por `message_id` y detección de duplicados por hash, referencia bancaria y señales débiles.
- Motivo de duplicado/conflicto persistido para trazabilidad administrativa.
- Conflictos entre usuarios/viviendas enviados a revisión sin revelar datos de terceros.
- Estados separados para recibido, pendiente de verificación, verificado, duplicado, no encontrado, revisión y rechazo.
- Google Sheets privado como tabla operativa (`Pagos`, `Viviendas`, `Conversaciones`, `Mensajes`, `Conciliacion`, `Configuracion`).
- Base maestra de viviendas editable desde el panel: bloque, casa, responsable opcional, teléfono, cuota, alta/baja y estado activo.
- Google Drive privado para conservar comprobantes de producción; el identificador del archivo se guarda en Sheets y nunca se publica directamente.
- Dashboard mensual: viviendas, pagadas, pendientes, cobranza, esperado, recibido, verificado, pendiente y sin identificar.
- Vistas por bloque y por casa, incluyendo historial de cuatro períodos y detalle completo de una vivienda.
- Bandejas de pagos, depósitos sin identificar, duplicados y casos en revisión.
- Corrección administrativa de vivienda y período sin repetir OCR.
- Conciliación determinística contra movimientos bancarios por banco + referencia + monto.
- Panel administrativo protegido con sesión HttpOnly firmada y clave por ambiente.
- Demo pública completamente sintética y separada de producción.
- Suite de pruebas y CI aislado.

## Estados

```text
COMPROBANTE_RECIBIDO
  ↓
PROCESANDO
  ↓
EXTRAIDO
  ├─ falta vivienda → ESPERANDO_RESPUESTA → PENDIENTE_VERIFICACION
  ├─ duplicado → DUPLICADO
  ├─ conflicto → EN_REVISION
  └─ válido → PENDIENTE_VERIFICACION
                    ↓
              CONCILIACION
              ├─ coincide → VERIFICADO
              ├─ no existe → NO_ENCONTRADO
              └─ ambiguo → EN_REVISION
```

## Estructura

```text
pagos-whatsapp-residencial/
├── app/                    # UI, panel y Route Handlers de Next.js
├── src/
│   ├── auth/               # sesión administrativa
│   ├── config/             # contrato de variables de entorno
│   ├── demo/               # datos y comprobantes sintéticos
│   ├── domain/             # estados, períodos, vivienda, duplicados
│   ├── ocr/                # Sharp + Tesseract.js
│   ├── parsers/            # parsers desacoplados por banco
│   │   └── bac/
│   ├── security/           # archivos, firmas y logging seguro
│   ├── services/           # procesamiento, dashboard, historial, conciliación
│   ├── storage/            # Google Sheets, Drive y memoria demo
│   └── whatsapp/           # payload y cliente Cloud API
├── tests/
├── docs/
└── .env.example
```

## Demo vs producción

### Demo

`APP_MODE=demo`

- no utiliza Meta, Google ni credenciales;
- no acepta el webhook real;
- usa únicamente datos ficticios;
- permite mostrar dashboard, parser, bloque/casa, duplicados y excepciones sin exponer información sensible.

### Producción

`APP_MODE=production`

Requiere variables de entorno en Vercel. Copiar `.env.example` sólo como referencia; **nunca** rellenarlo y subirlo al repositorio.

Variables principales:

- `ADMIN_ACCESS_KEY`
- `AUTH_SESSION_SECRET`
- `GOOGLE_SHEET_ID`
- `GOOGLE_CLIENT_EMAIL`
- `GOOGLE_PRIVATE_KEY`
- `GOOGLE_RECEIPT_FOLDER_ID`
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `META_APP_SECRET`
- `WHATSAPP_GRAPH_VERSION`
- `EXPECTED_BENEFICIARY` (opcional)
- `EXPECTED_ACCOUNT_LAST4` (opcional)

## Ejecución local

Requiere Node.js 22 o superior.

```bash
npm install
npm run dev
```

Validación completa:

```bash
npm run lint
npm run typecheck
npm test
npm run build
```

## Webhook

Endpoint:

```text
GET/POST /api/whatsapp/webhook
```

En producción:

1. `GET` valida `hub.mode`, `hub.verify_token` y devuelve `hub.challenge`.
2. `POST` lee el cuerpo crudo y valida HMAC-SHA256 antes de parsear JSON.
3. sólo procesa mensajes soportados;
4. los textos normales se ignoran salvo que exista un comprobante pendiente de vivienda;
5. un retry técnico con el mismo `message_id` no vuelve a descargar el archivo, no repite OCR y no genera una respuesta intencional.

## Google Sheets

El backend crea/valida las hojas requeridas y usa `valueInputOption=RAW` para evitar que texto extraído por OCR se convierta en fórmulas de Sheets.

La Sheet no debe publicarse. La cuenta de servicio sólo necesita acceso al documento operativo y al folder privado de comprobantes. La base `Viviendas` puede administrarse desde el panel, por lo que la operación normal no requiere editar filas manualmente.

Ver [`docs/SHEETS_SCHEMA.md`](docs/SHEETS_SCHEMA.md).

## Seguridad

El repositorio es público por diseño. Está prohibido versionar:

- tokens, claves o service-account JSON;
- comprobantes reales;
- teléfonos o nombres reales de vecinos;
- números de cuenta o referencias reales;
- archivos exportados desde producción.

Los logs no imprimen payloads completos. Teléfonos, referencias e identificadores se enmascaran cuando se registran eventos operativos.

Ver [`docs/SECURITY.md`](docs/SECURITY.md).

## OCR

La primera versión usa Tesseract.js en Node.js con modelo español local y Sharp para rotación, reducción, escala de grises, normalización y enfoque. No envía el comprobante a un proveedor de IA externo.

PDF no se habilita en el MVP inicial: Tesseract.js procesa imágenes, y añadir rasterización/PDF aumenta peso, superficie de ataque y cold start. El usuario recibe una instrucción clara para enviar JPG/PNG. Esta decisión puede revisarse en una fase posterior.

Ver [`docs/OCR_DECISION.md`](docs/OCR_DECISION.md).

## Conciliación

`src/services/reconciliation.ts` no confía en el OCR para verificar dinero. Para marcar `VERIFICADO` exige una coincidencia única de:

- banco;
- referencia;
- monto;
- y, si ambas fuentes tienen fecha, una fecha consistente.

La entrada puede provenir posteriormente de un archivo de movimientos, notificación bancaria o integración autorizada.

## Pruebas

La suite cubre, entre otros:

- BAC válido y sin vivienda;
- variaciones `B4 C18`;
- referencia y archivo duplicados;
- retry de webhook;
- archivo/MIME inválido;
- firma del webhook;
- acceso administrativo y sesión manipulada;
- cuenta destino inesperada;
- estado sin identificar y asignación posterior;
- contexto pendiente único;
- normalización de teléfonos;
- creación/actualización y unicidad de viviendas;
- historial mensual por casa;
- conciliación;
- exclusión de duplicados en totales.

Todos los datos de prueba son sintéticos.

## Limitaciones actuales del MVP

- Banco parseado: BAC Honduras.
- Entrada de comprobantes: JPG/JPEG y PNG; PDF se rechaza de forma segura.
- La conciliación bancaria está implementada como servicio determinístico, pero aún necesita una fuente bancaria real autorizada para producción.
- Google Sheets es apropiado para el volumen residencial del MVP, pero no es una base transaccional; una evolución de alto volumen debe usar un datastore con unicidad/transactions y mantener Sheets como salida operativa.
- La demo pública no ejecuta OCR binario real: usa texto OCR sintético y el parser real para demostrar reglas sin publicar imágenes de banca.

## Documentación

- [Arquitectura](docs/ARCHITECTURE.md)
- [Esquema de Google Sheets](docs/SHEETS_SCHEMA.md)
- [Seguridad y privacidad](docs/SECURITY.md)
- [Decisión de OCR](docs/OCR_DECISION.md)

## Portafolio

Este proyecto debe presentarse como una **plataforma de automatización de cobros residenciales**, no como un OCR aislado. Demuestra integración de APIs, backend, frontend, procesamiento documental, seguridad, idempotencia, reglas de negocio, excepciones, conciliación, pruebas y CI/CD.
