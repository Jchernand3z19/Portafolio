# Modelo común de datos y almacenamiento

Este documento define el modelo lógico estable. El estado operativo mutable vive en [`PROJECT_STATE.md`](PROJECT_STATE.md).

La primera fase usa Google Sheets como almacenamiento temporal estructurado. La lógica comercial permanece backend-neutral para permitir una migración posterior a BigQuery sin cambiar las reglas de negocio.

El diseño sigue el principio general `SOURCE -> RAW -> CLEAN -> CURATED -> SERVE`, pero **capa lógica no equivale automáticamente a tabla física**. Una tabla sólo se materializa cuando existe una diferencia real de grain, key, lifecycle, ownership/seguridad, patrón de acceso o consumidor. No se crean tablas por anticipación.

## 1. Flujo de dominio

```text
SOURCE
-> RawProduct                         # RAW/source-faithful
-> NormalizedOffer
-> ValidatedOffer                    # CLEAN/validated
-> decisión comercial ACCEPT/REJECT
-> CurrentCommercialOffer / OfferHistoryPeriod  # CURATED
-> TabularBatch
-> backend durable
-> Power BI                          # SERVE
```

`RawProduct` conserva lo observado; `NormalizedOffer` lo lleva al contrato común sin inventar datos; `ValidatedOffer` sella `state_hash`, revisión y quality events. Terminar técnicamente una extracción no equivale a aceptar sus datos para estado comercial.

### Reglas por capa

- **RAW**: source-faithful; unknown permanece unknown; una corrección nunca reescribe silenciosamente lo observado.
- **CLEAN**: tipos, normalización, identidad fuente y validaciones explícitas; los fallos quedan rechazados/pendientes, no convertidos en defaults plausibles.
- **CURATED**: sólo entradas aceptadas pueden cambiar current/history; debe conservarse lineage suficiente hacia run, fuente y evidencia.
- **SERVE**: Power BI consume semántica curada; no es el lugar donde se decide ubicación, aceptación, identidad o limpieza crítica.

## 2. Identidad

```text
source_product_id = producto dentro de una fuente/supermercado
product_id        = identidad potencialmente comparable entre fuentes
offer_id          = supermercado + ubicación comercial + producto fuente
```

Precio, promoción, disponibilidad y fecha no participan en IDs estables. `source_product_id` y `offer_id` son deterministas y se recalculan en fronteras críticas y durante rehidratación.

Mientras exista una sola fuente, `product_id` puede permanecer dentro del contrato de oferta sin obligar a materializar un catálogo maestro independiente. Separar lógicamente identidad fuente e identidad potencialmente canónica evita bloquear el futuro; materializar MDM antes de tener una necesidad cross-source sólo añade estado duplicado y reconciliaciones prematuras.

### GTIN y mapping

Un barcode sólo se usa como identidad común si es GTIN-8/12/13/14 válido por check digit. Se normaliza a GTIN-14:

```text
GTIN válido     -> product_id = prod_gtin_<gtin14>
GTIN no usable  -> product_id = prod_pending_<hash>
```

Un producto provisional conserva `pending_product_mapping`. Su `prod_pending_*` es determinista respecto a `source_product_id` y la frontera lógica lo recalcula antes de clasificar el mapping como pendiente. Un prefijo reservado que no reconcilia falla cerrado.

`dim_products` y `map_source_products` continúan definidos como **contratos lógicos diferidos**. Se materializan cuando exista al menos una segunda fuente o un consumidor real que requiera equivalencia cross-source. Hasta entonces no forman parte del backend físico activo y una semejanza de nombre nunca crea equivalencia por sí sola.

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

No se crea un snapshot histórico completo por cada ejecución cuando nada cambió. `fact_scrape_runs` demuestra que el proceso corrió; `fact_offer_history` representa periodos comerciales, no un log diario duplicado.

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

## 8. Contrato físico activo

Google Sheets materializa **seis tablas activas**:

```text
cfg_supermarkets
cfg_locations
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

### Grain y responsabilidad

- `cfg_supermarkets`: **una fila por supermercado**; configuración de fuente y modo de ubicación.
- `cfg_locations`: **una fila por ubicación comercial**; alcance, granularidad, binding y habilitación.
- `fact_offers_current`: **una fila por `offer_id`**; último estado comercial aceptado conocido.
- `fact_offer_history`: **una fila por periodo histórico de una oferta**; abre/cierra sólo ante transición comercial real.
- `fact_scrape_runs`: **una fila por run terminal**; registra cada ejecución independientemente de si hubo cambios.
- `fact_quality_events`: **una fila por evento de calidad**; problemas/advertencias auditables asociados a run/oferta cuando aplica.

No se crea una tabla por supermercado. Tampoco se separan marca, categoría, presentación, precio o disponibilidad en tablas distintas cuando comparten el grain y lifecycle de la oferta; hacerlo en esta fase sería sobre-normalización sin beneficio operativo.

## 9. Contratos lógicos diferidos

```text
dim_products
map_source_products
```

- `dim_products`: futuro catálogo canónico cross-source, una fila por `product_id` aceptado.
- `map_source_products`: futura relación una fila por `source_product_id` hacia identidad canónica/revisión.

Las funciones de identidad/mapping pueden existir y probarse antes de su materialización. Eso preserva capacidad futura sin obligar al backend temporal a mantener tablas sin consumidor actual.

Criterios mínimos para activar estas tablas: una segunda fuente real, un consumidor que necesite producto canónico cross-source, reglas de matching/revisión definidas y estrategia de backfill/reconciliación demostrable.

## 10. Batch comercial y atomicidad

La frontera comercial construye un `TabularBatch` completo antes de escribir. En la fase física actual puede incluir configuración, current/history, run y quality events. `source_product_id` y `product_id` permanecen dentro de current/history, por lo que diferir las tablas cross-source no pierde la identidad necesaria para reconstrucción futura.

Un run no aceptado no materializa current/history. `InMemoryTabularStore` conserva el modelo lógico backend-neutral y puede seguir probando contratos diferidos; el adapter Google Sheets rechaza explícitamente un batch que intente escribir una tabla diferida para evitar una falsa sensación de durabilidad.

## 11. Rehidratación durable

Un runner nuevo debe poder reconstruir current/history y revalidar IDs, `state_hash`, precios, ubicación, runs de apertura/cierre, versiones, review metadata, cronología, gaps y overlaps. `raw_values` voluminoso no forma parte del snapshot tabular durable cuando no participa en identidad/hash/transición; la evidencia raw necesaria para auditoría/rebuild debe conservarse en la frontera de provenance adecuada, no mezclarse silenciosamente con Gold/curated.

## 12. Google Sheets

El adapter lee sólo las tablas físicas activas, reconstruye el store, valida esquema/PK, aplica el batch localmente y materializa el snapshot mediante un único plan de workbook.

Pestañas ajenas y contratos diferidos se preservan pero no se interpretan como parte del snapshot activo. Una migración/limpieza de tabs físicos es una operación explícita, con preflight y read-back; no queda escondida dentro de una escritura comercial.

La ruta de bootstrap reserva una fila visible adicional para tablas que sólo tienen encabezado, usa `spreadsheets.batchUpdate` para la materialización y se valida operativamente mediante `check -> apply-config -> check`. El resultado productivo concreto del workbook se documenta en `PROJECT_STATE.md`, no en este modelo estable.

La existencia del workbook o de sus tablas no autoriza a escribir ofertas comerciales: la mutación de current/history sigue subordinada a ubicación, completitud y autoridad upstream.

## 13. Power BI y BigQuery

Power BI consume datos aceptados/persistidos y no decide identidad, ubicación, completitud ni autoridad.

BigQuery puede incorporarse cuando el flujo sea estable. No se copiará mecánicamente el layout de Google Sheets: el modelo físico futuro se decidirá por grain, volumen, consultas, particionamiento, clustering, costos y capacidades del warehouse, manteniendo el significado de identidad, current/history, runs, quality, UTC, lineage y autoridad upstream.
