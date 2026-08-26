# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia/historia; no conceden por sí solos autoridad comercial ni autorización live.

## Corte

Estado verificado al **2026-08-26 UTC**, con `main` en el merge de `#310` y `#311` abierto para el intento full-catalog #14:

```text
main_observed = 6287cdcfbff66a13002536c68d39c88639c0d89e
last_merged_pr = #310 — Recupera huecos de paginación en buckets SPS
active_live_pr = #311 — Permite recovery después de páginas cortas SPS
active_attempt_sequence = 14
SPS_TECHNICAL_CONTEXT = CONFIRMED
location_id = la_colonia_sps
granularity = city
technical_binding_confirmed = true
full_crawl = true
live_read_only = true
google_sheets_writes = false
commercial_persistence = false
catalog_accepted = false
production_authority = false
extraction_enabled = false
ACTIVE_AUTHORIZATION_IDS = []
```

`ACTIVE_AUTHORIZATION_IDS = []` significa que no existe un identificador opaco de autorización asignado por el usuario; no invalida la solicitud humana explícita materializada abajo. README deliberadamente no replica SHAs/runs/flags mutables.

## Autorización live vigente — catálogo completo read-only

La muestra MVP ya no es la frontera vigente. [`../.automation/la-colonia-mvp-live-request.json`](../.automation/la-colonia-mvp-live-request.json) materializa la instrucción humana explícita para obtener **todo el catálogo de La Colonia San Pedro Sula**, seguida por la continuación explícita para comenzar:

```text
authorization_mode = one_time_full_catalog_after_staged_validation
authorized_at_utc = 2026-08-25T21:13:44Z
authorization_statement = podes trabajar en obtener todo el catalogo
continued_at_utc = 2026-08-25T22:31:45Z
continuation_statement = ok comenza a trabajar
active = true
termination_condition = first_successful_downloadable_full_sps_catalog
attempt_sequence = 14
trigger_pr_number = 311
supermarket_id = la_colonia
location_id = la_colonia_sps
city = San Pedro Sula
page_size = 50
max_planned_product_requests = 400
delay_seconds = 1.5
commercial_retries_per_attempt = 0
full_crawl = true
live_read_only = true
google_sheets_writes = false
commercial_persistence = false
catalog_accepted = false
production_authority = false
extraction_enabled = false
```

Esta autorización permite continuar intentos técnicos dentro del mismo full crawl read-only hasta el primer catálogo completo descargable, mientras marker/workflow sigan cubriendo exactamente ese alcance. La evidencia histórica **no se interpreta como autorización abierta**. Cualquier tráfico fuera de este alcance **requiere autorización humana explícita vigente**. No se amplía a persistencia comercial, Sheets, cron diario, autoridad productiva ni otra fuente.

Los intentos siguen siendo finitos, secuenciales y fail-closed. Son stop conditions, entre otras, `403`, `429`, CAPTCHA/login, ciudad no verificada, host inesperado, presupuesto excedido, cambio de totals, overflow, cobertura incompleta o riesgo de carga excesiva. No se evaden controles anti-bot.

## De muestra MVP a full catalog

La autorización posterior cambió explícitamente el objetivo a catálogo completo. La ruta operativa actual es:

```text
SOURCE
-> SPS CONTEXT
-> FULL CATALOG
-> COMPLETENESS VALIDATION
-> RAW
-> NORMALIZED
-> VALIDATED
-> RUN ACCEPT/REJECT
-> CURRENT
-> HISTORY
-> GOOGLE SHEETS
-> DAILY AUTOMATION
-> POWER BI
```

Seguimos en `FULL CATALOG -> COMPLETENESS VALIDATION`. Un CSV descargable no concede por sí mismo `catalog_accepted`, `production_authority` ni permiso de persistencia.

## Estrategia full-catalog aprendida

`productSearchV3` funciona con productos/precios reales y paginación, pero una sola búsqueda VTEX deja de ser utilizable alrededor de **2,500 productos**. Tras probar categorías, frontera jerárquica, partición híbrida y marcas, la estrategia vigente usa **brand buckets**:

- `facets` sólo descubre marcas/estima buckets;
- `recordsFiltered` de `productSearchV3` es el total autoritativo raíz y por bucket;
- buckets conservadoramente bajo la ventana VTEX;
- deduplicación global por `productId` y aceptación exacta por bucket;
- `OrderByNameASC` primario y `OrderByNameDESC` sólo como recovery de bucket incompleto;
- `page_size = 50`, una solicitud a la vez, `delay_seconds = 1.5`;
- presupuesto global máximo `400` requests de producto;
- preflight del tamaño real de URL para ASC y DESC.

### Hitos importantes

```text
#298 -> primer full crawl; confirmó ventana VTEX ~2,500
#300/#301 -> categorías/frontera
#302 -> partición por marca
#306 -> partición híbrida
#307 -> brand buckets
#308 -> recordsFiltered/productSearchV3 total autoritativo
#309 -> corrige HTTP 414 con preflight de URL
#310 -> recovery de bucket incompleto en orden inverso
#311 -> deja que una página corta parseable llegue a la validación/recovery de bucket
```

## Intento #12 / PR #309

```text
run = 32913876083
artifact_id = 9587666151
result = stopped
reason = partial_or_unexpected_product_page
location_verified_same_run = true
catalog_products_reported = 9464
partitions_detected = 62
partitions_completed = 35
planned_product_requests = 215
product_requests_completed = 189
pages_attempted = 188
pages_completed = 187
skus_extracted = 8636
skus_with_price = 8636
blocked_http_status_observed = null
max_bucket_url_bytes = 3467
```

El HTTP 414 dejó de ser blocker. El run alcanzó **8,636 SKU / 187 páginas completas** y falló correctamente ante 47 productos observados frente a 48 esperados.

## Intento #13 / PR #310 — blocker observado

```text
run = 32916820363
artifact_id = 9588488404
result = stopped
reason = page_validation_failed
location_verified_same_run = true
catalog_products_reported = 9464
partitions_detected = 62
partitions_completed = 0
planned_product_requests = 215
product_requests_completed = 2
pages_attempted = 1
pages_completed = 0
skus_extracted = 49
skus_with_price = 49
short_product_pages = 1
last_expected_products_on_page = 50
last_observed_products_on_page = 49
partition_recovery_passes = 0
blocked_http_status_observed = null
```

La evidencia aisló un fallo de control, no un nuevo problema de cobertura: el extractor base marca una página 49/50 como `quality:partial_product_page` y `accepted=false`; el runner operativo abortaba inmediatamente en `_process_page()`, antes de llegar al final del bucket donde `#310` compara `unique productIds` contra `recordsFiltered` y puede ejecutar recovery DESC. No hubo 403/429 ni errores estructurales; los 49 SKU fueron parseables y tenían precio.

## PR #311 — frontera actual

`#311` corrige únicamente ese bloqueo. El extractor base conserva intacta su semántica fail-closed. El nuevo entrypoint full-catalog acepta operativamente una página rechazada **sólo** cuando se cumplen simultáneamente:

```text
quality:partial_product_page presente
structural_events == 0
errors == 0
skus_extracted > 0
skus_with_price > 0
```

Esto no acepta el bucket ni el catálogo: sólo permite contabilizar esos SKU y continuar hasta la cobertura autoritativa. Luego siguen vigentes:

```text
primary_order = OrderByNameASC
recovery_order = OrderByNameDESC
recovery_only_when_bucket_unique_product_count_mismatches = true
recovery_respects_global_request_budget = true
primary_and_recovery_url_preflight = true
duplicates_during_recovery_do_not_inflate_coverage = true
bucket_acceptance = unique productIds == bucket recordsFiltered
final_acceptance = global unique productIds == root recordsFiltered
fail_closed_after_unsuccessful_recovery = true
commercial_retries_per_attempt = 0
```

El merge de `#311` es el one-shot del intento #14. Antes de fusionar deben permanecer verdes CI/revisión, autorización/scope, pacing/budget, stop conditions y todos los flags de persistencia/autoridad en `false`.

## Binding técnico SPS

```text
location_id = la_colonia_sps
city = San Pedro Sula
location_verification_method = structural_exact_city_control
technical_binding_confirmed = true
source_location_key = request:regionid:sha256:d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
sps_region_fingerprint = d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
```

El runner vuelve a verificar SPS en el mismo run. No se persisten cookies, `regionId` raw, sesión ni headers sensibles.

## Semántica de precios

Se mantiene `current_price` y `reported_regular_price`. `reported_regular_price` es la referencia declarada por la tienda, no baseline de ahorro real. El ahorro real compara el `current_price` aceptado actual contra el `current_price` aceptado inmediatamente anterior. Sin histórico aceptado no se inventa ahorro.

## Persistencia

Google Sheets sigue con exactamente seis tabs físicos gestionados:

```text
cfg_supermarkets
cfg_locations
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

`dim_products` y `map_source_products` siguen diferidos. **Todavía no existe escritura comercial del catálogo** y permanecen:

```text
google_sheets_writes = false
commercial_persistence = false
production_authority = false
catalog_accepted = false
extraction_enabled = false
```

Tras un catálogo completo validado, reutilizar adapters/batches/rehydration existentes para el camino mínimo `evidence -> acceptance -> Raw/Normalized/Validated -> current/history -> Sheets`. No habilitar cron diario hasta demostrar aceptación, persistencia, replay y rechazo sin contaminación.

## Power BI y segunda fuente

Power BI sigue siendo el dashboard único y debe consumir la proyección semántica existente. No conectar refresh productivo sin estado comercial aceptado/durable. No iniciar supermercado #2 hasta cerrar La Colonia end-to-end.

## Próximo paso exacto

1. cerrar revisión/CI de `#311`;
2. fusionar con expected head SHA sólo si marker/workflow siguen cubriendo exactamente el full-catalog SPS read-only autorizado;
3. observar el intento live #14 hasta estado terminal;
4. inspeccionar artifact JSON/CSV y demostrar cobertura completa o aislar el blocker exacto;
5. si falla técnicamente dentro del mismo alcance, corregir únicamente la causa observada y continuar;
6. si logra catálogo completo, neutralizar el one-shot, sincronizar este documento y avanzar offline a aceptación/persistencia mínima segura sin conceder autoridad por accidente.
