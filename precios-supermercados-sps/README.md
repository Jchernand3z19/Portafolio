# Precios de Supermercados de San Pedro Sula

Proyecto para recolectar, normalizar, validar, historizar y comparar precios de supermercados con alcance inicial en San Pedro Sula.

> Estado operativo vigente: [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md)  
> Arquitectura estable: [`docs/arquitectura.md`](docs/arquitectura.md)  
> Modelo de datos: [`docs/modelo-datos.md`](docs/modelo-datos.md)

## Estado actual

Corte verificado al **2026-08-22 (America/Tegucigalpa)**:

- inventario histórico de ramas `precios-sps`: **cerrado** por PR #160; no quedaron ramas `UNIQUE_UNMERGED`;
- contratos `RawProduct -> NormalizedOffer -> ValidatedOffer`: conectados operacionalmente por PR #159;
- identidad de producto y contexto raw de ubicación: endurecidos por PR #161;
- última suite completa observada en el merge-ref final de #161: **1481/1481 PASS** + `compileall`;
- GATE-17: `PASS_PRODUCTIVE_EVIDENCE`;
- `ACTIVE_AUTHORIZATION_IDS=[]`;
- `LIVE_REQUESTS_CURRENT_RUN=0`;
- `READY_FOR_LIVE=NO`;
- `SPS_TECHNICAL_CONTEXT=UNCONFIRMED`;
- `production_authority=false`;
- `catalog_accepted=false`.

La Colonia continúa deliberadamente bloqueada para nuevas peticiones live. El contexto raw utilizado por el extractor es **`la_colonia_online`** y representa únicamente el catálogo público en línea observado; **no es SPS, Tegucigalpa ni una tienda**. Ese contexto debe permanecer `location_status=unknown` hasta que una frontera de binding separada produzca una ubicación comercial demostrada.

La sonda Cloudflare contra infraestructura propia sí fue ejecutada físicamente. Demostró OIDC, Durable Object, fetch al origen controlado y receipt Ed25519. El código actual ya implementa reconciliación estricta `traces -> events` para custom span + child fetch, pero esa ruta todavía debe ejecutarse exitosamente contra la evidencia física existente antes de considerar cerrada la verificación de Workers Observability. No se repetirá una request a La Colonia para resolver ese punto.

Google Sheets sigue siendo el storage temporal de la primera fase. El workbook físico existe, pero el contrato lógico actual ya contiene **ocho** tablas gestionadas; el workbook físico fue materializado antes de incorporar `dim_products` y `map_source_products`, por lo que debe migrarse mediante el workflow seguro de storage y revalidarse por read-back. Esa migración no autoriza persistencia comercial ni tráfico live.

## Contratos protegidos

- `RawProduct`: observación fiel a la fuente.
- `NormalizedOffer`: formato común sin inventar datos faltantes.
- `ValidatedOffer`: oferta validada con identidad, `state_hash`, revisión y evidencia de calidad.

Una oferta `in_stock` exige `current_price > 0`. Estados `out_of_stock`, `not_listed` y `unknown` pueden conservar precio nulo.

## Identidad de producto

La plataforma separa tres identidades:

```text
source_product_id = producto dentro de un supermercado/fuente
offer_id          = supermercado + ubicación comercial + producto fuente
product_id        = producto normalizado/comparable entre fuentes
```

`source_product_id` y `offer_id` son deterministas y se recalculan en fronteras críticas.

Para `product_id`:

- un GTIN-8/12/13/14 válido se verifica mediante check digit y se normaliza a GTIN-14;
- un GTIN válido puede producir `prod_gtin_<gtin14>` como identidad cross-supermercado;
- barcode ausente/inválido conserva `prod_pending_*` y el evento `pending_product_mapping`;
- un mapping explícitamente revisado puede sustituir el provisional sin cambiar la identidad fuente.

No se usa precio, promoción, disponibilidad ni fecha para construir IDs estables.

## Presentación y multipacks

No se colapsan presentaciones distintas. Cuando la fuente permite demostrarlo, se conservan por separado:

```text
unit_count
content_per_unit
measurement_unit
total_content
```

Ejemplo: `2 x 500 ml` se conserva como 2 unidades de 500 ml y total 1000 ml; no se convierte silenciosamente en un solo envase de 1000 ml.

## Regla comercial del histórico

`reported_regular_price` es un dato informado por el supermercado; **no demuestra ahorro real**.

La reducción real se calcula contra el `current_price` del periodo histórico **aceptado inmediatamente anterior**. `reported_regular_price` e `is_promotion` no participan en esa fórmula. Si no existe baseline confiable, no se inventa una reducción.

Runs `rejected`, `failed`, `abandoned` o no autoritativos no alteran current/history.

## Ubicaciones

Todos los supermercados comparten el mismo modelo de ubicación.

Para La Colonia se mantienen separados:

```text
la_colonia_online = contexto fuente raw, no comercial
la_colonia_sps    = ubicación comercial candidata dentro del alcance
la_colonia_tgu    = ubicación comercial conocida fuera del alcance inicial
```

Estado de `la_colonia_sps`:

```text
granularity = unknown
technical_binding_confirmed = false
source_location_key = null
extraction_enabled = false
```

Registrar una ciudad visible no demuestra granularidad comercial. Antes de etiquetar precios como SPS debe saberse si precio/inventario cambia por ciudad, tienda u otro nivel y debe existir un binding técnico verificable.

## Persistencia inicial

Las tablas comunes actuales son:

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

`dim_products` contiene atributos normalizados/canónicos y no replica columnas de supermercado, ubicación, precio o run. `map_source_products` conserva la relación entre identidad fuente y `product_id`; allí viven también los mappings pendientes de revisión.

El diseño protege estas reglas:

- una sola estructura para todos los supermercados;
- current/history rehidratables y restaurables entre runners;
- nuevo periodo sólo ante un cambio comercial relevante;
- todo run final queda registrado aunque no haya cambios;
- replay durable idéntico se reconoce por evidencia ligada; divergencia falla;
- runs rechazados/fallidos no contaminan current/history ni materializan dimensión/mapping comercial;
- escritura atómica planificada mediante `spreadsheets.batchUpdate`;
- lectura de Google Sheets separada de la frontera de escritura;
- ninguna decisión caller-controlled puede conceder autoridad productiva.

El siguiente paso del storage es ejecutar desde `main` el workflow seguro con la service account ya prevista: primero `mode=check`, luego `apply-config` para materializar/actualizar las ocho tabs, y finalmente otro `check` de read-back. No se deben escribir ofertas para demostrar esa ruta.

BigQuery queda para una fase posterior, cuando el proceso esté estable.

## Power BI

Power BI será el dashboard del proyecto. La proyección semántica común ya centraliza:

- producto, marca y presentación;
- supermercado y ubicación + certeza de ubicación;
- precio actual;
- baseline histórico aceptado anterior;
- monto/porcentaje de reducción real y dirección del precio;
- precio regular/referencia declarado por la tienda como dato separado;
- promoción y disponibilidad;
- estado de revisión de la normalización.

El dataset/refresh productivo sigue bloqueado hasta disponer de persistencia comercial autoritativa.

## Orden de avance

```text
cerrar preflights de infraestructura sin tocar La Colonia
-> radiografía y binding de ubicación con nueva autorización humana
-> validación live exacta del catálogo
-> aceptación autoritativa
-> persistencia comercial en Google Sheets
-> ejecución diaria
-> dataset/refresh Power BI
-> cerrar La Colonia end-to-end
-> supermercado #2
```

## Pruebas

Desde la raíz del monorepositorio:

```bash
python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts
pytest precios-supermercados-sps/tests
```

La suite también ejecuta la suite Node canónica declarada en `edge/cloudflare/package.json` y la auditoría fail-closed de GitHub Actions.

## Seguridad live

Sin una autorización humana explícita y vigente están prohibidos nuevos HTTP/VTEX/GraphQL/Playwright/crawler/diagnostics/facet discovery/smoke/full crawl hacia La Colonia.

No se inventan ni reutilizan authorization IDs. `production_authority` y `catalog_accepted` sólo pueden cambiar por una frontera explícita que aporte evidencia suficiente; una prueba offline, un fingerprint de replay, un workbook físico o una radiografía de ubicación no los concede.
