# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia/historia; no conceden por sí solos autoridad comercial ni autorización live.

## Corte

Estado verificado al **2026-08-26 UTC**:

```text
main_observed = b484edf02e1aee0bfa816a41e32884219a275c00
last_merged_pr = #313 — Cierra one-shot del catálogo completo SPS
active_offline_pr = #314 — Formaliza aceptación técnica offline del catálogo SPS
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

El marker queda inactivo. El workflow conserva el `push` del marker únicamente como verificación fail-closed del estado **consumido**: ese camino produce `capture_mode=consumed_no_network` y no ejecuta ningún request comercial ni full crawl. El workflow manual conserva sólo la muestra MVP read-only explícitamente autorizada por input; `live-crawl` y el entrypoint context-bound de facets siguen deshabilitados. No existe un segundo full crawl automático pendiente.

El cierre quedó verificado después del merge de `#313`:

```text
closure_merge_sha = b484edf02e1aee0bfa816a41e32884219a275c00
closure_verification_run = 32926533667
capture_mode = consumed_no_network
commercial_requests_executed = 0
full_catalog_executed = false
artifact_uploaded = false
live_crawl_job = skipped
context_bound_facet_job = skipped
```

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

## Calidad observada y semántica de disponibilidad

El artifact #15 contiene:

```text
presentation_missing = 763 / 9439
availability_in_stock = 7081 / 9439
availability_unknown = 2358 / 9439
current_price_positive = 9439 / 9439
```

La implementación fuente distingue internamente `price_positive_quantity_positive`, `price_positive_quantity_zero`, `price_absent_quantity_zero` e `insufficient_evidence`, pero el artifact sanitizado #15 no conservó `availability_evidence` ni `available_quantity`. Por tanto, los 2,358 `unknown` **no pueden reclasificarse de forma fiable offline a partir de ese artifact**.

La vista pública sin binding SPS tampoco se usa como autoridad de disponibilidad: durante la revisión apareció al menos un SKU que el run SPS marcó `in_stock` mientras una vista pública lo presentaba como agotado. Esto demuestra que contexto/caché puede diferir. La regla actual es fail-closed:

```text
unknown_is_not_out_of_stock_by_inference = true
unknown_is_quality_warning = true
presentation_missing_is_quality_warning = true
public_unbound_page_can_relabel_sps = false
```

No se inventan presentaciones ni disponibilidad. Una futura captura autorizada debe conservar evidencia sanitizada suficiente para explicar cada estado sin persistir cookies, `regionId`, sesión, headers ni request URLs sensibles.

## Aceptación técnica offline — PR #314

La nueva capa `la_colonia_operational_artifact.py` evalúa artifacts ya descargados y no hace red. Separa blockers de warnings:

```text
blockers = cobertura/contexto/identidad/precio/contadores/flags de autoridad inconsistentes
warnings = presentación faltante / availability unknown / promoción sin regular comparable
technical_catalog_complete = blockers == []
ready_for_normalization = technical_catalog_complete
catalog_accepted = false
production_authority = false
```

El CLI `scripts/evaluar_catalogo_sps_la_colonia_offline.py` sólo lee un JSON local y devuelve el assessment sanitizado. Esta capa no muta `CURRENT/HISTORY`, no escribe Sheets y no convierte evidencia técnica en autoridad productiva.

## Frontera del producto

```text
SOURCE
-> SPS CONTEXT
-> FULL CATALOG [DONE]
-> COMPLETENESS VALIDATION [DONE]
-> TECHNICAL ARTIFACT ASSESSMENT [IN PROGRESS]
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

La frontera actual es **offline**. No requiere ni autoriza un nuevo crawl.

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
#313 -> one-shot consumido y verificado sin tráfico
#314 -> aceptación técnica offline del artifact
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

1. cerrar CI/revisión de `#314` y validar el assessment contra el artifact real #15;
2. conservar en futuras evidencias sanitizadas `availability_evidence`/cantidad observable suficiente, sin persistir contexto sensible;
3. diseñar el bridge seguro desde artifact sanitizado a la capa común `Normalized/Validated` sin inventar `source_url` ni disponibilidad;
4. formalizar `RunStatus` y quality events que alimentarán `fact_scrape_runs`/`fact_quality_events`;
5. probar `CURRENT/HISTORY` y replay completamente offline antes de cualquier persistencia real.
