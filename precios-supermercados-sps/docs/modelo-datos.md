# Modelo común de datos y almacenamiento

## Contratos de aplicación

### `RawProduct`

Representa una observación fiel a la fuente. Conserva identificadores disponibles, textos originales, URL, evidencia de ubicación, auditoría y `raw_values`. No asigna todavía el producto normalizado ni interpreta una oferta real.

### `NormalizedOffer`

Representa la salida común de todos los extractores. Contiene identidad fuente y normalizada, atributos del producto, precio, disponibilidad, ubicación, auditoría y valores originales.

### `ValidatedOffer`

Agrupa una `NormalizedOffer`, su `state_hash`, el momento de validación y eventos de calidad. Es la entrada aprobada para la futura capa de persistencia.

## Vocabularios cerrados

### Disponibilidad

- `in_stock`
- `out_of_stock`
- `not_listed`
- `unknown`

### Ubicación

- `confirmed`
- `inferred`
- `unknown`

### Llave fuente

- `internal_id`
- `sku`
- `barcode`
- `api_id`
- `stable_url`

## Identificadores

| Campo | Regla |
|---|---|
| `source_product_id` | SHA-256 determinista de `supermarket_id`, `source_key_type` y `source_key`; prefijo `sp_`. |
| `product_id` | Identidad normalizada transversal. Se definirá mediante catálogo y revisión, no por precio. |
| `offer_id` | SHA-256 determinista de supermercado, ubicación y `source_product_id`; prefijo `of_`. |
| `state_hash` | SHA-256 completo de atributos relevantes del estado. |

El precio nunca participa en `source_product_id`, `product_id` ni `offer_id`.

## Tabs futuras de Google Sheets

Las fechas se almacenarán en ISO 8601 UTC. Los decimales se escribirán como números, nunca como texto monetario. Las llaves se consideran únicas aunque Google Sheets no aplique restricciones físicas.

### `cfg_supermarkets`

**Propósito:** catálogo de supermercados habilitados y versión del extractor.

**Llave primaria:** `supermarket_id`.

| Columna | Tipo | Obligatorio | Valores o regla |
|---|---|---:|---|
| `supermarket_id` | string | Sí | Slug estable y único. |
| `supermarket_name` | string | Sí | Nombre público. |
| `base_url` | string | Sí | URL absoluta. |
| `active` | boolean | Sí | `true` / `false`. |
| `extractor_version` | string | Sí | Versión semántica. |
| `schema_version` | string | Sí | Versión del contrato. |
| `created_at_utc` | datetime | Sí | ISO 8601 UTC. |
| `updated_at_utc` | datetime | Sí | ISO 8601 UTC. |
| `notes` | string | No | Observaciones no sensibles. |

**Relaciones:** uno a muchos con `cfg_locations`, `map_source_products`, `fact_offers_current` y `fact_scrape_runs`.

### `cfg_locations`

**Propósito:** catálogo de ubicaciones o ámbitos de precio.

**Llave primaria:** `location_id`.

| Columna | Tipo | Obligatorio | Valores o regla |
|---|---|---:|---|
| `location_id` | string | Sí | Identidad estable. |
| `supermarket_id` | string | Sí | FK a `cfg_supermarkets`. |
| `location_name` | string | Sí | Nombre legible. |
| `city` | string | Sí | Inicialmente San Pedro Sula. |
| `location_status` | enum | Sí | `confirmed`, `inferred`, `unknown`. |
| `location_evidence` | string | Condicional | Requerido para confirmed/inferred. |
| `location_confidence` | decimal | Condicional | 0 a 1; requerido para confirmed/inferred. |
| `active` | boolean | Sí | `true` / `false`. |
| `created_at_utc` | datetime | Sí | ISO 8601 UTC. |
| `updated_at_utc` | datetime | Sí | ISO 8601 UTC. |

**Relaciones:** muchos a uno con `cfg_supermarkets`; uno a muchos con ofertas y ejecuciones.

### `dim_products`

**Propósito:** catálogo de productos normalizados comparables entre supermercados.

**Llave primaria:** `product_id`.

| Columna | Tipo | Obligatorio | Valores o regla |
|---|---|---:|---|
| `product_id` | string | Sí | Identidad normalizada estable. |
| `normalized_name` | string | Sí | Nombre canónico. |
| `normalized_brand` | string | Sí | Marca canónica. |
| `category` | string | Sí | Categoría normalizada. |
| `subcategory` | string | Sí | Subcategoría normalizada. |
| `variant` | string | No | Sabor, tipo u otra variante. |
| `unit_count` | integer | Sí | Mayor que cero. |
| `content_per_unit` | decimal | Sí | Mayor que cero. |
| `measurement_unit` | string | Sí | Unidad canónica, por ejemplo `g`, `ml`, `unit`. |
| `total_content` | decimal | Sí | Mayor que cero. |
| `barcode` | string | No | Código de barras cuando exista. |
| `created_at_utc` | datetime | Sí | ISO 8601 UTC. |
| `updated_at_utc` | datetime | Sí | ISO 8601 UTC. |

**Relaciones:** uno a muchos con `map_source_products` y, mediante ese mapeo, con ofertas.

### `map_source_products`

**Propósito:** vincular cada producto fuente con un producto normalizado y conservar trazabilidad.

**Llave primaria:** `source_product_id`.

| Columna | Tipo | Obligatorio | Valores o regla |
|---|---|---:|---|
| `source_product_id` | string | Sí | ID determinista con prefijo `sp_`. |
| `supermarket_id` | string | Sí | FK a `cfg_supermarkets`. |
| `source_key_type` | enum | Sí | `internal_id`, `sku`, `barcode`, `api_id`, `stable_url`. |
| `source_key` | string | Sí | Llave estable original/canónica. |
| `source_sku` | string | No | SKU publicado. |
| `source_name` | string | Sí | Nombre original más reciente. |
| `source_brand` | string | No | Marca original. |
| `source_presentation` | string | No | Presentación original. |
| `source_category` | string | No | Categoría original. |
| `product_url` | string | Sí | URL absoluta del producto. |
| `image_url` | string | No | URL absoluta. |
| `product_id` | string | Sí | FK a `dim_products`. |
| `mapping_status` | enum | Sí | `automatic`, `reviewed`, `rejected`, `pending`. |
| `mapping_confidence` | decimal | Sí | 0 a 1. |
| `first_observed_at_utc` | datetime | Sí | ISO 8601 UTC. |
| `last_observed_at_utc` | datetime | Sí | ISO 8601 UTC. |

**Relaciones:** muchos a uno con `cfg_supermarkets` y `dim_products`; uno a muchos con ofertas.

### `fact_offers_current`

**Propósito:** estado vigente y última observación de cada oferta.

**Llave primaria:** `offer_id`.

| Columna | Tipo | Obligatorio | Valores o regla |
|---|---|---:|---|
| `offer_id` | string | Sí | ID determinista con prefijo `of_`; único. |
| `supermarket_id` | string | Sí | FK a `cfg_supermarkets`. |
| `location_id` | string | Sí | FK a `cfg_locations`. |
| `source_product_id` | string | Sí | FK a `map_source_products`. |
| `product_id` | string | Sí | FK a `dim_products`. |
| `currency` | string | Sí | Código ISO, inicialmente `HNL`. |
| `current_price` | decimal | Sí | Mayor que cero. |
| `reported_regular_price` | decimal | No | Mayor que cero cuando exista. |
| `is_promotion` | boolean | Sí | Indicador observado/normalizado. |
| `unit_price` | decimal | No | Mayor que cero. |
| `unit_price_basis` | string | No | Ejemplo `100 g`, `1 l`, `1 unit`. |
| `availability` | enum | Sí | Cuatro valores aprobados. |
| `state_hash` | string | Sí | SHA-256 hexadecimal. |
| `first_observed_at_utc` | datetime | Sí | Inicio del estado actual. |
| `last_observed_at_utc` | datetime | Sí | Última confirmación, cambie o no. |
| `scrape_run_id` | string | Sí | Última ejecución observadora. |
| `extractor_version` | string | Sí | Versión que produjo el dato. |
| `schema_version` | string | Sí | Versión del contrato. |
| `source_url` | string | Sí | URL de auditoría. |

**Relaciones:** muchos a uno con catálogos y uno a uno con el periodo abierto de `fact_offer_history`.

### `fact_offer_history`

**Propósito:** periodos históricos solo cuando cambia un atributo relevante.

**Llave primaria:** `offer_history_id`.

| Columna | Tipo | Obligatorio | Valores o regla |
|---|---|---:|---|
| `offer_history_id` | string | Sí | ID idempotente del periodo. |
| `offer_id` | string | Sí | FK a `fact_offers_current`. |
| `state_hash` | string | Sí | Estado del periodo. |
| `currency` | string | Sí | Código ISO. |
| `current_price` | decimal | Sí | Mayor que cero. |
| `reported_regular_price` | decimal | No | Valor informado. |
| `is_promotion` | boolean | Sí | Estado del periodo. |
| `availability` | enum | Sí | Cuatro valores aprobados. |
| `normalized_brand` | string | Sí | Marca usada en el hash. |
| `unit_count` | integer | Sí | Mayor que cero. |
| `total_content` | decimal | Sí | Mayor que cero. |
| `measurement_unit` | string | Sí | Unidad canónica. |
| `valid_from_utc` | datetime | Sí | Inicio inclusive. |
| `valid_to_utc` | datetime | No | Fin exclusivo; nulo para actual. |
| `first_scrape_run_id` | string | Sí | Ejecución que abrió el periodo. |
| `last_scrape_run_id` | string | Sí | Última ejecución que confirmó el periodo. |
| `last_observed_at_utc` | datetime | Sí | Última observación del mismo estado. |

**Valor permitido:** solo un registro con `valid_to_utc` vacío por `offer_id`.

### `fact_scrape_runs`

**Propósito:** registrar cada ejecución aunque no existan cambios.

**Llave primaria:** `scrape_run_id`.

| Columna | Tipo | Obligatorio | Valores o regla |
|---|---|---:|---|
| `scrape_run_id` | string | Sí | ID único e idempotente. |
| `supermarket_id` | string | Sí | FK a `cfg_supermarkets`. |
| `location_id` | string | No | FK cuando la ejecución sea por ubicación. |
| `started_at_utc` | datetime | Sí | ISO 8601 UTC. |
| `finished_at_utc` | datetime | No | ISO 8601 UTC. |
| `status` | enum | Sí | `running`, `success`, `partial`, `failed`. |
| `extractor_version` | string | Sí | Versión ejecutada. |
| `schema_version` | string | Sí | Versión esperada. |
| `observed_count` | integer | Sí | Mayor o igual que cero. |
| `validated_count` | integer | Sí | Mayor o igual que cero. |
| `changed_count` | integer | Sí | Mayor o igual que cero. |
| `quality_event_count` | integer | Sí | Mayor o igual que cero. |
| `error_summary` | string | No | Resumen sin secretos. |
| `github_run_id` | string | No | Trazabilidad con Actions. |

**Relaciones:** uno a muchos con observaciones actuales, periodos y eventos de calidad.

### `fact_quality_events`

**Propósito:** registrar anomalías, rechazos y advertencias sin perder evidencia.

**Llave primaria:** `quality_event_id`.

| Columna | Tipo | Obligatorio | Valores o regla |
|---|---|---:|---|
| `quality_event_id` | string | Sí | ID único. |
| `scrape_run_id` | string | Sí | FK a `fact_scrape_runs`. |
| `supermarket_id` | string | Sí | FK a `cfg_supermarkets`. |
| `location_id` | string | No | FK cuando corresponda. |
| `source_product_id` | string | No | FK cuando pueda identificarse. |
| `offer_id` | string | No | FK cuando exista. |
| `event_type` | enum | Sí | `validation_error`, `mapping_warning`, `structure_change`, `availability_gap`, `other`. |
| `severity` | enum | Sí | `info`, `warning`, `error`, `critical`. |
| `field_name` | string | No | Campo afectado. |
| `message` | string | Sí | Descripción sin secretos. |
| `raw_value` | string | No | Valor público limitado y sanitizado. |
| `detected_at_utc` | datetime | Sí | ISO 8601 UTC. |
| `resolved_at_utc` | datetime | No | ISO 8601 UTC. |
| `resolution_note` | string | No | Decisión humana. |

**Relaciones:** muchos a uno con ejecución y, cuando corresponda, ubicación, producto fuente y oferta.

## Relaciones principales

```text
cfg_supermarkets 1 ── * cfg_locations
cfg_supermarkets 1 ── * map_source_products
cfg_supermarkets 1 ── * fact_scrape_runs
dim_products      1 ── * map_source_products
cfg_locations     1 ── * fact_offers_current
map_source_products 1 ── * fact_offers_current
fact_offers_current 1 ── * fact_offer_history
fact_scrape_runs  1 ── * fact_quality_events
```

## Regla de periodos históricos

1. Se obtiene o valida la oferta y se genera su `state_hash`.
2. Si no existe `offer_id`, se crea el estado actual y exactamente un periodo abierto.
3. Si el hash coincide, no se crea una fila histórica; se actualizan `last_observed_at_utc` y `last_scrape_run_id`.
4. Si el hash cambia, se cierra el periodo anterior en el instante de la observación y se abre exactamente uno nuevo.
5. Solo puede existir un periodo abierto por `offer_id`.
6. Un reintento con la misma ejecución y estado debe ser idempotente.
7. Cada ejecución queda registrada en `fact_scrape_runs` aunque `changed_count` sea cero.

## Campos incluidos en `state_hash`

- `current_price`
- `reported_regular_price`
- `is_promotion`
- `availability`
- `normalized_brand`
- `unit_count`
- `total_content`
- `measurement_unit`

Se normalizan Unicode, espacios, mayúsculas/minúsculas y representación decimal. URLs, imágenes, parámetros de seguimiento y otros cambios cosméticos no abren periodos.
