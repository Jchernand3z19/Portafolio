# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia/historia; no conceden por sí solos autoridad comercial ni autorización live.

## Corte

Estado verificado al **2026-08-26 UTC**, con `main` en el merge de `#309` y `#310` abierto para el intento full-catalog #13:

```text
main_observed = ba1c8e9c8d8af3a96965497930fcb8e627247a9b
last_merged_pr = #309 — Evita URLs excesivas en buckets SPS
active_live_pr = #310 — Recupera huecos de paginación en buckets SPS
active_attempt_sequence = 13
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
```

El README deliberadamente no replica SHAs/runs/flags mutables. Si este documento vuelve a quedar detrás de una frontera funcional importante, debe sincronizarse dentro de esa misma frontera cuando sea razonable.

## Autorización live vigente — catálogo completo read-only

La muestra MVP ya no es la frontera vigente. Existe una instrucción humana explícita materializada en [`../.automation/la-colonia-mvp-live-request.json`](../.automation/la-colonia-mvp-live-request.json) para obtener **todo el catálogo de La Colonia San Pedro Sula**, seguida por una continuación explícita para comenzar el trabajo:

```text
authorization_mode = one_time_full_catalog_after_staged_validation
authorized_at_utc = 2026-08-25T21:13:44Z
authorization_statement = podes trabajar en obtener todo el catalogo
continued_at_utc = 2026-08-25T22:31:45Z
continuation_statement = ok comenza a trabajar
active = true
termination_condition = first_successful_downloadable_full_sps_catalog
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

Esta autorización permite continuar los intentos técnicos necesarios dentro del mismo full crawl read-only hasta el primer catálogo completo descargable, siempre que el marker/workflow vigente siga cubriendo exactamente ese alcance. No se amplía a persistencia comercial, Sheets, cron diario, autoridad productiva ni otra fuente.

Los intentos siguen siendo finitos, secuenciales y fail-closed. Son stop conditions, entre otras, `403`, `429`, CAPTCHA/login, ciudad no verificada, host inesperado, presupuesto excedido, cambio de totals, overflow, cobertura incompleta o riesgo de carga excesiva. No se evaden controles anti-bot.

## De muestra MVP a full catalog

La frontera de muestra fue superada y la autorización posterior cambió explícitamente el objetivo a catálogo completo. La ruta operativa actual es:

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

Todavía estamos en `FULL CATALOG -> COMPLETENESS VALIDATION`. Un CSV descargable no concede por sí mismo `catalog_accepted`, `production_authority` ni permiso de persistencia.

## Estrategia full-catalog aprendida

La evidencia live demostró que `productSearchV3` funciona con productos/precios reales y paginación, pero una única ventana de búsqueda VTEX deja de ser utilizable alrededor de **2,500 productos**. Por eso se probaron progresivamente categorías, frontera jerárquica, partición híbrida y marcas.

La estrategia vigente usa **brand buckets**:

- `facets` se usa para descubrir marcas y estimar cómo empacarlas;
- los buckets se mantienen conservadoramente por debajo de la ventana VTEX;
- `recordsFiltered` de `productSearchV3` es el total autoritativo del catálogo raíz y de cada bucket;
- los `productId` se deduplican globalmente y cada bucket exige cobertura exacta;
- `page_size = 50`, una solicitud a la vez y `delay_seconds = 1.5`;
- presupuesto global máximo: `400` requests de producto;
- ambos órdenes de consulta se validan contra el límite real codificado de URL antes de enviar tráfico.

### Hitos de los intentos de full catalog

```text
#298 -> primer full crawl; confirmó la ventana VTEX al cruzar ~2,500 productos
#300/#301 -> partición y frontera por categorías
#302 -> partición por marca
#306 -> partición híbrida
#307 -> brand buckets para reducir cientos de marcas a pocos recorridos
#308 -> productSearchV3/recordsFiltered pasa a ser total autoritativo por bucket
#309 -> preflight por bytes corrige el HTTP 414 de URLs demasiado largas
#310 -> recovery de bucket incompleto con orden inverso
```

No se considera ninguna de estas estrategias aceptada por mera intención: gobierna la evidencia del último run.

## Último intento observado — #12 / PR #309

Workflow:

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

El HTTP 414 ya no fue el blocker. El run llegó a **8,636 SKU / 187 páginas completadas** y se detuvo correctamente porque una página final devolvió **47 productos cuando `recordsFiltered` implicaba 48**. No hubo 403/429 observado y no se aceptó silenciosamente la cardinalidad incorrecta.

## PR #310 — frontera actual

`#310` mantiene `OrderByNameASC` como pase principal. Si al terminar un bucket los `productId` únicos no igualan su `recordsFiltered`, hace recovery **sólo en ese bucket** con `OrderByNameDESC`.

Contratos del cambio:

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
```

El merge de `#310` no es rutinario: el workflow reconoce exactamente ese merge como el intento live #13. Antes del merge deben permanecer verdes CI/revisión, autorización/scope, pacing/budget, stop conditions, `google_sheets_writes=false`, `commercial_persistence=false`, `catalog_accepted=false`, `production_authority=false` y `extraction_enabled=false`.

## Binding técnico SPS

La evidencia durable de ubicación confirmó que el contexto seleccionado es San Pedro Sula y el runner operativo vuelve a verificar la ciudad en el mismo run mediante el control estructural aprendido. No se persisten cookies, `regionId` raw, sesiones ni headers sensibles.

```text
location_id = la_colonia_sps
city = San Pedro Sula
location_verification_method = structural_exact_city_control
technical_binding_confirmed = true
```

## Semántica de precios

Se mantiene:

```text
current_price
reported_regular_price
```

`reported_regular_price` es la referencia declarada por la tienda; no es baseline de ahorro real. El ahorro real compara el `current_price` del estado aceptado actual contra el `current_price` del periodo aceptado inmediatamente anterior. Sin histórico aceptado no se inventa ahorro.

## Persistencia

Google Sheets sigue siendo el backend físico temporal con exactamente seis tabs gestionados:

```text
cfg_supermarkets
cfg_locations
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

`dim_products` y `map_source_products` siguen siendo contratos lógicos diferidos mientras exista una sola fuente y no haya un consumidor real que los requiera.

**Todavía no existe escritura comercial de este catálogo a Google Sheets.** Permanecen:

```text
google_sheets_writes = false
commercial_persistence = false
production_authority = false
catalog_accepted = false
extraction_enabled = false
```

Cuando exista un catálogo completo validado, la siguiente frontera debe reutilizar los adapters/batches/rehydration ya existentes y recorrer el camino mínimo seguro `evidence -> acceptance -> Raw/Normalized/Validated -> current/history -> Sheets`. No se habilita cron diario hasta demostrar aceptación, persistencia, replay y rechazo sin contaminación.

## Power BI y segunda fuente

Power BI sigue siendo el dashboard único y debe consumir la proyección semántica existente; no debe absorber lógica paralela de limpieza/identidad/ahorro. No se conecta refresh productivo sin estado comercial aceptado y durable.

No se inicia supermercado #2 hasta cerrar La Colonia end-to-end.

## Próximo paso exacto

1. terminar revisión de `#310` y confirmar CI/threads;
2. fusionar `#310` con expected head SHA sólo si la autorización materializada sigue activa y el alcance sigue siendo exactamente full-catalog SPS read-only;
3. observar el intento live #13 hasta estado terminal;
4. inspeccionar su artifact JSON/CSV y demostrar cobertura completa o identificar el blocker exacto;
5. si falla por una causa técnica dentro del mismo alcance autorizado, corregir únicamente esa causa y continuar;
6. si consigue catálogo completo, neutralizar el trigger one-shot cuando corresponda, actualizar este documento y avanzar offline a aceptación/persistencia mínima segura sin conceder autoridad por accidente.
