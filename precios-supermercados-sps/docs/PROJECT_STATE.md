# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia histórica; por sí solos no conceden autoridad.

## Corte

Estado verificado al **2026-08-23 (America/Tegucigalpa)**.

Corte técnico inmediatamente anterior a este sync documental:

```text
main = f91ee72a0524c2f489b0838893efdee4fe280ccf (merge de PR #207)
última suite completa observada = 1511/1511 PASS (PR #207, run 32652480368)
python -m pip check = PASS
compileall = PASS
ACTIVE_AUTHORIZATION_IDS = []
CONSUMED_LOCATION_BINDING_AUTHORIZATION_IDS = [LC-location-binding-336, LC-location-binding-331, LC-location-binding-332, LC-location-binding-333]
READY_FOR_LIVE = NO
SPS_TECHNICAL_CONTEXT = UNCONFIRMED
production_authority = false
catalog_accepted = false
extraction_enabled = false
```

El SHA anterior identifica el corte auditado previo al merge de este documento; no pretende ser autorreferencial.

## Frontera crítica actual

La primera dependencia real sigue siendo demostrar técnicamente el binding de **San Pedro Sula** antes de etiquetar precios como SPS.

Estado de la ubicación candidata:

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

## Radiografías live de ubicación consumidas

Se ejecutaron cuatro radiografías mínimas, cada una bajo una autorización humana explícita, independiente y de un solo uso. Todas fueron consumidas y retiradas después de su única ejecución.

| Authorization ID | Run | Resultado | Acciones lógicas | Conclusión |
|---|---:|---|---:|---|
| `LC-location-binding-336` | `32617926053` | `target_city_not_found` | 2 | no encontró control seleccionable de ciudad |
| `LC-location-binding-331` | `32619994748` | `target_city_not_found` | 2 | no encontró control seleccionable de ciudad |
| `LC-location-binding-332` | `32644498929` | `target_city_not_unique` | 2 | encontró más de un candidato exacto para SPS |
| `LC-location-binding-333` | `32651129634` | `target_city_not_unique` | 2 | volvió a detectar ambigüedad antes de seleccionar ciudad |

La ejecución única de `LC-location-binding-333` provino del merge `157458c8f169bcb1975fb998e07cd7043920c85e` de PR #205. Su preflight pasó y la radiografía llegó a la home exacta, abrió el selector y se detuvo fail-closed antes de seleccionar ciudad.

Evidencia sanitizada de LC-333:

```text
source run = 32651129634
source conclusion = failure
stop_reason = target_city_not_unique
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
artifact id = 9496212175
artifact sha256 = dee6dcd58bcccad41946c57c1368eb3bbdd423351a284e46bda8f577f9d45201
```

PR #206 consumió inmediatamente `LC-location-binding-333`, vació la allow-list, restauró `LIVE_EXECUTION_ENABLED=False`, bloqueó nuevamente el job live y reconcilió el artifact mediante GitHub sin repetir tráfico hacia La Colonia. PR #207 retiró después el reconciliador temporal y dejó nuevamente el workflow normal en `workflow_dispatch` con `radiography if:false`.

No hubo smoke, facets, GraphQL replay, crawl, extracción de productos ni persistencia comercial bajo ninguna de estas autorizaciones.

## Evidencia humana del modal de ciudad

Después de LC-333, el usuario aportó evidencia visual actual de lo que aparece al pulsar el control superior de ubicación.

El control superior aportado es:

```html
<div class="vtex-flex-layout-0-x-flexColChild vtex-flex-layout-0-x-flexColChild--notificationBarRight pb0" style="height: 100%;">
  <div class="cont-btn-selector">
    <button class="btn-modal-selector">San pedro sula</button>
  </div>
</div>
```

Al pulsarlo, la captura aportada muestra un modal con:

```text
¿Desde qué ciudad nos visita?
TEGUCIGALPA
SAN PEDRO SULA
*Los precios e inventario pueden variar dependiendo la ciudad
```

Las dos opciones aparecen como tarjetas visuales con indicador tipo radio. La captura muestra `SAN PEDRO SULA` resaltada en verde.

Esta evidencia humana sí demuestra la estructura visual que debemos reproducir en el resolver, pero **no demuestra todavía**:

- el atributo DOM exacto que cambia en producción al seleccionar SPS;
- si la semántica accesible real es `radio`, `button` u otra combinación;
- el `source_location_key`;
- si el binding comercial final es por ciudad o por tienda;
- qué cookie/storage/header/variable VTEX constituye la evidencia técnica;
- que un catálogo o precio concreto ya esté autoritativamente ligado a SPS.

Por eso `SPS_TECHNICAL_CONTEXT` permanece `UNCONFIRMED`.

## Hardening offline posterior a LC-333

PR #207 integró el hardening basado en la pantalla aportada sin ejecutar tráfico nuevo hacia La Colonia.

El resolver vigente ahora:

- sigue abriendo exactamente un `button.btn-modal-selector` visible;
- reconoce el prompt exacto `¿Desde qué ciudad nos visita?`;
- cuando ese prompt está visible, acota la búsqueda al menor ancestro del modal que contiene la opción objetivo;
- evita que un control homónimo fuera del modal compita con la selección real;
- prioriza semántica de ciudad `radio > option > menuitem > button`;
- si una única tarjeta visual expone simultáneamente un `radio` y una superficie `button` con el mismo nombre, selecciona el `radio` semántico en lugar de declarar una falsa ambigüedad;
- mantiene fallo cerrado si existen dos radios visibles o dos candidatos del mismo rol para `San Pedro Sula`;
- conserva soporte para selects nativos, ignorando duplicados cuyo `<select>` ancestro esté oculto;
- continúa excluyendo el botón de header `btn-modal-selector` como falsa opción de ciudad;
- mantiene la espera acotada de readiness del modal;
- no concede autoridad ni cambia configuración comercial.

CI de PR #207:

```text
run = 32652480368
pip check = PASS
compileall = PASS
pytest = 1511/1511 PASS
```

Esto prueba el comportamiento **offline** del resolver, no el resultado live actual de La Colonia.

## Seguridad live vigente

Estado confirmado en código después de PR #207:

```text
LIVE_EXECUTION_ENABLED = False
ACTIVE_AUTHORIZATION_IDS = []
CONSUMED_AUTHORIZATION_IDS = {
  LC-location-binding-336,
  LC-location-binding-331,
  LC-location-binding-332,
  LC-location-binding-333
}
```

El workflow de radiografía está nuevamente bloqueado. Ningún ID consumido puede reutilizarse.

Sin una autorización humana nueva y explícita están prohibidos nuevos HTTP/VTEX/GraphQL/Playwright/crawler/diagnostics/facet discovery/smoke/full crawl hacia La Colonia.

Una autorización futura de radiografía sólo autorizaría **una** observación mínima de binding dentro de sus límites. No autorizaría automáticamente catálogo, facets, GraphQL replay, crawl, persistencia comercial ni ejecución diaria.

## Catálogo y autoridad

La estructura offline de catálogo está avanzada, pero sigue separada de la autoridad productiva.

Reglas vigentes:

- `catalog_accepted` no puede venir de un boolean caller-controlled;
- readiness técnica no equivale a autoridad;
- la evidencia estructural/Cloudflare por sí sola no concede `production_authority`;
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

Todo el trabajo offline que podía realizarse con la evidencia actual quedó cerrado en PR #207.

El siguiente paso capaz de cambiar `SPS_TECHNICAL_CONTEXT=UNCONFIRMED` requiere una **nueva autorización humana explícita y de un solo uso** para una única radiografía mínima de ubicación usando el resolver de PR #207 o posterior.

El usuario debe elegir un authorization ID nuevo. No se inventa ni reutiliza uno desde el código o desde la automatización.
