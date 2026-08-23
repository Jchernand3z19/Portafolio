# Modelo común de datos y almacenamiento

Este documento define el modelo lógico estable. El estado operativo mutable vive en [`PROJECT_STATE.md`](PROJECT_STATE.md).

La primera fase usa Google Sheets como almacenamiento temporal estructurado. La lógica comercial permanece backend-neutral para permitir una migración posterior a BigQuery sin cambiar las reglas de negocio.

## 1. Flujo de dominio

```text
RawProduct
-> NormalizedOffer
-> ValidatedOffer
-> decisión comercial
-> CurrentCommercialOffer / OfferHistoryPeriod
-> TabularBatch
-> backend durable
```

`RawProduct` conserva lo observado; `NormalizedOffer` lo lleva al contrato común sin inventar datos; `ValidatedOffer` sella `state_hash`, revisión y quality events.

## 2. Identidad

```text
source_product_id = producto dentro de una fuente/supermercado
product_id        = producto normalizado/comparable entre fuentes
offer_id          = supermercado + ubicación comercial + producto fuente
```

Precio, promoción, disponibilidad y fecha no participan en IDs estables. `source_product_id` y `offer_id` son deterministas y se recalculan en fronteras críticas y durante rehidratación. Un mapping de producto puede corregir `product_id` sin cambiar las otras dos identidades.

### GTIN y mapping

Un barcode sólo se usa como identidad común si es GTIN-8/12/13/14 válido por check digit. Se normaliza a GTIN-14:

```text
GTIN válido     -> product_id = prod_gtin_<gtin14>
GTIN no usable  -> product_id = prod_pending_<hash>
```

Un producto provisional conserva `pending_product_mapping`. Su `prod_pending_*` es determinista respecto a `source_product_id` y la frontera tabular lo recalcula antes de clasificar el mapping como pendiente. Un prefijo reservado que no reconcilia falla cerrado. Un mapping revisado puede sustituir el `product_id` provisional.

Antes de incorporar otra cadena, productos sin GTIN compartido ni mapping explícitamente revisado permanecen pendientes; una semejanza de nombre no basta para crear equivalencia cross-supermercado.

## 3. Ubicación

Se separan dos conceptos:

- **contexto fuente raw**: identifica el contexto en que se obtuvo el payload, pero no afirma ciudad/tienda comercial;
- **ubicación comercial**: ciudad/tienda demostrada y apta para etiquetar una oferta.

Para La Colonia:

```text
la_colonia_online = contexto fuente raw; location_status=unknown
la_colonia_sps    = ubicación comercial candidata; in_scope=true
la_colonia_tgu    = ubicación comercial conocida; in_scope=false
```

`la_colonia_online` no puede promoverse bajo el mismo ID a `confirmed` o `inferred`. La frontera de binding debe producir una ubicación comercial distinta y verificable.

La configuración comercial conserva granularidad, binding técnico, `source_location_key`, alcance y `extraction_enabled`. No se persisten ofertas comerciales de una ubicación que no esté habilitada.

## 4. Presentación

Los componentes normalizados se mantienen separados:

```text
unit_count
content_per_unit
measurement_unit
total_content
```

No se colapsan multipacks. `2 x 500 ml` se conserva como 2 unidades de 500 ml y total 1000 ml. Si la fuente no demuestra un componente, queda nulo y puede requerir revisión.

## 5. Estado e histórico

`state_hash` incluye el estado comercial relevante: precio actual, precio regular reportado, promoción, disponibilidad y atributos normalizados relevantes.

```text
mismo state_hash -> confirmar current y mantener periodo abierto
state_hash distinto -> cerrar periodo anterior, abrir uno nuevo, actualizar current
```

Una ausencia en el payload no implica `not_listed`, `out_of_stock` ni eliminación.

## 6. Precio regular y reducción real

```text
current_price
reported_regular_price
previous_accepted_current_price
```

`reported_regular_price` es una referencia declarada por la tienda. La reducción real usa únicamente:

```text
max(previous_accepted_current_price - current_price, 0)
```

Sin baseline aceptado no se inventa ahorro.

## 7. Runs y replay

Estados: `running`, `success`, `warning`, `rejected`, `failed`, `abandoned`.

Sólo una decisión aceptada y autoritativa puede mutar current/history. `running` es transitorio. Un replay terminal se reconoce únicamente cuando decisión, evidencia y payload coinciden; divergencia bajo el mismo `scrape_run_id` falla cerrado. Un fingerprint demuestra igualdad, no autoridad.

## 8. Tablas comunes

Todos los supermercados comparten ocho tablas gestionadas:

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

- `cfg_supermarkets`: configuración común de supermercados.
- `cfg_locations`: ubicaciones comerciales, alcance, granularidad y binding.
- `dim_products`: una fila por `product_id` mapeado; sólo atributos normalizados/canónicos, sin supermercado, ubicación, precio ni run.
- `map_source_products`: una fila por `source_product_id`; relación fuente -> producto, estado/método de mapping y cola de `pending_product_mapping`.
- `fact_offers_current`: snapshot actual por `offer_id`.
- `fact_offer_history`: periodos históricos.
- `fact_scrape_runs`: toda ejecución terminal.
- `fact_quality_events`: eventos de calidad/estructura.

No se crea una tabla por supermercado.

## 9. Batch comercial y atomicidad

La frontera comercial construye un `TabularBatch` completo antes de escribir. Un run aceptado puede incluir configuración, dimensión/mapping, current/history, run y quality events. Un run no aceptado no materializa dimensión/mapping/current/history.

`InMemoryTabularStore` es la referencia backend-neutral: preflight antes de commit, batch completo o nada, upsert de tablas mutables, runs/calidad inmutables y rechazo de divergencias.

## 10. Rehidratación durable

Un runner nuevo debe poder reconstruir current/history y revalidar IDs, `state_hash`, precios, ubicación, runs de apertura/cierre, versiones, review metadata, cronología, gaps y overlaps. `raw_values` voluminoso no forma parte del snapshot durable cuando no participa en identidad/hash/transición.

## 11. Google Sheets

El adapter lee las tablas gestionadas, reconstruye el store, valida esquema/PK, aplica el batch localmente y materializa el snapshot mediante un único plan de workbook. Pestañas ajenas se preservan y el texto fuente se escribe como texto, no como fórmula.

El contrato físico y lógico usa las mismas ocho tablas gestionadas. La ruta de bootstrap reserva una fila visible adicional para tablas que sólo tienen encabezado, usa `spreadsheets.batchUpdate` para la materialización y se valida operativamente mediante `check -> apply-config -> check`. El resultado productivo concreto del workbook se documenta en `PROJECT_STATE.md`, no en este modelo estable.

La existencia del workbook o de sus tablas no autoriza a escribir ofertas comerciales: la mutación de current/history sigue subordinada a ubicación, completitud y autoridad upstream.

## 12. Power BI y BigQuery

Power BI consume datos aceptados/persistidos y no decide identidad, ubicación, completitud ni autoridad. BigQuery puede incorporarse cuando el flujo sea estable; la migración debe conservar identidades, mapping, current/history, replay, run log, quality events, UTC y autoridad upstream.
