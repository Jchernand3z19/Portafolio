# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia histórica; por sí solos no conceden autoridad.

## Corte

Estado verificado al **2026-08-23 (America/Tegucigalpa)**.

Corte técnico inmediatamente anterior a este sync documental:

```text
main = d78010f740e2b67940c710df37946a2a11b7ed30 (merge de PR #225)
PR #225 CI = PASS (run 32662803489)
ACTIVE_AUTHORIZATION_IDS = []
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

## Evidencia live e IDs consumidos

Las autorizaciones de binding usadas históricamente son de un solo uso. Operacionalmente están consumidas y **no pueden reutilizarse**:

```text
LC-location-binding-336
LC-location-binding-331
LC-location-binding-332
LC-location-binding-333
LC-location-binding-334
LC-location-binding-335
LC-location-binding-337
```

El código de captura en `main` todavía sólo persiste hasta `LC-location-binding-335`; agregar `LC-location-binding-337` al set canónico es deuda de seguridad pendiente y no debe interpretarse como permiso para reutilizarlo.

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

El workflow de ubicación permanece fail-closed para tráfico live.

## Evidencia DOM aportada por el usuario

La evidencia humana ya no se limita a una captura visual. El usuario aportó la estructura DOM exacta de las opciones de ciudad:

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

La evidencia DOM sí identifica ahora el nodo real que representa cada ciudad y el estado visual seleccionado/no seleccionado. **Todavía no demuestra por sí sola qué cookie/storage/request/VTEX binding gobierna precios e inventario**, por lo que `SPS_TECHNICAL_CONTEXT` permanece `UNCONFIRMED`.

## Resolver vigente — PR #225

PR #225 (`Resuelve botones reales del selector de ciudad de La Colonia`) fue fusionado en `main` con merge:

```text
d78010f740e2b67940c710df37946a2a11b7ed30
```

El resolver ahora:

- abre `button.btn-modal-selector` cuando es único;
- busca primero la estructura confirmada `.cont-btn-ciudad`;
- sólo considera `button.btn-ciudad-selected` y `button.btn-ciudad-noselected` dentro de ese contenedor;
- identifica la ciudad por texto visible exacto case-insensitive;
- conserva las ciudades hermanas observadas;
- ignora contenedores fuera del viewport;
- falla cerrado si existen múltiples superficies válidas para la misma ciudad;
- usa roles ARIA únicamente como fallback cuando la estructura confirmada no está presentada.

CI de PR #225:

```text
run = 32662803489
job = tests
conclusion = success
```

Esto demuestra resolución **offline** de la estructura aportada. No demuestra todavía una transición productiva real.

## Deuda inmediata detectada después de PR #225

El resolver ya encuentra correctamente la ciudad, pero el flujo de captura todavía requiere hardening antes de una futura verificación live:

1. `ResolvedCityControl` aún no transporta explícitamente el estado `selected|noselected`.
2. La activación actual hace click en un botón estructural incluso si ya tiene `btn-ciudad-selected`.
3. El capturador duplica lógica de activación en `_activate_option` en vez de usar una única frontera state-aware.
4. No existe todavía una verificación explícita `before -> action/no-op -> after` que compruebe el estado estructural de la ciudad y el header.
5. Falta una integración browser-loopback que reproduzca exactamente `.cont-btn-ciudad`, la transición de clases y evidencia técnica sintética.
6. `LC-location-binding-337` debe incorporarse al set versionado de IDs consumidos.
7. El reconciliador temporal y su marker de la radiografía completa siguen presentes en `main` aunque el job live esté bloqueado; deben retirarse de forma segura y restaurar el workflow a manual-only.

Todo lo anterior es trabajo offline justificable y debe cerrarse antes de solicitar otra observación live.

## Seguridad live vigente

Estado efectivo:

```text
LIVE_EXECUTION_ENABLED = False
ACTIVE_AUTHORIZATION_IDS = []
radiography workflow job = if: false
production_authority = false
catalog_accepted = false
extraction_enabled = false
```

Sin una autorización humana nueva, explícita, vigente y de un solo uso están prohibidos nuevos HTTP/VTEX/GraphQL/Playwright/crawler/diagnostics/facet discovery/smoke/full crawl hacia La Colonia.

Ningún agente puede inventar un Authorization ID y ningún ID consumido puede reutilizarse.

Una futura autorización de binding sólo autorizaría el alcance que el usuario apruebe; no concede automáticamente catálogo, facets, crawl, persistencia comercial ni ejecución diaria.

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

Primero cerrar completamente offline el contrato de selección de ciudad con la estructura DOM confirmada:

```text
resolver estado selected/noselected
-> no-op seguro cuando SPS ya está selected
-> click sólo cuando SPS está noselected
-> verificar estado visual/header
-> integración browser-loopback + contexto técnico sintético
-> registrar LC-location-binding-337 como consumida
-> retirar reconciliador temporal
-> suite completa + revisión de seguridad + merge
```

Sólo después, el siguiente paso capaz de cambiar `SPS_TECHNICAL_CONTEXT=UNCONFIRMED` requiere una **nueva autorización humana explícita y de un solo uso** para una única observación controlada de binding con el resolver corregido.
