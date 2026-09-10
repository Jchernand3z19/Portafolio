# Diccionario de publicación — estado vigente y contratos legados

## Estado actual

La arquitectura RPI vigente ya no usa un único contrato de publicación para todos los consumidores.

| Contrato | Estado | Frontera |
| --- | --- | --- |
| `rpi-business-mart/v1` | vigente | privado, B2B / Power BI |
| `rpi-consumer-mart/v2` | vigente | público, comparación analítica B2C |
| `rpi-consumer-catalog/v3` | vigente | público, navegación de Compra Inteligente |
| `precios-sps-publication/v1` | legado | compatibilidad / evidencia histórica |
| `precios-sps-static-bi-dataset/v1` | legado | compatibilidad BI de fase anterior |

La publicación pública RPI se materializa en la rama `portfolio-data` bajo:

```text
precios-supermercados-sps/published/rpi/consumer-mart.json
precios-supermercados-sps/published/rpi/manifest.json
precios-supermercados-sps/published/rpi/v3/...
```

Business Mart **no se copia al namespace público**. Permanece dentro del artifact analítico validado para el flujo B2B.

Antes de reemplazar un corte público, el sync verifica schema, scope, hashes, tamaños, frontera pública y ausencia de material secreto. La sustitución del namespace v3 es atómica; un fallo conserva el último corte válido.

Para la definición detallada de los contratos actuales, consultar `RPI-DATA-MART-DICTIONARY.md`.

---

# Contrato legado `precios-sps-publication/v1`

Esta sección se conserva porque artifacts y documentación histórica todavía pueden referenciar este contrato. No debe presentarse como la arquitectura RPI principal.

El dataset se deriva únicamente del comparador seguro y sólo contiene productos que superaron el gate fail-closed. No incluye credenciales, URLs privadas de base de datos, tokens ni secretos operativos.

## Metadatos raíz

| Campo | Tipo | Definición |
| --- | --- | --- |
| `schema` | texto | versión del contrato |
| `comparison_policy` | texto | política que autorizó las comparaciones |
| `currency` | texto | moneda; HNL |
| `scope` | lista | pares explícitos `supermarket_id + location_id` |
| `offers` | lista | precios actuales comparables |
| `products` | lista | resumen de comparación por producto canónico |
| `common_basket` | lista | total del mismo denominador por supermercado |
| `excluded_group_counts` | objeto | exclusiones agregadas sin exponer precios bloqueados |

## `scope`

Una comparación nunca mezcla dos ubicaciones de la misma cadena dentro del mismo alcance.

| Campo | Tipo | Definición |
| --- | --- | --- |
| `supermarket_id` | texto | identificador estable de la cadena |
| `location_id` | texto | contexto exacto del precio |

## `offers`

| Campo | Tipo | Definición |
| --- | --- | --- |
| `canonical_product_id` | texto | identidad canónica segura |
| `canonical_gtin` | texto | GTIN usado como identidad fuerte |
| `supermarket_id` | texto | cadena |
| `location_id` | texto | contexto exacto |
| `source_record_id` | texto | identidad trazable del registro fuente |
| `current_price` | decimal-texto | precio efectivo observado en HNL |
| `is_best_price` | booleano | coincide con el mínimo del producto en el alcance |

Los importes se serializan como decimal-texto para evitar redondeos binarios.

## `products`

| Campo | Tipo | Definición |
| --- | --- | --- |
| `canonical_product_id` | texto | producto canónico |
| `canonical_gtin` | texto | GTIN canónico |
| `best_supermarket_id` | texto | desempate determinista interno entre mínimos |
| `best_location_id` | texto | ubicación del mínimo determinista |
| `best_price` | decimal-texto | precio mínimo |
| `highest_price` | decimal-texto | precio máximo |
| `savings_vs_highest` | decimal-texto | diferencia máximo - mínimo |
| `savings_vs_highest_pct` | decimal-texto | diferencia relativa porcentual |
| `supermarket_count` | entero | número de supermercados incluidos |

El campo singular `best_supermarket_id` no elimina empates reales y no debe interpretarse como ganador global fuera del scope.

## `common_basket`

Cada fila representa exactamente el mismo conjunto comparable en un supermercado.

| Campo | Tipo | Definición |
| --- | --- | --- |
| `supermarket_id` | texto | supermercado |
| `location_id` | texto | ubicación |
| `total` | decimal-texto | suma de precios actuales del denominador común |
| `is_cheapest` | booleano | coincide con el mínimo del alcance |
| `product_count` | entero | cantidad de productos/unidades evaluadas |
| `denominator_definition` | texto | regla exacta del denominador |

Ausencia no equivale a cero. Si falta precio válido en una ubicación requerida, el producto sale del denominador común o la canasta queda incompleta según el contrato aplicado.

## Exclusiones

Motivos agregados posibles incluyen:

- `review_required`;
- `not_comparable`;
- `scope_membership_incomplete_or_ambiguous`;
- `price_missing_in_scope`.

Estos conteos permiten explicar pérdida de cobertura sin publicar comparaciones inseguras.

## Consumo legado en BI

Los consumidores que todavía lean este contrato deben usar IDs estables y los campos publicados. No deben rehacer matching por nombre, marca o presentación dentro de DAX o Power Query.
