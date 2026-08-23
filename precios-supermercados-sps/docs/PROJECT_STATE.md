# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia histórica; por sí solos no conceden autoridad.

## Corte

Estado verificado al **2026-08-23 (America/Tegucigalpa)**.

Corte técnico inmediatamente anterior a este sync documental:

```text
main = a2d4ec130f9de0fe21d65b63f58a5088e72e76e0 (merge de PR #217)
última suite completa observada = 1519/1519 PASS (PR #217, run 32656851068)
python -m pip check = PASS
compileall = PASS
ACTIVE_AUTHORIZATION_IDS = []
CONSUMED_LOCATION_BINDING_AUTHORIZATION_IDS = [LC-location-binding-336, LC-location-binding-331, LC-location-binding-332, LC-location-binding-333, LC-location-binding-334, LC-location-binding-335]
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

Se ejecutaron seis radiografías mínimas, cada una bajo una autorización humana explícita, independiente y de un solo uso. Todas están consumidas y ningún ID puede reutilizarse.

| Authorization ID | Run | Resultado | Acciones lógicas | Conclusión |
|---|---:|---|---:|---|
| `LC-location-binding-336` | `32617926053` | `target_city_not_found` | 2 | no encontró control seleccionable de ciudad |
| `LC-location-binding-331` | `32619994748` | `target_city_not_found` | 2 | no encontró control seleccionable de ciudad |
| `LC-location-binding-332` | `32644498929` | `target_city_not_unique` | 2 | encontró más de un candidato exacto para SPS |
| `LC-location-binding-333` | `32651129634` | `target_city_not_unique` | 2 | ambigüedad antes de seleccionar ciudad |
| `LC-location-binding-334` | `32653410569` | `target_city_not_unique` | 2 | persistió ambigüedad después de acotar por modal/rol |
| `LC-location-binding-335` | `32655634910` | `target_city_not_unique` | 2 | persistió ambigüedad después de filtrar controles fuera del viewport |

Ninguna de estas ejecuciones realizó smoke de catálogo, facet discovery, GraphQL replay, crawl, extracción de productos ni persistencia comercial.

### Evidencia sanitizada de LC-335

La sexta ejecución es la observación live más reciente y gobierna cualquier conclusión sobre el estado actual.

```text
authorization = LC-location-binding-335
source merge = ad8b3d2abf9b4fb41c887a7f25b0c6b7055a1964
source run = 32655634910
source conclusion = failure
stop_reason = target_city_not_unique
logical_actions = 2
browser_started = true
target_navigation_started = true
target_navigation_completed = true
visible_location = null
available_cities = 0
available_stores = 0
binding_report = null
store_selection_observed = false
production_authority = false
catalog_accepted = false
extraction_enabled = false
artifact id = 9497365576
artifact sha256 = e03a79f9f47e3068f33f7125d3adde2aa1f53aec9a99e37f4dfe4d386b8b41ec
```

La reconciliación GitHub-only de LC-335 validó la existencia y forma del artifact sin repetir tráfico a La Colonia. El cierre posterior retiró el reconciliador temporal, eliminó su marker, restauró el workflow a `workflow_dispatch` con `radiography if:false`, vació la allow-list y registró `LC-location-binding-335` como consumida.

Por lo tanto, **todavía no existe evidencia live de que el automatismo haya hecho clic en San Pedro Sula**. La ejecución se detuvo antes de reservar la tercera acción lógica `select_city`.

## Evidencia humana del modal de ciudad

La evidencia aportada por el usuario muestra el control superior:

```html
<div class="vtex-flex-layout-0-x-flexColChild vtex-flex-layout-0-x-flexColChild--notificationBarRight pb0" style="height: 100%;">
  <div class="cont-btn-selector">
    <button class="btn-modal-selector">San pedro sula</button>
  </div>
</div>
```

Al pulsarlo, la captura visual muestra:

```text
¿Desde qué ciudad nos visita?
TEGUCIGALPA
SAN PEDRO SULA
*Los precios e inventario pueden variar dependiendo la ciudad
```

Las opciones se presentan como tarjetas con indicador visual tipo radio. Esta evidencia demuestra el flujo visual que debe reproducir el resolver, pero no identifica por sí sola el nodo DOM único que recibe el gesto, ni el canal de contexto VTEX que prueba el binding comercial.

Por eso `SPS_TECHNICAL_CONTEXT` permanece `UNCONFIRMED`.

## Hardening offline vigente tras LC-335

PR #217 integró una nueva corrección completamente offline y dejó de nuevo cerrada la frontera live.

El resolver vigente conserva todas las defensas previas y además:

- abre exactamente el selector de ubicación observado `button.btn-modal-selector` cuando es único;
- reconoce el prompt exacto `¿Desde qué ciudad nos visita?`;
- filtra controles que Playwright considera visibles pero cuya caja está completamente fuera del viewport;
- prioriza `radio > option > menuitem > button`;
- excluye el botón del header como falsa opción de ciudad;
- conserva soporte fail-closed para `<select>` nativos y duplicados ocultos;
- colapsa coincidencias **estrictamente anidadas** ancestro/descendiente cuando Playwright representa el mismo gesto visual con varios nodos accesibles;
- conserva el nodo más específico de ese único gesto;
- mantiene ambigüedad fail-closed si existen dos candidatos hermanos o en ramas DOM distintas;
- nunca usa esta deduplicación para elegir arbitrariamente entre dos opciones físicamente distintas;
- si una ambigüedad persiste en una futura observación autorizada, puede persistir únicamente diagnóstico acotado `stage`, `role`, `candidate_count`, `effective_count`;
- prohíbe en ese diagnóstico HTML, selectores, atributos, URLs y valores de contexto crudos.

La integración browser-loopback reproduce un modal con prompt anidado y un radio contenedor + radio descendiente para `San Pedro Sula`; el resolver colapsa el único gesto visual, selecciona SPS y observa un cambio técnico sintético sin conceder autoridad comercial.

CI de PR #217:

```text
run = 32656851068
pip check = PASS
compileall = PASS
pytest = 1519/1519 PASS
```

Esto demuestra el comportamiento **offline**. No demuestra que el DOM productivo actual use exactamente esa forma.

## Seguridad live vigente

Estado confirmado después de PR #217:

```text
LIVE_EXECUTION_ENABLED = False
ACTIVE_AUTHORIZATION_IDS = []
CONSUMED_AUTHORIZATION_IDS = {
  LC-location-binding-336,
  LC-location-binding-331,
  LC-location-binding-332,
  LC-location-binding-333,
  LC-location-binding-334,
  LC-location-binding-335
}
```

El workflow de radiografía está bloqueado. Sin una autorización humana nueva y explícita están prohibidos nuevos HTTP/VTEX/GraphQL/Playwright/crawler/diagnostics/facet discovery/smoke/full crawl hacia La Colonia.

Una autorización futura de radiografía sólo autorizaría **una** observación mínima de binding dentro de sus límites. No autorizaría catálogo, facets, GraphQL replay, crawl, persistencia comercial ni ejecución diaria.

## Catálogo y autoridad

La estructura offline de catálogo está avanzada, pero sigue separada de la autoridad productiva.

Reglas vigentes:

- `catalog_accepted` no puede venir de un boolean caller-controlled;
- readiness técnica no equivale a autoridad;
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

Con PR #217 quedó cerrado el trabajo offline justificable con la evidencia disponible: cierre operacional de LC-335, filtro de viewport, deduplicación estricta de nodos anidados y diagnóstico sanitizado para una posible ambigüedad futura.

El siguiente paso capaz de cambiar `SPS_TECHNICAL_CONTEXT=UNCONFIRMED` requiere una **nueva autorización humana explícita y de un solo uso** para una única radiografía mínima de ubicación usando el resolver de PR #217 o posterior.

El usuario debe elegir un authorization ID nuevo. No se inventa ni reutiliza uno desde el código o desde la automatización.
