# La Colonia — catálogo sanitizado de solicitudes públicas

Fecha: 2026-08-06. Estado: incompleto. No contiene cookies, tokens, secretos ni datos personales.

| Propósito | Método | Endpoint conceptual | Protocolo | operationName | Variables/campos | Respuesta relevante | Paginación | Ubicación | Estado |
|---|---|---|---|---|---|---|---|---|---|
| Inicio | GET | `https://www.lacolonia.com/` | HTML/HTTPS | n/a | n/a | shell VTEX, menú, selector | n/a | selector visible | observed |
| Robots | GET | `/robots.txt` | texto/HTTPS | n/a | n/a | sitemap y rutas disallow | n/a | no | confirmed |
| Supermercado raíz | GET | `/supermercado?map=departamento` | HTML/HTTPS | n/a | `map=departamento` | total visible y facets | UI/GraphQL detrás | no confirmada | observed |
| Categoría | GET | `/supermercado/<slug>?map=c` | HTML/HTTPS | n/a | slug + `map=c` | listado/facets | UI/GraphQL | no confirmada | observed |
| Búsqueda | GET | `/<texto>/supermercado?map=ft` | HTML/HTTPS | n/a | texto + `map=ft` | resultados cruzados | UI/GraphQL | no confirmada | observed |
| Colección | GET | `/supermercado/<cluster>?map=c,productClusterIds` | HTML/HTTPS | n/a | cluster público | conjunto editorial | UI/GraphQL | no confirmada | observed |
| Listado técnico | GET | endpoint público VTEX GraphQL de `productSearch` | GraphQL/JSON/HTTPS | Pendiente | `from`, `to`, `orderBy`, query/map/fullText | `data.productSearch.products`, `recordsFiltered` | from/to inclusivos | contexto Pendiente | confirmed by extractor |
| Facets | GET/GraphQL | búsqueda/facets VTEX asociada a ruta y map | GraphQL/JSON/HTTPS | Pendiente | ruta, map, filtros seleccionados | categorías, marcas, landing, impuestos, subcategoría | no aplica | posible | partial |
| Producto | GET | `/<linkText>/p` | HTML/HTTPS | n/a | linkText | SKU, atributos, agotado | n/a | probable | observed |
| Producto técnico | GET/GraphQL | consulta VTEX de producto/búsqueda por slug | JSON/HTTPS | Pendiente | slug/productId | productId, items, sellers, offer | n/a | probable | pending exact request |
| Imágenes | GET | host público `vtexassets.com` | binario/HTTPS | n/a | ruta de asset | imagen pública | n/a | no | observed |
| FAQ | GET | `/preguntas-frecuentes` | HTML/HTTPS | n/a | n/a | reglas de ciudad, pickup y disponibilidad | n/a | sí | official |
| Sitemap | GET | `/sitemap.xml` | XML/HTTPS | n/a | n/a | URLs públicas | n/a | no | pending detailed review |

## Estructura GraphQL confirmada por el extractor existente

```text
data.productSearch.recordsFiltered
data.productSearch.products[]
products[].productId
products[].productReference
products[].productName
products[].linkText
products[].brand
products[].categories
products[].categoryTree
products[].items[]
items[].itemId
items[].referenceId
items[].ean
items[].name
items[].nameComplete
items[].measurementUnit
items[].unitMultiplier
items[].images[]
items[].sellers[]
sellers[].sellerId
sellers[].commertialOffer.Price
sellers[].commertialOffer.ListPrice
sellers[].commertialOffer.AvailableQuantity
```

Nota: `commertialOffer` conserva la grafía usada por VTEX.

## Parámetros de paginación

```text
from = índice inicial inclusivo
to = índice final inclusivo
page_size = to - from + 1
orderBy = valor allow-listed
```

Orden determinista recomendado para validación: `OrderByNameASC`.

## Headers y sesión

- User-Agent identificable: permitido por el cliente seguro existente.
- Cookies: redacted / no conservadas.
- Tokens: redacted / no observados como necesarios para el catálogo público.
- Sales channel, binding, región, ciudad y tienda: Pendiente.
- Contexto de checkout: no inspeccionado porque no fue necesario ni autorizado para esta etapa.

## Límites operativos

```text
concurrency = 1
delay mínimo = 1.5 segundos
reintentos máximos autorizados = 1
stop = 403 persistente, 429, antibot, autenticación o impacto potencial
```

## Solicitudes no realizadas

- endpoints autenticados;
- `/account`, `/login`, `/checkout`;
- operaciones de compra;
- full crawl;
- descarga masiva;
- controlador operacional;
- workflows live.
