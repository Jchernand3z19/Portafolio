# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia; no conceden por sí solos autoridad comercial.

## Corte

Estado verificado al **2026-08-24 (America/Tegucigalpa / UTC)**, después de fusionar los PRs `#254`–`#266`, simplificar el storage temporal, cerrar offline la frontera `RawProduct -> la_colonia_sps`, componer el futuro entrypoint de facets y preparar provenance seguro para placements `header` y `query`.

```text
main_observed = 0474e34a6ed371f330d4745d202d3cffc043945f
SPS_TECHNICAL_CONTEXT = CONFIRMED
location_id = la_colonia_sps
granularity = city
technical_binding_confirmed = true
extraction_enabled = false
production_authority = false
catalog_accepted = false
ACTIVE_AUTHORIZATION_IDS = []
```

La ubicación SPS, el plan estructural, las páginas de catálogo y la frontera de materialización raw permanecen ligados al mismo contexto técnico. El almacenamiento temporal separa modelo lógico de materialización física y mantiene sólo seis tablas activas en Google Sheets.

La suite completa del PR `#266` terminó verde en el run `32769032672`: **1701 passed**. Ese run ejecutó `pip check` y `compileall` con `SyntaxWarning` tratado como error; ambos terminaron limpios.

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

La captura histórica deliberadamente **no conserva el placement** de `regionId` dentro del request. Por tanto el repositorio no puede afirmar todavía si el contexto real observado para el endpoint GraphQL relevante fue `header`, `query` o alguna forma distinta/anidada. Esa ausencia no se completa por inferencia. Las rutas preparadas para `header` y `query` no convierten una tercera forma hipotética en soportada: cualquier placement no contratado debe fallar cerrado hasta disponer de evidencia concreta.

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

Continúa siendo un **contexto fuente raw**, no una ubicación comercial. El extractor histórico sigue produciendo `location_id=la_colonia_online`, `location_status=unknown`, evidencia fuente explícita y confianza nula. Ese comportamiento no se modificó ni se reinterpreta retrospectivamente.

## Frontera RawProduct -> SPS — cerrada offline

El PR `#261` añadió una frontera separada para atribuir un SKU a `la_colonia_sps` sin cambiar la semántica raw histórica.

Cadena permitida:

```text
ContextBoundVerifiedCatalogPageObservation
-> receipt de catálogo v3 firmado
-> binding source/evidence SPS canónicos
-> mismo run + traversal + partition
-> mismos context/wire fingerprints
-> parse offline de la misma página verificada
-> reconciliación exacta de itemId contra RawPageEvidence
-> la_colonia_sps / CONFIRMED
```

Invariantes:

- sólo se acepta una `ContextBoundVerifiedCatalogPageObservation` real;
- el receipt debe ser `schema_version=3`, estar firmado y declarar `location_context_bound=true`;
- `binding_source_key` y `binding_evidence` deben coincidir exactamente con `LA_COLONIA_SPS`;
- run, traversal role, partición, contexto y wire fingerprint deben ser los mismos de la página;
- la respuesta se vuelve a parsear **offline**, sin una nueva solicitud;
- la secuencia completa de `itemId` debe coincidir exactamente con la evidencia de cobertura de esa misma página;
- SKU duplicados, páginas incompletas, parser rechazado o identidad divergente fallan cerrado;
- antes de promover cada producto se exige que aún sea `la_colonia_online / UNKNOWN` con la evidencia fuente canónica y sin confianza inventada;
- el resultado promovido usa `la_colonia_sps / CONFIRMED`, confianza `1` y evidencia compuesta sólo por hashes/fingerprints sanitizados;
- la materialización de catálogo usa únicamente el traversal `primary`; reconciliation no duplica productos comerciales;
- una identidad fuente repetida entre páginas primary se rechaza;
- la salida mantiene `production_authority=false`, `catalog_accepted=false` y `extraction_enabled=false`.

Normalizar un `RawProduct` promovido por esta frontera ya no genera `pending_location_binding`; normalizar directamente un raw histórico continúa preservando el contexto online desconocido.

## Autorización live

No existe autorización live vigente para una observación nueva:

```text
location-binding workflow = workflow_dispatch only / job fail-closed
facet-discovery workflow = workflow_dispatch only / job fail-closed
ACTIVE_AUTHORIZATION_IDS = []
```

La ejecución histórica de binding puede reutilizarse como evidencia offline, pero **no se interpreta como autorización abierta**. Cualquier tráfico nuevo **requiere autorización humana explícita vigente** y limitada al propósito autorizado. Los IDs históricos consumidos no se reutilizan. La autonomía técnica del agente cubre GitHub/offline, pero no crea por inferencia autorización de tráfico contra el supermercado.

La próxima observación live prevista es mínima y exclusivamente de **facets bajo SPS**. No concede por sí sola `production_authority`, `catalog_accepted`, persistencia comercial ni autorización para un crawl de catálogo.

## Facets estructurales context-bound — preparación offline cerrada

Los PRs `#263`–`#265` cerraron la preparación del futuro entrypoint sin habilitar tráfico live.

El plan cerrado contiene exactamente:

```text
root_total
category_tree
```

Y fija:

```text
max_requests = 2
concurrency = 1
max_retries = 0
```

La cadena preparada incluye:

```text
GitHub workflow fail-closed
-> environment controlado
-> OIDC de audience fija
-> transporte HTTP Cloudflare allowlisted
-> observación efímera de regionId
-> SpsStructuralFacetPlan
-> root_total
-> category_tree
-> receipts contextuales firmados
-> artefacto sanitizado
```

Invariantes principales:

- el gate humano ocurre antes de OIDC, browser y red;
- el workflow mantiene el job bloqueado y no puede ejecutar tráfico en el estado actual;
- sólo se permiten endpoints `https://*.workers.dev` y las rutas edge explícitamente contratadas;
- redirects y retries implícitos están desactivados;
- el mismo bearer OIDC se reutiliza dentro del presupuesto cerrado;
- el contexto deriva del plan SPS, no de overrides caller-controlled;
- el valor raw de `regionId` sólo puede existir de forma transitoria en memoria;
- los artefactos públicos conservan fingerprints/evidencia sanitizada, no el valor raw;
- receipt legacy, contexto divergente, secuencia distinta de `root_total -> category_tree` o request adicional fallan cerrado;
- `production_authority`, `catalog_accepted` y `extraction_enabled` permanecen en `false`.

La ejecución de red no está autorizada actualmente.

## Catálogo context-bound — cerrado offline

Los PRs `#254`–`#257` cerraron la cadena de catálogo context-bound:

```text
VerifiedStructuralDiscovery
+ receipts estructurales contextuales
+ SpsStructuralFacetPlan
-> VerifiedSpsStructuralContext
-> contexto SPS derivado por página
-> /v1/catalog-execute
-> receipt de catálogo schema v3
-> verificación criptográfica + body estricto
-> primary + reconciliation canónicos
-> provenance físico reconciliable
-> readiness técnico context-bound
```

Invariantes principales:

- cada página exige `CatalogEdgeLocationContext` derivado del proof SPS, no del caller;
- `/v1/catalog-execute` aplica el contexto justo antes del fetch y firma receipt `schema_version=3`;
- el receipt v3 conserva sólo binding/evidencia/fingerprints y nunca el `regionId` raw;
- downgrade a v2/legacy se rechaza;
- primary y reconciliation derivan del mismo discovery y plan;
- request IDs, reservation IDs, nonces, receipts, evidence IDs y wire fingerprints no se reutilizan entre páginas;
- `WAIT`/`DENY` no producen retries ocultos;
- el resultado continúa con `production_authority=false` y `catalog_accepted=false`.

### Observability y placement — rutas seguras preparadas

El PR `#266` eliminó la deuda offline de provenance para el caso `query` sin seleccionar ni inferir el placement real.

- `header`: continúa usando la reconciliación legacy, donde el URL físico coincide con el request base y el contexto sensible viaja fuera del URL;
- `query`: el verifier obtiene candidatos raw de Workers Observability sólo de forma transitoria, exige que el URL físico sea exactamente el request base más un único parámetro directo de región, reconcilia identidad/status/body/script/timestamps y devuelve evidencia redactada basada en hashes;
- la evidencia durable de `query` no conserva `url.full`, `fetch_url` ni el valor raw de ubicación;
- el builder run-level produce el mismo `EdgeProvenanceRunManifest` sin reintroducir el URL físico;
- ambos caminos continúan con `production_authority=false`.

El finalizador usa el placement ya atestiguado por el contexto SPS y sólo admite los placements explícitamente soportados `header`/`query`; cualquier otro placement falla cerrado. Como la evidencia histórica no preservó ese dato, todavía no se sabe qué forma corresponde al sitio real. Esa selección depende de una observación live futura autorizada; no se inventa una tercera ruta sin evidencia de su forma exacta.

## Readiness de catálogo

La evaluación exige simultáneamente:

- `VerifiedSpsStructuralContext`;
- collection context-bound;
- manifest físico del mismo plan/discovery;
- mismo `location_id` y `context_fingerprint`;
- page set exacto del plan;
- cobertura canónica primary/reconciliation.

Aunque toda la parte técnica esté completa, el resultado mantiene obligatoriamente los blockers:

```text
trusted_collector_provenance_unavailable
production_authority_not_established
```

Por diseño, esta capa no puede devolver `catalog_accepted=true` ni `production_authority=true`.

## Google Sheets y persistencia — contrato físico sincronizado

El PR `#259` aplicó el criterio de `production-data-engineering`: una entidad lógica sólo se materializa cuando existe una diferencia real de grain, lifecycle, ownership/seguridad, acceso o consumidor.

El workbook físico contiene exactamente seis tabs gestionados:

```text
cfg_supermarkets
cfg_locations
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

Se retiraron, después de preflight y read-back, los tabs vacíos `Sheet1`, `dim_products` y `map_source_products`. Los dos últimos permanecen como **contratos lógicos diferidos** en el código; no son estado durable activo durante la fase de una sola fuente. `source_product_id` y `product_id` continúan dentro de current/history, por lo que la futura materialización cross-source puede reconstruirse/backfillearse sin inventar observaciones.

Read-back del workbook confirmó:

- `cfg_supermarkets`: configuración de La Colonia preservada;
- `cfg_locations`: SPS/TGU preservadas;
- `la_colonia_sps.extraction_enabled = false`;
- `fact_offers_current`, `fact_offer_history`, `fact_scrape_runs` y `fact_quality_events`: sólo headers, sin filas comerciales reales todavía;
- no quedan tabs físicos diferidos ni pestaña vacía por defecto.

El adapter de Sheets gestiona sólo las seis tablas activas y rechaza antes de I/O un batch que intente persistir una tabla diferida. Pestañas ajenas se preservan; cualquier migración destructiva futura requiere preflight y read-back explícitos.

No se escriben ofertas SPS en `current/history` antes de cerrar aceptación autoritativa. Runs fallidos, rechazados o no autoritativos no alteran estado comercial. Hashes y fingerprints prueban igualdad, no autoridad.

## Auditoría y CI de Fase 0

La reauditoría reproducible de ramas históricas se incorporó mediante PR `#253`. El warning conocido de `compileall` fue corregido en PR `#252`.

Último conteo observado:

```text
workflow = Precios Supermercados SPS - Pruebas base
run = 32769032672
result = success
pytest = 1701 passed
pip check = clean
compileall SyntaxWarning = none
```

## Fronteras offline restantes

Las fronteras genéricas que podían prepararse sin observar de nuevo el request real ya están cubiertas para el contrato soportado:

- storage físico simplificado y read-back verificado;
- `RawProduct -> la_colonia_sps` evidence-bound;
- entrypoint futuro de facets compuesto y fail-closed;
- transporte OIDC/Cloudflare acotado;
- provenance segura para los placements explícitamente soportados `header` y `query`;
- CI base verde y compileall estricto.

Queda una única actividad de cierre de Fase 0 que no requiere tráfico al supermercado:

1. **Reauditoría y sincronización final**: volver a verificar ramas históricas, workflows, CI, documentación estable/mutable y ausencia de deuda offline conocida contra el `main` actual. Si el snapshot histórico requiere nuevos overrides explícitos, deben versionarse y quedar reproducibles antes de declarar cerrada la fase.

La selección del placement real **no es una frontera offline**: depende de evidencia live nueva y no se resuelve por inferencia. Si esa observación revela un placement no soportado, se abrirá una frontera nueva ligada a esa evidencia en lugar de adivinar su contrato ahora.

## Próxima dependencia humana real

Después de completar la reauditoría/sincronización final, la primera dependencia humana real será una autorización nueva, mínima y explícita para observar **facets bajo SPS** y capturar de forma sanitizada el placement real de `regionId` en los requests GraphQL pertinentes.

Hasta entonces deben permanecer:

```text
production_authority = false
catalog_accepted = false
extraction_enabled = false
ACTIVE_AUTHORIZATION_IDS = []
```
