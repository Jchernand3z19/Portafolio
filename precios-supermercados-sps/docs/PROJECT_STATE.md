# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo físico en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md).

GitHub sigue siendo la fuente de verdad para `main`, SHA, PRs y CI. Este archivo no duplica esos valores transitorios para no quedar obsoleto al fusionar el mismo cambio que lo actualiza.

## Corte actual

Estado verificado al **2026-08-27 UTC**:

```text
SPS_TECHNICAL_CONTEXT = CONFIRMED
location_id = la_colonia_sps
granularity = city
technical_binding_confirmed = true
full_catalog_validation_passed = true
full_crawl = true
products_normalized = 9439 / 9439
presentation_pending = 0
history_change_integration = verified_offline
tabular_rehydrate_restore_cycle = verified_offline
persistent_backend_selected = bigquery
bigquery_contract = verified_offline
bigquery_adapter = verified_offline
bigquery_fake_client = verified_offline
bigquery_bootstrap = verified_offline
bigquery_first_load = simulated_offline
bigquery_replay = verified_offline
bigquery_partial_failure = verified_offline
bigquery_read_back = verified_offline
google_sheets_selected = false
google_sheets_productive_path = retired_fail_closed
google_sheets_writes = false
first_durable_bigquery_load = false
commercial_persistence = false
catalog_accepted = false
production_authority = false
extraction_enabled = false
ACTIVE_AUTHORIZATION_IDS = []
```

`ACTIVE_AUTHORIZATION_IDS = []` significa que no existe autorización live vigente. La evidencia histórica **no se interpreta como autorización abierta**. Cualquier nuevo tráfico contra La Colonia requiere una autorización humana nueva y explícita.

No se necesita tráfico live para la frontera BigQuery actual: el catálogo ya descargado es evidencia suficiente para continuar todo lo que sea estrictamente offline.

## One-shot full catalog — consumido

La autorización humana para obtener una vez el catálogo completo read-only de La Colonia San Pedro Sula terminó correctamente en el intento #15.

```text
authorization_mode = one_time_full_catalog_after_staged_validation
authorized_at_utc = 2026-08-25T21:13:44Z
termination_condition = first_successful_downloadable_full_sps_catalog
termination_condition_met = true
attempt_sequence = 15
active = false
```

Fingerprint técnico SPS preservado:

```text
sps_region_fingerprint = d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
```

No se persisten cookies, `regionId` raw, sesión, headers ni URLs sensibles.

## Catálogo completo — técnicamente aceptado, no promovido a autoridad comercial

Evidencia del intento #15:

```text
run_id = 32922877781
artifact_id = 9590684834
artifact_name = la-colonia-sps-data-32922877781
result = success
catalog_complete = true
validation_passed = true
catalog_product_coverage = 1.0
location_verified_same_run = true
catalog_products_reported = 9437
unique_products_extracted = 9437
skus_extracted = 9439
skus_with_price = 9439
skus_without_price = 0
partitions_detected = 62
partitions_completed = 62
product_requests_completed = 252
```

La diferencia 9,439 SKU vs 9,437 `productId` es válida: 9,435 productos tienen un SKU y 2 productos tienen dos SKU. Las 9,439 identidades fuente son únicas.

La capa `la_colonia_operational_artifact` demuestra **completitud técnica** pero prohíbe promover ese assessment por sí mismo a `catalog_accepted=true` o `production_authority=true`. El motor comercial exige que `catalog_accepted` provenga de un collector/verificador autoritativo y el binding durable de replay exige un `authority_evidence_id` real.

Por tanto siguen separados:

```text
technical_catalog_complete = true
catalog_accepted = false
production_authority = false
extraction_enabled = false
```

Esto no es inercia: son fronteras distintas. La primera carga durable puede prepararse desde evidencia ya descargada, pero no se falsificará una autoridad productiva que el contrato actual no demuestra.

## Productos y normalización — cerrado para el snapshot actual

```text
sku_input = 9439
source_keys_unique = 9439
presentation_normalized = 9439
presentation_pending = 0
source_values_preserved = true
versioned_overrides = true
normalization_before_state_hash = true
```

La fuente original permanece separada de valores normalizados. Overrides manuales se ligan a `source_product_id + source_signature`; si cambia la evidencia fuente el override anterior no se reutiliza silenciosamente.

## Historial comercial — verificado offline

El motor backend-neutral verifica:

- primera observación crea current y periodo inicial;
- observación idéntica confirma sin duplicar periodos;
- cambio real de `current_price` cierra el periodo anterior y abre uno nuevo;
- replay exacto es idempotente;
- rehidratación/restauración permite continuar en un proceso nuevo;
- replay durable divergente falla cerrado.

Estas pruebas no equivalen a persistencia cloud.

## BigQuery — frontera offline cerrada

**BigQuery es el único backend físico activo.** `storage_contract.py` ya no presenta Google Sheets como backend activo.

Tablas físicas cerradas:

```text
supermarkets
locations
productos
precios_historicos
inventario_historico
scrape_runs
quality_events
normalization_overrides
product_mapping
```

El contrato define grain, logical key, null semantics, partitioning y clustering. BigQuery no hace cumplir primary keys; el adapter aplica las logical keys y replay explícitamente.

Frontera de implementación:

```text
DOMAIN / CURRENT-HISTORY ENGINE
        ↓
BigQueryWritePlan
        ↓
BigQueryClientPort
        ↓
BigQueryAdapter
        ├─ FakeBigQueryClient
        └─ GoogleCloudBigQueryClient
```

El dominio no importa el SDK de Google.

### Historia analítica

BigQuery conserva una observación por **run comercial aceptado**, incluso cuando el precio no cambió. Así se distingue:

```text
precio igual observado hoy
!=
no hubo observación hoy
```

El motor Python de periodos y el histórico observacional BigQuery son representaciones distintas y reconciliadas por tests.

### Idempotencia y fallo parcial

Offline quedó verificado:

- bootstrap de dataset/tablas con fake;
- primera carga simulada;
- upsert de productos;
- append de precio/inventario;
- `unknown` de inventario permanece `unknown`;
- registro de run/quality events;
- overrides explícitos;
- replay exacto no duplica;
- mismo run con fingerprint distinto falla cerrado;
- fallo parcial no publica un subconjunto del run;
- run rechazado no contamina productos/precios/inventario/mapping;
- read-back reconstruye productos, última observación de precio/inventario y ledger de runs.

El cliente Google Cloud usa staging efímero y una única transacción DML para mutaciones destino. No crea Google Cloud projects ni datasets.

## Google Sheets — retirado

Google Sheets ya no forma parte del camino objetivo.

- `ACTIVE_STORAGE_BACKEND = bigquery`;
- planner/adapter/bootstrap Sheets se conservan sólo como evidencia/compatibilidad histórica y usan constantes `LEGACY_SHEETS_*`;
- el workflow `.github/workflows/precios-supermercados-sps-google-sheets-storage.yml` conserva auditoría histórica pero su preflight emite siempre `allowed=false`;
- el job que porta credenciales sigue condicionado a `allowed == true`, por lo que no puede ejecutar;
- no se añadirá funcionalidad nueva ni se solicitarán nuevas credenciales para Sheets.

## Precio

```text
current_price          = precio efectivo observado
reported_regular_price = precio regular/tachado declarado por la tienda
previous_price         = derivado de una observación histórica aceptada anterior
```

`reported_regular_price` nunca sustituye a `previous_price`. El ahorro real compara `current_price` aceptado actual contra el aceptado anterior.

## Disponibilidad e inventario

El artifact #15 conserva:

```text
availability_in_stock = 7081
availability_unknown = 2358
```

Los 2,358 `unknown` permanecen `unknown`. El snapshot actual no preservó suficientemente `available_quantity_observed`, `availability_evidence` y `seller_id`; esos campos se mantienen `NULL` y `quantity_is_exact=false` cuando no existe evidencia.

Completar inventario de primera clase probablemente requerirá una futura observación live y, por tanto, autorización humana nueva.

## Visualización

La capa de consumo seleccionada es **Python Dash + Plotly**. Power BI queda legado y no recibirá funcionalidad nueva.

Las views previstas después de la primera carga durable son:

```text
vw_precios_actuales
vw_inventario_actual
vw_ofertas_actuales
```

y derivaciones de `previous_price`, `price_change`, `price_change_pct` y `real_saving`. Dash consumirá esas reglas y no las redefinirá.

## Frontera del producto

```text
SOURCE                                  [DONE]
SPS CONTEXT                             [DONE]
FULL CATALOG                            [DONE]
COMPLETENESS / TECHNICAL ACCEPTANCE     [DONE]
PRODUCT NORMALIZATION                   [DONE]
CURRENT / HISTORY SEMANTICS             [DONE OFFLINE]
REHYDRATE / REPLAY                      [DONE OFFLINE]
BIGQUERY CONTRACT                       [DONE OFFLINE]
BIGQUERY ADAPTER + FAKE + BOOTSTRAP     [DONE OFFLINE]
SIMULATED LOAD / REPLAY / ROLLBACK      [DONE OFFLINE]
GOOGLE SHEETS PRODUCTIVE PATH           [RETIRED]
FIRST DURABLE BIGQUERY LOAD              [NEXT — CLOUD/HUMAN BOUNDARY]
INVENTORY EVIDENCE / HISTORY            [PENDING]
DAILY AUTOMATION                        [PENDING]
DASH + PLOTLY                           [PENDING]
TEGUCIGALPA                             [PENDING]
SUPERMARKET #2                          [PENDING]
```

## Próximo paso exacto — frontera humana/cloud

No crear recursos cloud por inferencia.

Antes de la primera escritura durable hace falta una decisión/configuración humana real en Google Cloud:

1. seleccionar o crear el Google Cloud project que será dueño de los datos y confirmar que puede usar billing;
2. habilitar BigQuery API si aún no está habilitada;
3. elegir **dataset ID y región** y crear ese dataset;
4. configurar autenticación de mínimo privilegio para que el runtime pueda consultar, crear/validar tablas dentro de ese dataset, cargar staging y ejecutar DML/transacciones;
5. sólo después ejecutar bootstrap de tablas y la primera carga durable.

La primera carga no requiere volver a consultar La Colonia. Se reutilizará la evidencia offline disponible y cualquier promoción a run comercial autoritativo deberá cumplir el contrato de evidencia, sin inventar `catalog_accepted` ni `production_authority`.
