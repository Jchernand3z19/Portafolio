# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia/historia; no conceden por sí solos autoridad comercial ni autorización live.

## Corte

Estado verificado al **2026-08-25 UTC** después del cierre de la quinta autorización y con el ajuste offline `#288` en revisión:

```text
main_observed = 4860c5494d7df4565f6d3fdef9518f799d5712d7
last_live_pr = #286
last_cleanup_pr = #287
offline_fix_pr = #288
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

**No existe autorización live activa.** La autorización humana explícita recibida a `2026-08-25T13:59:21Z` fue consumida por el run `32857812255` y no se reutiliza. No se inventa un Authorization ID porque el usuario no proporcionó uno.

La evidencia histórica puede reutilizarse offline, pero **no se interpreta como autorización abierta**. Cualquier tráfico posterior **requiere autorización humana explícita vigente** para su alcance concreto.

## Objetivo MVP vigente

```text
NEXT VISIBLE MILESTONE = obtener y revisar hasta 10 productos reales de La Colonia SPS
MVP PATH = source -> SPS context -> product data -> validation -> test artifact
PERSISTENCE = todavía deshabilitada
FULL CRAWL = todavía no autorizado
```

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

El valor raw de `regionId` no se persiste. El fingerprint sólo comprueba igualdad con el contexto SPS ya demostrado; no concede autoridad comercial. La radiografía histórica mostró además que `vtexsegment` cambia después de seleccionar ciudad; su valor raw tampoco se persiste.

## Evidencia live MVP acumulada

### Primer sample — autorización consumida

```text
authorized_at_utc = 2026-08-25T01:20:22Z
run = 32798014154
result = failure
SPS selection = verified
catalog navigation = executed
error_code = catalog_product_search_response_not_observed
artifact = none
```

### Segundo sample — autorización consumida

```text
authorized_at_utc = 2026-08-25T02:05:35Z
run = 32800883695
location_verified_same_run = true
graphql_responses_seen = 9
product_search_payloads_seen = 0
blocked_http_status_observed = null
artifact_id = 9546438971
artifact_zip_sha256 = 4452576636671a17a0d704b16364e43c148d59eb11da968c90f6f7638389aac1
```

### Tercer sample bound — autorización consumida

```text
authorized_at_utc = 2026-08-25T03:50:45Z
run = 32807247386
job = 97679646582
merge = e8afbcd129e2d3deb037fe853eab7f8fc6e00412
preflight = success
city_activation = failed before verification
catalog_navigation = not reached
explicit_product_search_requests = 0
result = failure
error = Playwright TimeoutError during city click after DOM detach
artifact = none
```

`#282` corrigió offline ese blocker mediante como máximo una re-resolución del mismo control de San Pedro Sula, sin añadir retries comerciales.

### Cuarto sample bound resiliente — autorización consumida

```text
authorized_at_utc = 2026-08-25T04:30:59Z
run = 32809740940
job = 97686681957
merge = b7b27c576550bb354c0014b4883307944bd21247
location_verified_same_run = true
graphql_responses_seen = 9
product_search_payloads_seen = 0
blocked_http_status_observed = null
region_binding_fingerprint_verified = true
region_context_replayable_placements = 0
region_context_body_only_observed = true
explicit_product_search_requests = 0
result = failure
error_code = sps_region_binding_observed_but_not_replayable
artifact_id = 9549381649
artifact_zip_sha256 = f3ed5bbd0d726c194d448b7bdca5a91def36f2170b834bc27d01ebd40f0556c2
```

Este run confirmó SPS y el fingerprint canónico de `regionId` en la misma sesión, pero el valor apareció únicamente dentro del body de una request observada. No se inventó un placement header/query.

### Quinto sample shared-segment — autorización consumida

Autorización humana explícita:

```text
authorized_at_utc = 2026-08-25T13:59:21Z
statement = si
request_sequence = 5
trigger_pr_number = 286
scope = SPS same BrowserContext + max 1 DOM re-resolution + passive observation + verify canonical region binding + verify vtexsegment transition if body-only + max 1 explicit productSearchV3 + retain max 10 products
max_explicit_product_search_requests = 1
commercial_retries = 0
full_crawl = not authorized
google_sheets_writes = not authorized
commercial_persistence = not authorized
```

Ejecución:

```text
workflow = La Colonia - Recorrido live manual
run = 32857812255
job = 97834000946
merge = 3428d19b6e37442d906f65390dec9933fe0e5ba6
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
raw_context_persisted = false
result = failure
error_code = sps_region_binding_body_only_without_segment_cookie_transition
artifact_id = 9566896451
artifact_name = la-colonia-sps-mvp-sample-32857812255
artifact_zip_sha256 = 6ec05ad88da14c53f9241388018dafaaffe6d3905f876e8fa131429c0a46f520
```

El artifact sanitizado confirma que San Pedro Sula quedó verificado y que el fingerprint canónico de `regionId` volvió a coincidir en la misma ejecución. El fallback se detuvo porque la observación de headers de requests no pudo demostrar una transición de `vtexsegment`. **No se emitió el GET explícito** (`explicit_product_search_requests=0`), no hubo 403/429, no se ejecutó full crawl y no se escribió en Google Sheets.

La autorización de `2026-08-25T13:59:21Z` queda consumida y cerrada porque sí hubo tráfico live.

## Corrección offline actual — PR #288

El análisis del quinto run mostró que el problema no es el binding SPS, sino la forma de observar la cookie. `#288` mantiene el mismo enfoque fail-closed pero usa como señal primaria el cookie jar real del `BrowserContext` asociado a cada request:

```text
before SPS activation:
  observe latest vtexsegment fingerprint while tracker inactive

after tracker activation:
  observe vtexsegment fingerprints from request.frame.page.context.cookies()

body-only fallback requires:
  canonical SPS region fingerprint verified = true
  preselection vtexsegment baseline exists = true
  at least one active vtexsegment fingerprint differs from baseline = true
```

Sólo se conservan SHA256 efímeros en memoria. El valor raw de `vtexsegment` no se guarda, no se imprime y no aparece en artifacts. Cookies con dominio ajeno a `lacolonia.com` se ignoran. Si no existe baseline previa o el fingerprint no cambia, el runner continúa deteniéndose con `sps_region_binding_body_only_without_segment_cookie_transition`.

La señal histórica basada en header `Cookie` se conserva como evidencia secundaria compatible, pero ya no es la única forma de observar la sesión. Un placement explícito de `regionId` previamente demostrado en header/query sigue teniendo prioridad y no necesita este fallback.

Este PR es **offline**: no ejecuta navegación a La Colonia ni concede autoridad para hacerla.

## Fuente de productos conocida

```text
https://www.lacolonia.com/_v/segment/graphql/v1
operation = productSearchV3
```

El constructor solicita `hideUnavailableItems=false`, `skusFilter=ALL` y los campos necesarios para IDs, nombre, marca, categorías, presentación, imagen, precio actual, precio regular informado, seller, unidad, multiplicador y cantidad publicada.

Una muestra histórica sin binding SPS produjo 10 productos/10 SKU con precio y confirma la forma del parser, pero no se reetiqueta como SPS.

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

No existen ofertas SPS reales persistidas todavía. Permanecen:

```text
production_authority = false
catalog_accepted = false
extraction_enabled = false
commercial_persistence = false
ACTIVE_AUTHORIZATION_IDS = []
```

## Próxima frontera humana

Primero `#288` debe cerrar CI/revisión y quedar fusionado. Después, si el ajuste permanece verde, el siguiente paso que puede producir información nueva vuelve a requerir tráfico live y por tanto una **nueva autorización humana explícita**. La autorización de `2026-08-25T13:59:21Z` no se reutiliza.
