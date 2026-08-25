# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia/historia; no conceden por sí solos autoridad comercial ni autorización live.

## Corte

Estado verificado al **2026-08-25 UTC** después del merge de `#288` y con una nueva instrucción humana explícita vigente recibida a `2026-08-25T14:41:06Z`:

```text
main_observed = d56b93cc53b0300bc6c49f2cdd33f774147af5e1
last_live_pr = #286
last_cleanup_pr = #287
last_offline_fix_pr = #288
active_live_pr = #289
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

Mientras esa condición no ocurra, un fallo técnico dentro del mismo alcance no consume por sí solo la instrucción completa; debe corregirse offline y puede ejecutarse otro intento bounded sin pedir nuevamente al usuario. Los markers de intentos anteriores siguen siendo evidencia histórica y no se reutilizan.

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

El valor raw de `regionId` no se persiste. El fingerprint sólo comprueba igualdad con el contexto SPS ya demostrado; no concede autoridad comercial. La radiografía histórica mostró además que `vtexsegment` cambia después de seleccionar ciudad; su valor raw tampoco se persiste.

## Evidencia live MVP acumulada

```text
run 32798014154 -> SPS verificado; catálogo abierto; productSearch pasivo no observado
run 32800883695 -> SPS verificado; 9 GraphQL; 0 productSearch; artifact 9546438971
run 32807247386 -> re-render del botón SPS; 0 GET explícitos
run 32809740940 -> SPS + fingerprint regionId canónico confirmados; regionId body-only; 0 GET explícitos
run 32857812255 -> SPS + fingerprint regionId canónico confirmados; tracker de headers no demostró transición vtexsegment; 0 GET explícitos; artifact 9566896451
```

Las cinco autorizaciones anteriores están consumidas/cerradas y no se reutilizan. La autorización vigente es exclusivamente la instrucción condition-bound de `2026-08-25T14:41:06Z`.

## Corrección offline ya fusionada — PR #288

`#288` está fusionado en `main` como:

```text
d56b93cc53b0300bc6c49f2cdd33f774147af5e1
```

El wrapper resiliente usa el cookie jar real del `BrowserContext` como señal primaria para `vtexsegment`:

```text
before SPS activation:
  conservar sólo fingerprint efímero de vtexsegment

after SPS activation:
  observar fingerprints desde request.frame.page.context.cookies()

body-only fallback requires:
  canonical SPS region fingerprint verified = true
  preselection vtexsegment baseline exists = true
  at least one active vtexsegment fingerprint differs from baseline = true
```

No se guarda ni imprime el valor raw de `vtexsegment`. Cookies de dominios ajenos a `lacolonia.com` se ignoran. Un placement explícito de `regionId` demostrado en header/query sigue teniendo prioridad.

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

`#289` debe validar CI y revisión, fusionarse sólo si permanece verde y ejecutar el primer intento bajo la autorización condition-bound vigente. Si falla por una causa técnica dentro del mismo alcance, se corrige offline y se continúa con otro intento bounded. No se vuelve a pedir autorización mientras siga vigente esta condición y no aparezca una frontera de seguridad fuera del alcance.
