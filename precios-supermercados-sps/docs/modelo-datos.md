# Modelo común de datos y almacenamiento

Este documento describe el contrato físico BigQuery cerrado en código. El estado operativo mutable vive en [`PROJECT_STATE.md`](PROJECT_STATE.md).

**BigQuery es el único backend persistente activo.** El layout Google Sheets/current-period permanece sólo como legado y motor backend-neutral de transición; no define las tablas productivas.

## 1. Identidades

```text
supermarket_id    = supermercado
location_id       = ubicación comercial demostrada
source_product_id = identidad estable del producto dentro de la fuente
product_id        = identidad canónica/comparable cuando puede demostrarse
offer_id          = supermercado + ubicación + source_product_id
scrape_run_id     = ejecución terminal
```

Precio, promoción, disponibilidad y timestamps no participan en identidades estables.

BigQuery no aplica primary keys. Cada tabla declara una **logical key** que el adapter debe validar durante insert/upsert/replay.

## 2. Relaciones

```text
supermarkets 1 ─── N locations
supermarkets 1 ─── N productos
productos    1 ─── N precios_historicos
locations    1 ─── N precios_historicos
productos    1 ─── N inventario_historico
locations    1 ─── N inventario_historico
scrape_runs  1 ─── N precios_historicos
scrape_runs  1 ─── N inventario_historico
scrape_runs  1 ─── N quality_events
source product ─── product_mapping ─── product_id
```

La ciudad pertenece a `locations` y a la observación mediante `location_id`; no se duplica dentro de `productos`.

## 3. `supermarkets`

**Grain:** una fila por supermercado.  
**Logical key:** `(supermarket_id)`.

```text
supermarket_id STRING NOT NULL
supermarket_name STRING NOT NULL
country_code STRING NOT NULL
location_selection_mode STRING NOT NULL
is_active BOOL NOT NULL
```

Sin partición ni clustering: dimensión pequeña.

## 4. `locations`

**Grain:** una fila por ubicación comercial.  
**Logical key:** `(location_id)`.  
**Clustering:** `supermarket_id`.

```text
location_id STRING NOT NULL
supermarket_id STRING NOT NULL
city_id STRING NOT NULL
city_name STRING NOT NULL
granularity STRING NOT NULL
source_location_key STRING
is_available BOOL NOT NULL
in_scope BOOL NOT NULL
extraction_enabled BOOL NOT NULL
technical_binding_confirmed BOOL NOT NULL
evidence STRING
```

`extraction_enabled` no se convierte en `true` por existir evidencia técnica; su transición sigue requiriendo autoridad operativa explícita.

## 5. `productos`

**Grain:** una fila por producto fuente estable dentro de un supermercado.  
**Logical key:** `(supermarket_id, source_product_id)`.  
**Clustering:** `supermarket_id`, `normalized_brand`, `category`.

```text
supermarket_id STRING NOT NULL
source_product_id STRING NOT NULL
product_id STRING NOT NULL
source_key_type STRING NOT NULL
source_key STRING NOT NULL
source_sku STRING
source_name STRING NOT NULL
normalized_name STRING NOT NULL
source_brand STRING
normalized_brand STRING
source_presentation STRING
source_category STRING
category STRING
subcategory STRING
variant STRING
unit_count INT64
content_per_unit NUMERIC
measurement_unit STRING
total_content NUMERIC
barcode STRING
product_url STRING NOT NULL
image_url STRING
review_status STRING NOT NULL
first_seen_at_utc TIMESTAMP NOT NULL
last_seen_at_utc TIMESTAMP NOT NULL
last_scrape_run_id STRING NOT NULL
```

Los valores `source_*` se preservan separados de los normalizados. La tabla no contiene ciudad, precio ni inventario.

## 6. `precios_historicos`

**Grain:** una observación de precio por producto + ubicación + run aceptado.  
**Logical key:** `(price_observation_id)`.  
**Partición:** `DATE(observed_at_utc)`.  
**Clustering:** `supermarket_id`, `location_id`, `source_product_id`.

```text
price_observation_id STRING NOT NULL
supermarket_id STRING NOT NULL
location_id STRING NOT NULL
source_product_id STRING NOT NULL
product_id STRING NOT NULL
currency STRING NOT NULL
current_price NUMERIC
reported_regular_price NUMERIC
is_promotion BOOL NOT NULL
promotion_evidence STRING
observed_at_utc TIMESTAMP NOT NULL
scrape_run_id STRING NOT NULL
extractor_version STRING NOT NULL
schema_version STRING NOT NULL
```

`current_price` es nullable porque una observación `out_of_stock`, `not_listed` o `unknown` puede no tener precio. `reported_regular_price` nunca representa `previous_price`.

Se persiste una observación por run comercial aceptado aunque el precio sea igual al run anterior. Así se distingue:

```text
precio igual observado hoy
!=
no hubo observación hoy
```

`previous_price`, cambio, porcentaje y ahorro real se derivan posteriormente con ventanas SQL sobre observaciones aceptadas.

## 7. `inventario_historico`

**Grain:** una observación de disponibilidad por producto + ubicación + seller cuando exista + run aceptado.  
**Logical key:** `(inventory_observation_id)`.  
**Partición:** `DATE(observed_at_utc)`.  
**Clustering:** `supermarket_id`, `location_id`, `source_product_id`.

```text
inventory_observation_id STRING NOT NULL
supermarket_id STRING NOT NULL
location_id STRING NOT NULL
source_product_id STRING NOT NULL
product_id STRING NOT NULL
seller_id STRING
available_quantity_observed NUMERIC
availability STRING NOT NULL
availability_evidence STRING
quantity_is_exact BOOL NOT NULL
observed_at_utc TIMESTAMP NOT NULL
scrape_run_id STRING NOT NULL
extractor_version STRING NOT NULL
schema_version STRING NOT NULL
```

El snapshot actual no conserva cantidad/seller/evidencia suficiente para completar esos campos. Por tanto:

```text
unknown -> unknown
available_quantity_observed = null cuando no existe evidencia
seller_id = null cuando no existe evidencia
quantity_is_exact = false cuando no puede demostrarse exactitud
```

No se inventa `out_of_stock`, cantidad ni seller.

## 8. `scrape_runs`

**Grain:** una fila por ejecución terminal.  
**Logical key:** `(scrape_run_id)`.  
**Partición:** `DATE(started_at_utc)`.  
**Clustering:** `supermarket_id`, `location_id`, `run_status`.

```text
scrape_run_id STRING NOT NULL
run_fingerprint STRING NOT NULL
run_evidence_id STRING
supermarket_id STRING NOT NULL
location_id STRING NOT NULL
run_status STRING NOT NULL
catalog_accepted BOOL NOT NULL
commercial_update_allowed BOOL NOT NULL
started_at_utc TIMESTAMP NOT NULL
finished_at_utc TIMESTAMP NOT NULL
products_observed INT64 NOT NULL
offers_observed INT64 NOT NULL
quality_event_count INT64 NOT NULL
current_created INT64 NOT NULL
current_changed INT64 NOT NULL
current_confirmed INT64 NOT NULL
offers_ignored INT64 NOT NULL
catalog_products_reported INT64
unique_products_extracted INT64
skus_extracted INT64
skus_with_price INT64
catalog_product_coverage NUMERIC
extractor_version STRING
schema_version STRING
```

`run_fingerprint` liga el ID del run al plan durable completo. Replay exacto con el mismo fingerprint es no-op; el mismo `scrape_run_id` con evidencia diferente falla cerrado.

Todo run terminal se registra. Un run rechazado conserva ledger/quality events, pero no crea productos, precios, inventario ni mapping comerciales.

## 9. `quality_events`

**Grain:** una fila por evento auditable.  
**Logical key:** `(quality_event_id)`.  
**Partición:** `DATE(observed_at_utc)`.  
**Clustering:** `supermarket_id`, `location_id`, `event_code`.

```text
quality_event_id STRING NOT NULL
scrape_run_id STRING NOT NULL
supermarket_id STRING NOT NULL
location_id STRING NOT NULL
source_product_id STRING
offer_id STRING
category STRING NOT NULL
severity STRING NOT NULL
event_code STRING NOT NULL
observed_at_utc TIMESTAMP NOT NULL
```

## 10. `normalization_overrides`

**Grain:** una corrección manual/versionada explícita.  
**Logical key:** `(override_id)`.  
**Clustering:** `supermarket_id`, `source_product_id`, `status`.

```text
override_id STRING NOT NULL
supermarket_id STRING NOT NULL
source_product_id STRING NOT NULL
source_signature STRING NOT NULL
field_name STRING NOT NULL
source_value STRING
override_value STRING
reason STRING NOT NULL
status STRING NOT NULL
created_at_utc TIMESTAMP NOT NULL
updated_at_utc TIMESTAMP NOT NULL
```

No existe una fila por producto por defecto. Un override se materializa sólo cuando existe una excepción explícita. `source_signature` impide reutilizar silenciosamente la corrección si cambia la evidencia fuente.

Durante el MVP, Git/versionado sigue siendo la autoridad de las reglas; BigQuery materializa evidencia operativa/auditable.

## 11. `product_mapping`

**Grain:** relación fuente → producto canónico dentro del supermercado.  
**Logical key:** `(supermarket_id, source_product_id)`.  
**Clustering:** `supermarket_id`, `mapping_status`.

```text
supermarket_id STRING NOT NULL
source_product_id STRING NOT NULL
product_id STRING NOT NULL
mapping_status STRING NOT NULL
mapping_method STRING NOT NULL
canonical_gtin STRING
review_reason STRING
last_observed_at_utc TIMESTAMP NOT NULL
last_scrape_run_id STRING NOT NULL
```

GTIN válido puede resolver mapping automáticamente. Sin identidad fuerte se conserva mapping `pending`/singleton; la observación no se descarta.

## 12. Atomicidad e idempotencia

El adapter productivo no confía en “insert succeeded”. El flujo es:

```text
BigQueryWritePlan validado
-> staging efímero por tabla/run
-> una transacción DML sobre tablas destino
-> COMMIT
-> limpieza best-effort de staging
```

Las observaciones y ledger son inmutables por logical key. Dimensiones/mapping/overrides son upsertables. Un fallo antes o dentro de la transacción no debe dejar un subconjunto durable del run.

El fake client replica estas invariantes offline y permite inyectar fallo después de N mutaciones staged para demostrar rollback.

## 13. Read-back / reconciliación

`BigQueryAdapter.read_back()` reconstruye por supermercado/ubicación:

- productos;
- última observación de precio por `source_product_id`;
- última observación de inventario por `source_product_id`;
- runs ordenados.

Los tests reconcilian dos representaciones deliberadamente distintas:

```text
motor Python current/history = periodos y transición comercial
BigQuery                   = observaciones analíticas por run aceptado
```

Un run con precio idéntico confirma el periodo Python sin abrir otro, pero añade una nueva observación BigQuery. Un cambio real abre/cierra periodos Python y también añade su observación BigQuery.

## 14. Views derivadas — siguiente consumidor, no parte del bootstrap actual

Cuando exista la primera carga durable se crearán/validarán las views de consumo:

- `vw_precios_actuales`;
- `vw_inventario_actual`;
- `vw_ofertas_actuales`;
- derivaciones de `previous_price`, `price_change`, `price_change_pct`, `real_saving`.

Dash consumirá estas reglas; no las redefinirá.

## 15. Google Sheets legado

El planner/adapter de Sheets se conserva sólo como evidencia de la etapa anterior y está ligado a nombres `LEGACY_SHEETS_*`. No importa `ACTIVE_STORAGE_TABLE_SPECS`.

El workflow legado queda fail-closed con `allowed=false`, por lo que el job que porta credenciales no puede ejecutar. No se agregará funcionalidad nueva a esa ruta.
