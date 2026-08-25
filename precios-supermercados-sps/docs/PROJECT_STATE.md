# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia/historia; no conceden por sí solos autoridad comercial ni autorización live.

## Corte

Estado verificado al **2026-08-24 America/Tegucigalpa / 2026-08-25 UTC** contra el merge de `#281`:

```text
main_observed = e8afbcd129e2d3deb037fe853eab7f8fc6e00412
last_technical_pr = #282
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

**No existe autorización live activa.** La autorización humana explícita recibida a `2026-08-25T03:50:45Z` fue consumida por el run `32807247386` y no se reutiliza. No se inventa un Authorization ID porque el usuario no proporcionó uno.

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

Autorización humana explícita:

```text
authorized_at_utc = 2026-08-25T03:50:45Z
statement = si
request_sequence = 3
trigger_pr_number = 281
scope = open homepage + select/verify SPS + open catalog once + passive observation + max 1 explicit productSearchV3 + retain max 10 products
max_explicit_product_search_requests = 1
commercial_retries = 0
full_crawl = not authorized
commercial_persistence = not authorized
```

Ejecución:

```text
workflow = La Colonia - Recorrido live manual
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

El log muestra que el botón exacto de San Pedro Sula fue localizado, estaba visible/habilitado/estable y, al intentar el click, **el nodo fue reemplazado por un re-render del DOM**. Playwright continuó esperando sobre el locator hasta agotar 30 segundos. El runner bound no alcanzó `/supermercado` ni ejecutó el GET explícito autorizado, por lo que todavía no existe una muestra de productos de este intento.

La autorización queda **consumida independientemente de que el GET comercial no se alcanzara**, porque sí hubo tráfico live a La Colonia. No se reejecuta automáticamente.

## Corrección offline actual — PR #282

El fallo de `32807247386` reveló un blocker concreto en la interacción de ubicación, no en el fallback GraphQL. `#282` hace únicamente lo necesario para eliminarlo y cerrar la autorización consumida:

- retira el marker y trigger one-shot de `#281`;
- restaura el workflow live manual fail-closed;
- restaura la auditoría de workflow sin autorización activa;
- añade `probar_muestra_sps_la_colonia_resilient.py`, que reutiliza el runner bound existente;
- si el primer click termina en `TimeoutError`, primero verifica si SPS ya quedó seleccionado;
- sólo si no quedó seleccionado, re-resuelve **una vez** el mismo control exacto de San Pedro Sula y vuelve a intentar esa misma acción;
- un segundo timeout termina fail-closed;
- esta recuperación DOM no añade consultas `productSearchV3`, retries comerciales, páginas de catálogo ni persistencia;
- pruebas offline cubren selección ya aplicada, una única re-resolución, segundo timeout y errores no retryables.

El fallback comercial preparado continúa siendo el mismo: sólo después de confirmar SPS en la misma sesión, si no aparece `productSearch` pasivo y el `regionId` observado coincide exactamente con el fingerprint SPS canónico, puede realizar **como máximo un GET explícito `productSearchV3`** cuando exista una nueva autorización humana que lo cubra.

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

Después de que `#282` cierre con CI verde y sea fusionado, todo el trabajo offline inmediato para este blocker queda terminado. Para volver a tocar La Colonia se necesitará una **nueva autorización explícita**. El siguiente scope útil será el mismo objetivo de muestra, con esta precisión técnica:

```text
open homepage
select/verify San Pedro Sula
allow at most one bounded re-resolution of the same SPS city control if DOM rerenders
open /supermercado once
observe productSearch passively
if absent and same-run SPS binding fingerprint matches, allow max 1 explicit productSearchV3 GET
retain max 10 public products
commercial retries = 0
full crawl = false
Google Sheets writes = false
production_authority = false
catalog_accepted = false
```

No se pedirá full crawl ni persistencia hasta obtener primero una muestra real y revisar sus campos/precios.