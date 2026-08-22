# Precios de Supermercados de San Pedro Sula

Proyecto para recolectar, normalizar, validar, historizar y comparar precios de supermercados con alcance inicial en San Pedro Sula.

> Estado operativo vigente: [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md)  
> Arquitectura estable: [`docs/arquitectura.md`](docs/arquitectura.md)

## Estado actual

Corte verificado al **2026-08-22 (America/Tegucigalpa)**:

- base técnica del corte: `da342bf9439e260a8bc213c8c83e805412c5741d` (merge de **#154**);
- último PR documental integrado antes de este corte: **#155**;
- última suite completa observada: **1462/1462 pruebas aprobadas** + `compileall`;
- GATE-17: `PASS_PRODUCTIVE_EVIDENCE`;
- no existe autorización live activa para La Colonia;
- `READY_FOR_LIVE=NO`;
- SPS technical context: `UNCONFIRMED`;
- `production_authority=false`;
- `catalog_accepted=false`.

La sonda Cloudflare contra infraestructura propia **sí fue ejecutada físicamente**. El run `32551882793` demostró OIDC, Durable Object, fetch al origen controlado y receipt Ed25519; un verifier-only posterior revalidó firma/bytes/identidad. La reconciliación estricta del custom span contra la API pública de Workers Observability permanece sin cerrar porque esa API no expone el detalle requerido. El verificador no se rebajó para fabricar un PASS.

La persistencia Google Sheets está implementada offline hasta el adapter read-modify-write, rehidratación/restauración durable, bootstrap manual y batch comercial. PR #150–#153 añadieron además guard de autoridad, binding durable de replay y un loader read-only Google Sheets → estado comercial restaurado.

Además, ya existe un workbook físico canónico **`Precios Supermercados SPS - Storage`** en la cuenta Google conectada. Se materializaron y releyeron las seis tablas comunes con configuración fail-closed; las cuatro tablas `fact_*` permanecen sin filas. Esto demuestra el artefacto físico de storage, pero **no** demuestra todavía la ruta GitHub Actions → service account → Google Sheets ni autoriza persistencia de ofertas.

PR #154 añadió una proyección semántica read-only para Power BI que centraliza precio actual, baseline histórico aceptado, ahorro real, dirección del precio, precio regular reportado, promoción, disponibilidad, certeza de ubicación y estado de revisión. Power BI no debe recalcular estas reglas por su cuenta.

La Colonia SPS continúa deliberadamente bloqueada:

```text
granularity = unknown
technical_binding_confirmed = false
source_location_key = null
extraction_enabled = false
```

PR #145–#148 dejaron preparada una radiografía mínima y sanitizada para decidir si el contexto comercial varía por `city` o por `store`. Su workflow sigue bloqueado, el fuse live está apagado y la allow-list de autorizaciones está vacía.

**Cualquier siguiente acción live sobre La Colonia requiere una nueva autorización humana explícita.** Mientras tanto pueden seguir avanzando verificaciones de infraestructura que no contacten la fuente.

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

El workbook físico ya refleja este contrato y tiene timezone `America/Tegucigalpa`. Su configuración conserva a SPS dentro de alcance pero con extracción apagada y binding técnico no confirmado; Tegucigalpa permanece fuera del alcance inicial. No hay ofertas, históricos, runs ni quality events persistidos todavía.

El diseño protege estas reglas:

- una sola estructura para todos los supermercados;
- current/history rehidratables y restaurables entre runners;
- nuevo periodo sólo ante un cambio comercial relevante;
- todo run final queda registrado aunque no haya cambios;
- replay durable idéntico se reconoce por evidencia ligada; divergencia falla;
- runs rechazados/fallidos no contaminan current/history;
- materialización del workbook como snapshot completo;
- escritura atómica planificada mediante `spreadsheets.batchUpdate`;
- lectura de Google Sheets separada de la frontera de escritura;
- ninguna decisión caller-controlled puede conceder autoridad productiva.

La ruta pendiente de storage es enlazar este workbook a GitHub Actions mediante una service account dedicada, validar primero `mode=check` read-only y sólo después comprobar `apply-config`. Eso no requiere tráfico a La Colonia.

BigQuery y Cloud Run se reservan para una fase posterior, cuando el proceso esté estable.

## Power BI

Power BI será el dashboard del proyecto. La proyección semántica offline ya expone, entre otros:

- producto, marca y presentación;
- supermercado y ubicación + certeza de ubicación;
- precio actual;
- precio histórico aceptado anterior;
- monto/porcentaje de reducción real y dirección del precio;
- precio regular/referencia declarado por la tienda como dato separado;
- promoción y disponibilidad;
- estado de revisión de la normalización;
- fecha de observación y runs de referencia.

El dataset/refresh productivo sigue bloqueado hasta disponer de persistencia comercial autoritativa.

## Orden de avance

```text
radiografía y binding de ubicación
-> validación live exacta del catálogo
-> aceptación autoritativa
-> persistencia comercial en Google Sheets
-> ejecución diaria
-> dataset/refresh Power BI
-> cerrar La Colonia end-to-end
-> supermercado #2
```

La infraestructura física de Google Sheets ya existe; la autenticación de GitHub Actions sigue siendo una dependencia externa separada de la autorización live de La Colonia.

## Pruebas

Desde la raíz del monorepositorio:

```bash
python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts
pytest precios-supermercados-sps/tests
```

La suite también cubre componentes Node del edge Cloudflare y auditoría fail-closed de GitHub Actions.

Último resultado completo observado antes de esta actualización documental:

```text
1462 passed
compileall PASS
```

## Seguridad live

Sin una autorización humana explícita y vigente están prohibidos nuevos HTTP/VTEX/GraphQL/Playwright/crawler/diagnostics/facet discovery/smoke/full crawl hacia La Colonia.

No se inventan ni reutilizan authorization IDs. `production_authority` y `catalog_accepted` sólo pueden cambiar por una frontera explícita que aporte evidencia suficiente; una prueba offline, un fingerprint de replay, un workbook físico o una radiografía de ubicación no los concede.
