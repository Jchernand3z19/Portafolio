# La Colonia — inventario completo de campos

Fecha de revisión: 2026-08-06. Estado: **radiografía incompleta**. Este documento no modifica contratos.

Estados:

- `confirmed`: confirmado por código existente o evidencia pública directa;
- `inferred`: mapeo razonable todavía no comprobado bajo contexto SPS;
- `unavailable`: no disponible en la evidencia actual;
- `inconsistent`: datos contradictorios o corruptos;
- `pending`: pendiente de captura.

## 1. Producto y SKU

| Campo del sitio | Fuente | Nivel | RawProduct | NormalizedOffer | ValidatedOffer | Transformación | Obligatorio | Puede faltar | Depende de ubicación | Ejemplo sanitizado | Estado |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `productId` | `productSearch.products[]` | product | `raw_values.product_id` | relación de agrupación; no es la llave primaria actual | vía offer/raw | texto estable | recomendado | posible | no | `12345` | confirmed |
| `productReference` | product | product | fallback de `source_sku` | evidencia secundaria | vía offer | primer valor no vacío | no | sí | no | `REF-001` | confirmed |
| `productName` | product | product | `source_name` fallback | `source_name`, `normalized_name` | vía offer | trim; normalización posterior | sí | raro | no | `Producto ejemplo` | confirmed |
| `linkText` | product | product | construye `product_url` | `product_url` | vía offer | URL absoluta `/<slug>/p` | fallback | sí | no | `producto-ejemplo` | confirmed |
| `brand` | product | product | `source_brand` | `source_brand`, `normalized_brand` | state hash | trim/canonicalización | no | sí | no | `Marca` | confirmed |
| `description` | PDP/consulta producto | product | no mapeado actualmente | hueco potencial | no | sanitizar HTML/texto | no | sí | no | `Descripción...` | pending |
| `categories` | product | product | `raw_values.categories` | categorías fuente | vía offer | conservar lista ordenada | no | sí | posible | `[/Supermercado/.../]` | confirmed |
| `categoryTree` | product | product | `source_category`, raw | `category`, `subcategory` | state hash | ruta jerárquica | no | sí | posible | `Supermercado > Abarrotes` | confirmed |
| breadcrumb | PDP | product | no mapeado | evidencia de categoría | no | lista ordenada | no | sí | no | `Supermercado > ...` | observed/partial |
| `itemId` | `items[]` | SKU | `source_key` preferida (`internal_id`) | base real del `source_product_id` actual | vía offer | texto estable | sí para identidad preferida | posible | no | `67890` | confirmed |
| `referenceId` | SKU | SKU | `source_sku` | `source_sku` | vía offer | seleccionar valor público | no | sí | no | `SKU-01` | confirmed |
| `ean` | SKU | SKU | `raw_values.ean` | `barcode` | vía offer | trim; no inventar | no | sí | no | `0000000000000` | confirmed |
| `name` | SKU | SKU | `raw_values.item_name` | `variant` candidato | state hash | trim | no | sí | no | `500 Ml` | confirmed |
| `nameComplete` | SKU | SKU | `source_name`, fallback presentación | nombre/variante/presentación | vía offer | parser conservador | no | sí | no | `Producto 500 Ml` | confirmed |
| `measurementUnit` | SKU | SKU | raw | `measurement_unit` | state hash | normalizar unidad | no | sí | no | `un`, `kg` | confirmed |
| `unitMultiplier` | SKU | SKU | raw | `content_per_unit` o multiplicador | state hash | decimal positivo | no | sí | no | `1` | confirmed |
| `images[].imageUrl` | SKU | SKU | `image_url` | `image_url` | vía offer | primera URL HTTPS válida | no | sí | no | `https://.../asset.jpg` | confirmed |
| atributos/especificaciones SKU | PDP/Search GraphQL | SKU | `raw_values` futuro | presentación/variante | state hash si se normaliza | allow-list por campo | no | sí | no | `sabor=...` | pending |

### Aclaración de identidad

El contrato genera `source_product_id` desde `source_key`. Como La Colonia selecciona primero `itemId`, ese identificador es actualmente **SKU-level**, no `productId`-level. Deben conservarse ambos:

```text
product aggregate = productId
SKU identity = itemId
source_product_id actual = hash de itemId, salvo fallback
```

## 2. Oferta, precio y promoción

| Campo del sitio | Fuente | Nivel | RawProduct | NormalizedOffer | ValidatedOffer | Transformación | Obligatorio | Puede faltar | Depende de ubicación | Ejemplo sanitizado | Estado |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `sellerId` | `items[].sellers[]` | offer | `raw_values.seller_id` | hueco: no existe campo explícito | vía raw/offer | texto | recomendado | sí | sí/probable | `seller-1` | confirmed |
| `sellerDefault` | seller | offer | no conservado | selección de seller | no | booleano | no | sí | sí | `true` | confirmed by query schema |
| `Price` | `commertialOffer` | offer/SKU | `raw_values.current_price` | `current_price` | state hash | decimal positivo | sí si `in_stock` | sí si no disponible | sí, no verificado | `99.90` | confirmed by code |
| `Price` como precio pagadero | offer/SKU | offer/SKU | raw | semánticamente `effective_price` | state hash vía current | usar solo bajo contexto reproducible | sí para oferta | sí | sí | `99.90` | inferred pending SPS |
| `ListPrice` | offer/SKU | offer/SKU | `source_list_price` | `reported_regular_price` solo si mayor que Price | state hash | decimal positivo | no | sí | sí/probable | `119.90` | confirmed by code |
| `PriceWithoutDiscount` | Search GraphQL disponible en plataforma | offer | no solicitado | hueco potencial | no | no usar sin captura | no | sí | sí | `...` | pending |
| `spotPrice` | Search GraphQL disponible en plataforma | offer | no solicitado | hueco potencial | no | no usar sin captura | no | sí | sí | `...` | pending |
| `AvailableQuantity` | offer/SKU | offer | `raw_values.available_quantity` | `availability` | state hash | señal no negativa; no asumir stock exacto | no | sí | sí | `10` | confirmed by code |
| `discountHighlights[].name` | offer | offer | `promotion_evidence` | `is_promotion`; texto sin campo dedicado | state hash booleano | sanitizar | no | sí | posible | `Promoción` | confirmed by query schema |
| `teasers[].name` | offer | offer | `promotion_evidence` | `is_promotion`; texto sin campo dedicado | state hash booleano | sanitizar | no | sí | posible | `Oferta` | confirmed by query schema |
| `discount_percentage` | derivado | offer | raw futuro | hueco o derivado de Price/ListPrice | no directo | `(ListPrice-Price)/ListPrice` | no | sí | sí | `16.68` | inferred |
| moneda | contexto/UI/oferta | offer | raw futuro | `currency` | vía offer | código ISO `HNL` solo cuando se confirme | sí | posible | no | `HNL` | pending explicit field |
| `Tax` | Search GraphQL/checkout | offer | no solicitado | hueco potencial | no | decimal | no | sí | posible | `...` | pending |
| `taxPercentage` | Search GraphQL | offer | no solicitado | hueco potencial | no | porcentaje | no | sí | posible | `15` | pending |
| `Impuestos` | especificación/facet | product/facet | raw futuro | no mapear sin limpieza | quality event | allow-list `0/15/18`; rechazar fórmulas | no | sí | no | `15` | inconsistent |
| `PriceValidUntil` | oferta VTEX | offer | no solicitado | hueco potencial | no | UTC/nullable | no | sí | sí/promoción | `...` | pending |

### Semántica de precios

```text
current_price = Price
selling_price = Price
effective_price = Price mostrado como pagadero bajo contexto verificado
list_price = ListPrice
reported_regular_price = ListPrice solo si el sitio lo presenta por encima de Price
```

Una reducción respecto al histórico del proyecto no convierte por sí sola el registro en promoción declarada.

## 3. Disponibilidad y ubicación

| Campo/mecanismo | Fuente | Nivel | RawProduct | NormalizedOffer | ValidatedOffer | Regla | Obligatorio | Puede faltar | Estado |
|---|---|---|---|---|---|---|---|---|---|
| estado visible `No disponible` | PDP sin tienda | context/SKU | evidencia raw | `availability=unknown` mientras no haya tienda | state hash | no interpretar como agotado global | no | sí | observed |
| `AvailableQuantity` | offer | offer | raw | availability | state hash | combinar con seller y Price | no | sí | confirmed by code |
| mensaje `Agotado SPS/TGU` | términos | context/SKU | evidencia futura | out_of_stock por ciudad | state hash | requiere observarlo bajo contexto | no | sí | official/pending observation |
| ciudad | selector | context | `location_evidence` | `location_status` | vía offer | SPS debe ser reproducible | sí para objetivo SPS | sí | pending technical mechanism |
| tienda/sucursal | selector/checkout | context | `location_id` | `location_id` | parte de offer_id | ID público no recuperado | sí para SPS | sí | pending |
| Plaza Pedregal | FAQ | pickup | evidencia | no es por sí sola `location_id` | no | punto funcional SPS | no | n/a | official |
| `vtex_session` | plataforma VTEX | session | no guardar valor | contexto potencial | no | registrar nombre, no contenido | no | sí | platform inference |
| `vtex_segment` | plataforma VTEX | segment | no guardar valor | contexto potencial | no | registrar nombre, no contenido | no | sí | platform inference |
| `postalCode`/`geoCoordinates` | VTEX session | context | no capturado | contexto potencial | no | dato público solo si indispensable | no | sí | platform inference |
| `country` | VTEX session | context | no capturado | contexto potencial | no | ISO país | no | sí | platform inference |
| `regionId` | VTEX checkout/segment | context | no capturado | contexto oferta | parte potencial de identidad | valor redacted si sensible | recomendado | sí | platform inference |
| sales channel/binding | VTEX | context | no capturado | contexto oferta | no | registrar identificador público | recomendado | sí | pending |
| localStorage/sessionStorage/query/header | navegador | context | no capturado | contexto oferta | no | inspección futura | no | sí | pending |

Regla actual correcta:

```text
location_id = la_colonia_online
location_status = unknown
location classification = location_not_verified
```

## 4. Taxonomía, facets y consulta

| Campo/filtro | Fuente | Nivel | Mapeo | Transformación | Estructural | Puede faltar | Ubicación | Estado |
|---|---|---|---|---|---:|---:|---:|---|
| `recordsFiltered` | `productSearch` | query | métricas de cobertura | entero >= productos devueltos | n/a | no esperado | sí/posible | confirmed by code |
| `from` | variables | query | source URL/trazabilidad | entero inclusivo | n/a | no | no | confirmed |
| `to` | variables | query | source URL/trazabilidad | entero inclusivo | n/a | no | no | confirmed |
| `orderBy` | variables | query | source URL/trazabilidad | allow-list | n/a | no | no | confirmed |
| `query` | variables | query | ruta de categoría | texto | sí según map | no | posible | confirmed by code |
| `fullText` | variables | search | búsqueda | trim | no | sí | posible | confirmed by code |
| `selectedFacets[].key/value` | variables | query | partición/filtro | allow-list | depende | sí | posible | confirmed by code |
| `hideUnavailableItems` | variables | query | cobertura | mantener false en auditoría | n/a | no | sí | confirmed by code |
| `skusFilter` | variables | query | cobertura SKU | `ALL` | n/a | no | no | confirmed by code |
| `sampling` | respuesta facets | query | bloqueo de cobertura | booleano | n/a | no esperado | posible | pending live capture |
| `facets[].type` | facets | facet | clasificación | enum/texto | depende | no | posible | pending live capture |
| `facets[].name` | facets | facet | nombre visible | texto | depende | sí | posible | pending live capture |
| `values[].key` | facets | facet | nivel técnico | `category-N`/spec | depende | no | posible | pending live capture |
| `values[].value` | facets | facet | slug/valor | conservar/sanitizar | depende | no | posible | pending live capture |
| `values[].quantity` | facets | facet | presupuesto | entero >=0 | n/a | no | posible | pending live capture |
| `values[].children` | facets | facet | árbol | lista | sí | puede omitirse | posible | pending live capture |
| `values[].selected` | facets | facet | estado filtro | booleano | no | sí | posible | pending live capture |
| Departamento/`category-1` | URL/facet | structural | `source_category`, category | nivel 1 | sí | no | posible | confirmed/partial |
| Categoría/`category-2` | UI/URL | structural | category | nivel 2 | sí | sí | posible | observed |
| Sub-Categoría/`category-3` | UI/URL | structural | subcategory | nivel 3 | sí | sí | posible | observed |
| `category-4...8` | analizador | structural possible | pendiente | no asumir | posible | sí | posible | pending |
| Marca/`brand` | facet | facet | brand | normalizar | no | sí | posible | observed |
| Landing | facet | editorial | raw/metadata | no categoría | no | sí | posible | observed |
| `Subcategoria` | specification | facet | hueco o clasificación auxiliar | no asumir hoja | no demostrado | sí | posible | observed |
| Impuestos | specification | facet | quality event | validar allow-list | no | sí | no | inconsistent |
| `productClusterIds` | URL | collection | membership | conservar por evidencia | no | sí | posible | observed |
| `ft` | URL | search | consulta diagnóstica | texto | no | sí | posible | observed |

## 5. Campos del proyecto sin fuente confirmada

| Campo NormalizedOffer | Situación | Estado |
|---|---|---|
| `normalized_name` | derivable de nombres; reglas específicas no revisadas | pending normalization |
| `normalized_brand` | fuente brand confirmada, normalización pendiente | partial |
| `variant` | `name`/atributos SKU candidatos | pending |
| `unit_count` | nombre o atributos, no confirmado | pending |
| `content_per_unit` | unitMultiplier/nombre, semántica depende del SKU | pending |
| `measurement_unit` | fuente confirmada | confirmed by code |
| `total_content` | derivado solo si cantidad/unidad confiables | pending |
| `unit_price` | requiere precio y contenido verificados | pending |
| `unit_price_basis` | regla por unidad pendiente | pending |
| `currency` | HNL esperado, campo técnico explícito pendiente | pending |
| `availability` | parser existe, contexto SPS pendiente | partial |

## 6. Huecos de contrato candidatos

No se implementan en esta etapa.

1. **`seller_id` explícito:** necesario si un SKU tiene ofertas distintas por seller.
2. **`source_product_catalog_id` o `vtex_product_id`:** para separar el agregado `productId` de la identidad SKU actual.
3. **contexto de tienda/región/canal:** necesario para reproducir precio y disponibilidad SPS.
4. **`promotion_text` estructurado:** actualmente solo puede conservarse en `raw_values`.
5. **`effective_price`:** decidir si `current_price` es el nombre contractual definitivo o si se agrega un alias semántico.
6. **impuestos:** solo si se confirma una fuente técnica limpia; el facet visible contiene datos corruptos.
7. **vigencia de precio/promoción:** `PriceValidUntil` si la respuesta real lo ofrece.
8. **estado `location_not_verified`:** decidir si permanece como evento/calificación sobre `LocationStatus.UNKNOWN` o requiere enum propio.

## 7. Campos obligatorios a localizar en la siguiente prueba

Prioridad bloqueante:

1. mecanismo público de ciudad/tienda SPS;
2. identificador de contexto público no sensible;
3. `productId`, `itemId`, seller;
4. Price, ListPrice, AvailableQuantity;
5. moneda;
6. respuesta de facets con sampling, quantities y children;
7. categoría jerárquica completa;
8. una oferta normal, una promocional y una no disponible bajo SPS.

No se deben modificar contratos hasta capturar esas evidencias.
