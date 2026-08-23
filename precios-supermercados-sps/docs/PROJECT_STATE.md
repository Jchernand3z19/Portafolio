# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. [`arquitectura.md`](arquitectura.md) describe la arquitectura estable; PRs, runs, ramas y artifacts son evidencia histórica y no conceden autoridad.

## Corte

Estado verificado al **2026-08-22 (America/Tegucigalpa)**.

El corte técnico inmediatamente anterior a este sync documental es:

```text
main = 3cb97255427a939a63bce1e49614cca0e066835e (merge de PR #197)
última suite completa observada = 1507/1507 PASS (PR #197, run 32621469076)
python -m pip check = PASS
compileall = PASS
GitHub Actions Node-24-compatible pins = VERIFIED
GATE-17 = PASS_PRODUCTIVE_EVIDENCE
ACTIVE_AUTHORIZATION_IDS = []
CONSUMED_LOCATION_BINDING_AUTHORIZATION_IDS = [LC-location-binding-336, LC-location-binding-331]
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
| 0A — suite completa | `DONE` | Suite Python + Node canónica. Último run observado: 1507/1507 PASS. |
| 0B — hardening físico de catálogo | `DONE` | Rechazo temprano de reutilización conflictiva de `physical_evidence_id` / `fetch_span_id`. |
| 0C — ramas históricas | `DONE` | Auditoría reproducible cerró el inventario sin `UNIQUE_UNMERGED`. |
| 0E — Raw → Normalized → Validated | `DONE` | Transformación operacional conectada sin conceder autoridad. |
| 0F — semántica de ubicación | `DONE_OFFLINE` | `la_colonia_online` es contexto fuente raw `UNKNOWN`; no puede convertirse bajo ese ID en SPS/TGU/tienda. Las radiografías live únicas `LC-location-binding-336` y `LC-location-binding-331` terminaron en `target_city_not_found`. PR #197 incorpora offline el botón estructural observado `button.btn-modal-selector`, pero la evidencia humana de UI/DOM y el fixture loopback no sustituyen una confirmación técnica live. |
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

### Radiografía mínima `LC-location-binding-331`

Tras el primer hardening offline, el usuario concedió una segunda autorización explícita e independiente para una sola radiografía mínima. `LC-location-binding-331` no reutilizó la autoridad de `LC-location-binding-336` y fue consumida después de su única ejecución.

Evidencia reconciliada:

```text
source run = 32619994748
source commit = b5b8aeb707ad66d570ed21aa5843b2943d7c2dbf
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

La reconciliación GitHub-only del merge de PR #195 confirmó que el artefacto sanitizado era válido y publicó de forma separada identidad de run, outcome y evidencia. El resultado físico siguió siendo negativo: la home cargó, se abrió el flujo de ubicación, pero el contrato entonces vigente no encontró un control de ciudad seleccionable para `San Pedro Sula`.

Cadena de cierre:

- PR #194 activó exclusivamente `LC-location-binding-331` para una única ejecución;
- PR #195 consumió inmediatamente el ID, cerró el fuse live y reconcilió offline el único run `32619994748`;
- PR #196 retiró el mecanismo temporal de reconciliación y dejó nuevamente el workflow live en `if: false`, con allow-list vacía;
- `LC-location-binding-331` y `LC-location-binding-336` permanecen consumidas y no son reutilizables.

No hubo smoke, facets, GraphQL replay, crawl ni persistencia comercial bajo `LC-location-binding-331`.

### Evidencia humana de UI/DOM posterior a las radiografías

Después de las dos ejecuciones, el usuario aportó una captura visual actual de la home y el fragmento HTML exacto del control superior de ubicación:

```html
<div class="vtex-flex-layout-0-x-flexColChild vtex-flex-layout-0-x-flexColChild--notificationBarRight pb0" style="height: 100%;">
  <div class="cont-btn-selector">
    <button class="btn-modal-selector">San pedro sula</button>
  </div>
</div>
```

Esta evidencia permite afirmar únicamente que la UI mostrada por el usuario presenta **San Pedro Sula** como ubicación visible y que el elemento que abre el selector tiene la clase pública `btn-modal-selector` en ese DOM aportado.

No permite afirmar por sí sola:

- cuál es el `source_location_key` técnico;
- si el binding real es por ciudad o por tienda;
- qué cookie, storage key, request header/variable o contexto VTEX cambia al seleccionar ubicación;
- que los precios observados sean autoritativamente SPS;
- que `la_colonia_online` pueda etiquetarse como `la_colonia_sps`.

Por tanto esta evidencia humana **no cambia** `SPS_TECHNICAL_CONTEXT=UNCONFIRMED`.

### Hardening offline del selector de ubicación

PR #192 amplió el resolver de ciudad para controles exactos `option`, `radio`, `menuitem` o `button`, conservando fallo cerrado ante ausencia, ocultamiento o ambigüedad.

PR #197 incorporó la evidencia HTML posterior sin volver a tocar La Colonia:

- prioriza exactamente un `button.btn-modal-selector` visible como control estructural de ubicación;
- conserva el fallback accesible histórico para `Selecciona tu tienda`, `Selecciona una tienda` o `Ubicación`;
- lee la ubicación pública visible antes de abrir el selector y la guarda como `visible_location` en el artefacto sanitizado;
- falla cerrado si el selector estructural es ambiguo o carece de etiqueta legible;
- excluye explícitamente el botón `btn-modal-selector` del conjunto de opciones de ciudad, evitando confundir el texto del header `San Pedro Sula` con una opción real del modal;
- mantiene separado el resolver DOM de cualquier autorización, target live o autoridad comercial.

Una integración browser-loopback reproduce la estructura aportada por el usuario, abre el botón `btn-modal-selector`, localiza una opción sintética de `San Pedro Sula` y demuestra el pipeline sin tráfico externo. La suite completa de PR #197 cerró en **1507/1507 PASS** (`run 32621469076`), con `pip check` y `compileall` también en PASS.

Este hardening mejora la siguiente observación física, pero **no convierte el fixture sintético ni el HTML aportado por el usuario en evidencia técnica de binding**.

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

La causa observable de los dos `target_city_not_found` ya tiene un hardening offline más específico: además del resolver de opciones de ciudad, la radiografía reconoce el botón de header `button.btn-modal-selector`, conserva su texto visible y evita usar ese mismo botón como falsa opción de ciudad.

Eso no convierte la hipótesis en evidencia física. El siguiente paso capaz de cambiar `SPS_TECHNICAL_CONTEXT=UNCONFIRMED` requiere una **nueva autorización humana explícita** para una única radiografía mínima sobre La Colonia con el código de PR #197 o posterior. Hasta entonces no se enviará otra request a la fuente.

Una autorización futura para esta radiografía no autoriza automáticamente smoke, facets, GraphQL replay, crawl, persistencia comercial ni ejecución diaria.

## Tráfico live

En esta frontera se realizaron exactamente dos radiografías mínimas autorizadas de ubicación, cada una con un ID distinto y de un solo uso:

```text
LC-location-binding-336 -> consumed -> target_city_not_found
LC-location-binding-331 -> consumed -> target_city_not_found
```

Después de cada ejecución se cerró el fuse y se retiró la autorización. El trabajo posterior —incluido PR #197 y su browser-loopback— fue offline.

Estado vigente:

```text
ACTIVE_AUTHORIZATION_IDS = []
CONSUMED_LOCATION_BINDING_AUTHORIZATION_IDS = [LC-location-binding-336, LC-location-binding-331]
LIVE_REQUESTS_CURRENT_RUN = 0
READY_FOR_LIVE = NO
SPS_TECHNICAL_CONTEXT = UNCONFIRMED
production_authority = false
catalog_accepted = false
extraction_enabled = false
```

No se realizaron retries con IDs consumidos, smoke, facets, GraphQL replay, crawl ni escrituras comerciales bajo estas autorizaciones.
