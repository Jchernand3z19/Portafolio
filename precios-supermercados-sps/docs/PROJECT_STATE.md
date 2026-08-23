# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia histórica; por sí solos no conceden autoridad.

## Corte

Estado verificado al **2026-08-23 (America/Tegucigalpa)**.

```text
main = ba8151da5d49dd1cebc27a83c7f5e667dd68857c (merge de PR #227)
PR #227 CI = PASS (run 32665734312, 1529/1529 tests)
python -m pip check = PASS
compileall = PASS
ACTIVE_AUTHORIZATION_IDS = []
READY_FOR_LIVE = NO
SPS_TECHNICAL_CONTEXT = UNCONFIRMED
production_authority = false
catalog_accepted = false
extraction_enabled = false
```

## Frontera crítica actual

La siguiente dependencia capaz de cambiar el estado del producto es demostrar técnicamente el binding de **San Pedro Sula** antes de etiquetar precios como SPS.

```text
location_id = la_colonia_sps
city = San Pedro Sula
in_scope = true
granularity = unknown
technical_binding_confirmed = false
source_location_key = null
extraction_enabled = false
```

El contexto fuente `la_colonia_online` continúa siendo un contexto raw de catálogo público, no una ubicación comercial. No puede convertirse por inferencia en SPS, Tegucigalpa o una tienda.

Hasta demostrar binding técnico no se habilitan extracción comercial, persistencia de ofertas ni aceptación de catálogo.

## Evidencia live e IDs consumidos

Las autorizaciones históricas de binding son de un solo uso y están consumidas en código y operación:

```text
LC-location-binding-336
LC-location-binding-331
LC-location-binding-332
LC-location-binding-333
LC-location-binding-334
LC-location-binding-335
LC-location-binding-337
```

`LC-location-binding-337` fue incorporada al set canónico `CONSUMED_AUTHORIZATION_IDS` en PR #227. Ninguno de estos IDs puede reutilizarse.

Observaciones históricas relevantes:

| Authorization ID | Run | Resultado | Conclusión |
|---|---:|---|---|
| `LC-location-binding-336` | `32617926053` | `target_city_not_found` | no encontró control seleccionable de ciudad |
| `LC-location-binding-331` | `32619994748` | `target_city_not_found` | no encontró control seleccionable de ciudad |
| `LC-location-binding-332` | `32644498929` | `target_city_not_unique` | encontró más de un candidato exacto para SPS |
| `LC-location-binding-333` | `32651129634` | `target_city_not_unique` | ambigüedad antes de seleccionar ciudad |
| `LC-location-binding-334` | `32653410569` | `target_city_not_unique` | persistió ambigüedad después de acotar por modal/rol |
| `LC-location-binding-335` | `32655634910` | `target_city_not_unique` | persistió ambigüedad después de filtrar controles fuera del viewport |
| `LC-location-binding-337` | `32658270045` | `target_city_not_found` | el resolver previo no identificó la superficie real de ciudad |

Ninguna de esas ejecuciones concedió `production_authority`, aceptó catálogo ni persistió ofertas comerciales.

## Radiografía completa de 2026-08-23

El usuario autorizó una única radiografía live completa enfocada en entender el selector de ubicación. La activación se fusionó en PR #222 mediante el commit fuente:

```text
52d305e97f98840f1b3786b3d7358cbaa5e87e46
```

El workflow live fue cerrado inmediatamente después en PR #223. La reconciliación GitHub-only de PR #224 no consiguió recuperar/verificar el artifact de esa ejecución y publicó fallo de reconciliación. Ese fallo **no demuestra que la selección haya fallado ni que haya funcionado**; sólo deja esa ejecución sin evidencia recuperada suficiente para cerrar el binding.

PR #227 retiró el reconciliador temporal y su marker. El workflow de ubicación volvió a quedar exclusivamente en `workflow_dispatch`, con el job `radiography` bloqueado por `if: ${{ false }}` y permisos globales `contents: read`.

## Evidencia DOM aportada por el usuario

El usuario aportó la estructura DOM exacta de las opciones de ciudad:

```html
<div class="cont-btn-ciudad">
  <button class="btn-ciudad-noselected">
    <span class="radio"></span>
    Tegucigalpa
  </button>
  <button class="btn-ciudad-selected">
    <span class="radio"></span>
    San pedro sula
  </button>
</div>
```

Esto demuestra estructuralmente que:

- `.cont-btn-ciudad` agrupa las ciudades;
- `.btn-ciudad-selected` representa la ciudad seleccionada;
- `.btn-ciudad-noselected` representa una ciudad seleccionable no activa;
- la identidad de ciudad está en el texto visible del `button`;
- `San pedro sula` estaba seleccionada en la evidencia aportada.

También se mantiene la evidencia del botón superior:

```html
<div class="cont-btn-selector">
  <button class="btn-modal-selector">San pedro sula</button>
</div>
```

La evidencia DOM identifica el nodo real que representa cada ciudad y el estado visual seleccionado/no seleccionado. **Todavía no demuestra por sí sola qué cookie/storage/request/VTEX binding gobierna precios e inventario**, por lo que `SPS_TECHNICAL_CONTEXT` permanece `UNCONFIRMED`.

## Selección determinista vigente — PR #227

PR #227 (`Hace determinista la selección de ciudad de La Colonia`) fue fusionado con:

```text
ba8151da5d49dd1cebc27a83c7f5e667dd68857c
```

El contrato offline vigente ahora:

- abre el selector superior `button.btn-modal-selector` cuando es único;
- resuelve primero `.cont-btn-ciudad`;
- identifica exactamente el botón de la ciudad por texto visible case-insensitive;
- deriva un estado explícito `selected|unselected` de `btn-ciudad-selected` / `btn-ciudad-noselected`;
- falla cerrado si un target tiene un estado estructural contradictorio;
- hace **no-op** si San Pedro Sula ya está `selected`;
- hace click únicamente si San Pedro Sula está `unselected`;
- después de usar el contrato estructural verifica que SPS quede seleccionada y, cuando el header expone ubicación, que éste sea consistente;
- conserva el fallback histórico ARIA/select para estructuras no equivalentes;
- mantiene deduplicación estricta, visibilidad/viewport y fail-closed ante ambigüedad;
- no concede autoridad comercial por una selección visual.

El capturador conserva evidencia `before -> action/no-op -> after` de los canales técnicos permitidos y sólo el analizador de binding puede concluir si existió un cambio técnico fuerte.

### Integración browser-loopback

PR #227 añadió una integración local que reproduce la forma DOM aportada por el usuario:

```text
Tegucigalpa = btn-ciudad-selected
San Pedro Sula = btn-ciudad-noselected
-> click SPS
-> Tegucigalpa = btn-ciudad-noselected
-> SPS = btn-ciudad-selected
-> header = San pedro sula
-> cambio sintético de regionId
```

La prueba demuestra que el flujo detecta la transición y clasifica el cambio técnico sintético como binding de ciudad fuerte.

También existe el caso inverso:

```text
SPS ya selected
-> no click de ciudad
-> estado visual verificado
-> logical_actions = 2
-> sin inventar cambio técnico
-> granularity_candidate = unknown
```

Esto es importante: un estado visual ya seleccionado no se convierte artificialmente en evidencia de binding técnico.

CI de PR #227:

```text
run = 32665734312
job = 97258706029
pip check = PASS
compileall = PASS
pytest = 1529/1529 PASS
```

## Seguridad live vigente

Estado efectivo:

```text
LIVE_EXECUTION_ENABLED = False
ACTIVE_AUTHORIZATION_IDS = []
CONSUMED_AUTHORIZATION_IDS incluye LC-location-binding-337
workflow location binding = workflow_dispatch only
radiography job = if: false
reconciliation marker = absent
reconciliation job = absent
production_authority = false
catalog_accepted = false
extraction_enabled = false
```

Sin una autorización humana nueva, explícita, vigente y de un solo uso están prohibidos nuevos HTTP/VTEX/GraphQL/Playwright/crawler/diagnostics/facet discovery/smoke/full crawl hacia La Colonia.

Ningún agente puede inventar un Authorization ID y ningún ID consumido puede reutilizarse.

La próxima observación live de binding debe usar un Authorization ID nuevo elegido por el usuario. Esa autorización sólo cubre el alcance expresamente aprobado y no concede automáticamente catálogo, facets, crawl, persistencia comercial ni ejecución diaria.

## Qué puede demostrar la próxima observación

El selector de ciudad ya no es la incógnita estructural. La próxima ejecución controlada puede distinguir dos casos:

1. **SPS aparece no seleccionada:** el flujo hará click, verificará la transición visual y observará los canales técnicos permitidos antes/después. Un cambio fuerte asociado puede cerrar el binding SPS.
2. **SPS ya aparece seleccionada:** el flujo hará no-op y verificará el estado visual. Si no existe una transición técnica observable, conservará `SPS_TECHNICAL_CONTEXT=UNCONFIRMED` en vez de inferir autoridad.

Si el segundo caso impide demostrar la asociación entre ciudad y contexto técnico, cualquier experimento posterior que altere deliberadamente otra ciudad y regrese a SPS necesitará alcance live explícito separado; no se amplía silenciosamente la autorización.

## Catálogo y autoridad

La estructura offline de catálogo está avanzada, pero sigue separada de la autoridad productiva.

Reglas vigentes:

- `catalog_accepted` no puede venir de un boolean caller-controlled;
- readiness técnica no equivale a autoridad;
- una selección visual de ciudad no equivale a binding técnico;
- evidencia estructural o Cloudflare por sí sola no concede `production_authority`;
- current/history sólo pueden mutar tras una decisión autoritativa aceptada;
- runs rechazados, fallidos o no autoritativos no alteran estado comercial.

La cadena correcta sigue siendo:

```text
binding SPS demostrado
-> revalidación estructural/facets bajo contexto SPS
-> recorrido de catálogo con evidencia física
-> autoridad productiva
-> decisión accept/reject
-> current/history
-> Google Sheets
-> Power BI
-> automatización diaria
```

## Persistencia inicial

Google Sheets continúa como backend temporal estructurado de la primera fase. La infraestructura física fue demostrada previamente mediante `check -> apply-config -> check` y read-back de:

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

No se introdujeron ofertas comerciales para demostrar esa infraestructura. La persistencia comercial de La Colonia permanece bloqueada por ubicación no confirmada y falta de autoridad de catálogo.

BigQuery y Cloud Run siguen fuera de esta fase salvo justificación posterior.

## Identidad y semántica comercial

Se mantiene la separación:

```text
source_product_id = identidad dentro de la fuente
product_id        = identidad comparable entre fuentes
offer_id          = supermercado + ubicación comercial + producto fuente
```

GTIN válido puede producir identidad fuerte cross-supermercado. Sin GTIN fuerte se mantiene `prod_pending_*` determinista hasta mapping revisado. No se unen productos sólo por semejanza de nombre.

`reported_regular_price` es un precio de referencia declarado por el supermercado; no demuestra ahorro real. La reducción real se calcula contra el `current_price` del periodo histórico aceptado inmediatamente anterior cuando existe baseline confiable.

## Cloudflare / Observability

La sonda física histórica de Cloudflare sigue existiendo, pero la única re-evaluación controlada del verifier actual terminó en:

```text
probe_discovery_trace_missing
```

Ese frente permanece `BLOCKED_EXTERNAL`. No se debilita el verifier ni se repite la sonda sólo para intentar obtener otro resultado. Esta frontera tampoco concede ni revoca autoridad de catálogo.

## Power BI

Power BI sigue siendo el dashboard final. La proyección semántica común ya está definida, pero el dataset/refresh productivo debe esperar datos comerciales aceptados y persistidos. No se construye un dashboard productivo con datos cuya ubicación o autoridad aún no están demostradas.

## Próxima dependencia real

El trabajo offline justificable para la selección de ciudad quedó cerrado en PR #227.

El siguiente paso capaz de cambiar `SPS_TECHNICAL_CONTEXT=UNCONFIRMED` requiere una **nueva autorización humana explícita y de un solo uso** para una única observación controlada de binding con el resolver vigente. El usuario debe elegir un Authorization ID nuevo; no se inventa desde código ni automatización.
