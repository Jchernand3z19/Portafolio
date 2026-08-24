# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md). PRs, runs y artifacts son evidencia; no conceden por sí solos autoridad comercial.

## Corte

Estado verificado al **2026-08-24 (America/Tegucigalpa / UTC)**, después de fusionar los PRs `#248`, `#249` y `#250`.

```text
main_observed = 6184e3e8687ba72e2ce31f6edd0dde5f7b25eb7c
SPS_TECHNICAL_CONTEXT = CONFIRMED
location_id = la_colonia_sps
granularity = city
technical_binding_confirmed = true
extraction_enabled = false
production_authority = false
catalog_accepted = false
ACTIVE_AUTHORIZATION_IDS = []
```

La frontera de ubicación de San Pedro Sula está cerrada y el transporte **estructural/facets** ya quedó ligado offline al contexto SPS confirmado. Fase 0 todavía no sale: quedan trabajo reproducible/offline y documentación antes de llegar a la siguiente frontera humana live.

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

Continúa siendo un **contexto fuente raw** y no una ubicación comercial. Permanece `location_status=unknown` y no puede reutilizarse ni convertirse silenciosamente a SPS/TGU/tienda.

## Autorización live vigente

La ejecución `32677568208` es evidencia histórica ya producida por una observación pública read-only y puede reutilizarse offline. Esa evidencia **no se interpreta como autorización abierta** para repetir el binding ni para nuevas fases live.

Estado fail-closed actual:

```text
standing location-binding marker = absent
location-binding workflow = workflow_dispatch only
location-binding job = if: false
facet-discovery workflow = workflow_dispatch only
facet-discovery job = if: false
ACTIVE_AUTHORIZATION_IDS = []
```

El CLI de binding no expone `--standing-public-read-only`; exige un `--authorization-id` explícito y, sin un ID activo versionado, la captura se detiene antes de abrir navegador.

Los IDs históricos `LC-location-binding-331` a `337` relevantes siguen consumidos y no se reutilizan. La solicitud histórica `la-colonia-facet-discovery-001` tampoco concede permiso para una nueva ejecución.

La **próxima observación live** permitida por el plan, cuando todo el trabajo offline previo haya terminado, debe ser mínima y exclusivamente de facets bajo SPS. Requiere autorización humana explícita nueva con propósito, supermercado, alcance, máximo de requests, concurrencia, pacing, observables y exclusiones. No puede conceder por sí sola persistencia comercial, `production_authority` ni `catalog_accepted`.

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

## Facets estructurales bajo SPS — estado offline

El merge `54fc86a4eae7e85bea7e61b9951a0b70362ede9e` preparó la frontera offline que impide reutilizar una consulta GraphQL genérica como si ya estuviera ligada a SPS. Posteriormente, el PR `#248` (`2b454df97e05af443d7a8fb3d87a82bd2d2bc239`) cerró la integración del transporte verificado de facets con ese plan SPS.

La ruta vigente:

- exige `la_colonia_sps` con granularidad `city` y binding técnico confirmado;
- toma como evidencia canónica el fingerprint de `request:regionid`;
- sólo observa/conserva el valor raw de contexto en memoria y no lo expone en representaciones públicas;
- conserva de forma sanitizada `placement`, `wire_key`, `value_path` y `wire_request_fingerprint`;
- deriva `StructuralEdgeLocationContext` desde el plan y binding confirmados, no desde valores caller-controlled;
- transmite el contexto al gateway estructural y exige receipt contextual firmado;
- rechaza downgrade o mismatch de `location_id`, binding, evidencia, fingerprint, placement, wire key/path o wire fingerprint;
- prepara/acepta exactamente `root_total` y `category_tree` en esta frontera;
- conserva `production_authority=false` y no acepta catálogo;
- para ejecución de red exige plan SPS: la construcción offline sin plan puede existir para consumers ya materializados, pero un `__call__` sin plan falla cerrado;
- no hay retries ocultos ante `WAIT`, `DENY`, firma/body inválidos o cambio de contexto.

El CI de integración del PR `#248` quedó verde en el run `32736195663`: `1591 passed`. Ese mismo run demuestra que `compileall` todavía emite un warning corregible en `scripts/radiografiar_selector_ubicacion_la_colonia.py` por una secuencia `\s` dentro del JavaScript embebido. Por tanto **Fase 0 no puede declararse limpia todavía**.

## Storage físico de Google Sheets

Los PRs `#249` y `#250` usaron la ruta productiva ya existente de storage (`apply-config` y luego `check`), sin arreglos manuales de celdas para saltar el preflight.

El read-back físico posterior de `cfg_locations` confirmó para `la_colonia_sps`:

```text
granularity = city
technical_binding_confirmed = true
source_location_key = request:regionid:sha256:d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
extraction_enabled = false
```

El workbook sigue siendo almacenamiento temporal y **no debe recibir ofertas SPS** antes de la aceptación autoritativa del catálogo.

## Catálogo y provenance — frontera actual

La ruta de catálogo todavía no está cerrada al mismo nivel que la estructural. La frontera pendiente exige que **cada página** quede criptográficamente ligada a `la_colonia_sps` y al binding/evidence/fingerprint confirmado, manteniendo el mismo contexto entre traversal primario y reconciliación y rechazando cualquier receipt legacy/no contextual o página sin contexto SPS.

No es válido inferir SPS porque el proyecto esté limitado a SPS ni porque la sesión haya seleccionado SPS en otro paso.

La cadena correcta sigue siendo:

```text
binding SPS confirmado
-> facets estructurales context-bound offline
-> entrypoint de facets verificado y fail-closed
-> páginas de catálogo context-bound y provenance reconciliable
-> frontera raw -> ubicación comercial evidence-bound
-> autorización humana mínima de facets
-> revalidación live de facets/estructura bajo SPS
-> autorización separada para catálogo si corresponde
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

## Identidad, normalización y ubicación raw

Se conserva:

```text
source_product_id = identidad dentro de la fuente
product_id        = identidad comparable entre fuentes
offer_id          = supermercado + ubicación comercial + producto fuente
```

GTIN válido puede producir identidad fuerte cross-supermercado. Sin identidad fuerte se conserva `prod_pending_*` hasta mapping revisado. No se reintroduce una materialización automática de `dim_products`/`map_source_products` por el simple hecho de cerrar SPS; el mapping cross-supermercado puede permanecer pendiente hasta antes del supermercado #2 cuando no exista identidad fuerte determinística.

La normalización común preserva el `location_id` del `RawProduct`. Eso es intencional: un RawProduct histórico con `la_colonia_online` no puede salir como oferta SPS por intuición. La frontera pendiente de Fase 0 debe exigir evidencia concreta para cualquier promoción de contexto raw a ubicación comercial y mantener `UNKNOWN` cuando no exista.

`reported_regular_price` es sólo el precio regular declarado por la tienda. El ahorro real compara el `current_price` actual contra el `current_price` del periodo aceptado inmediatamente anterior cuando existe baseline confiable.

## Trabajo pendiente antes de salir de Fase 0

Fase 0 sólo puede salir cuando, sobre `main` limpio:

- PRs de la fase estén fusionados y CI verde;
- el conteo final de tests se observe en un run real y quede documentado;
- `python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts` no emita el `SyntaxWarning` conocido corregible;
- se re-ejecute de forma reproducible la auditoría de ramas históricas y se conserven sus resultados sanitizados;
- el entrypoint futuro de facets reemplace el camino histórico/legacy y use edge verificada + plan SPS contextual + OIDC/environment/collector existentes, exactamente `root_total` y `category_tree`, `max_requests=2`, `concurrency=1`, sin retries ocultos y fail-closed si no hay autorización humana vigente;
- cada página de catálogo quede context-bound a SPS y su provenance rechace downgrade/mismatch;
- la frontera RawProduct -> ubicación comercial impida convertir `la_colonia_online` a SPS sin evidencia;
- `PROJECT_STATE.md`, README, `AGENTS.md`, `.github/workflows/AGENTS.md`, arquitectura, modelo y decisiones técnicas estén sincronizados con el corte final;
- `production_authority=false`, `catalog_accepted=false`, `extraction_enabled=false` y `ACTIVE_AUTHORIZATION_IDS=[]` se mantengan hasta una frontera posterior que los pueda cambiar legítimamente.

## Próxima dependencia humana real

Todavía **no** corresponde pedir autorización live: queda trabajo offline de Fase 0.

Cuando todo lo anterior esté cerrado, la siguiente acción que no puede resolverse honestamente offline será una observación mínima de **facets bajo SPS**. En ese momento se debe detener el desarrollo en la frontera live y pedir una autorización humana explícita nueva; no se inventa ni reutiliza ningún Authorization ID histórico.
