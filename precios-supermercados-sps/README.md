# Precios de Supermercados de San Pedro Sula

Proyecto para recolectar, normalizar, validar, historizar y comparar precios de supermercados con alcance inicial en San Pedro Sula.

> Estado operativo vigente: [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md)  
> Arquitectura estable: [`docs/arquitectura.md`](docs/arquitectura.md)

## Estado actual

Corte verificado al **2026-08-22 (America/Tegucigalpa)**:

- `main`: `b4588d7425601963cc64cc6eec779fdbe9492b05` al abrir este corte documental;
- último PR técnico integrado: **#148**;
- última suite completa observada: **1418/1418 pruebas aprobadas** + `compileall`;
- GATE-17: `PASS_PRODUCTIVE_EVIDENCE`;
- no existe autorización live activa para La Colonia;
- `READY_FOR_LIVE=NO`;
- SPS technical context: `UNCONFIRMED`;
- `production_authority=false`;
- `catalog_accepted=false`.

La sonda Cloudflare contra infraestructura propia **sí fue ejecutada físicamente**. El run `32551882793` demostró OIDC, Durable Object, fetch al origen controlado y receipt Ed25519; un verifier-only posterior revalidó firma/bytes/identidad. La reconciliación estricta del custom span contra la API pública de Workers Observability permanece sin cerrar porque esa API no expone el detalle requerido. El verificador no se rebajó para fabricar un PASS.

La persistencia Google Sheets está implementada **offline** hasta el adapter read-modify-write, rehidratación durable, bootstrap manual y batch comercial. No se considera productiva todavía porque no se ha observado una escritura real con la configuración externa prevista.

La Colonia SPS continúa deliberadamente bloqueada:

```text
granularity = unknown
technical_binding_confirmed = false
source_location_key = null
extraction_enabled = false
```

PR #145–#148 dejaron preparada una radiografía mínima y sanitizada para decidir si el contexto comercial varía por `city` o por `store`. Su workflow sigue con `if: ${{ false }}`, el fuse live está apagado y la allow-list de autorizaciones está vacía.

**El siguiente paso que requiere intervención humana es una nueva autorización explícita para esa única radiografía de ubicación.** Esa autorización no cubriría crawl, smoke, facets, GraphQL replay ni persistencia de precios.

## Contratos protegidos

- `RawProduct`: observación fiel a la fuente.
- `NormalizedOffer`: formato común sin inventar datos faltantes.
- `ValidatedOffer`: oferta validada con identidad, `state_hash`, revisión y evidencia de calidad.

Una oferta `in_stock` exige `current_price > 0`. Estados `out_of_stock`, `not_listed` y `unknown` pueden conservar precio nulo.

## Regla comercial del histórico

`reported_regular_price` es un dato informado por el supermercado; **no demuestra ahorro real**.

La reducción real se calcula contra el `current_price` del periodo histórico **aceptado inmediatamente anterior**. `reported_regular_price` e `is_promotion` no participan en esa fórmula. Si no existe baseline confiable, no se inventa una reducción.

Runs `rejected`, `failed`, `abandoned` o no autoritativos no alteran current/history.

## Ubicaciones

Todos los supermercados comparten el mismo modelo de ubicación. Para La Colonia se conocen San Pedro Sula y Tegucigalpa; únicamente SPS está dentro del alcance inicial.

Registrar una ciudad visible no demuestra granularidad comercial. Antes de habilitar extracción debe saberse si el precio/inventario cambia por ciudad, tienda u otro nivel y debe existir un binding técnico verificable.

## Persistencia inicial

Google Sheets es el almacenamiento temporal estructurado previsto para la primera fase. Las tablas comunes son:

```text
cfg_supermarkets
cfg_locations
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

El diseño ya protege estas reglas:

- una sola estructura para todos los supermercados;
- current/history rehidratables entre runners;
- nuevo periodo sólo ante un cambio comercial relevante;
- todo run final queda registrado aunque no haya cambios;
- runs rechazados/fallidos no contaminan current/history;
- materialización del workbook como snapshot completo;
- escritura atómica planificada mediante `spreadsheets.batchUpdate`.

BigQuery y Cloud Run se reservan para una fase posterior, cuando el proceso esté estable.

## Power BI

Power BI será el dashboard del proyecto. El dataset deberá permitir, como mínimo:

- producto, marca y presentación;
- supermercado y ubicación comercial correcta;
- precio actual;
- precio histórico anterior;
- precio regular/referencia declarado por la tienda como dato separado;
- promoción y disponibilidad;
- fecha de observación;
- historial de cambios;
- detección de ofertas reales por comparación histórica.

No se conecta Power BI a datos de La Colonia hasta cerrar binding, aceptación y persistencia productiva.

## Orden de avance

```text
radiografía y binding de ubicación
-> validación live exacta del catálogo
-> aceptación autoritativa
-> Google Sheets productivo
-> ejecución diaria
-> Power BI
-> cerrar La Colonia end-to-end
-> supermercado #2
```

## Pruebas

Desde la raíz del monorepositorio:

```bash
python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts
pytest precios-supermercados-sps/tests
```

La suite también cubre componentes Node del edge Cloudflare y auditoría fail-closed de GitHub Actions.

Último resultado completo observado antes de esta actualización documental:

```text
1418 passed
compileall PASS
```

## Seguridad live

Sin una autorización humana explícita y vigente están prohibidos nuevos HTTP/VTEX/GraphQL/Playwright/crawler/diagnostics/facet discovery/smoke/full crawl hacia La Colonia.

No se inventan ni reutilizan authorization IDs. `production_authority` y `catalog_accepted` sólo pueden cambiar por una frontera explícita que aporte evidencia suficiente; una prueba offline o una radiografía de ubicación no los concede.
