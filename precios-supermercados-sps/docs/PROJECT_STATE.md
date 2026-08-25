# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia/historia; no conceden por sí solos autoridad comercial ni autorización live.

## Corte

Estado verificado al **2026-08-24 America/Tegucigalpa / 2026-08-25 UTC** después del run live de `#283`:

```text
main_observed = b7b27c576550bb354c0014b4883307944bd21247
last_live_pr = #283
PHASE0_OFFLINE = CLOSED
SPS_TECHNICAL_CONTEXT = CONFIRMED
location_id = la_colonia_sps
granularity = city
technical_binding_confirmed = true
extraction_enabled = false
production_authority = false
catalog_accepted = false
ACTIVE_AUTHORIZATION_IDS = []
```

**No existe autorización live activa.** La autorización humana explícita recibida a `2026-08-25T04:30:59Z` fue consumida por el run `32809740940` y no se reutiliza. No se inventa un Authorization ID porque el usuario no proporcionó uno.

La evidencia histórica puede reutilizarse offline, pero **no se interpreta como autorización abierta**. Cualquier tráfico posterior requiere autorización humana explícita vigente para su alcance concreto.

## Objetivo MVP vigente

```text
NEXT VISIBLE MILESTONE = obtener y revisar hasta 10 productos reales de La Colonia SPS
MVP PATH = source -> SPS context -> product data -> validation -> test artifact
PERSISTENCE = todavía deshabilitada
FULL CRAWL = todavía no autorizado
```

El camino productivo/edge, Cloudflare, receipts y hardening adicional permanecen diferidos mientras no sean necesarios para producir y validar el primer catálogo real.

## Binding técnico SPS confirmado

La evidencia durable `reports/discovery/la-colonia-location-binding-2026-08-24.json` confirmó ciudad y binding técnico fuerte:

```text
run = 32677568208
visible_location = San pedro sula
available_cities = [SAN PEDRO SULA, TEGUCIGALPA]
granularity_candidate = city
confidence = strong
technical_binding_observed = true
store_selection_observed = false
source_location_key = request:regionid:sha256:d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
```

El valor raw de `regionId` no se persiste. El fingerprint sólo permite comprobar igualdad con el contexto SPS ya demostrado; no concede autoridad comercial.

## Evidencia live MVP acumulada

### Primer sample — autorización consumida

```text
authorized_at_utc = 2026-08-25T01:20:22Z
run = 32798014154
job = 97653180423
result = failure
SPS selection = verified
catalog navigation = executed
error_code = catalog_product_search_response_not_observed
artifact = none
```

La entrada al catálogo no produjo una respuesta que cumpliera la firma histórica estricta de `productSearch`.

### Segundo sample — autorización consumida

```text
authorized_at_utc = 2026-08-25T02:05:35Z
run = 32800883695
job = 97661305983
merge = 73513c4eda9abe0d88e7923ed331508a4cf0a40c
result = failure
location_verified_same_run = true
graphql_responses_seen = 9
product_search_payloads_seen = 0
catalog_candidates_seen = 0
blocked_http_status_observed = null
artifact_id = 9546438971
artifact_zip_sha256 = 4452576636671a17a0d704b16364e43c148d59eb11da968c90f6f7638389aac1
```

Esta ejecución demostró que esperar más por el `productSearch` pasivo no es un camino suficiente: hubo actividad GraphQL real pero ninguna respuesta `data.productSearch`.

### Tercer sample bound — autorización consumida

```text
authorized_at_utc = 2026-08-25T03:50:45Z
run = 32807247386
job = 97679646582
merge = e8afbcd129e2d3deb037fe853eab7f8fc6e00412
preflight = success
home_navigation = executed
city_control = resolved
city_activation = failed before verification
catalog_navigation = not reached
explicit_product_search_requests = 0
live_crawl job = skipped
context_bound_facet job = skipped
result = failure
error = Playwright TimeoutError during city click after DOM detach
artifact = none
```

El botón exacto de San Pedro Sula fue reemplazado por un re-render mientras Playwright intentaba hacer click. `#282` corrigió offline ese blocker mediante como máximo una re-resolución del mismo control, sin añadir retries comerciales.

### Cuarto sample bound resiliente — autorización consumida

Autorización humana explícita:

```text
authorized_at_utc = 2026-08-25T04:30:59Z
statement = si
request_sequence = 4
trigger_pr_number = 283
scope = open homepage + select/verify SPS + max 1 DOM re-resolution + open catalog once + passive observation + max 1 explicit productSearchV3 + retain max 10 products
max_city_control_reresolutions = 1
max_explicit_product_search_requests = 1
commercial_retries = 0
full_crawl = not authorized
commercial_persistence = not authorized
```

Ejecución:

```text
workflow = La Colonia - Recorrido live manual
run = 32809740940
job = 97686681957
merge = b7b27c576550bb354c0014b4883307944bd21247
preflight = success
location_verified_same_run = true
graphql_responses_seen = 9
product_search_payloads_seen = 0
catalog_candidates_seen = 0
blocked_http_status_observed = null
region_binding_fingerprint_verified = true
region_context_replayable_placements = 0
region_context_body_only_observed = true
explicit_product_search_requests = 0
live_crawl job = skipped
context_bound_facet job = skipped
result = failure
error_code = sps_region_binding_observed_but_not_replayable
artifact_id = 9549381649
artifact_name = la-colonia-sps-mvp-sample-32809740940
artifact_zip_sha256 = f3ed5bbd0d726c194d448b7bdca5a91def36f2170b834bc27d01ebd40f0556c2
```

Este run cerró dos dudas importantes sin ampliar tráfico: **San Pedro Sula sí quedó verificado en la misma sesión** y el valor efímero de `regionId` observado después de seleccionar SPS **sí coincidió exactamente con el fingerprint canónico**. Sin embargo, la coincidencia apareció únicamente dentro del body de una request observada; no apareció en header ni query, por lo que el runner actual se negó correctamente a inventar un placement para el GET de `productSearchV3`.

No se emitió el GET explícito autorizado (`explicit_product_search_requests=0`), no hubo 403/429 y no se persistió URL, header, cookie, sesión, token ni `regionId` raw. La autorización queda **consumida y cerrada** porque sí hubo tráfico live al supermercado.

## Blocker actual

```text
CURRENT BLOCKER = SPS regionId exact match is body-only in same-run traffic
KNOWN SAFE FACTS = location verified + canonical fingerprint match + no passive productSearch
UNKNOWN = how the source expects the same SPS region context to be carried into the explicit productSearchV3 request
```

El siguiente trabajo debe ser offline primero. No se debe convertir un valor observado en body a header/query por intuición. La alternativa mínima es reutilizar evidencia y código existentes para modelar un replay body-bound sólo si puede demostrarse una transformación exacta y no ambigua hacia la operación pública de búsqueda; de lo contrario debe prepararse una captura sanitizada adicional que revele únicamente el **placement/shape**, nunca el valor raw.

## Fuente de productos conocida

La radiografía técnica histórica confirmó el endpoint público VTEX:

```text
https://www.lacolonia.com/_v/segment/graphql/v1
operation = productSearchV3
```

El constructor existente solicita `hideUnavailableItems=false`, `skusFilter=ALL`, página acotada y los campos necesarios para IDs, nombre, marca, categorías, presentación, imagen, precio actual, precio regular informado, seller, unidad, multiplicador y cantidad publicada.

Una muestra histórica sin binding SPS produjo 10 productos/10 SKU con precio y confirmó la forma del parser. Esa evidencia sirve offline, pero no se reetiqueta como SPS.

## Persistencia

El workbook físico mantiene exactamente seis tabs gestionados:

```text
cfg_supermarkets
cfg_locations
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

No existen ofertas SPS reales persistidas todavía. `current/history` no cambian con muestras fallidas o no aceptadas. Permanecen:

```text
production_authority = false
catalog_accepted = false
extraction_enabled = false
commercial_persistence = false
ACTIVE_AUTHORIZATION_IDS = []
```

## Próxima frontera humana

Antes de pedir otra autorización live debe agotarse el análisis offline del placement body-only observado en `32809740940` y preparar el cambio mínimo correspondiente con tests fail-closed.

Si después de ese trabajo todavía hace falta tráfico nuevo, se solicitará una autorización nueva y específica. La autorización de `2026-08-25T04:30:59Z` no se reutiliza.
