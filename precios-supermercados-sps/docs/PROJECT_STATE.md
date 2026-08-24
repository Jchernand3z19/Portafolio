# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia; no conceden por sí solos autoridad comercial ni autorización live.

## Corte

Estado verificado al **2026-08-24 (America/Tegucigalpa / UTC)** contra:

```text
main_observed = 50d63081c3c2634f5f0d4a7649f018f922527d91
last_technical_pr = #274
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

Los PRs `#254`–`#269` cerraron las fronteras offline conocidas de Fase 0: contexto SPS estructural, catálogo context-bound, materialización raw evidence-bound, storage físico simplificado, entrypoint de facets fail-closed, provenance segura para los placements soportados y reauditoría histórica reproducible.

Los PRs `#270`–`#271` materializaron una autorización humana transitoria para la observación mínima de facets y añadieron observabilidad GitHub temporal para identificar su run. La ventana terminó **sin realizar tráfico a La Colonia** porque el preflight de configuración Cloudflare falló antes de OIDC, navegador o red. El PR `#272` retiró el marker, wrapper y observador transitorios, restauró el workflow live manual fail-closed y dejó `SPS-context-and-root-facets-003` cerrada y no reutilizable.

El PR `#274` preparó un runbook productivo de Cloudflare, eliminó estado mutable obsoleto del README del edge y dejó explícito que el despliegue de infraestructura es una frontera separada de cualquier autorización live. Durante esa revisión se detectaron dos deudas offline adicionales: el preflight Cloudflare todavía conserva el blocker histórico `sps_context_unconfirmed` aunque este documento y la evidencia canónica ya tienen `SPS_TECHNICAL_CONTEXT=CONFIRMED`; además, `CloudflareDeploymentEvidence` continúa documentada en código como evidencia caller-controlled mientras no exista un adapter autenticado que haga read-back de la API real de Cloudflare. Esas deudas pertenecen a la futura ruta edge productiva; ya no se consideran bloqueadores automáticos del primer catálogo de prueba.

Durante la revisión de dirección del proyecto se detectó además que el proceso estaba optimizando seguridad/arquitectura como si cada prueba fuera ya una operación productiva. `AGENTS.md` ahora incorpora una política explícita **MVP primero**: ninguna nueva capa, adapter, verifier, preflight, workflow, tabla, documento o runbook puede crearse por previsión; debe desbloquear directamente extracción, binding SPS, validación, persistencia segura o una obligación de seguridad que no tenga una solución más simple. El objetivo inmediato vuelve a ser producir el primer catálogo real/verificable de La Colonia para SPS. PRs, conteo de tests y cantidad de capas dejan de tratarse como métricas de progreso.

La evidencia histórica puede reutilizarse offline, pero **no se interpreta como autorización abierta**. Cualquier tráfico nuevo **requiere autorización humana explícita vigente** para el alcance exacto solicitado.

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

La captura histórica deliberadamente **no preservó el placement** de `regionId` dentro del request. No se sabe todavía si el endpoint GraphQL relevante lo recibe como `header`, `query` u otra forma. Esa ausencia no se completa por inferencia.

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

El PR `#261` permite promover a `la_colonia_sps / CONFIRMED` únicamente una página con receipt de catálogo v3 firmado, binding SPS canónico, mismo run/traversal/partición, fingerprints reconciliados y `itemId` exactos contra `RawPageEvidence`. La materialización no abre red y conserva:

```text
production_authority = false
catalog_accepted = false
extraction_enabled = false
```

### Facets context-bound

Los PRs `#263`–`#266` dejaron preparado el contrato exacto:

```text
requests = [root_total, category_tree]
max_requests = 2
concurrency = 1
max_retries = 0
same_browser_context = required
artifact = sanitized only
```

El valor raw de `regionId` sólo puede existir transitoriamente en memoria. `header` y `query` tienen provenance durable segura; cualquier placement distinto abre una nueva frontera evidence-bound en vez de inferirse.

### Catálogo context-bound

La cadena técnica exige contexto SPS derivado por página, receipts v3, verificación criptográfica, primary + reconciliation canónicos, provenance física reconciliable y readiness del mismo plan/discovery. Readiness técnica no concede autoridad comercial.

## Intento live autorizado de facets — cerrado sin tráfico

Autorización humana recibida:

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

Ejecución asociada al merge de PR `#270`:

```text
workflow = La Colonia - Recorrido live manual
run = 32777363742
job = 97591389839
head_sha = 7a0df3c3971a4021862855166e527827035a3ea2
result = failure
error_code = env_cloudflare_edge_gateway_url_invalid
artifact_id = 9538444504
artifact_name = la-colonia-context-bound-facets-32777363742
artifact_digest = sha256:c87469499adba4b1fca34a109500c625ee69281f6065f2de3f87269caa4bb511
```

Los logs demostraron que en el Environment `la-colonia-live` estaban vacías:

```text
CLOUDFLARE_EDGE_GATEWAY_URL
CLOUDFLARE_EDGE_RECEIPT_PUBLIC_KEY_SPKI_B64URL
```

El runner emitió `env_cloudflare_edge_gateway_url_invalid` y terminó antes de solicitar OIDC, iniciar navegador, inicializar el gateway edge o contactar La Colonia. El job `live-crawl` quedó `skipped`. El artifact sanitizado contiene únicamente el status de fallo y `raw_values_exposed=false`.

La autorización `SPS-context-and-root-facets-003` queda cerrada después de ese intento operacional y no se reutiliza. Una ejecución futura requiere una autorización humana nueva para tráfico live. El despliegue productivo de Cloudflare sólo es prerequisito si se elige la ruta productiva edge; ya no se asume automáticamente como prerequisito de una prueba read-only/no autoritativa.

## Cloudflare — ruta productiva, no bloqueo universal del MVP

La sonda controlada no-La-Colonia ya produjo evidencia física histórica. Eso no equivale a un despliegue productivo.

El repositorio contiene el Worker productivo preparado en `edge/cloudflare/`, pero **no existe evidencia vigente de que `precios-sps-provenance` esté desplegado y conectado al Environment `la-colonia-live`**. El intento `32777363742` confirmó además que las dos variables necesarias para ese entrypoint estaban ausentes.

El PR `#274` añadió [`cloudflare-production-deploy-runbook.md`](cloudflare-production-deploy-runbook.md) para que el despliegue, read-back y configuración posterior del Environment se realicen de forma manual, versionada y fail-closed. Ese runbook no autoriza tráfico a La Colonia.

El modelo actual `CloudflareDeploymentEvidence` valida forma, hashes, flags y coherencia contra el manifest, pero su propio módulo declara que el snapshot sigue siendo caller-controlled mientras no exista un adapter que lo obtenga y autentique contra la API real de Cloudflare. Esa deuda debe cerrarse **antes de declarar la ruta edge como productiva**, no necesariamente antes de obtener evidencia de prueba por una ruta read-only más simple.

Si se decide usar la ruta productiva edge, antes del siguiente intento deben existir, con provenance verificable:

```text
1. Worker productivo Cloudflare desplegado con su Durable Object.
2. EDGE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL alojada únicamente en Cloudflare.
3. EDGE_RECEIPT_PUBLIC_KEY_SPKI_B64URL correspondiente.
4. EDGE_COLLECTOR_CODE_SHA256 coherente con el código desplegado.
5. GitHub Environment la-colonia-live con:
   - CLOUDFLARE_EDGE_GATEWAY_URL
   - CLOUDFLARE_EDGE_RECEIPT_PUBLIC_KEY_SPKI_B64URL
6. Read-back autenticado del deployment/version/código/Script Settings.
7. Preflight de identidad/release/clave en verde y semánticamente alineado con SPS ya confirmado.
```

La configuración/deploy real de Cloudflare requiere credenciales de la cuenta y puede crear o modificar infraestructura externa; no se deriva de una autorización read-only del supermercado.

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

No se escriben ofertas SPS en current/history antes de aceptación y autoridad reales. Runs fallidos, rechazados o no autoritativos no alteran estado comercial. Hashes/fingerprints prueban igualdad, no autoridad.

## Reauditoría histórica de Fase 0

La reauditoría final real dentro del PR `#269` cerró con:

```text
workflow = Precios Supermercados SPS - Pruebas base
run = 32773357812
job = phase0-final-historical-reaudit
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

Ventana transitoria de autorización, PR `#270`:

```text
run = 32776963711
result = success
pytest = 1709 passed
pip check = clean
compileall SyntaxWarning = none
```

Observador GitHub temporal, PR `#271`:

```text
run = 32777793715
result = success
pytest = 1711 passed
pip check = clean
compileall SyntaxWarning = none
```

Cierre fail-closed y limpieza de la ventana, PR `#272`:

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

El observador confirmó sobre SHA `7a0df3c3971a4021862855166e527827035a3ea2`:

```text
32777363736 = Precios Supermercados SPS - Pruebas base = success
32777363742 = La Colonia - Recorrido live manual = failure
```

## Fronteras pendientes

```text
MVP PRIORITY = first real/verifiable La Colonia SPS catalog
OFFLINE APPLICATION CODE = choose/prepare the shortest safe trial path
PRODUCTIVE EDGE DEBT = stale sps_context_unconfirmed blocker + authenticated Cloudflare deployment/read-back adapter
EXTERNAL PLATFORM CONFIGURATION = Cloudflare product worker + la-colonia-live vars only for edge production
LIVE EVIDENCE = actual regionId placement still unobserved
```

El siguiente trabajo técnico debe escoger y ejecutar el camino mínimo hacia el primer catálogo real, no continuar profundizando Cloudflare por inercia. Para una prueba read-only/no autoritativa, sólo deben bloquear seguridad básica, binding SPS verificable, límites de tráfico y una salida sanitizada; la infraestructura productiva se difiere si no es indispensable para esas propiedades.

La deuda del preflight `sps_context_unconfirmed` y la atestación autenticada de Cloudflare deben corregirse antes de declarar la ruta edge como productiva. No deben convertirse automáticamente en blockers del primer catálogo de prueba.

Mientras tanto deben permanecer:

```text
production_authority = false
catalog_accepted = false
extraction_enabled = false
ACTIVE_AUTHORIZATION_IDS = []
```
