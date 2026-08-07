# La Colonia — catálogo sanitizado de solicitudes públicas

Fecha: 2026-08-06. Estado: **incompleto**. No contiene cookies, tokens, secretos, identificadores privados ni datos personales.

## 1. Solicitudes y superficies

| Propósito | Método | Endpoint conceptual | Protocolo | operationName | Variables/campos principales | Respuesta relevante | Paginación | Ubicación | Confianza |
|---|---|---|---|---|---|---|---|---|---|
| Inicio | GET | `/` | HTML/HTTPS | n/a | n/a | shell, menú, promociones, selector | n/a | selector visible | observado |
| Supermercado raíz | GET | `/supermercado` | HTML/HTTPS | n/a | ruta | total 9,291, ordenamientos, facets | UI dinámica | no verificada | observado directo |
| Categoría | GET | `/supermercado/<slug-categoria>` | HTML/HTTPS | n/a | segmentos + `map` cuando aplica | total y filtros | UI/GraphQL | no verificada | observado/indexado |
| Subcategoría | GET | `/supermercado/<categoria>/<subcategoria>` | HTML/HTTPS | n/a | segmentos + `map` | total y filtros | UI/GraphQL | no verificada | observado/indexado |
| Búsqueda | GET | `/<texto>/supermercado?map=ft,category-1` o equivalente | HTML/HTTPS | n/a | término y mapa | conjunto transversal | UI/GraphQL | no verificada | observado/indexado |
| Marca | GET | ruta con `map=...,brand` | HTML/HTTPS | n/a | slug marca | conjunto de marca | UI/GraphQL | no verificada | observado/indexado |
| Landing | GET | ruta/facet `landing` | HTML/HTTPS | n/a | valor editorial | conjunto temporal | UI/GraphQL | no verificada | observado |
| Colección | GET | ruta con `productClusterIds` | HTML/HTTPS | n/a | ID público de cluster | conjunto curado | UI/GraphQL | no verificada | observado/indexado |
| Producto | GET | `/<linkText>/p` | HTML/HTTPS | n/a | slug | referencia, nombre, imágenes, specs, disponibilidad | n/a | alta | observado |
| Listado técnico | GET | `/_v/segment/graphql/v1` | GraphQL JSON/HTTPS | `productSearchV3` | query, fullText, selectedFacets, orderBy, from, to, hideUnavailableItems, skusFilter | `data.productSearch` | from/to inclusivos | segmento no verificado | confirmado por código existente |
| Menú técnico | Pendiente | Pendiente | Pendiente | Pendiente | categorías/enlaces | árbol o bloques de navegación | n/a | posible | pending |
| Facets técnicos | GET probable | búsqueda/facets VTEX ligada a ruta | JSON/GraphQL | Pendiente | ruta/map/selectedFacets | recordsFiltered, sampling, facets | n/a | posible | pending direct capture |
| Producto técnico | GET/GraphQL probable | consulta por slug/productId o reutilización de search | JSON/GraphQL | Pendiente | slug/productId | product, items, sellers, offers | n/a | alta | pending direct capture |
| Selector de tienda | interacción UI | mecanismo dinámico Pendiente | browser/session | n/a | ciudad/tienda | contexto comercial | n/a | sí | observed UI; technical pending |
| Localizador | GET | `/localizador-de-tiendas` | HTML/HTTPS | n/a | selector dinámico | ciudades/departamentos | n/a | funcional | observado |
| FAQ | GET | `/preguntas-frecuentes` | HTML/HTTPS | n/a | n/a | reglas de ciudad y pickup | n/a | sí | oficial |
| Términos | GET | `/terminos-y-condiciones` | HTML/HTTPS | n/a | n/a | precios/promos/disponibilidad por ciudad | n/a | sí | oficial |
| Cookies | GET | `/politicas-de-cookies` | HTML/HTTPS | n/a | n/a | descripción genérica de cookies | n/a | no específica | oficial |
| Robots | GET | `/robots.txt` | text/HTTPS | n/a | n/a | sitemap y rutas disallow | n/a | no | confirmado por red |
| Sitemap | GET | `/sitemap.xml` | XML/HTTPS | n/a | n/a | URLs públicas | n/a | no | pending content review |
| Imágenes | GET | `lacolonia.vtexassets.com/...` | binario/HTTPS | n/a | ruta asset | imagen pública | n/a | no | observado |

## 2. Consulta de listado implementada

Endpoint público implementado:

```text
https://www.lacolonia.com/_v/segment/graphql/v1
```

Método:

```text
GET
```

Parámetros de envelope utilizados por el código:

```text
workspace=master
maxAge=short
appsEtag=remove
domain=store
locale=es-HN
operationName=productSearchV3
query=<GraphQL document>
variables=<JSON compactado>
```

Proveedor GraphQL declarado:

```text
@context(provider: "vtex.search-graphql")
```

La URL completa no se publica porque contiene un documento GraphQL largo; no contiene un secreto, pero se conserva de forma conceptual para evitar ruido y acoplamiento accidental.

## 3. Variables de `productSearchV3`

| Variable | Tipo conceptual | Uso | Valor/regla actual | Estado |
|---|---|---|---|---|
| `query` | string | ruta categórica | `supermercado` o valor estructural | confirmed by code |
| `fullText` | string | búsqueda textual | vacío para categoría | confirmed by code |
| `selectedFacets` | lista key/value | filtros | por defecto `category-1=supermercado` | confirmed by code |
| `orderBy` | string | orden | allow-list | confirmed |
| `from` | int | inicio inclusivo | `(page-1)*page_size` | confirmed |
| `to` | int | fin inclusivo | `from+page_size-1` | confirmed |
| `hideUnavailableItems` | boolean | cobertura | `false` | confirmed |
| `skusFilter` | enum | SKU incluidos | `ALL` | confirmed |

Ordenamientos permitidos por el extractor:

```text
OrderByReleaseDateDESC
OrderByNameASC
OrderByNameDESC
OrderByPriceASC
OrderByPriceDESC
```

La UI muestra además relevancia, ventas y descuento. No se confirmó el identificador técnico de esos tres valores.

## 4. Estructura de respuesta solicitada

```text
data.productSearch.recordsFiltered
data.productSearch.products[]
products[].productId
products[].productName
products[].productReference
products[].linkText
products[].brand
products[].categories
products[].items[]
items[].itemId
items[].name
items[].nameComplete
items[].ean
items[].referenceId[].Key
items[].referenceId[].Value
items[].measurementUnit
items[].unitMultiplier
items[].images[].imageUrl
items[].sellers[].sellerId
items[].sellers[].sellerDefault
items[].sellers[].commertialOffer.Price
items[].sellers[].commertialOffer.ListPrice
items[].sellers[].commertialOffer.AvailableQuantity
items[].sellers[].commertialOffer.discountHighlights[].name
items[].sellers[].commertialOffer.teasers[].name
```

Nota: `commertialOffer` conserva la grafía histórica del esquema VTEX. El código la aliasa internamente como `commercialOffer` dentro del documento de consulta.

El parser también acepta `categoryTree` cuando está presente en la respuesta. Debe verificarse que el documento GraphQL actual realmente lo solicite o que se obtenga por otra consulta; el documento visible del helper no lo lista en la selección mínima mostrada. Esto es una inconsistencia a validar antes de modificar código.

## 5. Respuesta de facets esperada

El analizador offline espera un objeto sanitizado con:

```text
recordsFiltered: int
sampling: bool
facets: array
facets[].type: CATEGORYTREE | CATEGORY | otros
facets[].values[]
values[].key: category-N u otra facet
values[].value: slug/valor
values[].quantity: int >= 0
values[].children: array cuando aplica
```

Campos públicos de VTEX que también deben registrarse si aparecen:

```text
name
id
selected
hidden
```

La captura directa de esta respuesta no se realizó. Por tanto:

```text
endpoint exacto de facets = Pendiente
operationName = Pendiente
sampling actual = Pendiente
árbol real = Pendiente
```

## 6. Paginación

```text
from = índice inicial inclusivo
to = índice final inclusivo
page_size = to - from + 1
page_size máximo configurado por el runner = 50
```

El valor 50 es un límite del código actual, no una demostración del límite máximo del backend.

Para 9,291 productos en el contexto raíz sin tienda:

```text
ceil(9291 / 50) = 186 páginas
```

Ese cálculo no representa SPS y no autoriza un recorrido.

## 7. Contexto de ubicación y sesión

### Observado en La Colonia

- botón `Selecciona tu tienda`;
- selector de ciudad/departamento;
- PDP sin tienda con `No disponible`;
- documentación oficial de SPS y Plaza Pedregal.

### No observado

```text
cookie concreta = Pendiente
localStorage = Pendiente
sessionStorage = Pendiente
query parameter = Pendiente
header de región = Pendiente
contexto GraphQL = Pendiente
checkout session = Pendiente
seller/tienda interna = Pendiente
regionId = Pendiente
sales channel/binding = Pendiente
```

### Documentación de plataforma

VTEX describe como mecanismos posibles:

- `vtex_session`;
- `vtex_segment`;
- `postalCode` o `geoCoordinates`;
- `country`;
- `regionId`;
- canal y price tables.

No se registran valores de cookies, tokens o IDs de sesión. La presencia y configuración exactas en La Colonia deben demostrarse por UI pública en una prueba posterior.

## 8. Headers, cookies y datos sensibles

| Elemento | Tratamiento |
|---|---|
| User-Agent | identificable y conservador |
| Accept/Content-Type | estándar; confirmar en captura futura |
| cookies completas | `redacted`; no guardar |
| token de sesión | `redacted`; no guardar |
| identificadores personales | no recopilar |
| ID público de tienda/región | guardar solo si indispensable y no sensible |
| headers arbitrarios | prohibidos por contrato operacional |
| URL/query arbitraria | prohibida por contrato operacional |

## 9. Caché y CDN

Observado:

- assets desde CDN VTEX;
- query implementada usa `maxAge=short` y `appsEtag=remove`;
- endpoint bajo `/_v/segment/`, lo que sugiere contenido condicionado por segmento.

La semántica exacta de caché de La Colonia y las cabeceras reales de respuesta son Pendiente.

## 10. Errores y límites operativos

El cliente/runner existente distingue:

- HTTP 403 o captcha;
- HTTP 429;
- HTTP 5xx;
- respuesta vacía;
- JSON inválido;
- cambio de estructura;
- página parcial;
- página repetida;
- cambio de total;
- timeout/duración máxima.

Reglas de esta radiografía:

```text
concurrency = 1
delay mínimo entre requests lógicos de datos = 1.5 s
reintentos máximos = 1
stop = 403 persistente, 429, antibot, autenticación o riesgo de impacto
```

No apareció evidencia de 403, 429 o antibot porque no se ejecutó el endpoint técnico.

## 11. Solicitudes no realizadas

- endpoints autenticados;
- `/account`, `/login`, `/checkout`, `/api`;
- operaciones de carrito o compra;
- cambio de sesión por medios no públicos;
- consulta GraphQL masiva;
- full crawl;
- descarga de cientos o miles de productos;
- controlador operacional;
- workflows live;
- baseline500-003;
- validation500;
- recorrido particionado.

## 12. Evidencia y estado final

```text
solicitudes GraphQL exitosas en esta etapa = 0
respuestas de facets capturadas = 0
productos descargados por API = 0
PDP públicas muestreadas = conjunto pequeño mediante páginas/indexación
cookies/tokens guardados = 0
tráfico total exacto = Pendiente por limitación del tooling
```

La siguiente captura técnica propuesta es `SPS-context-and-root-facets-001`; todavía no está autorizada.
