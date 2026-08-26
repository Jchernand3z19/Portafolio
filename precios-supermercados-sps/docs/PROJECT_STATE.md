# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia/historia; no conceden por sí solos autoridad comercial ni autorización live.

## Corte actual

Estado verificado al **2026-08-26 UTC** después de los PR #315, #316, #319 y #320:

```text
last_merged_pr = #320 — Simula persistencia tabular de La Colonia
active_offline_pr = none
active_live_pr = none
active_attempt_sequence = none
last_successful_full_catalog_attempt = 15
SPS_TECHNICAL_CONTEXT = CONFIRMED
location_id = la_colonia_sps
granularity = city
technical_binding_confirmed = true
full_catalog_validation_passed = true
full_crawl = true
products_normalized = 9439 / 9439
presentation_pending = 0
history_change_integration = verified_offline
tabular_rehydrate_restore_cycle = verified_offline
persistent_backend_selected = bigquery
google_sheets_selected = false
google_sheets_writes = false
commercial_persistence = false
catalog_accepted = false
production_authority = false
extraction_enabled = false
ACTIVE_AUTHORIZATION_IDS = []
```

`ACTIVE_AUTHORIZATION_IDS = []` significa que no existe una autorización live vigente. La evidencia histórica **no se interpreta como autorización abierta** y cualquier nuevo tráfico contra La Colonia fuera de un alcance explícitamente autorizado **requiere autorización humana explícita vigente**.

## One-shot full catalog — consumido

La autorización humana para obtener una vez el catálogo completo read-only de La Colonia San Pedro Sula terminó correctamente en el intento #15. No existe un segundo full crawl pendiente ni implícitamente autorizado.

```text
authorization_mode = one_time_full_catalog_after_staged_validation
authorized_at_utc = 2026-08-25T21:13:44Z
termination_condition = first_successful_downloadable_full_sps_catalog
termination_condition_met = true
attempt_sequence = 15
active = false
```

El fingerprint técnico SPS preservado es:

```text
sps_region_fingerprint = d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
```

No se persisten cookies, `regionId` raw, sesión, headers ni URLs sensibles.

## Catálogo completo aceptado técnicamente

Intento #15:

```text
run_id = 32922877781
artifact_id = 9590684834
artifact_name = la-colonia-sps-data-32922877781
result = success
catalog_complete = true
validation_passed = true
catalog_product_coverage = 1.0
location_verified_same_run = true
catalog_products_reported = 9437
unique_products_extracted = 9437
skus_extracted = 9439
skus_with_price = 9439
skus_without_price = 0
partitions_detected = 62
partitions_completed = 62
product_requests_completed = 252
catalog_accepted = false
commercial_persistence = false
production_authority = false
extraction_enabled = false
```

La diferencia 9,439 SKU vs 9,437 `productId` es válida: 9,435 productos tienen un SKU y 2 productos tienen dos SKU. Las 9,439 identidades fuente son únicas.

## Productos y normalización — cerrado para el snapshot actual

Los PR #315 y #316 cerraron la normalización de productos/presentaciones y su integración con `RawProduct -> NormalizedOffer -> ValidatedOffer`.

```text
sku_input = 9439
source_keys_unique = 9439
presentation_normalized = 9439
presentation_pending = 0
source_values_preserved = true
versioned_overrides = true
normalization_before_state_hash = true
```

La fuente original se conserva separada de los valores normalizados. Correcciones manuales conocidas quedan ligadas a la identidad/firma fuente para no reutilizarse si el producto cambia.

## Historial comercial — verificado offline

El PR #319 verifica el motor común con el extractor/normalizador de La Colonia:

- primera observación crea current y periodo inicial;
- segunda observación idéntica confirma sin duplicar historial;
- cambio real de `current_price` cierra el periodo anterior y abre uno `price`;
- replay exacto es idempotente.

El PR #320 verifica además el ciclo backend-neutral de preparar filas, rehidratar/restaurar un proceso nuevo, continuar con un segundo run y reconciliar un replay durable exacto.

Estas pruebas **no son persistencia productiva** y no conceden `catalog_accepted`, `production_authority` ni `extraction_enabled`.

## Semántica de precio

Nombres oficiales:

```text
current_price              = precio efectivo observado que pagaría el cliente
reported_regular_price     = precio regular/tachado declarado por la tienda cuando es mayor
is_promotion               = condición promocional observada
previous_price             = derivado del histórico, nunca alias de reported_regular_price
```

No se usa una columna ambigua llamada simplemente `precio` como contrato canónico.

El ahorro real compara el `current_price` actual contra el `current_price` aceptado inmediatamente anterior. `reported_regular_price` no demuestra por sí solo ahorro real.

## Disponibilidad e inventario — siguiente frontera de datos

El artifact #15 conserva:

```text
availability_in_stock = 7081
availability_unknown = 2358
```

Los 2,358 `unknown` no pueden reclasificarse de forma fiable a partir del artifact actual porque éste no conservó `available_quantity` ni `availability_evidence` como columnas persistibles. `unknown` no se convierte en `out_of_stock` por inferencia.

Antes de confiar en inventario histórico se debe promover a campos de primera clase:

```text
available_quantity_observed
availability
availability_evidence
seller_id
```

y verificar que la cantidad corresponda al seller seleccionado. Una futura observación live requiere autorización humana nueva.

## Backend persistente seleccionado

**BigQuery es el backend persistente seleccionado desde esta etapa. Google Sheets queda fuera del camino objetivo.**

La lógica de dominio/current/history continúa backend-neutral. El código legado de Google Sheets puede permanecer temporalmente hasta que el reemplazo BigQuery esté probado, pero:

- no se utilizará para el catálogo;
- no se crearán nuevas dependencias funcionales sobre Sheets;
- los workflows/markers de Sheets deben quedar neutralizados o retirados antes de habilitar persistencia real;
- el contrato físico nuevo se diseñará para BigQuery.

Tablas objetivo mínimas:

```text
supermarkets
locations
productos
precios_historicos
inventario_historico
scrape_runs
quality_events
normalization_overrides
product_mapping
```

`locations` relaciona `location_id` con supermercado y ciudad. `productos` conserva identidad del producto y supermercado, pero no duplica ciudad. `precios_historicos` e `inventario_historico` contienen `supermarket_id`, `location_id` e identidad de producto, por lo que cada observación responde qué producto, de qué supermercado, en qué ciudad y cuándo.

`product_mapping` prepara la futura equivalencia entre fuentes, sin iniciar un segundo supermercado todavía.

## Visualización seleccionada

La capa de consumo final será **Python Dash + Plotly**. Power BI ya no es el destino del producto. El código legado de proyección Power BI no debe recibir nueva funcionalidad y podrá retirarse cuando no tenga consumidores activos.

## Frontera del producto

```text
SOURCE
-> SPS CONTEXT [DONE]
-> FULL CATALOG [DONE]
-> COMPLETENESS / TECHNICAL ACCEPTANCE [DONE]
-> PRODUCT NORMALIZATION [DONE]
-> CURRENT / HISTORY SEMANTICS [DONE OFFLINE]
-> REHYDRATE / REPLAY LIFECYCLE [DONE OFFLINE]
-> BIGQUERY CONTRACT [NEXT]
-> BIGQUERY ADAPTER + BOOTSTRAP
-> FIRST DURABLE LOAD
-> INVENTORY EVIDENCE / HISTORY
-> DAILY AUTOMATION
-> DASH + PLOTLY
-> SUPERMARKET #2
```

## Próximo paso exacto

1. definir y probar el contrato físico BigQuery con relaciones explícitas supermercado/producto/ubicación;
2. actualizar `storage_contract.py`, arquitectura y modelo para eliminar a Sheets como backend activo;
3. neutralizar el workflow de Sheets sin ejecutar ninguna escritura externa;
4. implementar el adapter BigQuery con cliente simulado y pruebas offline;
5. detenerse en la frontera real de credenciales/proyecto/dataset antes de cualquier escritura cloud que requiera acción humana;
6. después cerrar inventario de primera clase y sólo entonces preparar la ejecución diaria.
