# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia; no conceden por sí solos autoridad comercial.

## Corte

Estado verificado al **2026-08-23/24 (America/Tegucigalpa / UTC)**.

```text
SPS_TECHNICAL_CONTEXT = CONFIRMED
location_id = la_colonia_sps
granularity = city
technical_binding_confirmed = true
extraction_enabled = false
production_authority = false
catalog_accepted = false
```

La frontera de ubicación de San Pedro Sula está cerrada. La siguiente frontera real es **revalidar la estructura/facets y recorrer el catálogo bajo el contexto SPS confirmado**, sin promover todavía ese recorrido a autoridad comercial hasta que la aceptación autoritativa lo determine.

## Binding técnico confirmado de San Pedro Sula

La ejecución pública read-only `32677568208`, sobre el merge `01804bedf7302678f096d8cef632ca3f3c407b4f`, completó sin `stop_reason` y observó:

```text
visible_location = San pedro sula
available_cities = [SAN PEDRO SULA, TEGUCIGALPA]
granularity_candidate = city
confidence = strong
technical_binding_observed = true
store_selection_observed = false
```

El cambio decisivo ocurrió `after_city`. La evidencia sanitizada contiene:

- cambio débil de cookie `vtexsegment`;
- cambio débil de cookie `vtexsession`;
- cambio **fuerte** de `request:regionid` asociado a la selección de SPS.

La llave sanitizada canónica es:

```text
request:regionid:sha256:d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
```

El artifact de Actions fue:

```text
run = 32677568208
artifact_id = 9503156133
artifact_name = la-colonia-location-binding-32677568208
artifact_zip_digest = sha256:39bfed10e0918ea070aa4b3755ed05317f63297ddd3ce227da3afa97d857b2c4
```

El payload JSON sanitizado se conserva durablemente en:

[`reports/discovery/la-colonia-location-binding-2026-08-24.json`](../reports/discovery/la-colonia-location-binding-2026-08-24.json)

Su hash canónico, calculado por `evaluate_location_binding_artifact`, es:

```text
80f2e4d333043a38954603c9c72086d241ac9b5a1cc1f10b71a9fde772588d95
```

Por tanto la referencia de evidencia de `la_colonia_sps` es:

```text
location_binding_radiography:sha256:80f2e4d333043a38954603c9c72086d241ac9b5a1cc1f10b71a9fde772588d95
```

La transición cumple el contrato `CITY_BINDING_READY` de `location_binding_transition.py`. Esto confirma **ubicación y granularidad de ciudad**, pero deliberadamente conserva:

```text
extraction_enabled = false
production_authority = false
catalog_accepted = false
```

## Estado canónico de ubicaciones

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

`extraction_enabled` sigue falso porque cerrar la ubicación no equivale a aceptar el catálogo.

### `la_colonia_tgu`

```text
city = Tegucigalpa
in_scope = false
granularity = unknown
technical_binding_confirmed = false
extraction_enabled = false
```

No se promueve Tegucigalpa por inferencia ni por aparecer en el selector.

### `la_colonia_online`

Continúa siendo un **contexto fuente raw** y no una ubicación comercial. Permanece `location_status=unknown` y no puede reutilizarse como SPS/TGU/tienda.

## Autorización live vigente

La ejecución `32677568208` es evidencia histórica ya producida por una observación pública read-only y puede usarse para cerrar el binding técnico de SPS. Esa evidencia **no se interpreta como autorización abierta para nuevas fases live**.

El marker versionado actualmente existente:

```text
.github/workflows/requests/la-colonia-location-binding-standing-request.json
purpose = verify-location-binding
```

está acotado a la verificación de binding de ubicación. No concede por sí mismo autorización para `facet_discovery`, smoke de catálogo, recorrido por categorías ni full crawl, y no debe incrementarse o reutilizarse para ampliar alcance sin una instrucción humana explícita que cubra esa nueva observación.

El workflow histórico de facet discovery continúa cerrado mediante `if: ${{ false }}`. Su request histórico `la-colonia-facet-discovery-001` no se reutiliza como permiso para una nueva ejecución.

Los IDs históricos `LC-location-binding-331` a `337` relevantes siguen consumidos y no se reutilizan.

Siguen fuera de cualquier autorización implícita: secretos, cuentas, billing, compras, checkout, mutaciones externas, infraestructura nueva con coste, persistencia comercial y decisiones manuales de mapping.

## Cómo se cerró el problema del selector

La estructura real aportada por el usuario y posteriormente observada live es:

```html
<div class="cont-btn-ciudad">
  <button class="btn-ciudad-noselected">Tegucigalpa</button>
  <button class="btn-ciudad-selected">San pedro sula</button>
</div>
```

El sitio puede montar copias DOM superpuestas y puede renderizar el opener antes de que el estado hidratado acepte el click. La resolución vigente:

- identifica ciudad por texto exacto dentro de `.cont-btn-ciudad`;
- usa `btn-ciudad-selected` / `btn-ciudad-noselected` sólo como estado, no identidad;
- colapsa únicamente duplicados visualmente equivalentes con geometría + hit-test;
- tolera duplicación transitoria del prompt durante readiness;
- considera efectivo el opener sólo cuando aparece una superficie real del modal;
- si el primer gesto no produce modal, hace un único reintento bounded tras asentamiento;
- verifica la selección estructural y luego exige evidencia técnica separada.

La ejecución `32677568208` es la primera que cerró las tres capas necesarias: control correcto, SPS visible y cambio técnico fuerte de contexto.

## Catálogo y autoridad — frontera actual

La cadena correcta desde este punto es:

```text
binding SPS confirmado
-> revalidar facets/estructura bajo SPS
-> recorrido de catálogo con evidencia física
-> decisión autoritativa accept/reject
-> habilitación comercial controlada
-> current/history
-> Google Sheets
-> Power BI
-> automatización diaria
-> segundo supermercado
```

Reglas que siguen vigentes:

- `catalog_accepted` nunca viene de un boolean caller-controlled;
- binding técnico no concede `production_authority`;
- un crawl exitoso no muta `current/history` si no supera la frontera de aceptación;
- runs fallidos/rechazados/no autoritativos no alteran estado comercial;
- ausencia de producto en un run no implica baja;
- hashes prueban igualdad, no autoridad.

## Persistencia

Google Sheets sigue siendo el backend temporal inicial con las ocho tablas comunes:

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

La infraestructura física ya fue demostrada previamente. **No se deben persistir ofertas SPS todavía**: primero debe cerrarse la aceptación del catálogo bajo el binding confirmado.

BigQuery y Cloud Run siguen fuera de esta fase salvo justificación posterior.

## Identidad y precios

Se conserva:

```text
source_product_id = identidad dentro de la fuente
product_id        = identidad comparable entre fuentes
offer_id          = supermercado + ubicación comercial + producto fuente
```

GTIN válido puede producir identidad fuerte cross-supermercado. Sin identidad fuerte se conserva `prod_pending_*` hasta mapping revisado.

`reported_regular_price` es sólo el precio regular declarado por la tienda. El ahorro real compara el `current_price` actual contra el `current_price` del periodo aceptado inmediatamente anterior cuando existe baseline confiable.

## Próxima dependencia real

No hace falta más trabajo de radiografía para demostrar San Pedro Sula. El trabajo offline puede continuar preparando y endureciendo la revalidación de facets/catálogo para que use exclusivamente el contexto SPS confirmado y permanezca fail-closed.

La **próxima ejecución live** que consulte facets o catálogo bajo SPS es una observación distinta de la verificación de binding y requiere autorización humana explícita vigente para ese alcance antes de emitir tráfico nuevo a La Colonia.
