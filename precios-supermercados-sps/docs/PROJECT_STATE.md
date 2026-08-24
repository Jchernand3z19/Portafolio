# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia; no conceden por sí solos autoridad comercial ni autorización live.

## Corte

Estado verificado al **2026-08-24 (America/Tegucigalpa / UTC)** contra:

```text
main_observed = adcaefaeccbaf443c52e09895c096b79e6b1dba2
last_technical_pr = #268
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

Los PRs `#254`–`#268` cerraron las fronteras offline conocidas de la fase: contexto SPS estructural, catálogo context-bound, materialización raw evidence-bound, storage físico simplificado, entrypoint futuro de facets fail-closed, provenance segura para los placements soportados y reauditoría histórica reproducible.

La siguiente dependencia real ya no es una tarea offline: requiere una **autorización humana nueva y explícita** para una observación mínima de facets bajo SPS. Esa autorización todavía no existe.

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

El cambio decisivo ocurrió `after_city`. La evidencia sanitizada conserva dos cambios débiles de sesión (`vtexsegment`, `vtexsession`) y un cambio fuerte de `request:regionid`.

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

Continúa siendo un **contexto fuente raw**, no una ubicación comercial. El extractor histórico sigue produciendo `location_id=la_colonia_online`, `location_status=unknown`, evidencia fuente explícita y confianza nula. Nunca se reinterpreta retrospectivamente como SPS.

## Frontera RawProduct -> SPS — cerrada offline

El PR `#261` añadió una frontera separada para promover un producto raw a `la_colonia_sps` únicamente cuando la misma página posee evidencia SPS context-bound verificable.

Cadena permitida:

```text
ContextBoundVerifiedCatalogPageObservation
-> receipt de catálogo v3 firmado
-> binding source/evidence SPS canónicos
-> mismo run + traversal + partition
-> mismos context/wire fingerprints
-> parse offline de la misma página
-> reconciliación exacta de itemId contra RawPageEvidence
-> la_colonia_sps / CONFIRMED
```

Invariantes:

- sólo se acepta una observación context-bound real;
- receipt v3 firmado y `location_context_bound=true` son obligatorios;
- source key/evidence deben coincidir exactamente con `LA_COLONIA_SPS`;
- no se realiza una nueva solicitud para materializar raw;
- item IDs, run, traversal, partición y fingerprints deben reconciliar exactamente;
- duplicados, páginas incompletas, parser rechazado o identidad divergente fallan cerrado;
- el raw histórico debe llegar todavía como `la_colonia_online / UNKNOWN`;
- sólo después de reconciliar se promueve a `la_colonia_sps / CONFIRMED`, confianza `1` y evidencia sanitizada;
- la materialización comercial usa sólo traversal `primary`;
- `production_authority=false`, `catalog_accepted=false` y `extraction_enabled=false` se preservan.

## Facets estructurales context-bound — preparación offline cerrada

Los PRs `#263`–`#265` dejaron compuesto el futuro entrypoint sin habilitar tráfico live.

Plan exacto:

```text
root_total
category_tree
max_requests = 2
concurrency = 1
max_retries = 0
```

Cadena preparada:

```text
GitHub workflow fail-closed
-> gate humano
-> environment controlado
-> OIDC audience fija
-> transporte Cloudflare allowlisted
-> BrowserContext que establece SPS
-> observación efímera de regionId
-> SpsStructuralFacetPlan
-> root_total
-> category_tree
-> receipts contextuales firmados
-> artefacto sanitizado
```

Invariantes:

- el gate humano ocurre antes de OIDC, browser y red;
- el job live permanece bloqueado en el estado actual;
- no existen retries ocultos ni redirects implícitos;
- sólo se permiten los endpoints/rutas edge contratados;
- el mismo BrowserContext que establece SPS debe conservar la sesión VTEX durante la observación;
- el valor raw de `regionId` sólo puede existir transitoriamente en memoria;
- receipts legacy, cambio de contexto, secuencia distinta de `root_total -> category_tree` o request adicional fallan cerrado;
- ninguna observación estructural concede autoridad comercial.

## Catálogo context-bound — cerrado offline

Los PRs `#254`–`#257` cerraron la cadena técnica:

```text
VerifiedStructuralDiscovery
+ receipts estructurales contextuales
+ SpsStructuralFacetPlan
-> VerifiedSpsStructuralContext
-> contexto SPS derivado por página
-> /v1/catalog-execute
-> receipt catálogo v3
-> verificación criptográfica + body estricto
-> primary + reconciliation canónicos
-> provenance físico reconciliable
-> readiness técnico context-bound
```

Cada página exige contexto derivado del proof SPS y rechaza downgrade/legacy, reutilización de IDs o divergencias de fingerprints. Primary y reconciliation permanecen ligados al mismo discovery/plan.

### Placement y provenance

El PR `#266` cerró offline la provenance segura para los dos placements explícitamente soportados:

- `header`: reconciliación donde el URL físico no incorpora el valor sensible;
- `query`: verificación transitoria del URL físico y salida durable redactada basada en hashes, sin persistir `url.full`, `fetch_url` ni el valor raw de ubicación.

El finalizador selecciona una ruta sólo a partir del placement realmente atestiguado. Si la observación futura revela otra forma, se abrirá una nueva frontera evidence-bound; no se adivina ahora.

## Readiness de catálogo

La evaluación técnica exige simultáneamente contexto estructural SPS verificado, collection context-bound, manifest físico del mismo plan/discovery, mismo location/context fingerprint y page set/cobertura exactos.

Aun con la cadena técnica completa, los blockers productivos permanecen:

```text
trusted_collector_provenance_unavailable
production_authority_not_established
```

Por diseño, esta capa no puede devolver `catalog_accepted=true` ni `production_authority=true` por sí sola.

## Google Sheets y persistencia

El PR `#259` aplicó el criterio de `production-data-engineering`: una entidad lógica sólo se materializa cuando existe una diferencia real de grain, lifecycle, ownership/seguridad, acceso o consumidor.

El workbook físico mantiene exactamente seis tabs gestionados:

```text
cfg_supermarkets
cfg_locations
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

Se retiraron mediante preflight + read-back los tabs vacíos `Sheet1`, `dim_products` y `map_source_products`. Los dos últimos permanecen como contratos lógicos diferidos para una futura fase cross-source.

Read-back confirmado:

- configuración de La Colonia preservada;
- SPS/TGU preservadas;
- `la_colonia_sps.extraction_enabled=false`;
- current/history/runs/quality sin filas comerciales reales todavía;
- no quedan tabs físicos diferidos ni pestaña vacía por defecto.

No se escriben ofertas SPS en current/history antes de aceptación y autoridad reales. Runs fallidos, rechazados o no autoritativos no alteran estado comercial. Hashes/fingerprints prueban igualdad, no autoridad.

## Reauditoría histórica de Fase 0 — cerrada

El PR `#268` reemplazó la dependencia autorreferente del snapshot v1 por decisiones v2 ligadas a:

- un `reviewed_main` que debe seguir siendo ancestro del main auditado;
- tip SHA exacto por rama revisada;
- número exacto de patches únicos;
- fallo cerrado ante drift, desaparición o reaparición con PR abierto;
- retiro automático de una excepción cuando la rama ya quedó merged/subsumed.

La reauditoría final real contra `main=adcaefaeccbaf443c52e09895c096b79e6b1dba2` se ejecutó dentro del PR `#269` sin tráfico externo:

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
reviewed_main = d584622a50ecb9ed6090cb1b098a5bc13e2b34d1
decisions_no_longer_needed = 0
artifact_id = 9537023081
artifact_name = precios-sps-phase0-final-branch-reaudit-32773357812
artifact_digest = sha256:a058ed4c039ed3d22fe0bff452ed18dadcbd36ce2c8104d982d89bc763c29663
```

No quedaron ramas históricas con patches únicos sin decisión versionada ni ramas históricas abiertas que contradigan el cierre.

## CI

Última validación completa observada:

```text
workflow = Precios Supermercados SPS - Pruebas base
run = 32773357812
result = success
pytest = 1705 passed
pip check = clean
compileall SyntaxWarning = none
```

Ese mismo run contiene el job `phase0-final-historical-reaudit` aprobado y constituye la evidencia conjunta de suite base + cierre histórico contra el `main` observado.

## Fronteras offline restantes

```text
NONE
```

A este corte no existe deuda de implementación conocida que pueda cerrar el placement real sin volver a observar el sitio. La selección del placement de `regionId` es evidencia live faltante, no una tarea que deba resolverse por inferencia.

## Próxima dependencia humana real

La siguiente acción requiere una **autorización humana nueva, mínima y explícita** para una observación pública read-only de facets bajo SPS con este alcance cerrado:

```text
purpose = attest actual regionId placement under SPS
requests = [root_total, category_tree]
max_requests = 2
concurrency = 1
max_retries = 0
same_browser_context = required
artifact = sanitized only
catalog_crawl = not authorized
commercial_persistence = not authorized
production_authority = false
catalog_accepted = false
extraction_enabled = false
```

Hasta recibir esa autorización deben permanecer:

```text
production_authority = false
catalog_accepted = false
extraction_enabled = false
ACTIVE_AUTHORIZATION_IDS = []
```
