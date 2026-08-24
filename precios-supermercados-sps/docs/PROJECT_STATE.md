# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia; no conceden por sí solos autoridad comercial.

## Corte

Estado verificado al **2026-08-24 (America/Tegucigalpa / UTC)**, después de fusionar los PRs `#254`, `#255`, `#256` y `#257`.

```text
main_observed = d4fcd3c8fe30986a9e1e73109e3c99d0c92a888e
SPS_TECHNICAL_CONTEXT = CONFIRMED
location_id = la_colonia_sps
granularity = city
technical_binding_confirmed = true
extraction_enabled = false
production_authority = false
catalog_accepted = false
ACTIVE_AUTHORIZATION_IDS = []
```

La ubicación SPS, el plan estructural y la ruta offline de catálogo quedaron ligados criptográficamente al mismo contexto técnico. La suite completa del PR `#257` terminó verde en el run `32751267460`: **1640 passed**. Ese run también ejecutó `compileall` con `SyntaxWarning` tratado como error y terminó limpio.

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

La captura histórica deliberadamente **no conserva el placement** de `regionId` dentro del request. Por tanto el repositorio no puede afirmar todavía si el contexto real observado para el endpoint GraphQL relevante fue `header`, `query` o una forma anidada. Esa ausencia no se completa por inferencia.

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

Continúa siendo un **contexto fuente raw**, no una ubicación comercial. Permanece `location_status=unknown`; no puede convertirse silenciosamente a SPS/TGU/tienda.

## Autorización live

No existe autorización live vigente para una observación nueva:

```text
location-binding workflow = workflow_dispatch only / job fail-closed
facet-discovery workflow = workflow_dispatch only / job fail-closed
ACTIVE_AUTHORIZATION_IDS = []
```

La ejecución histórica de binding puede reutilizarse como evidencia offline, pero **no se interpreta como autorización abierta**. Cualquier tráfico nuevo **requiere autorización humana explícita vigente** y limitada al propósito autorizado. Los IDs históricos consumidos no se reutilizan. La autonomía técnica del agente cubre GitHub/offline, pero no crea por inferencia autorización de tráfico contra el supermercado.

La próxima observación live prevista es mínima y exclusivamente de **facets bajo SPS**, después de agotar el trabajo offline. Requiere autorización humana explícita nueva y acotada. No concede por sí sola `production_authority`, `catalog_accepted`, persistencia comercial ni autorización para un crawl de catálogo.

## Facets estructurales context-bound

La ruta estructural ya exige el binding SPS confirmado y mantiene el valor raw sólo en memoria. El plan cerrado contiene exactamente:

```text
root_total
category_tree
```

La cadena valida y liga:

- `location_id`;
- binding source/evidence;
- fingerprint de contexto;
- placement y wire key/path observados en memoria;
- fingerprint del request wire;
- request digest y run context;
- receipt contextual firmado;
- misma identidad criptográfica en root/tree.

Un receipt legacy, cambio de contexto, mismatch de fingerprint o material caller-controlled falla cerrado. La ejecución de red no está autorizada actualmente.

## Catálogo context-bound — cerrado offline

Los PRs `#254`–`#257` cerraron la frontera que antes faltaba.

Cadena vigente:

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

- cada página de catálogo exige `CatalogEdgeLocationContext` derivado del proof SPS, no del caller;
- `/v1/catalog-execute` aplica el contexto justo antes del fetch y firma receipt `schema_version=3`;
- el receipt v3 conserva sólo binding/evidencia/fingerprints y nunca el `regionId` raw;
- downgrade a v2/legacy se rechaza;
- primary y reconciliation derivan del mismo discovery y plan;
- request IDs, reservation IDs, nonces, receipts, evidence IDs y wire fingerprints no se pueden reutilizar entre páginas;
- `WAIT`/`DENY` no producen retries ocultos;
- el resultado continúa con `production_authority=false` y `catalog_accepted=false`.

### Observability y placement

El finalizador context-bound conserva una restricción explícita:

- `header`: puede reconciliarse con el contrato de tracing actual porque el URL físico continúa igual al request base y el valor sensible no entra en la traza pública;
- `query`: falla antes de solicitar token de Observability con `catalog_context_query_observability_redaction_required`, porque el contrato legacy serializa el URL físico y podría exponer el contexto raw.

Como la evidencia histórica de binding no guardó placement, **todavía no se sabe cuál de estas rutas corresponde al sitio real**. No se debe elegir `header` por comodidad ni usar `query` sin crear primero un contrato de provenance redactado seguro.

## Readiness de catálogo

La evaluación nueva exige simultáneamente:

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

## Google Sheets y persistencia

El storage físico ya refleja el binding SPS confirmado, pero continúa con:

```text
extraction_enabled = false
```

No se escriben ofertas SPS en `current/history` antes de cerrar aceptación autoritativa. Runs fallidos, rechazados o no autoritativos no alteran estado comercial. Hashes y fingerprints prueban igualdad, no autoridad.

## Auditoría y CI de Fase 0

La reauditoría reproducible de ramas históricas se incorporó mediante PR `#253`. El warning conocido de `compileall` fue corregido en PR `#252` y el run `32751267460` confirma que `compileall` fail-closed continúa limpio.

Último conteo observado:

```text
workflow = Precios Supermercados SPS - Pruebas base
run = 32751267460
result = success
pytest = 1640 passed
compileall SyntaxWarning = none
```

## Fronteras offline restantes

Antes de pedir autorización live para facets todavía se debe cerrar, como mínimo:

1. **RawProduct -> ubicación comercial evidence-bound**: impedir que `la_colonia_online` se convierta a `la_colonia_sps` sólo por configuración/alcance y exigir evidencia ligada al mismo catálogo/run.
2. **Placement-safe provenance**: decidir sólo con evidencia si el contexto real es header/query. Si resulta query, implementar una ruta de trace/provenance redactada que pruebe el fetch físico sin persistir el valor raw.
3. **Composición del entrypoint futuro de facets**: mantener exactamente `root_total` + `category_tree`, `max_requests=2`, `concurrency=1`, OIDC/environment/collector y todos los gates de autorización fail-closed.
4. **Sincronización documental final de Fase 0**: README, arquitectura, modelo, decisiones técnicas y agentes deben reflejar la cadena context-bound ya fusionada.

## Próxima dependencia humana real

Todavía **no** corresponde ejecutar tráfico live ni pedir autorización para catálogo. Cuando las fronteras offline anteriores estén cerradas, la primera dependencia humana real será una autorización nueva, mínima y explícita para observar **facets bajo SPS** y capturar de forma sanitizada el placement real de `regionId` en los requests GraphQL pertinentes.

Hasta entonces deben permanecer:

```text
production_authority = false
catalog_accepted = false
extraction_enabled = false
ACTIVE_AUTHORIZATION_IDS = []
```
