# Modelo común de datos y almacenamiento

Este documento define el modelo lógico/físico objetivo. El estado operativo mutable vive en [`PROJECT_STATE.md`](PROJECT_STATE.md).

**BigQuery es el backend persistente seleccionado.** Google Sheets queda como legado de una arquitectura anterior y no forma parte del camino objetivo.

## 1. Claves e identidades

```text
supermarket_id    = supermercado
location_id       = ubicación comercial (ciudad/tienda según granularidad demostrada)
source_product_id = producto estable dentro de la fuente
product_id        = identidad comparable entre fuentes
offer_id          = supermercado + ubicación + source_product_id
scrape_run_id     = ejecución
```

Precio, promoción, disponibilidad y timestamps no forman parte de identidades estables.

## 2. Relaciones principales

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
productos    N ─── 1 product_id canónico mediante product_mapping
```

La ciudad no se guarda como atributo del producto. Se resuelve mediante `location_id` en observaciones de precio/inventario.

## 3. `supermarkets`

**Grain:** una fila por supermercado.

Campos mínimos:

```text
supermarket_id STRING NOT NULL
supermarket_name STRING NOT NULL
country_code STRING NOT NULL
location_selection_mode STRING NOT NULL
is_active BOOL NOT NULL
```

Clave lógica: `supermarket_id`.

## 4. `locations`

**Grain:** una fila por ubicación comercial.

```text
location_id STRING NOT NULL
supermarket_id STRING NOT NULL
city_id STRING NOT NULL
city_name STRING NOT NULL
granularity STRING NOT NULL
source_location_key STRING
is_available BOOL NOT NULL
in_scope BOOL NOT NULL
technical_binding_confirmed BOOL NOT NULL
evidence STRING
```

Clave lógica: `location_id`.

Ejemplo conceptual:

```text
la_colonia_sps -> la_colonia -> sps -> San Pedro Sula -> city
```

## 5. `productos`

**Grain:** una fila por producto/SKU fuente estable dentro de un supermercado.

La tabla conserva tanto la identidad fuente como la identidad canónica asociada. Esto permite trabajar correctamente con una sola fuente y llegar preparado a comparación cross-supermercado sin mezclar ciudad/precio/inventario dentro del producto.

Campos objetivo:

```text
source_product_id STRING NOT NULL
supermarket_id STRING NOT NULL
product_id STRING NOT NULL
source_key_type STRING NOT NULL
source_key STRING NOT NULL
source_catalog_product_id STRING
source_item_id STRING
source_sku STRING
ean STRING
canonical_gtin STRING
source_name STRING NOT NULL
normalized_name STRING NOT NULL
source_brand STRING
normalized_brand STRING
source_category STRING
category STRING
subcategory STRING
source_presentation STRING
presentation_normalized STRING NOT NULL
presentation_kind STRING
unit_count INT64
content_per_unit NUMERIC
measurement_unit STRING
declared_content NUMERIC
content_scope STRING
total_content NUMERIC
normalization_status STRING NOT NULL
normalization_method STRING NOT NULL
product_url STRING
image_url STRING
first_seen_at_utc TIMESTAMP
last_seen_at_utc TIMESTAMP
last_scrape_run_id STRING
```

Clave lógica: `source_product_id`.

Reglas:

- `source_*` preserva la evidencia original;
- los campos normalizados nunca borran silenciosamente el valor fuente;
- `presentation_normalized` del snapshot actual de La Colonia tiene cobertura 9,439/9,439;
- un nuevo formato ambiguo puede quedar pendiente en una observación futura sin inventar contenido.

## 6. `precios_historicos`

**Grain:** una observación de precio por producto fuente + ubicación + run/instante.

```text
price_observation_id STRING NOT NULL
supermarket_id STRING NOT NULL
location_id STRING NOT NULL
source_product_id STRING NOT NULL
product_id STRING NOT NULL
currency STRING NOT NULL
current_price NUMERIC NOT NULL
reported_regular_price NUMERIC
is_promotion BOOL NOT NULL
promotion_evidence STRING
observed_at_utc TIMESTAMP NOT NULL
scrape_run_id STRING NOT NULL
extractor_version STRING
schema_version STRING
```

No existe una columna genérica `precio`/`price`.

`current_price` es el precio efectivo observado. `reported_regular_price` es la referencia regular/tachada declarada por la tienda cuando existe. `previous_price` se deriva del histórico y no se persiste como alias.

### Historia diaria

Se conserva una observación por run comercial exitoso aunque el precio no cambie. Esto permite diferenciar:

```text
precio igual observado hoy
vs
no hubo observación hoy
```

Partición: `DATE(observed_at_utc)`.

Clustering inicial: `supermarket_id`, `location_id`, `source_product_id`.

## 7. `inventario_historico`

**Grain:** una observación de disponibilidad/cantidad por producto fuente + ubicación + seller + run/instante.

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
quantity_is_exact BOOL
observed_at_utc TIMESTAMP NOT NULL
scrape_run_id STRING NOT NULL
extractor_version STRING
schema_version STRING
```

`available_quantity_observed` significa cantidad reportada/observada por la fuente. No equivale automáticamente a inventario físico exacto ni ventas.

Partición: `DATE(observed_at_utc)`.

Clustering inicial: `supermarket_id`, `location_id`, `source_product_id`.

## 8. `scrape_runs`

**Grain:** una fila por ejecución terminal.

Campos objetivo mínimos:

```text
scrape_run_id STRING NOT NULL
supermarket_id STRING NOT NULL
location_id STRING NOT NULL
run_status STRING NOT NULL
catalog_accepted BOOL NOT NULL
started_at_utc TIMESTAMP NOT NULL
finished_at_utc TIMESTAMP NOT NULL
catalog_products_reported INT64
unique_products_observed INT64
skus_observed INT64
skus_with_price INT64
requests_completed INT64
catalog_coverage NUMERIC
warnings_count INT64
errors_count INT64
extractor_version STRING
schema_version STRING
run_evidence_id STRING
```

Todo run terminal se registra. Un run rechazado/fallido no crea observaciones comerciales aceptadas.

Partición: `DATE(started_at_utc)`.

## 9. `quality_events`

**Grain:** una fila por evento de calidad.

```text
quality_event_id STRING NOT NULL
scrape_run_id STRING NOT NULL
supermarket_id STRING NOT NULL
location_id STRING NOT NULL
source_product_id STRING
category STRING NOT NULL
severity STRING NOT NULL
event_code STRING NOT NULL
observed_at_utc TIMESTAMP NOT NULL
```

Partición: `DATE(observed_at_utc)`.

## 10. `normalization_overrides`

**Grain:** una corrección versionada para una identidad/campo fuente.

```text
override_id STRING NOT NULL
supermarket_id STRING NOT NULL
source_product_id STRING NOT NULL
source_signature STRING NOT NULL
field_name STRING NOT NULL
source_value STRING
override_value STRING NOT NULL
reason STRING
active BOOL NOT NULL
created_at_utc TIMESTAMP
updated_at_utc TIMESTAMP
```

Durante el MVP, Git/versionado conserva la autoridad de las correcciones. La tabla BigQuery sirve para auditoría/operación; no se aceptan ediciones silenciosas que diverjan de la fuente versionada.

## 11. `product_mapping`

**Grain:** relación entre producto fuente y producto canónico.

```text
source_product_id STRING NOT NULL
supermarket_id STRING NOT NULL
product_id STRING NOT NULL
mapping_status STRING NOT NULL
mapping_method STRING NOT NULL
canonical_gtin STRING
review_reason STRING
last_observed_at_utc TIMESTAMP
last_scrape_run_id STRING
```

Cuando exista supermercado #2, múltiples `source_product_id` pueden apuntar al mismo `product_id` si la equivalencia está demostrada.

## 12. Views derivadas

### `vw_precios_actuales`
Última observación por supermercado + ubicación + producto fuente.

### `vw_inventario_actual`
Última observación de inventario por supermercado + ubicación + producto fuente/seller.

### `vw_ofertas_actuales`
Join de `productos`, `locations`, precio actual e inventario actual para Dash.

### Precio anterior / variación
Se deriva con funciones de ventana (`LAG`) sobre `precios_historicos`; `reported_regular_price` nunca sustituye al precio anterior.

## 13. Current/history del motor vs tablas BigQuery

El motor Python backend-neutral mantiene semántica de transición, `state_hash`, replay y rehidratación. Sus periodos no obligan a usar una tabla física SCD como único histórico analítico.

BigQuery conserva observaciones temporales para Dash/análisis. Las vistas derivan estado actual y cambios. Ambas capas deben reconciliarse en pruebas para evitar divergencia semántica.

## 14. Google Sheets legado

Las tablas/tabs del adapter Sheets existente son legado y no definen el nuevo contrato físico. No se escribirá el catálogo en Google Sheets ni se añadirán nuevas dependencias sobre ese backend.

La retirada del legado se hará de forma controlada después de que el contrato/adapter BigQuery esté probado.

## 15. Consumidor

Python Dash + Plotly consume views BigQuery y no redefine identidad, ahorro real ni disponibilidad. El dashboard no scrapea ni concede autoridad.
