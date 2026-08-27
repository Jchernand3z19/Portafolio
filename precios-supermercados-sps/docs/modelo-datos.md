# Modelo común de datos y almacenamiento

Este documento describe el **contrato físico operativo Turso/SQLite** cerrado en código. El estado mutable vive en [`PROJECT_STATE.md`](PROJECT_STATE.md) y la arquitectura estable en [`arquitectura.md`](arquitectura.md).

**Turso es el backend persistente activo.** SQLite `:memory:` ejecuta el mismo DDL/SQL para pruebas offline. BigQuery permanece como implementación legada/futura y Google Sheets como legado retirado.

## 1. Identidades

```text
supermarket_id    = supermercado
location_id       = ubicación comercial demostrada
source_product_id = identidad estable del producto dentro de la fuente
product_id        = identidad canónica/comparable cuando puede demostrarse
offer_id          = supermercado + ubicación + source_product_id
scrape_run_id     = ejecución terminal
offer_history_id  = periodo histórico estable de una oferta
```

Precio, promoción, disponibilidad y timestamps no participan en identidades estables.

Turso/SQLite sí aplica `PRIMARY KEY`, `UNIQUE`, `FOREIGN KEY`, `CHECK` y tablas `STRICT` donde el contrato los declara. La aplicación revalida además IDs deterministas y fingerprints antes de mutar.

## 2. Esquema y migraciones

El contrato ejecutable está en `src/precios_supermercados/turso_contract.py`.

```text
_schema_version
supermarkets
locations
products
source_products
offers_current
offer_history
scrape_runs
quality_events
normalization_overrides
```

`_schema_version` registra la versión física aplicada. El bootstrap activa foreign keys, aplica migraciones incrementales en transacción y falla si la base tiene una versión más nueva que la aplicación.

## 3. Relaciones principales

```text
supermarkets 1 ─── N locations
supermarkets 1 ─── N source_products
products     1 ─── N source_products          [relación lógica producto canónico]
source_products 1 ─── N offers_current        [por ubicación]
source_products 1 ─── N offer_history         [periodos]
locations    1 ─── N offers_current
locations    1 ─── N offer_history
scrape_runs  1 ─── N offers_current/history   [runs de apertura/última observación]
scrape_runs  1 ─── N quality_events
source_products 1 ─── N normalization_overrides
```

La ciudad pertenece a `locations` y se referencia desde la oferta por `location_id`; no participa en `product_id`.

## 4. `supermarkets`

**Grain:** una fila por supermercado.  
**Primary key:** `supermarket_id`.

```text
supermarket_id
supermarket_name
country_code
location_selection_mode
is_active
```

## 5. `locations`

**Grain:** una fila por ubicación comercial.  
**Primary key:** `location_id`.

```text
location_id
supermarket_id
city_id
city_name
granularity
source_location_key
is_available
in_scope
extraction_enabled
technical_binding_confirmed
evidence
```

`extraction_enabled` controla tráfico futuro. No se convierte en `true` por persistir un snapshot histórico aprobado.

## 6. `products`

**Grain:** una fila por identidad canónica/comparable.  
**Primary key:** `product_id`.

```text
product_id
canonical_gtin
identity_kind
```

`identity_kind` distingue identidad fuerte GTIN, explícita o pendiente según la evidencia disponible. No se hace fuzzy matching automático para fusionar supermercados.

## 7. `source_products`

**Grain:** una fila por identidad estable dentro del supermercado.  
**Primary key:** `source_product_id`.  
**Unique:** `(supermarket_id, source_key_type, source_key)`.

Conserva, entre otros:

```text
source_product_id
supermarket_id
source_key_type
source_key
source_sku
source_name
source_brand
source_presentation
barcode
product_url
image_url
product_id
mapping_status
mapping_method
review_reason
normalized_name
normalized_brand
category
subcategory
variant
unit_count
content_per_unit
measurement_unit
total_content
review_status
last_observed_at_utc
last_scrape_run_id
```

Los 474 SKU sin identidad fuerte permanecen `mapping_status=pending`; no se eliminan ni se fusionan por similitud textual.

## 8. `offers_current`

**Grain:** último estado comercial aceptado por `offer_id`.  
**Primary key:** `offer_id`.  
**Unique:** `(supermarket_id, location_id, source_product_id)`.

La tabla conserva las columnas backend-neutral de `FACT_OFFERS_CURRENT` para poder rehidratar el motor comercial, más la proyección física:

```text
current_price_minor
reported_regular_price_minor
seller_id
available_quantity_observed
availability_evidence
quantity_is_exact
```

Campos comerciales esenciales del contrato lógico incluyen:

```text
offer_id
supermarket_id
location_id
source_product_id
product_id
currency
current_price
reported_regular_price
is_promotion
availability
state_hash
review_status
observed/validated timestamps
last_observed_at_utc
last_scrape_run_id
```

`current_price_minor` y `reported_regular_price_minor` son enteros en centavos HNL. No reemplazan el valor decimal lógico; son una representación física segura para aritmética monetaria.

## 9. `offer_history`

**Grain:** un periodo comercial continuo por oferta/estado.  
**Primary key:** `offer_history_id`.

Conserva las columnas backend-neutral de `FACT_OFFER_HISTORY` más la misma proyección física de precio/inventario que `offers_current`.

Semántica:

```text
primera observación aceptada -> abre periodo
confirmación idéntica        -> NO crea periodo nuevo
cambio comercial real        -> cierra periodo abierto + abre otro
run rechazado                -> no muta historia
replay exacto                -> no duplica
```

Campos de trazabilidad incluyen `change_type`, `changed_fields_json`, `valid_from_utc`, `valid_to_utc`, `opened_by_scrape_run_id`, `closed_by_scrape_run_id`, `last_confirmed_by_scrape_run_id` y `last_observed_at_utc`.

`previous_price` se deriva del `current_price` del periodo aceptado inmediatamente anterior. `reported_regular_price` nunca se usa como sustituto.

## 10. `scrape_runs`

**Grain:** una fila por ejecución terminal.  
**Primary key:** `scrape_run_id`.  
**Inmutable por identidad de run.**

```text
scrape_run_id
run_fingerprint
supermarket_id
location_id
run_status
catalog_accepted
commercial_update_allowed
started_at_utc
finished_at_utc
products_observed
offers_observed
current_created
current_changed
current_confirmed
offers_ignored
quality_event_count
run_evidence_id
catalog_products_reported
unique_products_extracted
skus_extracted
skus_with_price
catalog_product_coverage
```

Cada run terminal se registra aunque no haya cambios comerciales. El mismo `scrape_run_id` + fingerprint es replay exacto; un fingerprint diferente bajo el mismo ID falla cerrado.

## 11. `quality_events`

**Grain:** una fila por evento auditable.  
**Primary key:** `quality_event_id`.  
**Inmutable.**

```text
quality_event_id
scrape_run_id
supermarket_id
location_id
offer_id
source_product_id
category
severity
event_code
observed_at_utc
```

Runs rechazados pueden conservar sus quality events sin contaminar current/history.

## 12. `normalization_overrides`

**Grain:** una corrección manual/versionada explícita.  
**Primary key:** `override_id`.

```text
override_id
supermarket_id
source_product_id
source_signature
field_name
source_value
override_value
reason
active
created_at_utc
updated_at_utc
```

Un override sólo se reutiliza mientras la firma de la evidencia fuente siga siendo válida.

## 13. Inventario: nulos son información

El snapshot inicial aprobado contiene:

```text
in_stock = 7081
unknown  = 2358
```

No contiene evidencia suficiente para afirmar cantidad/seller en todas las filas. Por ello:

```text
unknown -> unknown
seller_id = NULL cuando no existe evidencia
available_quantity_observed = NULL cuando no existe evidencia
availability_evidence = NULL cuando no existe evidencia
quantity_is_exact = false cuando no puede demostrarse exactitud
```

No se inventa `out_of_stock`.

## 14. Atomicidad y replay

`TursoAdapter.apply()` ejecuta el plan dentro de una transacción. Un fallo parcial hace rollback completo.

Antes de mutar, el adapter busca `scrape_run_id`:

```text
no existe                    -> aplica plan
existe + mismo fingerprint   -> exact replay / no-op
existe + fingerprint distinto -> TursoReplayConflict
```

Las confirmaciones idénticas actualizan el estado actual pero no materializan historia redundante.

## 15. Read-back y rehidratación

`read_back()` recupera source products, current, history, runs y quality events del scope solicitado. `rehydrate()` reconstruye el contrato lógico current/history y usa `offers_current` como evidencia de la última confirmación del periodo abierto cuando esa confirmación no fue reescrita físicamente en history.

La primera carga no se considera correcta sólo por terminar el INSERT: debe reconciliar los conteos y el fingerprint del run leído desde la base.

## 16. BigQuery legado/futuro

Los módulos `bigquery_contract.py`, `bigquery_persistence.py`, adapters, fake client y bootstrap GCP se conservan para no destruir trabajo útil y como posible backend analítico futuro.

Actualmente:

```text
ACTIVE_STORAGE_BACKEND = turso
BigQuery first-load workflow = retired/fail-closed
Google Sheets = retired/fail-closed
```

No se escriben datos a BigQuery desde la ruta productiva activa.
