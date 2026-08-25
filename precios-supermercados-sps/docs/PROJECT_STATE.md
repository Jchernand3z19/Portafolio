# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia; no conceden por sí solos autoridad comercial ni autorización live.

## Corte

Estado verificado al **2026-08-24 America/Tegucigalpa / 2026-08-25 UTC** contra:

```text
main_observed = 11e149699f7f944446d30c13a634d7e49b06d372
last_technical_pr = #279
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

`ACTIVE_AUTHORIZATION_IDS` permanece vacío porque esta autorización MVP no recibió un ID humano explícito y no se inventan IDs. Sí existe una autorización humana explícita vigente, recibida a `2026-08-25T02:05:35Z`, materializada de forma one-shot en el PR `#279` y limitada al scope exacto descrito más abajo.

Los PRs `#254`–`#269` cerraron las fronteras offline conocidas de Fase 0: contexto SPS estructural, catálogo context-bound, materialización raw evidence-bound, storage físico simplificado, entrypoint de facets fail-closed, provenance segura para los placements soportados y reauditoría histórica reproducible.

Los PRs `#270`–`#271` materializaron una autorización humana transitoria para la observación mínima de facets y añadieron observabilidad GitHub temporal para identificar su run. La ventana terminó **sin realizar tráfico a La Colonia** porque el preflight de configuración Cloudflare falló antes de OIDC, navegador o red. El PR `#272` retiró el marker, wrapper y observador transitorios, restauró el workflow live manual fail-closed y dejó `SPS-context-and-root-facets-003` cerrada y no reutilizable.

El PR `#274` preparó un runbook productivo de Cloudflare y dejó explícito que el despliegue de infraestructura es una frontera separada de cualquier autorización live. Las deudas restantes del preflight/read-back Cloudflare pertenecen a la futura ruta edge productiva; **no bloquean automáticamente el primer catálogo de prueba**.

El PR `#275` corrigió la dirección del proyecto con una política explícita **MVP primero**. Una nueva clase, adapter, verifier, preflight, workflow, tabla, documento o runbook sólo se crea cuando elimina un blocker actual o protege una frontera que no tenga solución más simple. PRs, conteo de tests y cantidad de capas no son métricas de progreso.

El PR `#276` creó el primer camino funcional MVP: reutiliza los controles DOM y el parser existentes para seleccionar/verificar **San Pedro Sula en la misma sesión**, observar pasivamente `productSearch` durante la entrada al catálogo y conservar sólo 5/10 SKUs públicos como artifact de prueba. El job es read-only, sin Cloudflare, secrets, vars, Environment, OIDC ni persistencia comercial; los caminos de crawl general y edge continúan bloqueados.

El PR `#277` materializó una única autorización humana explícita recibida a `2026-08-25T01:20:22Z` mediante un trigger one-shot ligado al merge del propio PR. Esa autorización sí alcanzó La Colonia y quedó consumida. El run asociado verificó el preflight, abrió el sitio, seleccionó/verificó SPS y navegó al catálogo, pero no observó una respuesta que cumpliera la firma histórica estricta de `productSearch`; por ello terminó fail-closed y no produjo muestra comercial.

El PR `#278` corrigió únicamente ese blocker observado: la forma histórica `query=supermercado/category-1` sigue teniendo prioridad, pero deja de ser requisito exclusivo; entre los `productSearch` emitidos pasivamente durante la navegación al catálogo se elige el candidato más fuerte por señales públicas (`recordsFiltered`, rango solicitado y cantidad devuelta). Además, aun ante fallo se genera evidencia sanitizada con contadores no sensibles. El PR retiró el trigger y marker one-shot consumidos y devolvió el workflow a modo manual. **No añadió un request comercial explícito ni reintentos de tráfico.**

El PR `#279` materializa una **nueva** autorización humana explícita recibida a `2026-08-25T02:05:35Z` para repetir una sola vez la muestra MVP read-only con la captura pasiva robustecida de `#278`. Usa un marker distinto (`request_sequence=2`) y una identidad de merge distinta; la autorización de `#277` no se reutiliza.

La evidencia histórica puede reutilizarse offline, pero **no se interpreta como autorización abierta**. Cualquier tráfico posterior a esta segunda muestra requerirá otra autorización humana explícita si el alcance no está ya cubierto.

## Binding técnico de San Pedro Sula

La ejecución pública read-only histórica `32677568208`, sobre el merge `01804bedf7302678f096d8cef632ca3f3c407b4f`, confirmó:

```text
visible_location = San pedro sula
available_cities = [SAN PEDRO SULA, TEGUCIGALPA]
granularity_candidate = city
confidence = strong
technical_binding_observed = true
store_selection_observed = false
```

Llave canónica sanitizada:

```text
request:regionid:sha256:d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
```

Evidencia durable:

```text
run = 32677568208
artifact_id = 9503156133
artifact_name = la-colonia-location-binding-32677568208
artifact_zip_digest = sha256:39bfed10e0918ea070aa4b3755ed05317f63297ddd3ce227da3afa97d857b2c4
artifact_json = reports/discovery/la-colonia-location-binding-2026-08-24.json
artifact_canonical_sha256 = 80f2e4d333043a38954603c9c72086d241ac9b5a1cc1f10b71a9fde772588d95
```

La captura histórica deliberadamente **no preservó el placement** de `regionId` dentro del request. No se sabe todavía si el endpoint GraphQL relevante lo recibe como `header`, `query` u otra forma. El MVP evita inventar ese dato: usa el request emitido por el propio navegador después de verificar SPS y no persiste headers, cookies, session ni `regionId` raw.

## Ubicaciones

### `la_colonia_sps`

```text
city = San Pedro Sula
in_scope = true
is_available = true
granularity = city
technical_binding_confirmed = true
source_location_key = request:regionid:sha256:d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
extraction_enabled = false
```

### `la_colonia_tgu`

```text
city = Tegucigalpa
in_scope = false
granularity = unknown
technical_binding_confirmed = false
extraction_enabled = false
```

### `la_colonia_online`

Continúa siendo un **contexto fuente raw**, no una ubicación comercial. El extractor histórico produce `location_id=la_colonia_online`, `location_status=unknown`, evidencia fuente explícita y confianza nula. Nunca se reinterpreta retrospectivamente como SPS.

## Fronteras offline cerradas

### RawProduct -> SPS

El PR `#261` permite promover a `la_colonia_sps / CONFIRMED` únicamente una página con receipt de catálogo v3 firmado, binding SPS canónico, mismo run/traversal/partición, fingerprints reconciliados y `itemId` exactos contra `RawPageEvidence`. Esa es la frontera productiva avanzada; el sample MVP no la usa para declarar autoridad y mantiene todos sus flags en `false`.

### Facets context-bound

Los PRs `#263`–`#266` dejaron preparado el contrato productivo de facets. Ese camino continúa disponible, pero no bloquea el sample MVP.

### Catálogo context-bound

La cadena técnica productiva exige contexto SPS derivado por página, receipts v3, verificación criptográfica, primary + reconciliation canónicos, provenance física reconciliable y readiness del mismo plan/discovery. Esas garantías continúan diferidas hasta la etapa de hardening productivo.

## Intento live autorizado de facets — cerrado sin tráfico

Autorización histórica consumida:

```text
authorization_id = SPS-context-and-root-facets-003
authorized_at = 2026-08-24T20:46:11Z
purpose = attest actual regionId placement under SPS
requests = [root_total, category_tree]
max_requests = 2
concurrency = 1
max_retries = 0
catalog_crawl = not authorized
commercial_persistence = not authorized
```

Ejecución asociada:

```text
workflow = La Colonia - Recorrido live manual
run = 32777363742
job = 97591389839
result = failure
error_code = env_cloudflare_edge_gateway_url_invalid
artifact_id = 9538444504
artifact_digest = sha256:c87469499adba4b1fca34a109500c625ee69281f6065f2de3f87269caa4bb511
```

Ese run terminó antes de OIDC, navegador o tráfico a La Colonia. La autorización quedó cerrada y no se reutiliza.

## Primer sample MVP live — autorización consumida

Autorización humana explícita recibida en chat:

```text
authorized_at_utc = 2026-08-25T01:20:22Z
statement = si
scope = open homepage + select/verify San Pedro Sula + open /supermercado once + observe productSearch + retain max 10 public products
full_crawl = not authorized
commercial_persistence = not authorized
production_authority = false
```

Ejecución asociada:

```text
workflow = La Colonia - Recorrido live manual
run = 32798014154
job = 97653180423
merge = 2565666e1c7a059ddf30d5427a9ca60a2e7c4901
preflight = success
location/browser path = executed
live_crawl job = skipped
context_bound_facet job = skipped
result = failure
error_code = catalog_product_search_response_not_observed
artifact = none
```

El run sí consumió tráfico dentro del alcance autorizado. No hubo 403/429 reportado, no hubo bypass anti-bot y no se amplió el alcance. El runner anterior sólo escribía artifact al producir una muestra exitosa, por lo que este fallo no dejó JSON durable; los logs de Actions son la evidencia disponible. La autorización queda **consumida y cerrada** y el marker one-shot se retiró en `#278`.

## Segundo sample MVP live — autorización vigente one-shot

Nueva autorización humana explícita recibida en chat:

```text
authorized_at_utc = 2026-08-25T02:05:35Z
statement = si
request_sequence = 2
trigger_pr_number = 279
scope = open homepage + select/verify San Pedro Sula + open /supermercado once + observe productSearch passively + retain max 10 public products
full_crawl = not authorized
commercial_persistence = not authorized
retries = not authorized
production_authority = false
catalog_accepted = false
extraction_enabled = false
```

El trigger de `#279` sólo acepta el marker exacto y el merge exacto del propio PR. Hasta que ese merge ocurra no existe tráfico nuevo. Una vez se ejecute, esta autorización quedará consumida independientemente del resultado y el marker/trigger deberán retirarse en el siguiente cierre offline.

## Cloudflare — diferido para ruta productiva salvo necesidad demostrada

El repositorio contiene el Worker productivo preparado en `edge/cloudflare/`, pero no existe evidencia vigente de despliegue/conexión productiva. El PR `#274` dejó el runbook correspondiente.

Las deudas conocidas son:

```text
stale sps_context_unconfirmed blocker
authenticated deployment/read-back adapter pendiente
Worker productivo + variables la-colonia-live no configurados/demostrados
```

Estas deudas deben resolverse antes de declarar la ruta edge como productiva. No se seguirá profundizando esa ruta durante el MVP salvo que evidencia real demuestre que es indispensable.

## Google Sheets y persistencia

El workbook físico mantiene exactamente seis tabs gestionados:

```text
cfg_supermarkets
cfg_locations
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

`dim_products` y `map_source_products` permanecen como contratos lógicos diferidos. No existen ofertas comerciales reales persistidas todavía. `la_colonia_sps.extraction_enabled=false` permanece.

No se escriben ofertas SPS en current/history antes de aceptación y autoridad reales. La muestra MVP se conserva únicamente como artifact/evidencia no autoritativa.

## Reauditoría histórica de Fase 0

La reauditoría final real dentro del PR `#269` cerró con:

```text
workflow = Precios Supermercados SPS - Pruebas base
run = 32773357812
result = success
branches_total = 272
MERGED_OR_SUBSUMED = 213
CLOSED_SUPERSEDED = 59
OPEN_CURRENT = 0
UNIQUE_UNMERGED = 0
artifact_id = 9537023081
artifact_digest = sha256:a058ed4c039ed3d22fe0bff452ed18dadcbd36ce2c8104d982d89bc763c29663
```

## CI observado

Cierre fail-closed, PR `#272`:

```text
run = 32780298454
result = success
pytest = 1705 passed
pip check = clean
compileall SyntaxWarning = none
```

Runbook productivo Cloudflare, PR `#274`:

```text
run = 32783366331
result = success
pytest = 1706 passed
pip check = clean
compileall SyntaxWarning = none
```

Primera implementación de muestra MVP, PR `#276`:

```text
run = 32790812120
result = success
pytest = 1712 passed
pip check = clean
compileall SyntaxWarning = none
```

Trigger one-shot autorizado, PR `#277`:

```text
run = 32797751724
result = success
pytest = 1712 passed
pip check = clean
compileall SyntaxWarning = none
```

Captura pasiva robustecida, PR `#278`:

```text
run = 32798590198
result = success
pip check = clean
compileall SyntaxWarning = none
suite = complete
```

Merge de `#278` en `main`:

```text
run = 32799607734
result = success
pip check = clean
compileall SyntaxWarning = none
suite = complete
```

## Fronteras pendientes

```text
NEXT VISIBLE MILESTONE = obtener y revisar hasta 10 productos reales de La Colonia SPS
MVP PATH = source -> SPS context -> browser-native productSearch -> validation -> test artifact
MVP ENTRYPOINT = authorized for one one-shot retry via PR #279; not yet consumed
PRODUCTIVE EDGE DEBT = deferred unless MVP demonstrates necessity
```

El primer intento demostró que el browser path y la selección SPS llegan al sitio; el blocker concreto fue la detección demasiado estricta de la respuesta de catálogo. `#278` corrigió ese punto sin añadir requests. La nueva autorización explícita de `2026-08-25T02:05:35Z` cubre únicamente una repetición de la misma muestra read-only de hasta 10 productos mediante `#279`.

La ejecución preparada:

- usa un único BrowserContext y acciones secuenciales;
- añade una pausa mínima de 1.5 s antes de navegar al catálogo;
- no reintenta requests comerciales;
- observa pasivamente los `productSearch` generados durante la entrada al catálogo y prioriza la firma histórica si aparece;
- si hay varias respuestas candidatas, selecciona por señales públicas sin persistir variables ni URL;
- ante éxito conserva como máximo 10 SKUs públicos;
- ante fallo conserva sólo razón y contadores sanitizados;
- se detiene ante 403/429, CAPTCHA, login o navegación fuera de `www.lacolonia.com`;
- no hace full crawl;
- no escribe Google Sheets;
- no conserva request URL, headers, cookies, session, token ni `regionId` raw;
- deja `production_authority=false`, `catalog_accepted=false` y `extraction_enabled=false`.

Después de obtener el sample, el siguiente paso será revisar la evidencia y ampliar únicamente lo necesario para cubrir el catálogo y validar paginación/duplicados antes de activar persistencia real.

Mientras tanto permanecen:

```text
production_authority = false
catalog_accepted = false
extraction_enabled = false
ACTIVE_AUTHORIZATION_IDS = []
```
