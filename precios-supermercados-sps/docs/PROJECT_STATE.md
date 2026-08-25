# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia/historia; no conceden por sí solos autoridad comercial ni autorización live.

## Corte

Estado verificado al **2026-08-25 UTC** después del intento condition-bound #1 y con el intento #2 en `#290`:

```text
main_observed = 8fd30b527517399ff5d48d0f54867673ba62d46f
standing_authorization_started_at_utc = 2026-08-25T14:41:06Z
last_live_pr = #289
last_live_run = 32862196684
active_live_pr = #290
active_attempt_sequence = 2
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

No se inventa un Authorization ID porque el usuario no proporcionó uno.

La evidencia histórica puede reutilizarse offline, pero **no se interpreta como autorización abierta**. Cualquier tráfico fuera del alcance concreto descrito abajo **requiere autorización humana explícita vigente**.

## Autorización live vigente — condition-bound

Instrucción humana explícita recibida:

```text
authorized_at_utc = 2026-08-25T14:41:06Z
statement = no me estes pidiendo autorizacion trabaja hasta que podamos descargar esto
authorization_mode = condition_bound_until_first_downloadable_sample
termination_condition = first_successful_downloadable_sps_sample
```

Esta instrucción no se interpreta como autonomía live permanente ni como autorización general para nuevas fases. Su alcance operativo vigente es únicamente continuar, sin volver a pedir confirmación entre intentos, el camino mínimo necesario para obtener la **primera muestra descargable** de La Colonia San Pedro Sula bajo estas fronteras:

```text
supermarket_id = la_colonia
location_id = la_colonia_sps
city = San Pedro Sula
same_browser_context = true
sample_size <= 10
max_city_control_reresolutions_per_attempt = 1
max_explicit_product_search_requests_per_attempt = 1
commercial_retries_per_attempt = 0
full_crawl = false
google_sheets_writes = false
commercial_persistence = false
catalog_accepted = false
production_authority = false
extraction_enabled = false
```

Cada intento debe seguir siendo finito y fail-closed. La autorización se cierra cuando exista la primera muestra descargable o si aparece una frontera no cubierta: `persistent_403`, `http_429`, CAPTCHA, login obligatorio, host mismatch, riesgo de carga excesiva, credenciales/secretos nuevos, coste/billing, mutación externa o una fase distinta como full crawl/persistencia comercial.

Mientras esa condición no ocurra, un fallo técnico dentro del mismo alcance no consume por sí solo la instrucción completa; debe corregirse offline y puede ejecutarse otro intento bounded sin pedir nuevamente al usuario. Cada intento usa un marker/PR distinto.

## Objetivo MVP vigente

```text
NEXT VISIBLE MILESTONE = obtener y revisar hasta 10 productos reales de La Colonia SPS
MVP PATH = source -> SPS context -> product data -> validation -> downloadable test artifact
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

El valor raw de `regionId` no se persiste. El fingerprint sólo comprueba igualdad con el contexto SPS ya demostrado; no concede autoridad comercial. Los valores raw de cookies tampoco se persisten.

## Evidencia live MVP acumulada

```text
run 32798014154 -> SPS verificado; catálogo abierto; productSearch pasivo no observado
run 32800883695 -> SPS verificado; 9 GraphQL; 0 productSearch; artifact 9546438971
run 32807247386 -> re-render del botón SPS; 0 GET explícitos
run 32809740940 -> SPS + fingerprint regionId canónico confirmados; regionId body-only; 0 GET explícitos
run 32857812255 -> SPS + fingerprint regionId canónico confirmados; tracker de headers no demostró transición vtexsegment; 0 GET explícitos; artifact 9566896451
```

Las cinco autorizaciones one-shot anteriores están consumidas/cerradas y no se reutilizan.

### Autorización condition-bound — intento #1

```text
trigger_pr = #289
merge = 8fd30b527517399ff5d48d0f54867673ba62d46f
run = 32862196684
job = 97848677289
preflight = success
location_verified_same_run = true
graphql_responses_seen = 9
product_search_payloads_seen = 0
region_binding_fingerprint_verified = true
region_context_body_only_observed = true
region_context_replayable_placements = 0
explicit_product_search_requests = 0
blocked_http_status_observed = null
result = failure
error_code = sps_region_binding_body_only_without_segment_cookie_transition
artifact_id = 9568630621
artifact_zip_sha256 = 1bc05277eea70b3b036b016ad60c7891f19b50ea6b87782a6e41d2ffe99c047d
```

No se alcanzó el GET explícito. No hubo 403/429, CAPTCHA, login ni otra stop condition. Por ello la autorización condition-bound sigue vigente.

El análisis offline del intento #1 mostró que el snapshot del cookie jar aún dependía de que una request ocurriera antes de activar SPS. Eso podía dejar la baseline sin capturar aunque el `BrowserContext` ya tuviera `vtexsegment`.

## Corrección offline del intento #2 — PR #290

El wrapper ahora difiere la activación real del tracker hasta disponer del control exacto de San Pedro Sula y ejecuta:

```text
1. resolve exact SPS control
2. snapshot BrowserContext.cookies() while tracker is still inactive
3. persist only SHA256 fingerprint of vtexsegment as baseline
4. enable region/segment tracker
5. activate SPS with max 1 DOM re-resolution
6. verify visible San Pedro Sula
7. snapshot BrowserContext.cookies() again while tracker is active
8. proceed with passive catalog observation
9. if regionId remains body-only, allow shared-cookie fallback only when fingerprints differ
```

Esto no agrega tráfico comercial. El único `productSearchV3` explícito continúa limitado a uno por intento y sólo puede ocurrir después de verificar SPS, el fingerprint canónico de `regionId` y la transición de segmento requerida.

No se guarda ni imprime el valor raw de `vtexsegment`; sólo fingerprints efímeros. Cookies de dominios ajenos a `lacolonia.com` se ignoran.

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

## Próximo paso

`#290` debe cerrar CI/revisión y fusionarse sólo si permanece verde. Su merge materializa el intento bounded #2 bajo la misma autorización condition-bound. Si falla por otra causa técnica dentro del mismo alcance y no aparece una stop condition, se corrige offline y se continúa sin volver a pedir autorización.
