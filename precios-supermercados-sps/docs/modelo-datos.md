# Modelo común de datos y almacenamiento

## Estado de implementación

Este documento define el **modelo lógico común** y las invariantes que debe respetar cualquier backend futuro. **No declara un backend productivo seleccionado ni conectado.**

Estado vigente:

- `commercial_state.py` implementa current/history de forma atómica e idempotente **offline**;
- `commercial_pricing.py` implementa la derivación de reducción real **offline**;
- Google Sheets y BigQuery son opciones históricas/evolutivas de almacenamiento, no infraestructura activa;
- ninguna escritura productiva debe depender de un `catalog_accepted`, `commercial_update_allowed` o booleano equivalente controlable por el caller;
- una futura persistencia productiva deberá consumir una decisión de autoridad tipada y verificable derivada de provenance productiva real.

Hasta que esa frontera exista, las tablas descritas abajo son un contrato lógico para diseño, pruebas y futura persistencia; no evidencian que los datos ya estén siendo almacenados comercialmente.

## Nomenclatura oficial

La Fase 0 utiliza una sola nomenclatura en modelos Python, pruebas y estructuras futuras. No se admiten alias para el mismo dato.

| Concepto | Nombre oficial |
|---|---|
| Precio actual | `current_price` |
| Precio regular informado | `reported_regular_price` |
| ID de ejecución | `scrape_run_id` |
| Disponibilidad | `availability` |
| Estado de ejecución | `run_status` |
| Fecha de observación | `observed_at_utc` |
| Estado de ubicación | `location_status` |
| Evidencia de ubicación | `location_evidence` |
| Confianza de ubicación | `location_confidence` |
| Versión del extractor | `extractor_version` |
| Versión del esquema | `schema_version` |

Los nombres `price_current`, `price_regular`, `run_id` y `availability_status` no forman parte del contrato.

## Contratos de aplicación

### `RawProduct`

Observación fiel a la fuente. Conserva identidad fuente, textos originales, URLs, ubicación, auditoría y `raw_values`. No interpreta silenciosamente marca, categoría, presentación o precio.

### `NormalizedOffer`

Salida común de los extractores. Permite normalización parcial legítima:

- `in_stock` exige `current_price` mayor que cero;
- `out_of_stock`, `not_listed` y `unknown` pueden conservar `current_price = null`;
- `normalized_brand`, `category`, `subcategory`, `unit_count`, `content_per_unit`, `measurement_unit` y `total_content` pueden ser nulos cuando la fuente no permita una interpretación segura;
- los campos nulos quedan en `pending_fields` y producen `review_status = needs_review`;
- no se inventan marcas, presentaciones ni categorías.

### `ValidatedOffer`

Oferta validada estructuralmente. Contiene `state_hash`, fecha de validación, `review_status` y eventos de calidad. Una oferta puede ser válida para trazabilidad aunque conserve campos pendientes. La aceptación comercial también depende del estado de la ejecución completa y, en producción, de autoridad externa verificable.

## Vocabularios cerrados

### `availability`

- `in_stock`
- `out_of_stock`
- `not_listed`
- `unknown`

### `location_status`

- `confirmed`
- `inferred`
- `unknown`

### `source_key_type`

- `internal_id`
- `sku`
- `barcode`
- `api_id`
- `stable_url`

### `review_status`

- `ready`
- `needs_review`

### `run_status`

- `running`
- `success`
- `warning`
- `rejected`
- `failed`
- `abandoned`

### `change_type`

- `initial`
- `price`
- `regular_price`
- `promotion`
- `availability`
- `product_attribute`
- `multiple`

## Identificadores

| Campo | Regla |
|---|---|
| `source_product_id` | SHA-256 determinista de `supermarket_id`, `source_key_type` y `source_key`; prefijo `sp_`. |
| `product_id` | Identidad transversal del producto normalizado. No depende del precio. |
| `offer_id` | SHA-256 determinista de `supermarket_id`, `location_id` y `source_product_id`; prefijo `of_`. |
| `state_hash` | SHA-256 completo de atributos relevantes del estado. |

Reglas de `source_key`:

1. Se prefiere ID interno, SKU, barcode, ID de API y por último URL estable.
2. ID interno, SKU, barcode e ID de API conservan mayúsculas y minúsculas; solo se eliminan espacios externos.
3. `SKU-001` y `sku-001` producen IDs diferentes.
4. La URL estable elimina fragmentos y únicamente tracking inequívoco: `utm_*`, `gclid`, `fbclid`, `msclkid`, `mc_cid`, `mc_eid`.
5. Parámetros potencialmente funcionales, incluido `ref`, se conservan.
6. `supermarket_id`, `location_id`, `source_product_id` y `source_key` vacíos se rechazan.

## Modelo lógico de almacenamiento

Las estructuras siguientes se diseñaron inicialmente con Google Sheets como almacenamiento temporal. Hoy deben leerse como **tablas lógicas backend-neutral**. Si en el futuro se usa Sheets, BigQuery u otra tecnología, el adaptador deberá conservar estas invariantes o documentar explícitamente una migración compatible.

Las fechas se almacenan en ISO 8601 UTC. Los decimales son valores numéricos. Los campos JSON se serializan de forma determinista. Si el backend no aplica restricciones físicas, la capa de persistencia debe validarlas antes de confirmar una transacción.

### `cfg_supermarkets`

**Propósito:** catálogo y umbrales operativos por supermercado.

**Llave primaria:** `supermarket_id`.

| Columna | Tipo | Obligatorio | Regla |
|---|---|---:|---|
| `supermarket_id` | string | Sí | Slug estable. |
| `supermarket_name` | string | Sí | Nombre público. |
| `base_url` | string | Sí | URL absoluta. |
| `active` | boolean | Sí | `true` / `false`. |
| `extractor_version` | string | Sí | Versión vigente. |
| `schema_version` | string | Sí | Versión del contrato. |
| `minimum_page_coverage_ratio` | decimal | Sí | 0 a 1. |
| `minimum_offer_coverage_ratio` | decimal | Sí | 0 a 1. |
| `minimum_price_coverage_ratio` | decimal | Sí | 0 a 1. |
| `maximum_rejected_ratio` | decimal | Sí | 0 a 1. |
| `created_at_utc` | datetime | Sí | UTC. |
| `updated_at_utc` | datetime | Sí | UTC. |
| `notes` | string | No | Sin secretos. |

**Relaciones:** uno a muchos con `cfg_locations`, `map_source_products` y `fact_scrape_runs`.

### `cfg_locations`

**Propósito:** catálogo de ubicaciones o ámbitos de precio.

**Llave primaria:** `location_id`.

| Columna | Tipo | Obligatorio | Regla |
|---|---|---:|---|
| `location_id` | string | Sí | Identidad estable. |
| `supermarket_id` | string | Sí | FK a `cfg_supermarkets`. |
| `location_name` | string | Sí | Nombre legible. |
| `city` | string | Sí | Inicialmente San Pedro Sula. |
| `location_status` | enum | Sí | `confirmed`, `inferred`, `unknown`. |
| `location_evidence` | string | Condicional | Requerido para confirmed/inferred. |
| `location_confidence` | decimal | Condicional | 0 a 1; requerido para confirmed/inferred. |
| `active` | boolean | Sí | `true` / `false`. |
| `created_at_utc` | datetime | Sí | UTC. |
| `updated_at_utc` | datetime | Sí | UTC. |

**Relaciones:** muchos a uno con `cfg_supermarkets`; uno a muchos con ofertas y ejecuciones.

### `dim_products`

**Propósito:** catálogo normalizado. Conserva productos aunque su interpretación esté pendiente.

**Llave primaria:** `product_id`.

| Columna | Tipo | Obligatorio | Regla |
|---|---|---:|---|
| `product_id` | string | Sí | Identidad estable. |
| `normalized_name` | string | Sí | Nombre canónico mínimo. |
| `normalized_brand` | string | No | Nulo si no puede interpretarse. |
| `category` | string | No | Nulo si está pendiente. |
| `subcategory` | string | No | Nulo si está pendiente. |
| `variant` | string | No | Variante normalizada. |
| `unit_count` | integer | No | Mayor que cero. |
| `content_per_unit` | decimal | No | Mayor que cero. |
| `measurement_unit` | string | No | Unidad canónica. |
| `total_content` | decimal | No | Mayor que cero. |
| `barcode` | string | No | Conserva el valor fuente. |
| `review_status` | enum | Sí | `ready`, `needs_review`. |
| `pending_fields` | JSON array | Sí | Campos pendientes, orden estable. |
| `created_at_utc` | datetime | Sí | UTC. |
| `updated_at_utc` | datetime | Sí | UTC. |

**Relaciones:** uno a muchos con `map_source_products`.

### `map_source_products`

**Propósito:** trazabilidad entre producto fuente y producto normalizado.

**Llave primaria:** `source_product_id`.

| Columna | Tipo | Obligatorio | Regla |
|---|---|---:|---|
| `source_product_id` | string | Sí | Prefijo `sp_`. |
| `supermarket_id` | string | Sí | FK. |
| `source_key_type` | enum | Sí | Valores aprobados. |
| `source_key` | string | Sí | Exacto con trim, o URL canónica. |
| `source_sku` | string | No | Valor original. |
| `source_name` | string | Sí | Nombre original más reciente. |
| `source_brand` | string | No | Sin inventar. |
| `source_presentation` | string | No | Texto original. |
| `source_category` | string | No | Texto original. |
| `product_url` | string | Sí | URL absoluta. |
| `image_url` | string | No | URL absoluta. |
| `product_id` | string | No | FK; nulo mientras el mapeo esté pendiente. |
| `mapping_status` | enum | Sí | `pending`, `automatic`, `reviewed`, `rejected`. |
| `mapping_confidence` | decimal | No | 0 a 1. |
| `first_observed_at_utc` | datetime | Sí | UTC. |
| `last_observed_at_utc` | datetime | Sí | UTC. |
| `extractor_version` | string | Sí | Versión observadora. |
| `schema_version` | string | Sí | Versión del contrato. |

**Relaciones:** muchos a uno con `cfg_supermarkets` y opcionalmente `dim_products`; uno a muchos con ofertas.

### `fact_offers_current`

**Propósito:** último estado comercial aceptado de cada oferta. En un backend productivo sólo puede actualizarse después de una decisión comercial autoritativa; un booleano enviado por el caller no es suficiente.

**Llave primaria:** `offer_id`.

| Columna | Tipo | Obligatorio | Regla |
|---|---|---:|---|
| `offer_id` | string | Sí | Prefijo `of_`. |
| `supermarket_id` | string | Sí | FK. |
| `location_id` | string | Sí | FK. |
| `source_product_id` | string | Sí | FK. |
| `product_id` | string | Sí | FK. |
| `currency` | string | Sí | ISO 4217. |
| `current_price` | decimal | Condicional | Mayor que cero para `in_stock`; puede ser nulo en otros estados. |
| `reported_regular_price` | decimal | No | Valor informado, no prueba descuento. |
| `source_current_price_raw` | string | No | Valor original extraído. |
| `source_regular_price_raw` | string | No | Valor original extraído. |
| `is_promotion` | boolean | Sí | No existe `promotion_text`. |
| `unit_price` | decimal | No | Mayor que cero. |
| `unit_price_basis` | string | No | Base canónica. |
| `availability` | enum | Sí | Cuatro valores aprobados. |
| `normalized_brand` | string | No | Puede estar pendiente. |
| `category` | string | No | Puede estar pendiente. |
| `subcategory` | string | No | Puede estar pendiente. |
| `variant` | string | No | Puede estar pendiente. |
| `unit_count` | integer | No | Puede estar pendiente. |
| `content_per_unit` | decimal | No | Puede estar pendiente. |
| `measurement_unit` | string | No | Puede estar pendiente. |
| `total_content` | decimal | No | Puede estar pendiente. |
| `review_status` | enum | Sí | `ready`, `needs_review`. |
| `pending_fields` | JSON array | Sí | Orden estable. |
| `location_status` | enum | Sí | Valores aprobados. |
| `location_evidence` | string | Condicional | Evidencia de la observación. |
| `location_confidence` | decimal | Condicional | 0 a 1. |
| `state_hash` | string | Sí | SHA-256. |
| `first_observed_at_utc` | datetime | Sí | Apertura del estado actual. |
| `last_observed_at_utc` | datetime | Sí | Última confirmación. |
| `scrape_run_id` | string | Sí | Ejecución aceptada más reciente. |
| `extractor_version` | string | Sí | Versión productora. |
| `schema_version` | string | Sí | Versión del contrato. |
| `source_url` | string | Sí | Auditoría. |

**Relaciones:** muchos a uno con catálogos; uno a uno con el periodo abierto de `fact_offer_history`.

### `fact_offer_history`

**Propósito:** periodos históricos solo cuando cambia `state_hash` de un estado comercial aceptado.

**Llave primaria:** `offer_history_id`.

| Columna | Tipo | Obligatorio | Regla |
|---|---|---:|---|
| `offer_history_id` | string | Sí | ID idempotente del periodo. |
| `offer_id` | string | Sí | FK. |
| `state_hash` | string | Sí | Estado del periodo. |
| `change_type` | enum | Sí | Valores aprobados. |
| `changed_fields` | JSON array | Sí | Campos cuyo valor cambió; orden estable. |
| `currency` | string | Sí | ISO 4217. |
| `current_price` | decimal | Condicional | Requerido para `in_stock`. |
| `reported_regular_price` | decimal | No | Valor informado. |
| `source_current_price_raw` | string | No | Valor fuente al abrir periodo. |
| `source_regular_price_raw` | string | No | Valor fuente al abrir periodo. |
| `is_promotion` | boolean | Sí | Estado del periodo. |
| `availability` | enum | Sí | Estado del periodo. |
| `normalized_brand` | string | No | Incluido determinísticamente en hash. |
| `category` | string | No | Incluido determinísticamente en hash. |
| `subcategory` | string | No | Incluido determinísticamente en hash. |
| `variant` | string | No | Incluido determinísticamente en hash. |
| `unit_count` | integer | No | Incluido determinísticamente en hash. |
| `content_per_unit` | decimal | No | Incluido determinísticamente en hash. |
| `measurement_unit` | string | No | Incluido determinísticamente en hash. |
| `total_content` | decimal | No | Incluido determinísticamente en hash. |
| `review_status` | enum | Sí | Estado de revisión al abrir periodo. |
| `pending_fields` | JSON array | Sí | Campos pendientes. |
| `location_status` | enum | Sí | Estado de ubicación. |
| `location_evidence` | string | Condicional | Evidencia asociada. |
| `location_confidence` | decimal | Condicional | 0 a 1. |
| `valid_from_utc` | datetime | Sí | Inicio inclusive. |
| `valid_to_utc` | datetime | No | Fin exclusivo; nulo para actual. |
| `opened_by_scrape_run_id` | string | Sí | Ejecución que abrió. |
| `closed_by_scrape_run_id` | string | No | Ejecución que cerró. |
| `last_confirmed_by_scrape_run_id` | string | Sí | Última ejecución con mismo hash. |
| `last_observed_at_utc` | datetime | Sí | Última observación del periodo. |
| `extractor_version` | string | Sí | Versión que abrió el periodo. |
| `schema_version` | string | Sí | Versión del contrato. |

**Restricción:** solo un registro con `valid_to_utc = null` por `offer_id`.

### `fact_scrape_runs`

**Propósito:** registrar cada ejecución, medir completitud y conservar la decisión técnica/comercial. En producción, la habilitación comercial requiere además autoridad productiva verificable y no se deriva únicamente de métricas o de un booleano caller-controlled.

**Llave primaria:** `scrape_run_id`.

| Columna | Tipo | Obligatorio | Regla |
|---|---|---:|---|
| `scrape_run_id` | string | Sí | ID único e idempotente. |
| `supermarket_id` | string | Sí | FK. |
| `location_id` | string | No | FK cuando aplique. |
| `started_at_utc` | datetime | Sí | UTC. |
| `finished_at_utc` | datetime | No | UTC. |
| `run_status` | enum | Sí | `running`, `success`, `warning`, `rejected`, `failed`, `abandoned`. |
| `commercial_update_allowed` | boolean | Sí | Campo lógico derivado de una decisión autoritativa; el caller no puede concederlo por sí solo. |
| `extractor_version` | string | Sí | Versión ejecutada. |
| `schema_version` | string | Sí | Versión esperada. |
| `discovered_page_count` | integer | Sí | Mayor o igual que cero. |
| `processed_page_count` | integer | Sí | Mayor o igual que cero. |
| `page_coverage_ratio` | decimal | Sí | Procesadas / descubiertas. |
| `discovered_product_count` | integer | Sí | Productos detectados. |
| `raw_product_count` | integer | Sí | `RawProduct` creados. |
| `normalized_offer_count` | integer | Sí | `NormalizedOffer` creadas. |
| `validated_offer_count` | integer | Sí | Ofertas estructuralmente válidas. |
| `review_pending_count` | integer | Sí | Ofertas con `needs_review`. |
| `rejected_offer_count` | integer | Sí | Registros rechazados individualmente. |
| `previous_successful_offer_count` | integer | Sí | Base de comparación. |
| `accepted_offer_count` | integer | Sí | Ofertas candidatas de esta ejecución. |
| `offer_coverage_ratio` | decimal | Sí | Cobertura frente a ejecución aceptada anterior. |
| `in_stock_count` | integer | Sí | Ofertas `in_stock`. |
| `current_price_present_count` | integer | Sí | Ofertas con precio actual. |
| `missing_in_stock_price_count` | integer | Sí | Debe ser cero para aceptar la ejecución. |
| `price_coverage_ratio` | decimal | Sí | Precios presentes / ofertas esperadas. |
| `changed_offer_count` | integer | Sí | Hash diferente. |
| `unchanged_offer_count` | integer | Sí | Hash igual. |
| `quality_event_count` | integer | Sí | Eventos de calidad. |
| `structural_event_count` | integer | Sí | Eventos estructurales. |
| `error_summary` | string | No | Sin secretos. |
| `github_workflow_name` | string | No | Nombre del workflow. |
| `github_workflow_run_id` | string | No | ID de GitHub Actions. |
| `github_run_attempt` | integer | No | Número de intento. |
| `git_commit_sha` | string | No | Commit ejecutado. |
| `git_ref` | string | No | Rama o tag ejecutado. |

**Reglas de aceptación técnica/comercial:**

- `running`: ejecución activa; no actualiza hechos comerciales.
- `success`: terminó técnicamente y puede ser candidata a aceptación; en producción aún requiere autoridad verificable.
- `warning`: terminó con eventos no bloqueantes y puede ser candidata; en producción aún requiere autoridad verificable.
- `rejected`: falló completitud o validaciones bloqueantes; no actualiza precios, disponibilidad ni periodos.
- `failed`: error técnico; no actualiza.
- `abandoned`: ejecución iniciada que no terminó dentro del límite; no actualiza.
- `commercial_update_allowed = true` sólo puede materializarse después de la decisión autoritativa correspondiente; no se acepta como input suficiente para conceder autoridad.

Una caída de cobertura, páginas faltantes, cambio estructural bloqueante o extracción parcial no se transforma en `not_listed`, `out_of_stock` ni reducción de precios. La ejecución completa se marca `rejected` y el último estado comercial aceptado permanece intacto.

### `fact_quality_events`

**Propósito:** registrar eventos de calidad y estructura sin perder evidencia.

**Llave primaria:** `quality_event_id`.

| Columna | Tipo | Obligatorio | Regla |
|---|---|---:|---|
| `quality_event_id` | string | Sí | ID único e idempotente. |
| `scrape_run_id` | string | Sí | FK. |
| `supermarket_id` | string | Sí | FK. |
| `location_id` | string | No | FK cuando aplique. |
| `source_product_id` | string | No | FK cuando se conozca. |
| `offer_id` | string | No | FK cuando exista. |
| `event_category` | enum | Sí | `quality`, `structure`. |
| `event_type` | string | Sí | Código estable. |
| `severity` | enum | Sí | `info`, `warning`, `error`, `critical`. |
| `blocking` | boolean | Sí | Impide actualización comercial cuando true. |
| `field_name` | string | No | Campo afectado. |
| `message` | string | Sí | Descripción sin secretos. |
| `observed_value` | string | No | Valor público sanitizado. |
| `expected_value` | string | No | Regla o referencia esperada. |
| `detected_at_utc` | datetime | Sí | UTC. |
| `resolved_at_utc` | datetime | No | UTC. |
| `resolution_status` | enum | Sí | `open`, `resolved`, `accepted_risk`, `false_positive`. |
| `resolution_note` | string | No | Decisión humana. |
| `extractor_version` | string | Sí | Versión detectora. |
| `schema_version` | string | Sí | Versión del contrato. |

Tipos iniciales de calidad incluyen `pending_normalization`, `missing_in_stock_price`, `invalid_value`, `mapping_pending` y `coverage_drop`. Tipos estructurales incluyen `selector_missing`, `field_missing`, `response_shape_changed`, `endpoint_changed` y `schema_changed`.

## Relaciones principales

```text
cfg_supermarkets      1 ── * cfg_locations
cfg_supermarkets      1 ── * map_source_products
cfg_supermarkets      1 ── * fact_scrape_runs
dim_products          1 ── * map_source_products
cfg_locations         1 ── * fact_offers_current
map_source_products   1 ── * fact_offers_current
fact_offers_current   1 ── * fact_offer_history
fact_scrape_runs      1 ── * fact_quality_events
```

## Regla de periodos históricos

1. Solo una ejecución **comercialmente aceptada por una frontera autoritativa** puede comparar y persistir estados comerciales.
2. Si no existe `offer_id`, se crea `fact_offers_current` y un periodo `initial` abierto.
3. Si `state_hash` coincide, no se crea historial; se actualizan `last_observed_at_utc` y `last_confirmed_by_scrape_run_id`.
4. Si cambia, se calcula `changed_fields`, se asigna `change_type`, se cierra el periodo anterior con `valid_to_utc` y `closed_by_scrape_run_id`, y se abre exactamente uno nuevo.
5. Solo existe un periodo abierto por `offer_id`.
6. El mismo `scrape_run_id`, `offer_id` y `state_hash` no puede duplicar historial.
7. Una ejecución rechazada, fallida, abandonada o sin autoridad productiva registra diagnóstico/evidencia, pero no abre ni cierra periodos productivos.

## Campos incluidos en `state_hash`

- `current_price`
- `reported_regular_price`
- `is_promotion`
- `availability`
- `normalized_brand`
- `category`
- `subcategory`
- `variant`
- `unit_count`
- `content_per_unit`
- `measurement_unit`
- `total_content`

Cada campo se incluye incluso cuando su valor es nulo. Los nulos tienen representación determinista. Se normalizan Unicode, espacios, mayúsculas/minúsculas de textos comparables y representación decimal. No se incluyen URLs, imágenes ni parámetros de tracking.
