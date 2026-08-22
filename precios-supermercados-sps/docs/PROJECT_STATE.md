# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable** del proyecto. `docs/arquitectura.md` describe la arquitectura estable; los PR, runs, comentarios y artefactos son evidencia histórica y no sustituyen este corte.

## Corte

Estado verificado al **2026-08-22 (America/Tegucigalpa)**.

```text
base técnica del corte = da342bf9439e260a8bc213c8c83e805412c5741d (merge de PR #154)
último PR técnico integrado antes de este corte documental = #154
última suite técnica completa observada = 1462/1462 PASS (PR #154)
compileall = PASS
GATE-17 = PASS_PRODUCTIVE_EVIDENCE
ACTIVE_AUTHORIZATION_IDS = []
READY_FOR_LIVE = NO
SPS_TECHNICAL_CONTEXT = UNCONFIRMED
production_authority = false
catalog_accepted = false
```

El HEAD mutable de `main` no se usa como autoridad por sí mismo; este corte fija únicamente la base técnica que fue validada antes de la actualización documental.

## Semántica de estado

| Estado | Significado |
|---|---|
| `DONE` | Contrato/lógica integrada y estable. |
| `DONE_OFFLINE` | Implementado y probado, pero sin afirmar efecto productivo externo. |
| `DONE_PRODUCTIVE` | Evidencia real/productiva observada para esa capacidad concreta. |
| `PARTIAL_PRODUCTIVE` | Una parte de la cadena se demostró físicamente, pero falta otra condición para aceptar la frontera completa. |
| `BLOCKED_LIVE` | Requiere observación real de la fuente. |
| `BLOCKED_HUMAN_DECISION` | Requiere autorización humana explícita. |
| `BLOCKED_EXTERNAL` | Requiere configuración/credencial/servicio externo no demostrado. |
| `BLOCKED_DEPENDENCIES` | Depende de cerrar una frontera anterior. |

## Resumen por área

| Área | Estado | Hecho verificable / bloqueo |
|---|---|---|
| Contratos `RawProduct` / `NormalizedOffer` / `ValidatedOffer` | `DONE` | Protegidos por pruebas e invariantes. |
| Extractor La Colonia, GraphQL, ventanas, facets, particiones, coverage y reconciliación de catálogo | `DONE_OFFLINE` | Implementados con fixtures y validación adversarial; no equivalen a catálogo productivo aceptado. |
| GATE-17 / protección de `main` | `DONE_PRODUCTIVE` | `PASS_PRODUCTIVE_EVIDENCE`. |
| Sonda Cloudflare: OIDC → Durable Object → origen controlado → receipt Ed25519 | `DONE_PRODUCTIVE` para esas capacidades | Run físico `32551882793`; evidencia firmada revalidada posteriormente. |
| Verificación criptográfica independiente de la sonda | `DONE_PRODUCTIVE` | Verifier-only `32552932554` revalidó firma, bytes e identidad. |
| Reconciliación estricta contra Workers Observability | `PARTIAL_PRODUCTIVE / BLOCKED_EXTERNAL` | Existe trace candidato real, pero la API pública consultada no expone el custom span/fetch hijo requerido; el verificador estricto se conserva. |
| Autoridad productiva del collector/catálogo | `BLOCKED_DEPENDENCIES` | No se deriva de sonda, fixtures, hashes ni caller input; sigue `production_authority=false` / `catalog_accepted=false`. |
| Modelo común de supermercados/ubicaciones | `DONE_OFFLINE` | La Colonia registra SPS y Tegucigalpa; sólo SPS está dentro del alcance inicial. |
| Granularidad comercial de La Colonia SPS | `BLOCKED_LIVE` | Se mantiene `unknown`; no se asume que precio/inventario varían sólo por ciudad. |
| Binding técnico SPS | `BLOCKED_LIVE` | `technical_binding_confirmed=false`, sin `source_location_key` productiva. |
| Radiografía de ubicación `city|store` | `DONE_OFFLINE` | Analizador, capturador Playwright, workflow manual y evaluador de transición integrados; workflow live permanece bloqueado. |
| Current/history + ahorro real | `DONE_OFFLINE` | Máquina comercial atómica/idempotente; ahorro contra precio histórico aceptado anterior. |
| Persistencia tabular común | `DONE_OFFLINE` | Config, current, history, runs y quality events comparten tablas para todos los supermercados. |
| Guard de autoridad antes de persistencia | `DONE_OFFLINE` | PR #150 impide que código operativo convierta una `CommercialRunDecision` caller-controlled en mutación de current/history. |
| Binding durable de replay | `DONE_OFFLINE` | PR #151 liga evidencia, decisión, ofertas, metadata y quality events con fingerprint `crev1_`; demuestra igualdad/replay, nunca autoridad. |
| Rehidratación + restauración entre runners | `DONE_OFFLINE` | PR #152 restaura el motor desde current/history/runs y reserva todos los IDs terminales históricos. |
| Google Sheets plan/transporte/adapter/bootstrap | `DONE_OFFLINE` | Plan atómico, transporte autenticado, read-modify-write y bootstrap manual implementados. No se ha observado aún una escritura productiva. |
| Google Sheets read-side → estado comercial | `DONE_OFFLINE` | PR #153 carga snapshot validado, recalcula métricas, rehidrata current/history y restaura el motor sin writes ni autoridad. |
| Batch comercial → Google Sheets | `DONE_OFFLINE` | Existe frontera comercial a `TabularBatch`, pero la entrada productiva mutante sigue cerrada hasta autoridad real. |
| Google Sheets productivo | `BLOCKED_EXTERNAL / BLOCKED_DEPENDENCIES` | Requiere configuración/credenciales productivas observadas y sólo podrá recibir datos comerciales autoritativos cuando ubicación/autoridad estén cerradas. |
| Proyección semántica Power BI | `DONE_OFFLINE` | PR #154 centraliza precio actual, baseline aceptado, ahorro real, dirección de precio, precio regular reportado, promoción, disponibilidad, ubicación y review status. |
| Dataset/refresh Power BI productivo | `BLOCKED_DEPENDENCIES` | Espera persistencia durable/autoritativa; Power BI no decide autoridad ni recalcula la semántica comercial. |
| Scraping diario | `BLOCKED_DEPENDENCIES` | Espera binding correcto, live estable, autoridad de catálogo y persistencia productiva. |
| Segundo supermercado | `BLOCKED_DEPENDENCIES` | Se inicia después de cerrar La Colonia end-to-end sobre la plataforma común. |

## Evidencia Cloudflare física

La afirmación histórica “sonda no desplegada/no ejecutada” ya no es válida.

```text
physical probe source run = 32551882793
verifier-only run         = 32552932554
```

La sonda demostró físicamente OIDC de GitHub, Worker/Durable Object, fetch al origen controlado `workers.dev`, challenge/body esperado, receipt Ed25519 y verificación independiente de firma/bytes/identidad.

La reconciliación estricta del custom span + child fetch mediante la API pública de Workers Observability **no** se declara cerrada. Los diagnósticos históricos mostraron que la superficie pública disponible no entrega el detalle que exige el reconciliador. No se fabrica un PASS ni se rebaja el verificador.

No se necesita repetir la sonda física salvo cambio de infraestructura o una hipótesis explícita nueva.

## La Colonia — ubicación y live

Estado de `la_colonia_sps`:

```text
city = San Pedro Sula
in_scope = true
granularity = unknown
technical_binding_confirmed = false
source_location_key = null
extraction_enabled = false
```

La UI conocida expone al menos San Pedro Sula y Tegucigalpa, pero eso no demuestra si el contexto comercial efectivo varía por ciudad o tienda.

La radiografía preparada compara `before -> after_city -> after_store` y busca mecanismos fuertes como `regionId`, `salesChannel`, `binding`, `store` o `storeId`. Valores opacos se convierten en fingerprints sanitizados. `vtex_session` / `vtex_segment` no bastan por sí solos para confirmar granularidad.

El workflow de radiografía sigue deliberadamente bloqueado y la allow-list live está vacía. **No debe iniciarse ninguna petición nueva a La Colonia sin una nueva autorización humana explícita y limitada.**

Una autorización para radiografía no cubriría smoke, facets, GraphQL replay, crawl completo ni persistencia de precios.

## Persistencia

Google Sheets sigue siendo el almacenamiento temporal estructurado de la primera fase; BigQuery se incorpora cuando el proceso esté estable.

Tablas comunes:

```text
cfg_supermarkets
cfg_locations
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

Reglas vigentes:

- un mismo esquema para todos los supermercados;
- current/history rehidratables y restaurables entre runners;
- nuevo periodo histórico sólo ante cambio relevante;
- cada run final se registra aunque no cambie ningún precio;
- runs rechazados/fallidos no alteran current/history;
- un retry durable sólo se reconoce cuando evidencia + decisión + payload coinciden;
- restaurar un snapshot no concede nueva autoridad;
- ausencia de una oferta en un payload no implica baja ni `out_of_stock`;
- Google Sheets se materializa como snapshot completo mediante un único `spreadsheets.batchUpdate` planificado;
- el read-side de Sheets sólo lee/valida/rehidrata/restaura;
- una decisión caller-controlled nunca sustituye evidencia autoritativa.

Configuración externa prevista:

```text
Environment: precios-sps-storage
Variable: PRECIOS_SPS_GOOGLE_SPREADSHEET_ID
Secret: PRECIOS_SPS_GOOGLE_SERVICE_ACCOUNT_JSON
```

La capacidad externa sigue sin declararse productiva hasta observar que esa configuración existe y que una operación de storage válida funciona. Esto puede verificarse sin contactar La Colonia.

## Regla comercial del precio y Power BI

Separar siempre:

```text
current_price              = precio observado que paga el cliente
reported_regular_price     = referencia declarada por la tienda
previous_accepted_price    = current_price del periodo aceptado inmediatamente anterior
```

La reducción real usa únicamente histórico propio aceptado:

```text
reduction = max(previous_accepted_price - current_price, 0)
```

Si no existe baseline, no se inventa ahorro. Una subida produce reducción cero. PR #154 expone esta semántica como proyección read-only para BI junto con `price_direction`, ubicación, `review_status`, promoción y disponibilidad; Power BI no debe redefinirla en DAX.

## Próximos pasos

Trabajo que todavía puede hacerse sin tráfico a La Colonia:

1. verificar en modo read-only si el environment `precios-sps-storage` ya contiene la variable/secret esperados;
2. si la configuración existe, revisar que el bootstrap de Google Sheets pueda ejecutarse sin tocar La Colonia antes de cualquier write externo;
3. mantener la proyección BI como contrato derivado, sin conectarla a datos no autoritativos.

La **próxima dependencia humana live** continúa siendo una nueva autorización explícita para una única radiografía limitada de ubicación de La Colonia.

Después de resolver ubicación y autoridad, el orden productivo es:

```text
binding de ubicación
-> validación live exacta/autorizada del catálogo
-> decisión autoritativa del catálogo
-> Google Sheets productivo
-> ejecución diaria
-> dataset/refresh Power BI
-> La Colonia end-to-end
-> supermercado #2
```

## Tráfico live reciente

PR #135–#154 y este corte documental se realizaron **sin nuevos requests a La Colonia**.

No usar esta frase para inferir que el proyecto nunca realizó pruebas live históricas; sólo describe este bloque de trabajo.
