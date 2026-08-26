# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia/historia; no conceden por sí solos autoridad comercial ni autorización live.

## Corte

Estado verificado al **2026-08-26 UTC**:

```text
main_observed = aca038e9f0014d62efa5a1300779b74fa039ec78
last_merged_pr = #311 — Permite recovery después de páginas cortas SPS
active_live_pr = #312 — Permite recovery ante páginas vacías SPS
active_attempt_sequence = 15
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

`ACTIVE_AUTHORIZATION_IDS = []` significa que no existe un identificador opaco de autorización asignado por el usuario; no invalida la solicitud humana explícita materializada abajo. La evidencia histórica **no se interpreta como autorización abierta** y cualquier tráfico fuera de este alcance **requiere autorización humana explícita vigente**.

## Autorización live vigente — catálogo completo read-only

[`../.automation/la-colonia-mvp-live-request.json`](../.automation/la-colonia-mvp-live-request.json) materializa la instrucción humana explícita para obtener **todo el catálogo de La Colonia San Pedro Sula**:

```text
authorization_mode = one_time_full_catalog_after_staged_validation
authorized_at_utc = 2026-08-25T21:13:44Z
authorization_statement = podes trabajar en obtener todo el catalogo
continued_at_utc = 2026-08-25T22:31:45Z
continuation_statement = ok comenza a trabajar
active = true
termination_condition = first_successful_downloadable_full_sps_catalog
attempt_sequence = 15
trigger_pr_number = 312
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

La autorización permite intentos técnicos secuenciales dentro del mismo full crawl read-only hasta el primer catálogo completo descargable. Siguen siendo stop conditions `403`, `429`, CAPTCHA/login, ciudad no verificada, host inesperado, presupuesto excedido, cambios incompatibles de totals, overflow, cobertura incompleta o riesgo de carga excesiva. No se evaden controles anti-bot.

## Frontera del producto

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
-> PYTHON DASH / PLOTLY
```

Seguimos en `FULL CATALOG -> COMPLETENESS VALIDATION`. Un CSV descargable no concede por sí mismo `catalog_accepted`, `production_authority` ni permiso de persistencia. La capa de visualización final del proyecto será **Python Dash + Plotly**, no Power BI.

## Estrategia full-catalog vigente

`productSearchV3` funciona con productos/precios reales y paginación, pero una sola búsqueda deja de ser utilizable alrededor de **2,500 productos**. La estrategia actual usa **brand buckets**:

- `facets` sólo descubre marcas y estima buckets;
- `recordsFiltered` de `productSearchV3` es total autoritativo raíz y por bucket;
- deduplicación global por `productId`;
- `OrderByNameASC` como recorrido primario;
- `OrderByNameDESC` únicamente como recovery de un bucket incompleto;
- `page_size = 50`, una solicitud a la vez y `delay_seconds = 1.5`;
- presupuesto global máximo de 400 requests de producto;
- preflight del tamaño de URL para ASC y DESC;
- aceptación de bucket sólo si `unique productIds == bucket recordsFiltered`;
- aceptación global sólo si `global unique productIds == root recordsFiltered`.

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
#311 -> páginas cortas parseables pueden llegar al recovery de bucket
#312 -> páginas vacías válidas pueden llegar al recovery sin aportar productos
```

## Intento #12 / PR #309

```text
run = 32913876083
artifact_id = 9587666151
result = stopped
reason = partial_or_unexpected_product_page
catalog_products_reported = 9464
partitions_detected = 62
partitions_completed = 35
planned_product_requests = 215
product_requests_completed = 189
pages_attempted = 188
pages_completed = 187
skus_extracted = 8636
skus_with_price = 8636
last_expected_products_on_page = 48
last_observed_products_on_page = 47
blocked_http_status_observed = null
```

## Intento #13 / PR #310

Valores corregidos directamente desde el artifact `9588488404`:

```text
run = 32916820363
artifact_id = 9588488404
result = stopped
reason = page_validation_failed
catalog_products_reported = 9437
partitions_detected = 62
partitions_completed = 0
partition_quantity_estimate_sum = 9437
partition_observed_total_sum = 1918
planned_product_requests = 215
product_requests_completed = 22
pages_attempted = 21
pages_completed = 20
skus_extracted = 1000
skus_with_price = 1000
short_product_pages = 1
last_expected_products_on_page = 50
last_observed_products_on_page = 49
partition_recovery_passes = 0
blocked_http_status_observed = null
```

El blocker era de control: el extractor rechazaba una página 49/50 antes de que el runner alcanzara la comparación de cobertura del bucket y su recovery DESC. `#311` corrigió únicamente esa frontera.

## Intento #14 / PR #311 — blocker observado

```text
run = 32917612034
result = failure
artifact = none
location authorization step = success
data acquisition step wrapper = completed with captured exit_code=1
final reflected result = failure
terminal_exception = EmptyResponseError
message = La página controlada no devolvió productos
blocked_http_status_observed = no evidence of 403/429 in logs
```

El intento avanzó durante varios minutos y encontró un nuevo caso real: `productSearchV3` mantuvo una forma válida con total positivo pero devolvió una página sin productos. `LaColoniaExtractor.parse_payload()` lanzó `EmptyResponseError` antes de que el runner pudiera completar el bucket, comparar `productId` únicos o ejecutar recovery inverso. Al ser una excepción no convertida a `FullCatalogError`, tampoco se produjo artifact JSON/CSV de fallo. No hay evidencia de CAPTCHA, login, 403 ni 429 en ese run.

## PR #312 — frontera actual / intento #15

`#312` modifica sólo el entrypoint full-catalog autorizado. Conserva el extractor base intacto y trata una página vacía como **hueco recuperable sin datos** únicamente cuando la respuesta es estructuralmente legible, `recordsFiltered > 0` y `products == []`.

La página vacía:

```text
contributes_products = false
contributes_skus = false
accepted_as_catalog_coverage = false
allows_bucket_traversal_to_continue = true
```

Después siguen siendo obligatorias todas las garantías:

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

Si recovery no recupera exactamente el total autoritativo, el bucket y el catálogo siguen rechazados.

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

Tras un catálogo completo validado, el camino mínimo será `evidence -> acceptance -> Raw/Normalized/Validated -> current/history -> Sheets`. No habilitar cron diario hasta demostrar aceptación, persistencia, replay y rechazo sin contaminación. La visualización final será una aplicación web **Python Dash + Plotly** orientada a comparación e historial de precios. No iniciar supermercado #2 hasta cerrar La Colonia end-to-end.

## Próximo paso exacto

1. cerrar CI/revisión de `#312`;
2. fusionar con expected head SHA sólo si marker/workflow siguen cubriendo exactamente el full-catalog SPS read-only autorizado;
3. observar el intento live #15 hasta estado terminal;
4. inspeccionar siempre artifact JSON/CSV cuando exista y demostrar cobertura completa o aislar el siguiente blocker exacto;
5. si falla técnicamente dentro del mismo alcance, corregir únicamente la causa observada y continuar secuencialmente;
6. si logra catálogo completo, neutralizar el one-shot y avanzar offline a aceptación/normalización/persistencia mínima segura sin conceder autoridad por accidente.
