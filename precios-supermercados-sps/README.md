# Precios de Supermercados de San Pedro Sula

Proyecto para recolectar, normalizar, validar, historizar y comparar precios de supermercados con alcance inicial en San Pedro Sula.

> Estado operativo vigente: [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md)  
> Arquitectura estable: [`docs/arquitectura.md`](docs/arquitectura.md)  
> Modelo de datos: [`docs/modelo-datos.md`](docs/modelo-datos.md)

## Estado actual

Corte verificado al **2026-08-22 (America/Tegucigalpa)**:

- contratos `RawProduct -> NormalizedOffer -> ValidatedOffer`: conectados operacionalmente;
- contexto raw de ubicación separado de ubicación comercial;
- identidad de producto con GTIN fuerte, mapping pendiente explícito y revalidación determinista de `prod_pending_*`;
- Google Sheets: ruta productiva de infraestructura `check -> apply-config -> check` demostrada y ocho tablas gestionadas verificadas por read-back;
- última suite completa observada: **1490/1490 PASS**, `python -m pip check` PASS y `compileall` PASS;
- GitHub Actions SPS migradas a generaciones oficiales compatibles con Node 24 y fijadas por SHA completo;
- GATE-17: `PASS_PRODUCTIVE_EVIDENCE`;
- Workers Observability: `BLOCKED_EXTERNAL` por `probe_discovery_trace_missing` en la única re-evaluación controlada del verifier actual;
- `ACTIVE_AUTHORIZATION_IDS=[]`;
- `LIVE_REQUESTS_CURRENT_RUN=0`;
- `READY_FOR_LIVE=NO`;
- `SPS_TECHNICAL_CONTEXT=UNCONFIRMED`;
- `production_authority=false`;
- `catalog_accepted=false`.

La Colonia continúa deliberadamente bloqueada para nuevas peticiones live. El contexto raw utilizado por el extractor es **`la_colonia_online`** y representa únicamente el catálogo público en línea observado; **no es SPS, Tegucigalpa ni una tienda**. Ese contexto permanece `location_status=unknown` hasta que una frontera de binding separada produzca una ubicación comercial demostrada.

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
- barcode ausente/inválido conserva `prod_pending_*` y `pending_product_mapping`;
- un `prod_pending_*` sólo es válido si coincide con el ID determinista derivado de `source_product_id`;
- un mapping explícitamente revisado puede sustituir el provisional sin cambiar la identidad fuente.

No se usa precio, promoción, disponibilidad ni fecha para construir IDs estables. Antes de sumar un segundo supermercado debe existir una política de equivalencia para casos sin GTIN compartido ni mapping revisado; no se unirán productos sólo por semejanza de nombre.

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

El workbook temporal de Google Sheets fue migrado y revalidado físicamente mediante GitHub Actions. Las ocho tablas gestionadas existen; una pestaña ajena al proyecto se preservó y no se introdujeron ofertas para demostrar la infraestructura. El check posterior confirmó que el workbook ya estaba consistente y no necesitaba otra escritura.

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

La infraestructura de storage está lista. La persistencia **comercial** de La Colonia sigue bloqueada por ubicación no confirmada y ausencia de autoridad de catálogo.

BigQuery queda para una fase posterior, cuando el proceso esté estable.

## Cloudflare y Observability

La sonda Cloudflare contra infraestructura propia demostró físicamente OIDC, Durable Object, fetch al origen controlado y receipt Ed25519. El verifier actual exige reconciliación estricta `traces -> events`.

La única re-evaluación controlada sobre la evidencia existente terminó con `probe_discovery_trace_missing`. Ese resultado se conserva como bloqueo externo: no se debilita el verifier, no se repite la sonda sólo para buscar otro resultado y no se contacta La Colonia para resolver este punto.

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
preflights de infraestructura cerrados
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
python -m pip check
python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts
pytest precios-supermercados-sps/tests
```

La suite también ejecuta la suite Node canónica declarada en `edge/cloudflare/package.json` y la auditoría fail-closed de GitHub Actions.

## Seguridad live

Sin una autorización humana explícita y vigente están prohibidos nuevos HTTP/VTEX/GraphQL/Playwright/crawler/diagnostics/facet discovery/smoke/full crawl hacia La Colonia.

No se inventan ni reutilizan authorization IDs. `production_authority` y `catalog_accepted` sólo pueden cambiar por una frontera explícita que aporte evidencia suficiente; una prueba offline, un fingerprint de replay, un workbook físico o una radiografía de ubicación no los concede.
