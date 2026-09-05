# Diccionario del dataset de publicación

Contrato actual: `precios-sps-publication/v1`.

El dataset se deriva únicamente de `AnalyticsResult`; por lo tanto sólo contiene productos que superaron el comparador fail-closed. No incluye credenciales, URLs de base de datos, tokens ni secretos operativos.

## Metadatos raíz

| Campo | Tipo | Definición |
| --- | --- | --- |
| `schema` | texto | Versión del contrato de publicación. |
| `comparison_policy` | texto | Política que autorizó las comparaciones. |
| `currency` | texto | Moneda de los importes publicados. Actualmente HNL. |
| `scope` | lista | Parejas explícitas `supermarket_id` + `location_id` que forman el alcance. |
| `offers` | lista | Precios actuales de productos comparables. |
| `products` | lista | Resumen de comparación por producto canónico. |
| `common_basket` | lista | Total de la misma canasta por supermercado. |
| `excluded_group_counts` | objeto | Conteos agregados por motivo de exclusión; nunca publica el precio del grupo bloqueado. |

## `scope`

| Campo | Tipo | Definición |
| --- | --- | --- |
| `supermarket_id` | texto | Identificador estable del supermercado. |
| `location_id` | texto | Ubicación exacta usada para obtener el precio. |

Una comparación nunca mezcla dos ubicaciones de la misma cadena dentro del mismo alcance.

## `offers`

| Campo | Tipo | Definición |
| --- | --- | --- |
| `canonical_product_id` | texto | Identidad canónica derivada de GTIN validado. |
| `canonical_gtin` | texto | GTIN normalizado usado como identidad fuerte. |
| `supermarket_id` | texto | Cadena del precio observado. |
| `location_id` | texto | Tienda/club/sucursal exacta. |
| `source_record_id` | texto | Identidad trazable del registro fuente dentro del modelo analítico. |
| `current_price` | decimal serializado como texto | Precio actual observado en HNL, con dos decimales. |
| `is_best_price` | booleano | Indica si el precio coincide con el mínimo del producto dentro del alcance. |

Los importes monetarios se serializan como texto decimal para no introducir redondeos binarios en JSON.

## `products`

| Campo | Tipo | Definición |
| --- | --- | --- |
| `canonical_product_id` | texto | Producto canónico. |
| `canonical_gtin` | texto | GTIN canónico. |
| `best_supermarket_id` | texto | Supermercado seleccionado de forma determinista entre los mínimos. |
| `best_location_id` | texto | Ubicación asociada a ese mínimo determinista. |
| `best_price` | decimal-texto | Precio mínimo. |
| `highest_price` | decimal-texto | Precio máximo del mismo producto y alcance. |
| `savings_vs_highest` | decimal-texto | Diferencia entre máximo y mínimo. |
| `savings_vs_highest_pct` | decimal-texto | `savings_vs_highest / highest_price * 100`. |
| `supermarket_count` | entero | Número de supermercados con oferta comparable incluida. |

El campo de supermercado “best” no debe interpretarse como ganador global fuera del alcance definido.

## `common_basket`

Cada fila representa el total de exactamente el mismo conjunto de productos en un supermercado.

| Campo | Tipo | Definición |
| --- | --- | --- |
| `supermarket_id` | texto | Supermercado. |
| `location_id` | texto | Ubicación usada. |
| `total` | decimal-texto | Suma de los precios actuales del denominador común. |
| `is_cheapest` | booleano | Indica el total mínimo del alcance. |
| `product_count` | entero | Número de unidades/productos según la canasta evaluada. En la canasta común base equivale al número de productos canónicos. |
| `denominator_definition` | texto | Regla exacta que define qué productos entraron al total. |

Denominador base:

`products_comparable_and_priced_in_every_supermarket_in_scope`

Para subcanastas con cantidades explícitas:

`explicit_quantities_drawn_only_from_current_common_comparable_universe`

## Exclusiones

`excluded_group_counts` permite medir por qué una comparación no se publicó sin exponer precios que podrían inducir a una equivalencia falsa. Entre los motivos posibles están:

- `review_required`;
- `not_comparable`;
- `scope_membership_incomplete_or_ambiguous`;
- `price_missing_in_scope`.

## Semántica de ausencia

Ausencia no equivale a cero. Un producto sin precio válido en cualquiera de las ubicaciones del alcance sale de la canasta común. El motor no imputa, promedia ni copia precios de otra tienda.

## Consumo en BI

Power BI debe importar `offers`, `products`, `common_basket` y `scope` como tablas separadas. Las métricas de ahorro deben usar los campos publicados o reproducir exactamente las fórmulas documentadas; no se debe volver a hacer matching por nombre, marca o presentación dentro de DAX/Power Query.