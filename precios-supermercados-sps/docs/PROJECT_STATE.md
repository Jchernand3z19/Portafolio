# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. [`arquitectura.md`](arquitectura.md) describe la arquitectura estable; PRs, runs, ramas y artifacts son evidencia histórica y no conceden autoridad.

## Corte

Estado verificado al **2026-08-22 (America/Tegucigalpa)**.

El corte técnico inmediatamente anterior a este sync documental es:

```text
main = 6c935178e15f17a2b912d6764188e8c604089b5e (merge de PR #192)
última suite completa observada = 1499/1499 PASS (PR #192, run 32619224093)
python -m pip check = PASS
compileall = PASS
GitHub Actions Node-24-compatible pins = VERIFIED
GATE-17 = PASS_PRODUCTIVE_EVIDENCE
ACTIVE_AUTHORIZATION_IDS = []
CONSUMED_LOCATION_BINDING_AUTHORIZATION_IDS = [LC-location-binding-336]
LIVE_REQUESTS_CURRENT_RUN = 0
READY_FOR_LIVE = NO
SPS_TECHNICAL_CONTEXT = UNCONFIRMED
production_authority = false
catalog_accepted = false
```

El SHA anterior identifica el corte auditado, no pretende ser un HEAD autorreferencial después del merge de este documento.

## Semántica de estado

| Estado | Significado |
|---|---|
| `DONE` | Contrato/lógica integrada y estable. |
| `DONE_OFFLINE` | Implementado y probado sin afirmar efecto productivo externo. |
| `DONE_PRODUCTIVE` | Evidencia física/productiva observada para esa capacidad concreta. |
| `PARTIAL_PRODUCTIVE` | Parte de la cadena se demostró físicamente, pero la frontera completa sigue abierta. |
| `BLOCKED_LIVE` | Requiere una observación real de la fuente. |
| `BLOCKED_HUMAN_DECISION` | Requiere autorización humana explícita. |
| `BLOCKED_EXTERNAL` | La siguiente evidencia depende de un servicio externo o de datos que éste ya no expone. |
| `BLOCKED_DEPENDENCIES` | Depende de cerrar una frontera anterior. |

## Fase 0

| Área | Estado | Evidencia / conclusión |
|---|---|---|
| 0A — suite completa | `DONE` | Suite Python + Node canónica. Último run observado: 1499/1499 PASS. |
| 0B — hardening físico de catálogo | `DONE` | Rechazo temprano de reutilización conflictiva de `physical_evidence_id` / `fetch_span_id`. |
| 0C — ramas históricas | `DONE` | Auditoría reproducible cerró el inventario sin `UNIQUE_UNMERGED`. |
| 0E — Raw → Normalized → Validated | `DONE` | Transformación operacional conectada sin conceder autoridad. |
| 0F — semántica de ubicación | `DONE_OFFLINE` | `la_colonia_online` es contexto fuente raw `UNKNOWN`; no puede convertirse bajo ese ID en SPS/TGU/tienda. La radiografía live `LC-location-binding-336` no resolvió el binding. PR #192 endureció offline la detección del control de ciudad, pero no altera la evidencia física ni confirma SPS. |
| 0G — identidad/dimensión de producto | `DONE_OFFLINE` | GTIN fuerte, mapping pendiente explícito, `dim_products` + `map_source_products`; PR #185 revalida también el `prod_pending_*` determinista antes de persistir. |
| 0H — documentación canónica | `DONE` | README, arquitectura, modelo, decisiones y estado separan arquitectura estable de estado operativo mutable. |
| 0I — workbook físico base | `DONE_PRODUCTIVE` | Workbook físico existe y fue auditado sin introducir ofertas. |
| 0J — GitHub Actions → Google Sheets | `DONE_PRODUCTIVE` | Se demostró `check -> apply-config -> check` con service account, write controlado y read-back físico de ocho tablas. |
| 0K — verifier Cloudflare/Observability | `BLOCKED_EXTERNAL` | Una única re-evaluación controlada del verifier actual terminó en `probe_discovery_trace_missing`; no se debilitó el contrato ni se repitió la sonda. |
| 0L — CI/protección | `DONE` | Enforcement de `main` ya demostrado; `pip check`, compileall, suite completa y actions oficiales Node-24-compatible fijadas por SHA completo. |

## Google Sheets — estado productivo de la infraestructura

Google Sheets es el backend temporal estructurado de la primera fase. La ruta productiva de infraestructura quedó demostrada sin escribir ofertas comerciales:

```text
GitHub Actions
-> Environment precios-sps-storage
-> service account
-> workbook
-> lectura segura
-> apply-config controlado
-> read-back
-> check final sin escritura
```

Secuencia relevante:

- PR #179: `check` de solo lectura → `ok-wrote-false`;
- PR #180: primer `apply-config` → fallo real `workbook_batch_update_failed`;
- PR #181: corrigió el planner porque Google Sheets rechaza `rowCount=1` junto con `frozenRowCount=1`;
- PR #182: `apply-config` corregido → `ok-wrote-true`;
- PR #183: `check` posterior → `ok-wrote-false`.

Read-back físico final:

```text
cfg_supermarkets
cfg_locations
dim_products
map_source_products
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

La pestaña ajena `Sheet1` se preservó. `dim_products`, `map_source_products` y las cuatro tablas `fact_*` permanecen sin filas comerciales. La configuración conserva La Colonia y sus ubicaciones candidatas sin activar extracción.

La concurrencia del workflow de storage es single-writer (`cancel-in-progress: false`) y el trigger automático sólo acepta el marker controlado sobre `main`.

## Cloudflare / Workers Observability

Evidencia física de sonda ya existente:

```text
physical probe source run = 32551882793
source run attempt        = 1
source commit             = cc15edef22709911beb1d1b027ae4c9992da1944
```

La evidencia firmada conserva la demostración histórica de OIDC, Worker/Durable Object, fetch a origen controlado, bytes y receipt Ed25519.

La re-evaluación controlada del verifier actual se ejecutó exactamente una vez mediante PR #176. El merge commit `5f6ea161e99c4ac3d740141035da74fa3c7ee6f4` publicó:

```text
precios-sps/cloudflare-evidence-verifier = failure
precios-sps/cloudflare-verifier-result/probe_discovery_trace_missing = failure
```

Conclusión canónica:

- el verifier actual no encontró el trace requerido en Workers Observability;
- no hay evidencia suficiente para declarar PASS de esa reconciliación;
- el estado permanece `BLOCKED_EXTERNAL`;
- no se repetirá la sonda ni una segunda re-evaluación sólo para intentar obtener otro resultado;
- no se debilita `traces -> events`, custom span, parent/child ni la reconciliación física;
- esta frontera no concede ni revoca autoridad de catálogo.

## CI y dependencias

PR #184 migró las actions SPS a generaciones oficiales compatibles con Node 24 y mantuvo pins SHA completos verificados. El runner observado (`2.336.0`) ejecutó directamente esas generaciones sin la advertencia anterior de actions Node 20 forzadas a Node 24.

CI actual ejecuta:

```text
Python 3.12
-> instalar requirements.txt
-> python -m pip check
-> python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts
-> pytest precios-supermercados-sps/tests
```

Los seis requerimientos directos están fijados a versión exacta. No existe lockfile con hashes de todo el grafo transitivo; por tanto la instalación es reproducible a nivel de dependencias directas, pero no hermética.

Lint, type checking, coverage y vulnerability scanning fueron evaluados. No se añadieron gates decorativos sin baseline/umbral y política de fallo definidos. Si una necesidad concreta aparece, debe añadirse como control exigible y probado, no como métrica ornamental.

## Identidad de producto

Se mantiene la separación:

```text
source_product_id = identidad dentro de la fuente
product_id        = identidad comparable entre fuentes
offer_id          = supermercado + ubicación comercial + producto fuente
```

Reglas vigentes:

- `source_product_id` es determinista;
- GTIN-8/12/13/14 válido por check digit se normaliza a GTIN-14 y puede producir `prod_gtin_*`;
- sin GTIN fuerte, `prod_pending_*` debe coincidir exactamente con `generate_pending_product_id(source_product_id)` antes de clasificarse como pendiente;
- un prefijo `prod_pending_` forjado falla cerrado;
- mapping revisado explícito continúa permitido;
- `dim_products` sólo materializa productos mapeados;
- `map_source_products` conserva la relación fuente → producto y la cola pendiente.

Antes de incorporar supermercado #2 debe existir una política operativa explícita para resolver equivalencias cuando no haya GTIN compartido ni mapping revisado; no se deben unir productos sólo por semejanza de nombre.

## La Colonia — ubicación y autoridad live

Contexto raw vigente:

```text
location_id = la_colonia_online
location_status = unknown
location_confidence = null
```

`la_colonia_online` representa el catálogo público en línea observado y no una ubicación comercial.

Ubicación candidata `la_colonia_sps`:

```text
city = San Pedro Sula
in_scope = true
granularity = unknown
technical_binding_confirmed = false
source_location_key = null
extraction_enabled = false
```

### Radiografía mínima `LC-location-binding-336`

El usuario autorizó una única radiografía mínima de binding para San Pedro Sula. La autorización quedó versionada, se ejecutó una sola vez y después fue consumida y retirada de todos los entrypoints temporales.

Evidencia reconciliada de la ejecución única:

```text
source run = 32617926053
source conclusion = failure
stop_reason = target_city_not_found
logical_actions = 2
browser_started = true
target_navigation_started = true
target_navigation_completed = true
available_cities = 0
available_stores = 0
granularity_candidate = none
confidence = none
technical_binding_observed = false
store_selection_observed = false
production_authority = false
catalog_accepted = false
extraction_enabled = false
```

Interpretación estricta:

- la home exacta de La Colonia sí fue alcanzada;
- el selector de ubicación pudo abrirse, porque la captura consumió las dos primeras acciones lógicas antes de detenerse;
- el capturador no pudo resolver de forma única `San Pedro Sula` con el contrato DOM vigente en esa ejecución;
- no existe evidencia suficiente para afirmar binding por ciudad ni por tienda;
- el fallo no convierte `la_colonia_online` en `la_colonia_sps`;
- no se ejecutó GraphQL replay, facets, smoke, crawl ni persistencia comercial;
- no se autoriza un retry con `LC-location-binding-336`.

Cadena de cierre:

- PR #187 activó exclusivamente `LC-location-binding-336` y produjo el único run live;
- PR #188 consumió inmediatamente la autorización y dejó el job live bloqueado;
- PR #189 leyó offline el mismo artefacto y publicó el detalle sanitizado sin repetir tráfico;
- PR #190 retiró los markers y el trigger temporal de reconciliación, dejando nuevamente el workflow manual globalmente bloqueado;
- PR #191 sincronizó este resultado en la fuente canónica de estado.

La UI conocida históricamente expone SPS y Tegucigalpa, pero la ejecución `LC-location-binding-336` no consiguió identificar el control de ciudad en el DOM observado. Por tanto `SPS_TECHNICAL_CONTEXT` continúa `UNCONFIRMED`.

### Hardening offline posterior a `target_city_not_found`

PR #192 corrigió la limitación conocida del capturador sin volver a tocar La Colonia.

El resolver de ciudad ahora:

- acepta únicamente controles interactivos con nombre **exacto** y roles `option`, `radio`, `menuitem` o `button`;
- exige exactamente un candidato en el conjunto completo de roles permitidos;
- rechaza controles custom ocultos;
- rechaza ambigüedad incluso cuando los duplicados aparecen con roles distintos;
- no convierte texto no interactivo en control seleccionable;
- conserva las ciudades hermanas de un `<select>` nativo y de un `role=listbox` inequívoco, filtrando placeholders;
- mantiene toda la lógica separada de target, autorización y autoridad productiva.

Pruebas de browser loopback demuestran offline que un botón custom exacto para `San Pedro Sula` puede producir binding de ciudad fuerte en el fixture sintético y que un duplicado falla antes de seleccionar. La suite completa de PR #192 cerró en **1499/1499 PASS**.

Este hardening sólo mejora la capacidad de observación de una eventual radiografía futura. **No demuestra que el DOM real actual de La Colonia use ninguno de esos controles, no confirma SPS y no concede autoridad.**

Cualquier nueva radiografía requiere una **nueva autorización humana explícita y limitada**. Esa autorización no puede reutilizar `LC-location-binding-336` y tampoco autoriza smoke, facets, GraphQL replay, crawl, persistencia comercial ni ejecución diaria.

## Persistencia comercial

La infraestructura de storage está lista, pero **persistencia comercial de La Colonia no está autorizada** porque ubicación y autoridad de catálogo continúan cerradas.

Sólo una ejecución aceptada y autoritativa puede mutar current/history. Runs rechazados/fallidos/no autoritativos pueden registrarse según su contrato, pero no materializan dimensión/mapping/current/history comercial.

## Regla comercial del precio

```text
current_price           = precio observado que paga el cliente
reported_regular_price  = referencia declarada por la tienda
previous_accepted_price = current_price del periodo aceptado inmediatamente anterior
```

Ahorro real:

```text
max(previous_accepted_price - current_price, 0)
```

`reported_regular_price` e `is_promotion` no sustituyen el histórico propio.

## Power BI

`power_bi_projection.py` permanece read-only/offline respecto a producción. Dataset y refresh productivo sólo pueden consumir datos comerciales aceptados y durables; Power BI no concede autoridad ni redefine la semántica de precio.

## Frontera actual

Las tareas técnicas que podían resolver **offline** la causa observada en `LC-location-binding-336` están cerradas: el selector de ciudad ya soporta controles exactos `option`/`radio`/`menuitem`/`button`, preserva select/listbox y falla cerrado ante ocultamiento, ausencia o ambigüedad.

Eso no convierte la hipótesis en evidencia física. El siguiente paso capaz de cambiar `SPS_TECHNICAL_CONTEXT=UNCONFIRMED` requiere una **nueva autorización humana explícita** para una única radiografía mínima sobre La Colonia. Hasta entonces no se enviará otra request a la fuente.

## Tráfico live

La única nueva interacción live de este bloque fue la radiografía mínima autorizada como `LC-location-binding-336`. Se limitó a la home y al selector de ubicación y terminó antes de seleccionar ciudad.

Después del cierre de PR #190 y del hardening exclusivamente offline de PR #192, el estado sigue siendo:

```text
ACTIVE_AUTHORIZATION_IDS = []
CONSUMED_LOCATION_BINDING_AUTHORIZATION_IDS = [LC-location-binding-336]
LIVE_REQUESTS_CURRENT_RUN = 0
READY_FOR_LIVE = NO
production_authority = false
catalog_accepted = false
```

No se realizaron retries, smoke, facets, GraphQL replay, crawl ni escrituras comerciales con esa autorización.
