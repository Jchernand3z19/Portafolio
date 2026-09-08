# Diccionario de los RPI Data Marts

## Contratos y reconstrucción

El exportador read-only `scripts/exportar_rpi_marts.py` genera desde el estado
persistido y el comparador seguro:

- `rpi-business-mart/v1`: dataset privado para Power BI;
- `rpi-consumer-mart/v1`: dataset público reducido para Compra Inteligente;
- `rpi-marts-manifest/v1`: alcance, timestamp, conteos y SHA-256 de cada archivo.

El grano de una oferta es `canonical_product_id + supermarket_id + location_id
+ source_product_id`. Ningún mart hace matching. Ambos se reconstruyen desde el
estado comercial aceptado y no escriben en Turso.

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

## Consumer Mart

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

El mart público no contiene credenciales, URL de base, queue de revisión,
payload RAW ni grupos inseguros. Los nombres sólo se renderizan como texto y no
autorizan nuevas equivalencias.

Cada producto expone `recommended_source_product_ids`. Puede contener más de un
ID cuando existe un empate real. Si la ventana no es comparable, la lista queda
vacía y el frontend no debe inventar una recomendación.

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
crea al final y registra SHA-256 de todos los archivos de datos. Los CSV
conservan headers aun con universo vacío. La publicación externa debe validar el
schema, scope, hashes y ausencia de secretos antes de reemplazar el último
artifact válido.
