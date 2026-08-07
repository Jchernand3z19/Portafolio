# La Colonia — inventario de campos

Estado: radiografía incompleta. No modifica contratos.

| Campo del sitio | Fuente | Nivel | RawProduct | NormalizedOffer | ValidatedOffer | Transformación | Obligatorio | Puede faltar | Ubicación | Estado |
|---|---|---|---|---|---|---|---|---|---|---|
| `productId` | GraphQL `productSearch.products[]` | product | `raw_values.product_id` | `source_product_id`, base de `product_id` | vía offer | texto estable | sí | no esperado | no confirmada | confirmed |
| `productReference` | product | product | fallback `source_sku` | evidencia secundaria | vía offer | primer valor no vacío | no | sí | no | confirmed |
| `productName` | product | product | `source_name` fallback | `source_name`, `normalized_name` | vía offer | trim | sí | raro | no | confirmed |
| `linkText` | product | product | `product_url` | `product_url` | vía offer | URL canónica `/linkText/p` | sí/fallback | sí | no | confirmed |
| `brand` | product | product | `source_brand` | `source_brand`, `normalized_brand` | vía offer | trim/normalización posterior | no | sí | no | confirmed |
| `categories` | product | product | `raw_values.categories` | `category/subcategory` | vía offer | conservar lista | no | sí | no | confirmed |
| `categoryTree` | product | product | `source_category`, raw | `category/subcategory` | vía offer | ruta `>` | no | sí | no | confirmed |
| `itemId` | `items[]` | SKU | clave fuente preferida | identidad SKU/oferta | vía offer | texto | sí para identidad preferida | posible | no | confirmed |
| `referenceId` | SKU | SKU | `source_sku` | `source_sku` | vía offer | seleccionar valor público | no | sí | no | confirmed |
| `ean` | SKU | SKU | `raw_values.ean` | `barcode` | vía offer | trim; no inventar | no | sí | no | confirmed |
| `name` | SKU | SKU | raw | `variant` potencial | vía offer | trim | no | sí | no | confirmed |
| `nameComplete` | SKU | SKU | `source_name`, presentación fallback | nombre/presentación | vía offer | parser conservador | no | sí | no | confirmed |
| `measurementUnit` | SKU | SKU | raw | `measurement_unit` | vía offer | normalizar unidad | no | sí | no | confirmed |
| `unitMultiplier` | SKU | SKU | raw | `content_per_unit`/multiplicador | vía offer | decimal positivo | no | sí | no | confirmed |
| `images[].imageUrl` | SKU | SKU | `image_url` | `image_url` | vía offer | primera HTTPS válida | no | sí | no | confirmed |
| `sellerId` | seller | offer | raw | parte de identidad oferta | vía offer | texto | recomendado | sí | probablemente | confirmed |
| `Price` | `commertialOffer` | offer | `raw_values.current_price` | `current_price` | state hash | decimal positivo | sí si in stock | sí si agotado | sí, pendiente | confirmed |
| `ListPrice` | offer | offer | raw | `reported_regular_price` | state hash | usar solo si mayor a Price | no | sí | sí, pendiente | confirmed |
| `AvailableQuantity` | offer | offer | raw | `availability` | state hash | no negativo; evidencia | no | sí | sí, pendiente | confirmed |
| teasers/promotions | offer | offer | `promotion_evidence` | `is_promotion` | state hash | sanitizar texto | no | sí | sí, pendiente | inferred/partial |
| `recordsFiltered` | `productSearch` | query | métricas | no comercial | no | entero >= productos | sí para cobertura | posible fallback | sí/índice | confirmed |
| `from` | variables | query | source URL | trazabilidad | no | índice inclusivo | sí | no | no | confirmed |
| `to` | variables | query | source URL | trazabilidad | no | índice inclusivo | sí | no | no | confirmed |
| `orderBy` | variables | query | source URL | trazabilidad | no | allow-list | sí | no | no | confirmed |
| Categoría visible | facets | facet | raw | category | vía offer | clasificar jerarquía | no | sí | posible | confirmed |
| Sub-Categoría visible | facets | facet | raw | subcategory | vía offer | clasificar jerarquía | no | sí | posible | confirmed |
| `Subcategoria` | specification facet | facet | raw | campo pendiente | vía eventos | no asumir hoja | no | sí | posible | confirmed |
| Marca | facets | facet | raw | normalized_brand | vía offer | facet no estructural | no | sí | posible | confirmed |
| Landing | facets | facet | raw | no mapeo directo | evento/metadata | promocional/editorial | no | sí | posible | confirmed |
| Impuestos | facets/especificación | product/facet | raw | hueco potencial | eventos | sanitizar; valores anómalos | no | sí | no | inconsistent |
| ciudad | selector | contexto | `location_evidence` | `location_status` | state hash indirecto | mecanismo Pendiente | sí para SPS | sí | sí | pending |
| tienda/sucursal | selector/checkout | contexto | `location_id` | `location_id` | state hash | ID público Pendiente | sí para SPS | sí | sí | pending |
| sales channel/binding | VTEX context | contexto | raw | contexto oferta | state hash | Pendiente | recomendado | sí | sí | pending |
| moneda explícita | respuesta/oferta | offer | raw | `currency` | vía offer | HNL esperado; confirmar campo | sí | posible | no | pending |
| timestamp | observación | run | `observed_at_utc` | igual | `validated_at_utc` | UTC | sí | no | no | confirmed |

## Huecos de contrato candidatos

No se implementan todavía.

1. **seller_id explícito en NormalizedOffer**: necesario si el mismo SKU puede tener ofertas distintas por seller.
2. **sales_channel/binding/store context**: necesario para reproducir precio y disponibilidad por ubicación.
3. **promotion_text/teaser estructurado**: el contrato actual conserva evidencia en `raw_values`, pero no tiene campo normalizado dedicado.
4. **effective_price**: actualmente `current_price` cumple funcionalmente este papel; debe decidirse si se agrega alias semántico o se documenta la equivalencia.
5. **tax_amount/tax_category**: solo si se confirma utilidad y limpieza; el facet observado contiene valores corruptos.

No modificar contratos hasta confirmar el mecanismo de ubicación y una muestra representativa de promociones.
