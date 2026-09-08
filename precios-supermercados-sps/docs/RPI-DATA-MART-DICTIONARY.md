# Diccionario de los RPI Data Marts

## Contratos y reconstrucción

El exportador read-only `scripts/exportar_rpi_marts.py` genera desde el estado
persistido y el comparador seguro:

- `rpi-business-mart/v1`: dataset privado para Power BI;
- `rpi-consumer-mart/v2`: dataset público reducido para Compra Inteligente;
- `rpi-marts-manifest/v1`: alcance, timestamp, schemas, conteos y SHA-256 de cada archivo.

El grano de una oferta es `canonical_product_id + supermarket_id + location_id
+ source_product_id`. Ningún mart hace matching. Ambos se reconstruyen desde el
estado comercial aceptado y no escriben en Turso.

La versión `v2` del Consumer Mart conserva el contrato actual y añade contexto
histórico resumido calculado en Python desde los periodos compactos ya persistidos.
No publica la serie histórica completa ni obliga al navegador a reconstruirla.

## Metadatos compartidos

| Campo | Semántica |
| --- | --- |
| `comparison_policy` | gate de identidad fuerte y consistencia comercial |
| `comparison_status` | `COMPARABLE` o `INSUFFICIENT_FRESH_COMPARISON` |
| `blocked_reasons` | motivos auditables que suprimen ranking/PCI |
| `currency` | `HNL` |
| `scope` | retailer + ubicación exacta |
| `as_of` | instante UTC de evaluación |
| `freshness_window_hours` | ventana de mercado configurada |
| `source_freshness` | último run válido, observación, edad y estado por scope |
| `coverage` | comparables, precios válidos, exclusiones y porcentaje |

Una fuente `STALE` conserva sus ofertas last-known-good visibles, pero los campos
competitivos quedan nulos. `REJECTED` nunca se elige como último run válido.

## Business Mart

### Dimensiones

| Tabla | Grano | Clave |
| --- | --- | --- |
| `dim_product` | producto canónico seguro | `canonical_product_id` |
| `dim_retailer` | cadena del scope | `supermarket_id` |
| `dim_location` | contexto comercial | `supermarket_id + location_id` |
| `dim_category` | categoría observada/normalizada presente | `category` |
| `dim_brand` | marca fuente presente | `brand` |

Las dimensiones de fecha e histórico se incorporarán junto con los facts
históricos; no se crean tablas vacías anticipadas.

### `fact_current_comparison`

Una fila por oferta segura actual. Incluye identidad, descriptores, precio
efectivo, referencia regular, promoción, disponibilidad, fechas, freshness y,
cuando la ventana es comparable, rank, PCI, mercado mínimo/máximo/media/mediana
y spread.

Los importes JSON/CSV se serializan como decimal-texto con dos posiciones. PCI y
porcentajes también son decimal-texto. `reported_regular_price` nunca sustituye
`current_price`.

### `fact_basket_cost`

Una fila por retailer/ubicación para exactamente el mismo universo común. Un
universo vacío no produce ganador. La evolución de canastas manuales usa
`shopping_analytics.py`, donde un faltante vuelve incompleto el total.

### `fact_metric_coverage`

Una fila por corte publicado con:

- `comparable_count`;
- `valid_price_count`;
- `excluded_count`;
- `coverage_pct`;
- `as_of`;
- `freshness_window_hours`.

## Consumer Mart v2

`products` contiene una fila por producto canónico y un arreglo `offers`. Cada
oferta conserva:

| Campo | Uso B2C |
| --- | --- |
| `canonical_product_id` | identidad segura compartida |
| `source_product_id` | oferta exacta elegida por el usuario |
| `supermarket_id`, `location_id` | contexto comercial |
| `category`, `product_type` | navegación y descripción |
| `product_name`, `brand`, `variant`, `presentation` | búsqueda/presentación, nunca matching |
| `current_price` | `unit_price` de Mi Compra |
| `reported_regular_price` | referencia visual opcional |
| `is_promotion` | declaración fuente |
| `rank`, `is_best_price` | recomendación calculada en Python; queda nula/inactiva cuando comparar no es seguro |
| `availability` | `in_stock` o `unknown` para ofertas publicadas |
| `observed_at` | inicio observado del estado comercial persistido |
| `last_successful_run`, `source_last_successful_at` | último corte fuente aceptado |
| `data_age_hours`, `freshness_status` | frescura visible |
| `historical_summary` | contexto histórico resumido calculado en Python |

El mart público no contiene credenciales, URL de base, queue de revisión,
payload RAW ni grupos inseguros. Los nombres sólo se renderizan como texto y no
autorizan nuevas equivalencias.

Cada producto expone `recommended_source_product_ids`. Puede contener más de un
ID cuando existe un empate real. Si la ventana no es comparable, la lista queda
vacía y el frontend no debe inventar una recomendación.

### `historical_summary`

Se calcula únicamente para la misma `source_product_id + supermarket_id +
location_id` ya autorizada por el universo seguro. El exportador lee sus periodos
compactos una vez, no publica RAW y no hace matching histórico.

Campos principales:

| Campo | Semántica |
| --- | --- |
| `observation_count` | estados de precio positivo realmente observados |
| `first_observed_at`, `last_observed_at` | límites reales de la serie disponible |
| `observed_minimum`, `observed_maximum` | extremos de toda la serie observada disponible |
| `previous_price` | precio efectivo del estado previo real, si existe |
| `current_vs_previous_pct` | cambio porcentual contra el estado previo |
| `days_since_last_change` | días observados desde el último cambio de precio |
| `historical_position` | clasificación auditable de `promotion_analytics.py` |
| `historical_price_reduction` | si el precio efectivo actual bajó contra el estado previo |
| `source_discount_depth_pct` | descuento declarado vs regular reportado, sólo cuando existe |
| `windows.30d`, `windows.90d` | media, mediana, mínimo, máximo y posición actual en ventanas completas |

Cada ventana expone `status=available` sólo cuando existe un baseline real que
cubre todo el periodo solicitado. Si no existe, usa `insufficient_history` y sus
métricas quedan `null`; no se acorta la ventana, no se interpola y no se trata el
precio regular declarado como historia observada.

`historical_position` puede ser `below_recent_average`, `near_recent_minimum`,
`normal_range`, `above_recent_average`,
`source_promotion_without_historical_reduction` o `insufficient_history`, según
las reglas autoritativas de Python.

## Contrato monetario B2C

```text
unit_price = current_price
line_total = unit_price * quantity
retailer_subtotal = sum(line_total)
grand_total = sum(retailer_subtotal)
```

No se agrega ISV ni cargos de shipping, delivery, service o membership. Si una
línea no tiene precio utilizable, su total y los totales que dependen de ella son
nulos/incompletos; nunca cero.

## Archivos y atomicidad

El exportador escribe temporalmente y renombra cada JSON/CSV. El manifest se
crea al final y registra SHA-256 de todos los archivos de datos, además de
`business_schema` y `consumer_schema`. Los CSV conservan headers aun con universo
vacío. La publicación externa debe validar schema, scope, hashes y ausencia de
secretos antes de reemplazar el último artifact válido.
