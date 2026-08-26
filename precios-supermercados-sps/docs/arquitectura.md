# Arquitectura — Precios de Supermercados SPS

Este documento describe la **arquitectura estable**. El estado operativo mutable, autorizaciones y evidencia concreta viven en [`PROJECT_STATE.md`](PROJECT_STATE.md).

No uses PRs históricos, ramas o este documento para inferir autorización live.

## 1. Objetivo

Construir una plataforma que recolecte precios e inventario observado de supermercados, normalice la información a un contrato común, valide identidad/calidad/completitud, conserve historia consultable y sirva una aplicación web **Python Dash + Plotly**.

Alcance inicial: **San Pedro Sula, un supermercado a la vez**. La Colonia debe quedar end-to-end antes de iniciar supermercado #2.

Principios:

1. la fuente manda; no se inventan atributos, disponibilidad ni ubicación;
2. contexto fuente y ubicación comercial son conceptos distintos;
3. corrección técnica no equivale a autoridad productiva;
4. toda ambigüedad crítica falla cerrada;
5. identidad estable no depende de precio, disponibilidad ni fecha;
6. todo run terminal se registra;
7. un mismo esquema sirve a todos los supermercados;
8. lógica comercial independiente del backend;
9. BigQuery es el backend persistente seleccionado;
10. Dash + Plotly es la capa de consumo seleccionada;
11. una tabla nueva requiere grain, key, lifecycle y consumidor reales.

## 2. Flujo principal

```text
Fuente
  ↓
Extractor específico
  ↓
RawProduct
  ↓
Normalización específica + reglas/overrides
  ↓
NormalizedOffer
  ↓
Validación + identidad + state_hash
  ↓
ValidatedOffer
  ↓
Completitud / provenance / decisión autoritativa
  ↓
Motor backend-neutral de current/history + replay
  ↓
Proyección de observaciones persistibles
  ↓
BigQuery
  ├─ productos
  ├─ precios_historicos
  ├─ inventario_historico
  ├─ scrape_runs
  └─ dimensiones/evidencia auxiliares
  ↓
Views de estado actual / variaciones
  ↓
Python Dash + Plotly
```

La lógica de dominio no depende de BigQuery. Los tests offline usan stores en memoria para demostrar transición, replay y rehidratación antes de cualquier escritura externa.

## 3. Contratos protegidos

### `RawProduct`
Observación fiel a la fuente. Conserva únicamente lo que el extractor pudo demostrar.

### `NormalizedOffer`
Forma común entre supermercados. Normalizar no significa completar información inexistente.

### `ValidatedOffer`
Oferta normalizada que pasó validaciones y contiene `state_hash`, estado de revisión y quality events.

Estos contratos sólo cambian cuando exista una necesidad demostrada, compatibilidad y pruebas.

## 4. Identidad

```text
source_product_id = identidad estable dentro de la fuente
product_id        = identidad comparable entre fuentes
offer_id          = supermercado + ubicación comercial + producto fuente
```

Precio, promoción, disponibilidad y fecha nunca forman parte de los IDs estables.

GTIN-8/12/13/14 sólo puede producir identidad cross-source cuando supera check digit y se normaliza a GTIN-14. Sin identidad fuerte se conserva `prod_pending_*`; la observación no se descarta.

### Producto vs ciudad

La identidad del producto **no pertenece a una ciudad**. Por eso `productos` conserva supermercado/identidad/descriptores, mientras precio e inventario llevan `location_id`.

```text
productos.supermarket_id
productos.source_product_id
productos.product_id

precios_historicos.supermarket_id
precios_historicos.location_id
precios_historicos.source_product_id
precios_historicos.product_id

inventario_historico.supermarket_id
inventario_historico.location_id
inventario_historico.source_product_id
inventario_historico.product_id
```

`locations` resuelve `location_id -> supermarket_id -> city_id/city_name`. Así cada observación puede responder qué producto, de qué supermercado, en qué ciudad y cuándo sin duplicar ciudad dentro de la dimensión de producto.

## 5. Producto y presentación

Se conservan por separado valores fuente y normalizados:

```text
source_name / normalized_name
source_brand / normalized_brand
source_category / category / subcategory
source_presentation / presentation_normalized
```

La presentación estructurada usa cuando sea demostrable:

```text
presentation_kind
unit_count
content_per_unit
measurement_unit
declared_content
content_scope
total_content
```

No se colapsan multipacks ni se inventa el alcance de un contenido. Overrides revisados deben ligarse a una identidad/firma fuente para no aplicarse si el producto cambia.

## 6. Ubicación

Se distinguen:

- **source location context**: contexto raw del payload;
- **commercial location**: ciudad/tienda demostrada a la que puede atribuirse una observación.

Para La Colonia:

```text
la_colonia_online = contexto fuente raw; no es ciudad ni tienda
la_colonia_sps    = ubicación comercial San Pedro Sula con binding técnico confirmado
la_colonia_tgu    = ubicación conocida fuera del alcance inicial
```

Nunca se convierte `la_colonia_online` en SPS bajo el mismo ID. La promoción a ubicación comercial ocurre en una frontera separada y auditable.

## 7. Precio

Nombres canónicos explícitos:

```text
current_price          = precio efectivo observado
reported_regular_price = precio regular/tachado declarado por la tienda cuando existe
is_promotion           = señal promocional observada
previous_price         = derivado de observaciones históricas
```

No existe un contrato ambiguo llamado sólo `precio`/`price`.

El ahorro real usa el precio histórico aceptado anterior, nunca `reported_regular_price` como sustituto de baseline.

## 8. Inventario observado

La disponibilidad debe conservar evidencia suficiente para distinguir estados sin inferencias silenciosas. La proyección persistible debe incluir como mínimo:

```text
available_quantity_observed
availability
availability_evidence
seller_id
observed_at_utc
scrape_run_id
```

Una cantidad de VTEX se describe como cantidad **observada/reportada por la fuente**. No se declara inventario físico exacto ni ventas derivadas salvo evidencia adicional.

`unknown` no se convierte automáticamente a `out_of_stock`.

## 9. Current/history backend-neutral

El motor común protege transición atómica, replay idempotente, continuidad de identidad/moneda/ubicación, cronología monotónica y rechazo de reutilización conflictiva de `scrape_run_id`. La ausencia de un producto no implica baja.

Estas estructuras validan el comportamiento comercial y permiten rehidratar/reconciliar procesos. BigQuery no copia ciegamente el layout físico del backend temporal anterior.

## 10. BigQuery — contrato físico objetivo

BigQuery es el backend persistente seleccionado desde la primera carga durable del catálogo.

Tablas mínimas:

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

### Grain

- `supermarkets`: una fila por supermercado;
- `locations`: una fila por ubicación comercial;
- `productos`: una fila por producto/SKU fuente estable dentro del supermercado, con `product_id` canónico asociado;
- `precios_historicos`: una observación de precio por producto + ubicación + run/instante;
- `inventario_historico`: una observación de inventario/disponibilidad por producto + ubicación + seller + run/instante;
- `scrape_runs`: una fila por ejecución terminal;
- `quality_events`: una fila por evento auditable;
- `normalization_overrides`: una fila por corrección manual/versionada aplicable a una identidad fuente;
- `product_mapping`: relación auditable producto fuente -> producto canónico.

### Historia observacional

Para Dash y análisis temporal, `precios_historicos` e `inventario_historico` conservan observaciones por ejecución exitosa incluso cuando el valor no cambie. Esto preserva cobertura temporal y permite distinguir “sin cambio” de “no hubo observación”.

Los cambios, precio anterior y estado actual se derivan mediante SQL/views con ventanas.

### Particionamiento inicial

```text
precios_historicos     PARTITION BY DATE(observed_at_utc)
inventario_historico   PARTITION BY DATE(observed_at_utc)
scrape_runs            PARTITION BY DATE(started_at_utc)
quality_events         PARTITION BY DATE(observed_at_utc)
```

Precio/inventario se clusterizan por claves consultadas con frecuencia, comenzando por `supermarket_id`, `location_id` e identidad de producto. El contrato exacto se fija en código/tests antes del adapter real.

## 11. Google Sheets legado

Google Sheets fue una arquitectura temporal anterior y queda **supersedida** por BigQuery.

El código/tests de Sheets puede permanecer transitoriamente mientras se migra sin romper la suite, pero no forma parte del camino objetivo, no recibe nueva funcionalidad, no debe persistir el catálogo y sus workflows/markers deben neutralizarse o retirarse antes de la primera persistencia real.

No se solicitan nuevas credenciales de Sheets.

## 12. Product mapping

Durante La Colonia, `product_id` ya se conserva junto a la identidad fuente. `product_mapping` formaliza la relación y será esencial cuando exista un segundo supermercado.

No iniciar el segundo supermercado sólo para justificar la tabla.

## 13. Normalization overrides

Git/versionado sigue siendo la fuente confiable de reglas y correcciones durante el MVP. BigQuery puede materializar `normalization_overrides` para auditoría/operación, pero una edición manual en BigQuery no se convierte silenciosamente en la única fuente de verdad sin un flujo explícito de sincronización.

## 14. Runs y quality events

Todo run terminal se registra aunque no cambie precio/inventario. Runs rechazados/fallidos no contaminan observaciones comerciales aceptadas. Hashes y fingerprints demuestran igualdad, no autoridad.

## 15. Cloudflare / provenance

La ruta edge existente conserva allowlists, OIDC, presupuesto/pacing, single-flight, replay/fencing, receipts y Observability. Su existencia no concede autoridad comercial ni autorización live.

La evidencia live ya obtenida puede reutilizarse offline. Una observación nueva de La Colonia requiere autorización humana vigente.

## 16. Automatización diaria

Sólo se habilita después de demostrar binding de ubicación, extracción/completitud estable, normalización/validación, persistencia BigQuery idempotente/recuperable, semántica de inventario suficiente y manejo de runs rechazados sin contaminación.

Los fallos no borran el último estado confiable.

## 17. Dash + Plotly

La aplicación web será el consumidor principal. Debe evolucionar sobre datos persistidos y validados para mostrar búsqueda, precio actual/anterior, variaciones, historial Plotly, promociones/caídas reales, disponibilidad/cantidad observada cuando sea confiable, filtros, última actualización y comparación entre supermercados cuando exista una segunda fuente.

Power BI queda como código legado; no se añade nueva funcionalidad a esa ruta.

## 18. GitHub y CI

Todo cambio sigue:

```text
audit main/PRs
-> rama
-> cambio mínimo
-> suite completa
-> PR
-> diff + CI + reviews/threads
-> merge con expected head SHA
```

Los workflows mantienen mínimo privilegio, pins SHA completos y entrypoints live fail-closed.

## 19. Orden actual

```text
CATÁLOGO LA COLONIA [DONE]
-> NORMALIZACIÓN PRODUCTOS [DONE]
-> CURRENT/HISTORY + REPLAY OFFLINE [DONE]
-> BIGQUERY CONTRACT
-> BIGQUERY ADAPTER / BOOTSTRAP
-> FIRST DURABLE LOAD
-> INVENTORY FIRST-CLASS
-> DAILY AUTOMATION
-> DASH + PLOTLY
-> SUPERMARKET #2
```
