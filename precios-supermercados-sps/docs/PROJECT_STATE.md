# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia/historia; no conceden por sí solos autoridad comercial ni autorización live.

## Corte

Estado verificado al **2026-08-26 UTC**:

```text
main_observed = 589b694fdc75fd97d47fcc5259062fb026cf7ee4
last_merged_pr = #312 — Permite recovery ante páginas vacías SPS
active_live_pr = none
active_attempt_sequence = none
last_successful_full_catalog_attempt = 15
SPS_TECHNICAL_CONTEXT = CONFIRMED
location_id = la_colonia_sps
granularity = city
technical_binding_confirmed = true
full_catalog_validation_passed = true
full_crawl = true
live_read_only = true
google_sheets_writes = false
commercial_persistence = false
catalog_accepted = false
production_authority = false
extraction_enabled = false
ACTIVE_AUTHORIZATION_IDS = []
```

`ACTIVE_AUTHORIZATION_IDS = []` significa que no existe un identificador opaco de autorización asignado por el usuario. La evidencia histórica **no se interpreta como autorización abierta** y cualquier nuevo tráfico fuera de un alcance explícitamente autorizado **requiere autorización humana explícita vigente**.

## One-shot full catalog — consumido

La autorización humana explícita para obtener el catálogo completo read-only de La Colonia San Pedro Sula cumplió su condición de terminación en el intento #15:

```text
authorization_mode = one_time_full_catalog_after_staged_validation
authorized_at_utc = 2026-08-25T21:13:44Z
authorization_statement = podes trabajar en obtener todo el catalogo
continued_at_utc = 2026-08-25T22:31:45Z
continuation_statement = ok comenza a trabajar
active = false
termination_condition = first_successful_downloadable_full_sps_catalog
termination_condition_met = true
attempt_sequence = 15
trigger_pr_number = 312
```

El marker queda inactivo y el workflow deja de escuchar `push` del marker. El workflow manual conserva únicamente la muestra MVP read-only explícitamente autorizada por input; `live-crawl` y el entrypoint context-bound de facets siguen deshabilitados. No existe un segundo full crawl automático pendiente.

## Primer catálogo completo descargable — intento #15

```text
run_id = 32922877781
run_number = 60
merge_sha = 589b694fdc75fd97d47fcc5259062fb026cf7ee4
artifact_id = 9590684834
artifact_name = la-colonia-sps-data-32922877781
artifact_sha256 = 0427e88be27df89fd9fcb50ed600ef5c6aef64177bfba92b4af3d2e25756a892
artifact_expires_at = 2026-09-09T02:40:58Z
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
partition_quantity_estimate_sum = 9437
partition_observed_total_sum = 9437
planned_product_requests = 215
product_requests_completed = 252
partition_recovery_passes = 2
recovery_pages_completed = 37
partition_products_recovered = 3
recovery_duplicate_skus_ignored = 1844
short_product_pages = 3
oversized_product_pages = 0
duplicate_skus_across_partitions = 0
catalog_accepted = false
commercial_persistence = false
production_authority = false
extraction_enabled = false
raw_context_persisted = false
```

La diferencia `9,439 SKU` vs `9,437 productId` es válida: 9,435 productos tienen un SKU y 2 productos tienen dos SKU. Las 9,439 identidades `source_key` son únicas.

Validación adicional del artifact descargado:

```text
full-catalog.json sha256 = 2780eeffa5ef62f2d1c8c2c8365e88da1ca0006622d2f7b1c3529f834c9b5e50
full-catalog.csv sha256  = d73815eb6b704dd1c453d33bf3bde649a3a42d1c7c476f370726c2b806423552
csv_rows = 9439
csv_unique_source_keys = 9439
csv_unique_product_ids = 9437
current_price_present = 9439
current_price_positive = 9439
promotion_rows = 780
promotion_rows_with_reported_regular_price = 780
promotion_rows_regular_price_gt_current_price = 780
```

La extracción completa ya está demostrada. `catalog_accepted=false` permanece intencionalmente: **completitud técnica del catálogo no equivale todavía a aceptación comercial/persistible**.

## Calidad observada que debe resolver la siguiente fase

Antes de aceptar el run para `CURRENT/HISTORY`, la capa offline debe formalizar reglas para datos que no comprometen la completitud pero sí la semántica:

```text
presentation_missing = 763 / 9439
availability_in_stock = 7081 / 9439
availability_unknown = 2358 / 9439
```

No se deben inventar presentaciones ni disponibilidad. La aceptación debe decidir explícitamente qué campos son obligatorios, cuáles pueden ser `unknown`, cómo registrar quality events y qué condiciones rechazan el run completo frente a una fila individual.

## Frontera del producto

```text
SOURCE
-> SPS CONTEXT
-> FULL CATALOG [DONE]
-> COMPLETENESS VALIDATION [DONE]
-> RAW
-> NORMALIZED
-> VALIDATED
-> RUN ACCEPT/REJECT
-> CURRENT
-> HISTORY
-> GOOGLE SHEETS
-> DAILY AUTOMATION
-> PYTHON DASH / PLOTLY
```

La siguiente frontera es **offline**: `RAW -> NORMALIZED -> VALIDATED -> RUN ACCEPT/REJECT`. No requiere ni autoriza un nuevo crawl.

## Estrategia full-catalog demostrada

`productSearchV3` funciona con productos/precios reales y paginación, pero una sola búsqueda deja de ser utilizable alrededor de 2,500 productos. La estrategia demostrada usa brand buckets con:

- `recordsFiltered` autoritativo raíz y por bucket;
- deduplicación global por `productId`;
- `OrderByNameASC` primario;
- `OrderByNameDESC` sólo como recovery de bucket incompleto;
- `page_size = 50`, una solicitud a la vez y `delay_seconds = 1.5`;
- máximo 400 requests de producto;
- preflight de URL ASC/DESC;
- aceptación exacta por bucket y cobertura global exacta.

### Hitos

```text
#298 -> primer full crawl; confirmó ventana VTEX ~2,500
#300/#301 -> categorías/frontera
#302 -> partición por marca
#306 -> partición híbrida
#307 -> brand buckets
#308 -> recordsFiltered/productSearchV3 autoritativo
#309 -> corrige HTTP 414 con preflight de URL
#310 -> recovery de bucket incompleto en orden inverso
#311 -> páginas cortas parseables pueden llegar al recovery
#312 -> páginas vacías válidas pueden llegar al recovery sin aportar productos
attempt #15 -> primer catálogo completo validado y descargable
```

## Intentos recientes previos

```text
#12 run 32913876083 / artifact 9587666151
result = stopped
reason = partial_or_unexpected_product_page
catalog_products_reported = 9464
partitions_completed = 35 / 62
skus_with_price = 8636

#13 run 32916820363 / artifact 9588488404
result = stopped
reason = page_validation_failed
catalog_products_reported = 9437
product_requests_completed = 22
pages_completed = 20
skus_with_price = 1000
last_expected_products_on_page = 50
last_observed_products_on_page = 49

#14 run 32917612034
result = failure
artifact = none
terminal_exception = EmptyResponseError
message = La página controlada no devolvió productos
```

Los totales del catálogo pueden cambiar entre runs; toda aceptación de completitud usa el `recordsFiltered` raíz observado en el **mismo run**.

## Binding técnico SPS

```text
location_id = la_colonia_sps
city = San Pedro Sula
location_verification_method = structural_exact_city_control
technical_binding_confirmed = true
source_location_key = request:regionid:sha256:d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
sps_region_fingerprint = d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
```

No se persisten cookies, `regionId` raw, sesión ni headers sensibles.

## Semántica de precios

Se mantiene `current_price` y `reported_regular_price`. `reported_regular_price` es la referencia declarada por la tienda, no baseline de ahorro real. El ahorro real comparará el `current_price` aceptado actual contra el `current_price` aceptado inmediatamente anterior. Sin histórico aceptado no se inventa ahorro.

## Persistencia y visualización

Google Sheets sigue con seis tabs físicos gestionados:

```text
cfg_supermarkets
cfg_locations
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

`dim_products` y `map_source_products` siguen diferidos. Todavía no existe escritura comercial del catálogo:

```text
google_sheets_writes = false
commercial_persistence = false
production_authority = false
catalog_accepted = false
extraction_enabled = false
```

No habilitar cron diario hasta demostrar aceptación, persistencia, replay y rechazo sin contaminación. La visualización final será una aplicación web **Python Dash + Plotly** orientada a comparación e historial de precios. No iniciar supermercado #2 hasta cerrar La Colonia end-to-end.

## Próximo paso exacto

1. cerrar CI/revisión del PR de neutralización one-shot y fusionarlo sólo si está verde;
2. sin nuevo tráfico live, usar el artifact exitoso #15 como fixture/evidencia para formalizar aceptación offline;
3. implementar `Raw -> Normalized -> Validated -> Run Accept/Reject` con quality events explícitos;
4. probar replay determinista y rechazo sin contaminación;
5. sólo después diseñar/habilitar el camino mínimo hacia `CURRENT/HISTORY` y Google Sheets, sin conceder autoridad productiva accidentalmente.
