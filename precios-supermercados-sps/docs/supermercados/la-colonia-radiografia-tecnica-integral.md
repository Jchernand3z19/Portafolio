# La Colonia — radiografía técnica integral

## 1. Resumen ejecutivo

Fecha de análisis: **2026-08-06**, sesión iniciada a las **22:55 America/Tegucigalpa**.

Clasificación final: **radiografía incompleta / inconclusive para full crawl**.

Hallazgos principales:

- **observado:** la superficie pública actual está construida sobre tecnología VTEX; usa assets de `lacolonia.vtexassets.com`, URLs con `map` y una PLP facetada;
- **confirmado en el código existente:** el extractor consume el endpoint público `/_v/segment/graphql/v1`, operación `productSearchV3`, proveedor `vtex.search-graphql`;
- **observado:** `/supermercado` muestra **9,291 productos** bajo el estado por defecto **sin tienda seleccionada**;
- **observado:** el sitio muestra `Selecciona tu tienda`; las fichas muestreadas, sin tienda, muestran `No disponible` y no presentan un precio pagadero;
- **documentación oficial de La Colonia:** el primer paso de compra es seleccionar ciudad; la venta en línea atiende Tegucigalpa y San Pedro Sula, con pickup SPS en Plaza Pedregal; precios, promociones, productos y disponibilidad pueden variar entre canales y ciudades;
- **conclusión:** no puede afirmarse que el total, precio o disponibilidad del contexto por defecto representen San Pedro Sula;
- **regla obligatoria:** mientras no exista un contexto SPS reproducible, toda observación comercial debe conservar `location_status=unknown` y clasificarse como `location_not_verified`;
- **observado:** la interfaz expone 15 categorías principales, al menos 81 valores visibles de `Sub-Categoría`, 34 landings, 1,475 marcas y 279 valores de la especificación `Subcategoria`; estos conteos proceden de botones `Mostrar N más` y no prueban que la respuesta técnica esté completa;
- **observado:** el facet `Impuestos` contiene valores válidos `0`, `15`, `18` y numerosos valores corruptos tipo `VLOOKUP(...)`;
- **no demostrado:** sampling, árbol completo, categorías hoja, solapamientos, productos sin hoja, límite efectivo de paginación, total SPS, estabilidad de páginas y presupuesto final;
- **decisión:** no está listo para full crawl.

No se ejecutó controlador operacional, GitHub Actions live, facet discovery, baseline500-003, validation500, recorrido particionado ni descarga masiva.

## 2. Alcance, método y niveles de confianza

Se revisaron contratos y código de PR #7, páginas públicas, documentación oficial de La Colonia y documentación pública de VTEX. No se inició sesión, no se usaron credenciales, no se añadió al carrito y no se accedió a rutas desautorizadas.

Clasificaciones usadas:

- **observado directamente:** visible en HTML o interfaz pública;
- **confirmado por red:** recuperado de una respuesta pública concreta;
- **confirmado por código existente:** campo o endpoint ya implementado sobre capturas anteriores del proyecto, pero no necesariamente revalidado en red en esta sesión;
- **documentación oficial:** afirmación publicada por La Colonia o VTEX;
- **inferencia:** conclusión razonable apoyada por evidencia, todavía no demostrada en La Colonia;
- **hipótesis:** requiere una prueba futura;
- **Pendiente:** no recuperado.

La herramienta de navegación no expone un contador fiable de requests de navegador ni DevTools. Por ello el tráfico total exacto se marca **Pendiente**. No se realizaron consultas directas exitosas al endpoint GraphQL ni un recorrido de productos.

## 3. Contratos existentes del proyecto

### 3.1 RawProduct

Campos obligatorios ya definidos:

- `supermarket_id`, `location_id`;
- `source_key_type`, `source_key`;
- `source_name`, `product_url`;
- `observed_at_utc`, `scrape_run_id`;
- `extractor_version`, `schema_version`, `source_url`.

Campos fuente opcionales:

- `source_sku`, `source_brand`, `source_presentation`, `source_category`;
- `image_url`;
- `location_status`, `location_evidence`, `location_confidence`;
- `raw_values`.

### 3.2 NormalizedOffer

El contrato espera:

- identidad determinista de producto y oferta;
- ubicación;
- nombre, marca, categoría, subcategoría y variante;
- precio actual, precio regular reportado y precio unitario opcional;
- moneda;
- promoción;
- disponibilidad;
- presentación descompuesta en cantidad, contenido y unidad;
- trazabilidad de corrida y fuente.

Campos que generan revisión pendiente cuando faltan:

- `normalized_brand`;
- `category`;
- `subcategory`;
- `unit_count`;
- `content_per_unit`;
- `measurement_unit`;
- `total_content`.

### 3.3 ValidatedOffer y state_hash

`ValidatedOffer` conserva la oferta, `state_hash` SHA-256, fecha UTC de validación y eventos de calidad.

El hash de estado incluye:

- `current_price`;
- `reported_regular_price`;
- `is_promotion`;
- `availability`;
- marca, categoría, subcategoría y variante normalizadas;
- cantidad, contenido, unidad y contenido total.

### 3.4 Identificadores actuales

Prioridad de `select_source_key`:

1. `internal_id`;
2. `sku`;
3. `barcode`;
4. `api_id`;
5. URL estable.

En La Colonia, `internal_id` recibe `items[].itemId`; por ello cada `RawProduct` representa actualmente un **SKU**, aunque el nombre `source_product_id` del contrato normalizado puede inducir a pensar en el agregado `productId`.

No se crearon contratos paralelos ni se modificaron contratos.

## 4. Mapa funcional público

| Superficie | URL conceptual | Tipo | Datos visibles | Dependencia de sesión/ubicación | Utilidad |
|---|---|---|---|---|---|
| Inicio | `/` | landing | menú, ofertas, promociones, campañas, selector | selector visible | descubrimiento editorial |
| Supermercado raíz | `/supermercado` | PLP raíz | total, ordenamientos, facets | contexto no verificado | universo de referencia candidato |
| Categoría | `/supermercado/<categoria>` | PLP estructural | total y facets | posible | partición candidata |
| Subcategoría | `/supermercado/<categoria>/<subcategoria>` | PLP estructural | total y facets | posible | hoja candidata, no demostrada |
| Búsqueda | `/<texto>/supermercado?map=ft,category-1` o equivalente | PLP full text | resultados cruzados | posible | diagnóstico, no cobertura primaria |
| Marca | ruta con `map=...,brand` | PLP facetada | productos de marca | posible | validación secundaria |
| Landing | ruta/facet `landing` | PLP editorial/promocional | conjuntos temporales | posible | no estructural |
| Colección | `productClusterIds` o searchable cluster | PLP curada | conjunto de campaña | posible | no estructural |
| Producto | `/<linkText>/p` | PDP | referencia, nombre, imágenes, especificaciones, disponibilidad | alta | detalle de SKU/producto |
| Selector de tienda | botón global | UI dinámica | `Selecciona tu tienda` | sí | contexto comercial bloqueante |
| Localizador | `/localizador-de-tiendas` | selector/listado | ciudad/departamento | no necesariamente sesión comercial | evidencia de sucursales |
| FAQ | `/preguntas-frecuentes` | documento oficial | proceso de compra y SPS | n/a | reglas funcionales |
| Términos | `/terminos-y-condiciones` | documento oficial | precios, promociones, disponibilidad por ciudad | n/a | límites y semántica |
| Robots | `/robots.txt` | texto | sitemap y rutas desautorizadas | n/a | límite operativo |
| Mobile legacy | `mobile.lacolonia.com` | storefront alterno | taxonomía histórica y `Sin ciudad` | sí | evidencia auxiliar; robots lo desautoriza |

No se debe tratar todo enlace de menú como categoría: ofertas, promociones, recetas, campañas, landings y colecciones son superficies editoriales o promocionales.

## 5. Ubicación, tienda y San Pedro Sula

### 5.1 Observado directamente

- el encabezado actual muestra `Selecciona tu tienda`;
- `/supermercado` devuelve el total sin mostrar una tienda seleccionada;
- fichas de producto muestreadas muestran `No disponible` sin precio;
- el localizador muestra `Elige ciudad o departamento`, pero los valores se cargan dinámicamente;
- la versión móvil indexada muestra `Enviar a Sin ciudad`.

### 5.2 Documentación oficial de La Colonia

- el primer paso de compra es seleccionar la ciudad del domicilio;
- la venta en línea atiende Tegucigalpa y San Pedro Sula;
- el pickup de SPS se realiza en Plaza Pedregal;
- la disponibilidad puede variar por ciudad;
- existen productos exclusivos por ciudad y mensajes como `AgotadoTGU` o `Agotado SPS`;
- precios, productos y promociones web pueden diferir de tiendas físicas y otros canales.

### 5.3 Mecanismo técnico

No se observó directamente en La Colonia cuál de estos mecanismos conserva la selección:

- cookie;
- `localStorage`;
- `sessionStorage`;
- query parameter;
- header;
- contexto GraphQL;
- sesión de checkout;
- binding/sales channel;
- `regionId`;
- seller o tienda interna.

La documentación de VTEX describe `vtex_session`, `vtex_segment`, `postalCode`, `country`, `regionId`, canal y tablas de precio como mecanismos posibles de regionalización. Esto es **documentación de plataforma**, no prueba de la configuración concreta de La Colonia.

### 5.4 Conclusión de ubicación

```text
San Pedro Sula disponible funcionalmente = confirmado
San Pedro Sula seleccionado en esta sesión = no
identificador interno de tienda SPS = Pendiente
identificador de región SPS = Pendiente
consulta por defecto representa SPS = no demostrado
location_status = unknown
clasificación comercial = location_not_verified
```

No puede garantizarse que precios o disponibilidad pertenezcan a SPS.

## 6. Plataforma y arquitectura técnica

### 6.1 Plataforma

Clasificación: **VTEX storefront / VTEX IO, confianza alta**.

Evidencia:

- assets públicos en `lacolonia.vtexassets.com`;
- URLs VTEX con `map`, `category-1`, `category-2`, `brand`, `ft`, `productClusterIds` y filtros de especificación;
- código existente sobre `vtex.search-graphql`;
- endpoint implementado `https://www.lacolonia.com/_v/segment/graphql/v1`;
- alias histórico `commertialOffer` propio del esquema VTEX.

La respuesta GraphQL actual no fue re-observada directamente en esta sesión porque la herramienta de navegación no permitió abrir la URL dinámica completa. Su vigencia debe validarse en la siguiente prueba controlada.

### 6.2 Listado técnico implementado

```text
método = GET
protocolo = HTTPS + GraphQL JSON
endpoint = /_v/segment/graphql/v1
operationName = productSearchV3
provider = vtex.search-graphql
nodo = data.productSearch
productos = data.productSearch.products
total = data.productSearch.recordsFiltered
```

Variables implementadas:

- `query`;
- `fullText`;
- `selectedFacets`;
- `orderBy`;
- `from`;
- `to`;
- `hideUnavailableItems=false`;
- `skusFilter=ALL`.

### 6.3 Menú, facets y producto

- endpoint exacto actual del menú: **Pendiente**;
- endpoint exacto actual de facets: **Pendiente**; el proyecto espera una respuesta con `recordsFiltered`, `sampling`, `facets`, `type`, `values`, `key`, `value`, `quantity`, `children`;
- endpoint exacto dedicado de PDP: **Pendiente**; el extractor reutiliza búsqueda/listado para campos del producto;
- imágenes: host público de assets VTEX.

## 7. Taxonomía observada

### 7.1 Niveles

| Nivel | Nombre visible/técnico | Clasificación | Estado |
|---|---|---|---|
| 1 | `category-1` / Departamento | estructural | confirmado por código y URLs |
| 2 | Categoría | estructural | observado |
| 3 | Sub-Categoría | estructural | observado |
| 4+ | `category-4...category-8` | posible | permitido por analizador, no observado |
| especificación | `Subcategoria` | filtro textual/especificación | observado; no asumir hoja |

### 7.2 Categorías principales visibles

La interfaz raíz muestra 10 y el botón `Mostrar 5 más`, es decir, **15 valores de Categoría visibles como mínimo**:

1. Abarrotes;
2. Belleza y Cuidado Personal;
3. Cuidado del Hogar;
4. Bebidas y Jugos;
5. Lácteos, no Lácteos, Derivados y Huevos;
6. Cervezas Licores y Vinos;
7. Bebé y Niños;
8. Congelados y Refrigerados;
9. Artículos para el Hogar y Útiles;
10. Panadería y Tortillas;
11–15. ocultas en el HTML resumido; la navegación histórica incluye Frutas y Verduras, Carnes y Aves, Pescados y Mariscos, Embutidos y Mascotas, pero su correspondencia actual debe verificarse.

### 7.3 Subcategorías y otros facets

- `Sub-Categoría`: 10 visibles + `Mostrar 71 más` = al menos **81**;
- `Landing`: 10 visibles + `Mostrar 24 más` = al menos **34**;
- `Marca`: 10 visibles + `Mostrar 1465 más` = al menos **1,475**;
- `Subcategoria`: 10 visibles + `Mostrar 269 más` = al menos **279**;
- `Impuestos`: valores normales `0`, `15`, `18` más al menos 40 valores adicionales, varios corruptos.

Estos conteos son de interfaz y pueden cambiar por consulta, contexto o actualización del índice. No sustituyen una respuesta de facets completa.

### 7.4 Distinciones obligatorias

- **departamento:** raíz estructural `Supermercado`;
- **categoría:** nivel estructural bajo departamento;
- **subcategoría:** nivel estructural bajo categoría;
- **categoría hoja:** nodo estructural sin hijos; todavía no identificada integralmente;
- **marca:** facet de marca, no categoría;
- **landing:** etiqueta editorial/promocional;
- **colección:** cluster de productos;
- **promoción:** condición comercial o conjunto temporal;
- **búsqueda:** full text `ft`;
- **filtro textual:** especificaciones como `Subcategoria`;
- **página especial:** ofertas, campañas, recetas;
- **desconocido:** cualquier ruta cuyo `map` no se haya interpretado.

## 8. Facets y filtros

| Filtro | Tipo | Estructural | Puede particionar | Riesgo de solapamiento | Estado |
|---|---|---:|---:|---:|---|
| Departamento | categoría nivel 1 | sí | candidato | bajo/medio | partial |
| Categoría | categoría nivel 2 | sí | candidato | alto con padre/hijos | observed |
| Sub-Categoría | categoría nivel 3 | sí | hoja candidata | alto | observed |
| Marca | brand | no | no primaria | alto | observed |
| Precio | rango/orden | no | solo diagnóstico | medio | Pendiente como facet visible |
| Impuestos | especificación | no | no | alto y datos corruptos | inconsistent |
| Landing | especificación/editorial | no | no | muy alto | observed |
| Promoción/Ofertas | especificación/cluster | no | no | muy alto | observed/partial |
| Disponibilidad | contexto seller | no | no primaria | cambia por ubicación | Pendiente |
| Vendedor | offer/seller | no | posible dimensión de oferta | sí | confirmado por código |
| Tipo de producto | especificación | no | Pendiente | Pendiente | Pendiente |
| `Subcategoria` | especificación textual | no demostrado | no primaria | alto | observed |
| `productClusterIds` | colección | no | no | alto | observed en URLs |
| `ft` | búsqueda | no | no | alto | observed en URLs |

Campos esperados de la respuesta técnica de facets: `sampling`, `quantity`, `children`, `selected`, `type`, `name`, `value`, `key`. Ninguno fue capturado directamente en esta sesión; quedan Pendiente.

## 9. Listados muestreados

| Superficie | Total observado/indexado | Clasificación |
|---|---:|---|
| raíz `/supermercado` | 9,291 | actual, sin tienda verificada |
| categoría Abarrotes | 2,934 en captura indexada reciente | grande |
| categoría Bebidas y Jugos | 574 | mediana |
| subcategoría Jugos | 200 | estructural candidata |
| filtro textual pequeño | 8–36 según ruta | pequeño, no necesariamente hoja |
| búsqueda `bebidas` | conjunto transversal | búsqueda, no partición |
| colección `productClusterIds` | 209 en una captura | colección |
| página de marca | 9–13 en ejemplos indexados | marca |

No se descargaron páginas de productos del listado ni se midieron IDs de unión.

## 10. Paginación y orden

Confirmado por código:

```text
from = índice inicial inclusivo
to = índice final inclusivo
page_size = to - from + 1
page_size máximo configurado = 50
```

Ordenamientos visibles:

- relevancia;
- ventas;
- fecha de release;
- descuento;
- precio ascendente/descendente;
- nombre ascendente/descendente.

El runner funcional usa `OrderByNameASC` como orden determinista y detecta:

- discontinuidad `from/to`;
- cambio de orden;
- páginas parciales;
- páginas repetidas mediante firma;
- cambios de total;
- duplicados de producto y SKU.

Pendiente de observar en red:

- tamaño de página real aceptado por el endpoint actual;
- límite máximo del backend;
- scroll infinito/carga diferida actual;
- estabilidad al repetir;
- páginas repetidas o parciales reales;
- sampling;
- comportamiento al superar fronteras.

## 11. Detalle de producto

Muestras públicas revisadas incluyen productos de cuidado personal, abarrotes y fruta. Sin tienda seleccionada mostraron:

- marca visible como `La Colonia` en la ficha;
- `Referencia`;
- nombre;
- imágenes;
- pestañas de descripción/especificaciones/ingredientes;
- `Subcategoria` e `Impuestos` cuando existen;
- estado `No disponible`;
- sin precio pagadero visible.

Campos confirmados por el extractor existente:

| Concepto | Campo fuente | Nivel |
|---|---|---|
| producto | `productId` | product |
| referencia producto | `productReference` | product |
| SKU | `items[].itemId` | SKU |
| referencia SKU | `items[].referenceId` | SKU |
| EAN/GTIN | `items[].ean` | SKU |
| nombre | `productName`, `name`, `nameComplete` | product/SKU |
| marca | `brand` | product |
| categorías | `categories`, `categoryTree` | product |
| slug | `linkText` | product |
| imágenes | `items[].images[].imageUrl` | SKU |
| vendedor | `items[].sellers[].sellerId` | offer |
| precio actual | `commertialOffer.Price` | offer/SKU |
| precio lista | `commertialOffer.ListPrice` | offer/SKU |
| cantidad | `commertialOffer.AvailableQuantity` | offer/SKU |
| promoción | `discountHighlights`, `teasers` | offer/SKU |
| unidad | `measurementUnit` | SKU |
| multiplicador | `unitMultiplier` | SKU |

No se confirmó en esta sesión un producto con precio normal, promoción visible, varios SKU o EAN ausente bajo contexto SPS. Esos casos permanecen Pendiente.

## 12. Precio, promoción y presentación

### 12.1 Reglas respaldadas por el código existente

| Campo objetivo | Fuente | Regla | Estado |
|---|---|---|---|
| `current_price` | `Price` | decimal positivo del seller seleccionado | confirmed by code |
| `effective_price` | `Price` | precio actual mostrado/pagadero bajo contexto verificado | inferred semantic mapping |
| `list_price` | `ListPrice` | conservar valor fuente | confirmed by code |
| `reported_regular_price` | `ListPrice` | solo si `ListPrice > Price` | confirmed by code |
| `is_promotion` | diferencia o teaser/highlight | no usar histórico para inventarla | confirmed by code |
| `promotion_text` | teaser/highlight | sanitizar; contrato normalizado no tiene campo dedicado | pending contract gap |
| `discount_percentage` | Price/ListPrice | derivar solo con ambos valores confirmados | inferred |
| `currency` | contexto comercial | HNL esperado, campo explícito no capturado | pending |
| `measurement_unit` | SKU | normalizar texto | confirmed by code |
| `unit_multiplier` | SKU | decimal positivo | confirmed by code |
| `presentation` | atributos SKU; fallback `nameComplete` | parser conservador | partial |
| `package_quantity` | nombre/atributos | no confirmado | pending |

`effective_price` significa el precio que el sitio presenta como pagadero en la observación actual. No es la diferencia contra el histórico del proyecto.

### 12.2 Dependencia de ubicación

La plataforma VTEX puede regionalizar sellers, precios y disponibilidad mediante sesión/región. Los términos de La Colonia confirman disponibilidad por ciudad, pero no se ejecutó una comparación TGU vs SPS. Por ello:

```text
precio depende de ubicación = Pendiente / plausible, no demostrado
promoción depende de ubicación = Pendiente
disponibilidad depende de ubicación = confirmada funcionalmente; mecanismo pendiente
```

## 13. Disponibilidad y agotado

El extractor actual combina:

- existencia de seller;
- `Price`;
- `AvailableQuantity`.

La documentación pública de VTEX advierte que `AvailableQuantity` en búsquedas legacy puede representar rangos o cantidades aproximadas. Debe tratarse como señal pública de disponibilidad, no como inventario exacto.

Reglas recomendadas:

- `in_stock`: seller elegible, precio positivo y cantidad positiva;
- `out_of_stock`: contexto de ubicación confirmado y evidencia explícita de cero/no disponible;
- `unknown`: contexto no verificado, seller ausente o señales contradictorias;
- `not_listed`: SKU previamente conocido que no aparece en una observación comparable.

`No disponible` sin tienda seleccionada **no** demuestra agotado global.

## 14. Identidad, oferta y deduplicación

### Producto

Usar `productId` para agrupar variantes/SKU del mismo producto VTEX.

### SKU

Usar `itemId` como identidad primaria. Fallback existente:

1. referencia SKU;
2. EAN;
3. `productId`;
4. URL estable.

### Oferta

La oferta debe distinguir como mínimo:

- supermercado;
- ubicación/región verificada;
- SKU;
- seller cuando exista más de uno.

El `offer_id` actual usa supermercado + ubicación + `source_product_id`. Como `source_product_id` es normalmente el `itemId`, funciona para un seller único, pero puede colisionar si el mismo SKU tiene ofertas simultáneas de sellers distintos. Se documenta como hueco potencial, sin cambiar contrato.

### Deduplicación

- deduplicar globalmente por `itemId`;
- conservar relación `productId -> itemId[]`;
- no deduplicar por nombre;
- no sumar productos de padre, hija, marca, landing y colección;
- registrar memberships múltiples por SKU;
- comparar cambios comerciales mediante `state_hash`, sin cambiar identidad.

## 15. Cobertura y solapamientos

Clasificación actual:

```text
taxonomía = sampled / inconclusive
cobertura = no demostrada
solapamientos = no medidos
productos sin categoría hoja = Pendiente
```

No son pruebas suficientes:

- `sum(quantity) >= root_total`;
- `unique_products == recordsFiltered` en una sola captura;
- que todas las categorías visibles tengan resultados.

La demostración futura requiere:

1. contexto SPS fijo;
2. total raíz estable;
3. árbol sin sampling;
4. IDs únicos de la raíz;
5. unión de IDs de hojas;
6. intersecciones entre hojas;
7. residual `root - union(leaves)`;
8. categorías con conjuntos idénticos;
9. repetición mínima para estabilidad.

## 16. Estabilidad

Observado:

- el total actual de raíz es 9,291 en contexto sin tienda;
- capturas indexadas de categorías y colecciones muestran totales distintos según fecha/ruta;
- los términos permiten cambios de precios, existencias y productos sin aviso.

No se repitió una misma consulta técnica con iguales variables y contexto. Por tanto:

```text
raíz = inconclusa
categoría pequeña = inconclusa
categoría mediana = inconclusa
búsqueda = inconclusa
producto = estable solo en identidad visible; precio no observado
```

## 17. Matriz de riesgos

| Riesgo | Probabilidad | Impacto | Evidencia | Mitigación | Bloquea full |
|---|---:|---:|---|---|---:|
| contexto SPS no reproducible | alta | crítica | selector y default sin tienda | capturar mecanismo público | sí |
| precio sin ubicación | alta | crítica | PDP sin precio | no normalizar como SPS | sí |
| total raíz contextual | alta | alta | 9,291 sin tienda | repetir bajo SPS | sí |
| sampling de facets | media | alta | campo esperado no capturado | capturar y detener si true | sí |
| árbol incompleto | alta | alta | solo UI parcial | response de facets + residual | sí |
| solapamiento | alta | alta | jerarquía/landings/clusters | unión e intersecciones por SKU | sí |
| páginas repetidas/parciales | media | alta | no probado | firmas y boundary probes | sí |
| orden no determinista | media | alta | default release date | `OrderByNameASC`, repetición | sí |
| facet Impuestos corrupto | alta | media | `VLOOKUP(...)` | allow-list/evento de calidad | no |
| EAN ausente | media | media | campo opcional | identidad por itemId | no |
| presentación solo en nombre | alta | media | parser regex actual | atributos + revisión | no |
| múltiples sellers | media | alta | esquema sellers[] | incluir seller en oferta | sí si aparece |
| 403/429/antibot | baja-media | crítica | no observado | concurrency 1, delay, stop | sí |
| cambio de esquema GraphQL | media | alta | endpoint no revalidado | fixtures/versionado | sí |
| disponibilidad dinámica | alta | media | términos oficiales | timestamp y contexto | no |

## 18. Revisión legal y operativa

### Robots

`robots.txt` publica un sitemap y desautoriza, entre otras, rutas:

- `/img*`;
- `/account*`;
- `/login*`;
- `/checkout*`;
- `/busca*`;
- `/quick-view*`;
- `/espiar*`;
- `/buscapagina*`;
- `/api*`;
- host QA;
- host móvil.

La ruta `/_v/segment/graphql/v1` no aparece nombrada en esa lista, pero esto no equivale a autorización jurídica. Debe usarse con operación conservadora y revisión humana antes de automatización completa.

### Términos

Los términos:

- prohíben evasión o prueba de vulnerabilidades;
- reconocen posibles errores/inexactitudes;
- permiten cambios de productos, precios, existencias y condiciones;
- distinguen precios/promociones web de otros canales;
- reconocen disponibilidad por ciudad.

Interpretación jurídica adicional: **no realizada**. Recomendación: revisión humana antes del full crawl.

## 19. Mapeo a contratos y huecos

El inventario completo está en `la-colonia-inventario-campos.md`.

Huecos candidatos, no implementados:

1. `seller_id` normalizado para distinguir ofertas múltiples;
2. contexto reproducible de tienda/región/sales channel;
3. `promotion_text` estructurado;
4. decisión semántica entre `current_price` y alias `effective_price`;
5. impuestos limpios (`Tax`/`taxPercentage`) solo si se confirma fuente confiable;
6. `productId` agregado separado de la identidad SKU generada;
7. estado explícito `location_not_verified` o mapeo documentado a `LocationStatus.UNKNOWN`.

## 20. Estrategias evaluadas

| Estrategia | Cobertura | Duplicados | Omisiones | Solicitudes | Dependencia ubicación | Decisión |
|---|---|---|---|---|---|---|
| A. raíz paginada | potencialmente completa | baja por SKU | límite/sampling | ~186 páginas con 9,291 y size 50, contexto no válido | alta | universo de referencia |
| B. categorías principales | parcial | alta padre/hijos | productos mal categorizados | Pendiente | alta | control secundario |
| C. categorías hoja | potencialmente eficiente | solapamiento posible | hojas incompletas | Pendiente | alta | candidata tras discovery |
| D. búsqueda prefijos | no garantizada | muy alta | silenciosas | alta | alta | solo diagnóstico |
| E. facets combinadas | variable | alta | sampling | variable | alta | no primaria |
| F. híbrida | máxima verificabilidad | controlable | detectables con residual | mayor pero presupuestable | alta | recomendada |
| G. producto conocido | mínima | ninguna | casi total | baja | alta | validación de campos |
| H. sitemap | URLs, no necesariamente ofertas | baja | productos no indexados | baja | baja | inventario auxiliar |

### Estrategia recomendada

**Híbrida:**

1. fijar contexto público SPS;
2. capturar raíz y facets;
3. usar raíz paginada como universo de referencia;
4. usar categorías hoja como particiones operativas solo si no hay sampling;
5. deduplicar por `itemId` y agrupar por `productId`;
6. medir solapamientos y residuales;
7. validar una muestra de PDP/SKU/ofertas;
8. detener ante páginas repetidas, parciales, total cambiante, 403 o 429;
9. calcular presupuesto antes de autorizar recorrido progresivo.

El cálculo `ceil(9291/50)=186` es únicamente un **piso provisional de páginas raíz bajo contexto no verificado**, no un presupuesto SPS ni autorización.

## 21. Información pendiente bloqueante

- mecanismo exacto de selección de SPS;
- identificador público de ciudad, tienda, seller, región o canal;
- precio y disponibilidad antes/después de seleccionar SPS;
- respuesta GraphQL actual;
- endpoint actual del menú;
- endpoint y respuesta de facets;
- `sampling`;
- árbol completo y niveles reales;
- categorías hoja y vacías;
- solapamientos y residuales;
- productos sin hoja;
- múltiples sellers;
- muestras con precio normal, promoción, peso, múltiples SKU y EAN ausente;
- estabilidad de total, IDs, orden y páginas;
- límite real de paginación;
- presupuesto final.

## 22. Evidencia pública principal

| Evidencia | Timestamp de consulta | Resultado | Confianza |
|---|---|---|---|
| `/supermercado` | 2026-08-06 noche HN | 9,291; selector; facets | observado directo |
| `/preguntas-frecuentes` | 2026-08-06 | seleccionar ciudad; SPS; Plaza Pedregal | oficial |
| `/terminos-y-condiciones` | 2026-08-06 | variación por canal/ciudad; `Agotado SPS/TGU` | oficial |
| `/localizador-de-tiendas` | 2026-08-06 | selector dinámico ciudad/departamento | observado |
| `/robots.txt` | 2026-08-06 | sitemap y disallow | confirmado por red |
| PDP muestreadas | 2026-08-06 | referencia, especificaciones, `No disponible` | observado |
| assets VTEX | 2026-08-06 | `vtexassets.com` | observado |
| contratos/código PR #7 | 2026-08-06 | campos, endpoint, operación y reglas | confirmado por repositorio |
| documentación VTEX | 2026-08-06 | sesión, región, facets y Search GraphQL | plataforma; no prueba configuración local |

No se guardaron cookies, tokens, sesiones ni datos personales.

## 23. Respuestas a las 35 preguntas obligatorias

1. **Plataforma:** VTEX storefront/VTEX IO, confianza alta; endpoint actual pendiente de revalidación.
2. **Selección SPS:** funcionalmente por selector de ciudad/tienda; mecanismo técnico Pendiente.
3. **Precios por ubicación:** plausible por VTEX, no demostrado en La Colonia; disponibilidad por ciudad sí está documentada.
4. **Total real correcto:** Pendiente. Se observan 9,291 sin tienda, no SPS.
5. **Niveles:** Departamento, Categoría, Sub-Categoría; `Subcategoria` es especificación; niveles adicionales Pendiente.
6. **Diferencias:** categoría/subcategoría son jerarquía; landing/colección/promoción/filtro no lo son.
7. **Estructurales:** `category-1/2/3` y rutas de categoría confirmadas.
8. **Promocionales:** Landing, Ofertas, campañas y product clusters.
9. **Hojas cubren todo:** Pendiente.
10. **Solapamientos:** esperables, no medidos.
11. **Productos sin hoja:** Pendiente.
12. **Endpoint menú:** Pendiente.
13. **Endpoint facets:** Pendiente; respuesta esperada documentada.
14. **Endpoint listados:** `/_v/segment/graphql/v1`, `productSearchV3`, confirmado por código existente.
15. **Endpoint producto:** PDP HTML `/<linkText>/p`; consulta técnica dedicada Pendiente.
16. **Paginación:** `from/to` inclusivos.
17. **Límite máximo:** configuración actual 50; backend real Pendiente.
18. **Orden estable:** no probado; recomendado `OrderByNameASC`.
19. **Páginas repetidas:** no observadas; runner las detecta por firma.
20. **Identificador producto:** `productId`.
21. **Identificador SKU:** `itemId`.
22. **EAN:** `items[].ean`.
23. **Presentación:** atributos SKU + `nameComplete` como fallback.
24. **Precio actual:** `commertialOffer.Price`.
25. **Precio regular:** `ListPrice` solo cuando el sitio lo presenta como superior al actual.
26. **Promoción:** diferencia válida, `discountHighlights` o `teasers`.
27. **Disponibilidad:** seller + Price + AvailableQuantity bajo ubicación.
28. **Agotado:** evidencia explícita bajo contexto confirmado; sin tienda es `unknown`.
29. **Evitar duplicados:** deduplicación global por `itemId`.
30. **Demostrar cobertura:** raíz vs unión de hojas, intersecciones y residual.
31. **Solicitudes estimadas:** piso raíz provisional 186; total híbrido Pendiente.
32. **Pendiente:** ubicación, endpoints, facets, sampling, cobertura, estabilidad, precios SPS y presupuesto.
33. **Listo para scraper completo:** no.
34. **Primero:** resolver contexto SPS reproducible.
35. **Siguiente prueba:** `SPS-context-and-root-facets-001`, propuesta y no autorizada.

## 24. Estado final de la etapa

```text
radiografía = incompleta pero documentada
estrategia = híbrida recomendada
listo para implementar full scraper = no
listo para full crawl = no
fixtures creados = 0
pruebas offline nuevas = 0
código ejecutable modificado = no
contratos modificados = no
workflows modificados = no
archivo operacional modificado = no
productos descargados masivamente = 0
ejecuciones live = 0
```
