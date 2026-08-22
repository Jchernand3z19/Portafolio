# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable** del proyecto. `docs/arquitectura.md` describe la arquitectura estable; los PR, runs, comentarios y artefactos son evidencia histórica y no sustituyen este corte.

## Corte

Estado verificado al **2026-08-22 (America/Tegucigalpa)**.

```text
main = b4588d7425601963cc64cc6eec779fdbe9492b05
último PR integrado = #148
última suite completa observada = 1418/1418 PASS
GATE-17 = PASS_PRODUCTIVE_EVIDENCE
ACTIVE_AUTHORIZATION_IDS = []
READY_FOR_LIVE = NO
SPS_TECHNICAL_CONTEXT = UNCONFIRMED
production_authority = false
catalog_accepted = false
```

No hay PR técnicos abiertos al cerrar este corte.

## Semántica de estado

| Estado | Significado |
|---|---|
| `DONE` | Contrato/lógica integrada y estable. |
| `DONE_OFFLINE` | Implementado y probado, pero sin afirmar efecto productivo externo. |
| `DONE_PRODUCTIVE` | Evidencia real/productiva observada para esa capacidad concreta. |
| `PARTIAL_PRODUCTIVE` | Una parte de la cadena se demostró físicamente, pero falta otra condición para aceptar la frontera completa. |
| `BLOCKED_LIVE` | Requiere observación real de la fuente. |
| `BLOCKED_HUMAN_DECISION` | Requiere autorización humana explícita. |
| `BLOCKED_EXTERNAL` | Requiere configuración/credencial/servicio externo no disponible desde el código. |
| `BLOCKED_DEPENDENCIES` | Depende de cerrar una frontera anterior. |

## Resumen por área

| Área | Estado | Hecho verificable / bloqueo |
|---|---|---|
| Contratos `RawProduct` / `NormalizedOffer` / `ValidatedOffer` | `DONE` | Protegidos por pruebas e invariantes. |
| Extractor La Colonia, GraphQL, ventanas, facets, particiones, coverage y reconciliación de catálogo | `DONE_OFFLINE` | Implementados con fixtures y validación adversarial; no equivalen a catálogo productivo aceptado. |
| GATE-17 / protección de `main` | `DONE_PRODUCTIVE` | `PASS_PRODUCTIVE_EVIDENCE`. |
| Sonda Cloudflare: OIDC → Durable Object → origen controlado → receipt Ed25519 | `DONE_PRODUCTIVE` para esas capacidades | Run físico `32551882793` completó la sonda; evidencia firmada revalidada posteriormente. |
| Verificación criptográfica independiente de la sonda | `DONE_PRODUCTIVE` | El verifier-only revalidó firma, bytes e identidad del intento físico. |
| Reconciliación estricta contra Workers Observability | `PARTIAL_PRODUCTIVE / BLOCKED_EXTERNAL` | Se descubrió trace candidato real, pero la API pública consultada no expone el custom span/fetch hijo con la forma requerida para cerrar el reconciliador estricto. PR #134 retiró el diagnóstico temporal sin rebajar el verificador. |
| Autoridad productiva del collector/catálogo | `BLOCKED_DEPENDENCIES` | No se deriva de la sonda ni de fixtures; sigue `production_authority=false` / `catalog_accepted=false`. |
| Modelo común de supermercados/ubicaciones | `DONE_OFFLINE` | La Colonia registra SPS y Tegucigalpa; sólo SPS está dentro del alcance inicial. |
| Granularidad comercial de La Colonia SPS | `BLOCKED_LIVE` | Se mantiene `unknown`; no se asume que precio/inventario varían sólo por ciudad. |
| Binding técnico SPS | `BLOCKED_LIVE` | `technical_binding_confirmed=false`, sin `source_location_key` productiva. |
| Radiografía de ubicación `city|store` | `DONE_OFFLINE` | Analizador, capturador Playwright, workflow manual y evaluador de transición integrados en PR #145–#148. Workflow live permanece bloqueado. |
| Current/history + ahorro real | `DONE_OFFLINE` | Máquina comercial atómica/idempotente; ahorro contra precio histórico aceptado anterior. |
| Persistencia tabular común | `DONE_OFFLINE` | Config, current, history, runs y quality events comparten tablas para todos los supermercados. |
| Rehidratación durable entre runners | `DONE_OFFLINE` | Current/history reconstruibles y revalidados desde snapshot tabular. |
| Google Sheets plan/transporte/adapter/bootstrap | `DONE_OFFLINE` | Plan atómico, transporte autenticado cerrado, read-modify-write y workflow manual implementados. No se observó una escritura real con credenciales productivas. |
| Batch comercial → Google Sheets | `DONE_OFFLINE` | Frontera comercial produce `TabularBatch` durable antes del adapter. |
| Google Sheets productivo | `BLOCKED_EXTERNAL / BLOCKED_DEPENDENCIES` | Requiere Environment/variable/service account y sólo debe recibir datos comerciales cuando la ubicación/autoridad correspondiente esté cerrada. |
| Scraping diario | `BLOCKED_DEPENDENCIES` | Espera live estable, binding correcto, autoridad de catálogo y persistencia productiva. |
| Power BI | `BLOCKED_DEPENDENCIES` | Espera dataset comercial durable/autoritativo. |
| Segundo supermercado | `BLOCKED_DEPENDENCIES` | Se inicia después de cerrar La Colonia end-to-end sobre la plataforma común. |

## Evidencia Cloudflare física

La afirmación histórica “sonda no desplegada/no ejecutada” ya no es válida.

Evidencia principal:

```text
physical probe source run = 32551882793
verifier-only run         = 32552932554
```

El ejercicio físico demostró de forma separada:

1. emisión y validación OIDC de GitHub contra Cloudflare;
2. ejecución del Worker gateway de sonda y `ProbeLedger`;
3. fetch físico al origen controlado `workers.dev`;
4. challenge/body esperado;
5. receipt Ed25519 y hash de respuesta;
6. verificación independiente de firma/bytes/identidad desde GitHub sin OIDC.

La parte que **no** se declara cerrada es la reconciliación estricta del custom span + child fetch mediante la API pública de Workers Observability. Los diagnósticos de PR #99–#134 confirmaron que la forma pública disponible no entrega el detalle que el reconciliador exige. El proyecto conserva el verificador estricto en vez de fabricar un PASS.

No se necesita repetir la sonda física para volver a demostrar OIDC/fetch/firma salvo que cambie esa infraestructura o exista una razón explícita distinta.

## La Colonia — ubicación

Estado de `la_colonia_sps`:

```text
city = San Pedro Sula
in_scope = true
granularity = unknown
technical_binding_confirmed = false
source_location_key = null
extraction_enabled = false
```

La UI conocida expone al menos San Pedro Sula y Tegucigalpa, pero eso **no demuestra** si el contexto comercial efectivo varía por ciudad o por tienda.

La radiografía preparada en PR #145–#148 está diseñada para resolver exclusivamente esa duda:

```text
home
-> selector público de ubicación
-> enumerar ciudades visibles
-> seleccionar San Pedro Sula
-> si aparecen tiendas, enumerarlas y elegir una opción determinista
-> comparar mecanismos de contexto before / after_city / after_store
-> emitir sólo fingerprints sanitizados
```

Mecanismos fuertes considerados incluyen `regionId`, `salesChannel`, `binding`, `store` y `storeId`. `vtex_session` / `vtex_segment` son evidencia débil y no bastan por sí solas para confirmar granularidad.

El workflow `La Colonia - Radiografía manual de ubicación` está deliberadamente cerrado con `if: ${{ false }}` y el capturador mantiene `LIVE_EXECUTION_ENABLED=False` + allow-list vacía. **No debe habilitarse hasta recibir una nueva autorización humana explícita.**

## Qué ocurre después de una radiografía autorizada

El artifact sanitizado no se aplica directamente; `location_binding_transition.py` lo evalúa fail-closed.

### Si demuestra `city + strong`

Puede proponerse:

```text
granularity = city
technical_binding_confirmed = true
source_location_key = fingerprint de evidencia
evidence = SHA-256 del artifact
extraction_enabled = false
```

Incluso en este caso la radiografía **no habilita automáticamente scraping comercial**.

### Si demuestra `store + strong`

No se promueve `la_colonia_sps` como una única ubicación comercial. Deben modelarse/bindearse las tiendas SPS individualmente antes de persistir precios como comparables.

### Si queda `unknown`

No se cambia configuración de ubicación y se diseña el diagnóstico mínimo siguiente; no se adivina.

## Persistencia

La decisión inicial sigue siendo **Google Sheets como almacenamiento temporal estructurado**, con evolución posterior a BigQuery cuando el proceso sea estable.

Ya están implementadas offline las tablas comunes:

```text
cfg_supermarkets
cfg_locations
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

Principios vigentes:

- un mismo esquema para todos los supermercados;
- current/history rehidratables entre runners;
- nuevo periodo histórico sólo ante cambio relevante;
- cada run final se registra aunque no cambie ningún precio;
- runs rechazados/fallidos no alteran current/history;
- Google Sheets se materializa como snapshot completo y no como parche parcial;
- escrituras planificadas mediante un único `spreadsheets.batchUpdate`;
- texto fuente no se convierte accidentalmente en fórmula;
- no se usa Google Drive como backend de aplicación.

Configuración externa prevista para el workflow de storage:

```text
Environment: precios-sps-storage
Variable: PRECIOS_SPS_GOOGLE_SPREADSHEET_ID
Secret: PRECIOS_SPS_GOOGLE_SERVICE_ACCOUNT_JSON
```

No se considera productivo hasta observar una configuración/escritura real válida.

## Regla comercial del precio

`reported_regular_price` es sólo el precio de referencia declarado por el supermercado; no demuestra una oferta real.

La reducción real se calcula contra el `current_price` del periodo histórico aceptado inmediatamente anterior. Por tanto:

```text
precio actual < último precio histórico aceptado  -> reducción real
precio actual = último precio histórico aceptado  -> sin reducción
precio actual > último precio histórico aceptado  -> subida
```

Si no existe baseline confiable, no se inventa ahorro.

## Próxima dependencia real

El siguiente paso que ya no puede completarse honestamente sólo con trabajo offline es una **nueva autorización humana explícita para una única radiografía live limitada de ubicación de La Colonia**.

Esa autorización no debe interpretarse como permiso para smoke, facets, GraphQL replay, crawl completo ni persistencia de precios.

Después de resolver `city|store` y el binding técnico, el orden sigue siendo:

```text
binding de ubicación
-> validación live exacta/autorizada del catálogo
-> decisión autoritativa del catálogo
-> Google Sheets productivo
-> ejecución diaria
-> dataset Power BI
-> La Colonia end-to-end
-> supermercado #2
```

## Tráfico live reciente

PR #135–#148 y esta actualización documental se realizaron **sin nuevos requests a La Colonia**.

No usar esta frase para inferir que el proyecto nunca realizó pruebas live históricas; sólo describe este bloque de trabajo.
