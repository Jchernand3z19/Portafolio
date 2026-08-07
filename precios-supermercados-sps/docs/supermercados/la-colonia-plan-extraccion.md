# La Colonia — plan de extracción posterior a la radiografía

## 1. Estado

Este documento es un plan. **No autoriza ninguna ejecución.**

```text
radiografía = incompleta
SPS-context-and-root-facets-001 = consumida; D — bloqueada por limitación de herramienta
diagnóstico de navegador SPS = preparado offline
contexto SPS real = no reproducible todavía
listo para implementar scraper completo = no
listo para full crawl = no
```

No se modifican scraper, runtime, contratos, workflows ni archivo operacional.

La siguiente ejecución live requiere primero el diagnóstico de navegador descrito
en `la-colonia-browser-context-diagnostic.md`, una autorización explícita nueva
y un ID nuevo asignado fuera del código. `SPS-context-and-root-facets-002` no ha
sido creado ni autorizado.

## 2. Objetivo

Construir un extractor verificable para el catálogo público de La Colonia que:

- represente San Pedro Sula de forma reproducible;
- identifique producto, SKU, seller y oferta;
- conserve precio y disponibilidad con contexto;
- demuestre cobertura y detecte omisiones;
- opere secuencialmente y bajo presupuesto;
- se detenga ante señales de bloqueo o inestabilidad.

## 3. Principios de arquitectura

1. **Ubicación antes que precio.** No normalizar precios como SPS sin contexto confirmado.
2. **SKU antes que nombre.** `itemId` es la identidad primaria de SKU; `productId` agrupa variantes.
3. **Raíz como referencia, hojas como particiones.** Ninguna de las dos demuestra cobertura por sí sola.
4. **Deduplicación global.** Un SKU puede aparecer en padre, hija, marca, landing, búsqueda y colección.
5. **Evidencia antes que inferencia.** Registrar `confirmed`, `inferred`, `pending` y eventos de calidad.
6. **Operación conservadora.** Concurrencia 1, pausa mínima 1.5 s y máximo un reintento.
7. **Sin full crawl hasta presupuesto y cobertura.**

## 4. Fase 1 — Resolver el contexto público de San Pedro Sula

### Estado de la prueba anterior

```text
Nombre: SPS-context-and-root-facets-001
Estado: consumida
Resultado: D — bloqueada por limitación de herramienta
Stop reason: tool_cannot_interact_with_store_selector_or_inspect_session_context
Repetición: no autorizada
```

La prueba 001 confirmó que la capacidad de navegación usada en esa etapa no
podía interactuar con el selector dinámico de tienda ni inspeccionar
cookies/localStorage/sessionStorage/XHR. Se detuvo antes de seleccionar SPS y
antes de consultar raíz/facets.

### Diagnóstico de navegador requerido

Se preparó offline:

```text
precios-supermercados-sps/src/precios_supermercados/diagnostics/
  la_colonia_sps_context_diagnostic.py
```

Su objetivo futuro es:

1. crear un browser context público limpio;
2. registrar el estado por defecto sin publicar valores sensibles;
3. localizar `Selecciona tu tienda` mediante selectores semánticos;
4. seleccionar San Pedro Sula mediante UI pública;
5. seleccionar Plaza Pedregal cuando la UI real lo requiera;
6. observar únicamente nombres/presencia/cambio de:
   - cookies;
   - localStorage;
   - sessionStorage;
   - query parameter;
   - header;
   - contexto GraphQL;
   - seller/tienda;
   - `regionId`;
   - sales channel/binding;
   - session/segment;
7. capturar el request GraphQL real de catálogo sin inventar endpoint;
8. reducir la ventana a `from=0`, `to<=4`;
9. capturar raíz/facets;
10. repetir una vez;
11. persistir solo diagnóstico sanitizado;
12. clasificar ubicación como `confirmed`, `ui_only` o `inconclusive`.

### Límites de una futura autorización

```text
concurrency = 1
delay = >= 1.5 s
retries = máximo 1
max_logical_requests = 8
root/facets = mínimo indispensable
full crawl = no
```

### Criterio de salida

Una consulta reproducible debe demostrar que pertenece a SPS. Si no:

```text
location_status = unknown
classification = location_not_verified
```

## 5. Fase 2 — Capturar taxonomía y facets

Después de confirmar SPS:

1. ejecutar una consulta raíz con page size mínimo y `OrderByNameASC`;
2. capturar una respuesta de facets sanitizada;
3. registrar `recordsFiltered` y `sampling`;
4. inventariar `type`, `name`, `key`, `value`, `quantity`, `selected`, `children`;
5. separar:
   - `category-1` Departamento;
   - `category-2` Categoría;
   - `category-3` Sub-Categoría;
   - niveles adicionales reales;
   - marca;
   - landing;
   - colección;
   - especificaciones como `Subcategoria` e Impuestos;
6. marcar categorías vacías y hojas positivas;
7. detener si `sampling=true`, faltan hijos esperados o las cantidades son inválidas;
8. excluir valores corruptos como fórmulas `VLOOKUP(...)`.

Criterio de salida: árbol estructural versionable con hojas candidatas,
cantidades y evidencia de completitud.

## 6. Fase 3 — Validar listados y paginación

Muestra mínima:

| Tipo | Prueba |
|---|---|
| raíz | páginas 1 y 2; repetir página 1 |
| categoría grande | primera página y una frontera controlada |
| categoría mediana | dos páginas consecutivas |
| categoría pequeña | primera y última página |
| hoja candidata | primera y última página |
| búsqueda | una página, solo para demostrar transversalidad |
| landing | una página |
| marca | una página |

Validar:

- `from/to` inclusivos;
- tamaño real de página;
- orden `OrderByNameASC` estable;
- total constante dentro de la ventana;
- primer y último ID;
- firmas de página distintas;
- ausencia de páginas parciales inesperadas;
- límite máximo del backend;
- ausencia de sampling;
- estabilidad al repetir.

Detener ante página repetida, cambio de total significativo o respuesta parcial.

## 7. Fase 4 — Validar productos y ofertas

Muestra objetivo, no masiva:

1. producto con precio normal;
2. producto con promoción declarada;
3. producto agotado en SPS;
4. producto vendido por peso;
5. producto con varios SKU/presentaciones;
6. producto con EAN ausente, si aparece;
7. producto con más de un seller, si aparece.

Campos mínimos:

```text
productId
productReference
productName
linkText
brand
categories/categoryTree
itemId
referenceId
ean
name/nameComplete
measurementUnit
unitMultiplier
sellerId/sellerDefault
Price
ListPrice
AvailableQuantity
discountHighlights
teasers
images
```

Reglas:

- `effective_price = Price` solo bajo contexto SPS confirmado;
- `reported_regular_price = ListPrice` solo si es mayor que Price y la fuente presenta la comparación;
- promoción declarada por diferencia válida o teaser/highlight;
- no inventar oferta por comparación histórica;
- `No disponible` sin tienda no es `out_of_stock` global;
- cantidades de VTEX Search son señal de disponibilidad, no inventario exacto.

## 8. Fase 5 — Identidad y deduplicación

### Claves

```text
product identity = productId
SKU identity = itemId
offer identity = supermarket + verified location/region + itemId + sellerId
state identity = state_hash comercial existente
```

Fallback SKU existente:

1. referencia SKU;
2. EAN;
3. productId;
4. URL estable.

### Índices de trabajo

- `products_by_product_id`;
- `skus_by_item_id`;
- `offers_by_context_item_seller`;
- `memberships_by_item_id` para categorías/landings/brands;
- `state_hash_by_offer`.

No usar `productName` como identidad.

## 9. Fase 6 — Demostrar cobertura

Estrategia recomendada: **híbrida**.

1. obtener la raíz paginada como universo de referencia bajo SPS;
2. obtener categorías hoja como particiones candidatas;
3. deduplicar ambos conjuntos por `itemId`;
4. agrupar por `productId` para métricas de producto;
5. calcular:
   - `root_unique_skus`;
   - `leaf_union_unique_skus`;
   - intersecciones entre hojas;
   - `root_minus_leaves`;
   - `leaves_minus_root`;
   - conjuntos idénticos;
   - productos/SKU sin hoja;
6. repetir una muestra para demostrar estabilidad;
7. clasificar:
   - `complete_and_partitionable`;
   - `complete_with_overlap`;
   - `incomplete`;
   - `sampled`;
   - `unstable`;
   - `inconclusive`.

No aceptar como prueba:

```text
sum(quantity) >= root_total
```

ni:

```text
unique_products == recordsFiltered
```

sin estabilidad, contexto y pertenencia demostrados.

## 10. Fase 7 — Presupuesto

### Piso provisional

La raíz pública sin tienda mostró 9,291 productos. Con page size 50:

```text
ceil(9291 / 50) = 186 páginas
```

Este valor es solo una referencia de la raíz **sin ubicación verificada**.
No es el total SPS ni una autorización.

### Fórmula final

```text
requests_context = requests necesarias para fijar/verificar SPS
requests_facets = raíz mínima + facets
requests_root = ceil(root_total_sps / safe_page_size)
requests_leaves = sum(ceil(leaf_total / safe_page_size))
requests_probes = fronteras y repeticiones mínimas
requests_recovery = reserva limitada
requests_total = context + facets + root + leaves + probes + recovery
```

### Optimización

- si la raíz es estable y no tiene límite, puede ser el recorrido primario;
- si la raíz se limita o repite, usar hojas estructurales;
- no recorrer landings, marcas o búsquedas como cobertura primaria;
- evitar detalle PDP cuando Search GraphQL ya entrega los campos requeridos;
- reservar PDP solo para validación y campos ausentes;
- detener si el presupuesto excede el límite aprobado.

El presupuesto definitivo permanece Pendiente hasta conocer total SPS, hojas,
sampling y solapamientos.

## 11. Fase 8 — Normalización y validación

Mapeo inicial:

```text
current_price = Price
effective_price = Price bajo contexto confirmado
reported_regular_price = ListPrice cuando ListPrice > Price
is_promotion = diferencia válida o teaser/highlight
availability = seller + Price + AvailableQuantity + contexto
presentation = atributos SKU; fallback conservador a nameComplete
location_status = confirmed solo con evidencia reproducible
```

Eventos de calidad sugeridos:

- `location_not_verified`;
- `missing_price`;
- `availability_conflict`;
- `missing_ean`;
- `presentation_from_name`;
- `multiple_sellers`;
- `facet_value_corrupt`;
- `sampling_detected`;
- `repeated_page`;
- `partial_page`;
- `catalog_total_changed`;
- `product_without_leaf_category`.

No modificar contratos antes de resolver los huecos documentados.

## 12. Fase 9 — Recuperación y checkpoints

Detener inmediatamente ante:

- HTTP 403 persistente;
- HTTP 429;
- captcha/antibot;
- exigencia de autenticación;
- JSON inválido persistente;
- cambio de esquema;
- página repetida;
- página parcial inesperada;
- contexto SPS perdido;
- total cambiante por encima del umbral aprobado;
- riesgo de afectar el servicio.

Checkpoint sanitizado por página:

```text
partition
from/to
orderBy
recordsFiltered
products_returned
unique_item_ids_hash
page_signature
duration
status
quality_events
```

No guardar catálogo completo en artefactos públicos ni cookies/tokens.

## 13. Orden de implementación recomendado

Estado actualizado:

1. **diagnóstico de navegador/verificador de contexto SPS — preparado offline**;
2. captura sanitizada de sesión comercial pública — preparada en el diagnóstico;
3. cliente de facets con contrato cerrado;
4. parser de árbol y clasificación de facets;
5. fixtures sanitizados de respuestas reales únicamente después de captura autorizada;
6. pruebas offline de ubicación/facets/precios;
7. validación mínima de paginación;
8. validación representativa de SKU/ofertas;
9. cálculo de cobertura y presupuesto;
10. recorrido progresivo únicamente con autorización nueva.

## 14. Estrategias comparadas

| Estrategia | Cobertura | Duplicados | Omisiones | Estabilidad | Mantenibilidad | Uso recomendado |
|---|---|---|---|---|---|---|
| raíz paginada | alta potencial | baja | límite/sampling | Pendiente | alta | universo de referencia |
| categorías principales | parcial | alta | residuales | media | media | control |
| categorías hoja | alta potencial | media/alta | hojas faltantes | Pendiente | media | partición operativa |
| rangos/prefijos | no demostrable | alta | alta | baja | baja | diagnóstico |
| facets combinadas | variable | alta | sampling | baja-media | baja | recuperación limitada |
| híbrida | mayor verificabilidad | controlable | detectables | mejor | media | recomendada |
| producto conocido | mínima | ninguna | casi total | alta | alta | validación |
| sitemap | URLs | baja | no indexados | media | alta | auxiliar |

## 15. Criterios de listo para implementar

Todos deben cumplirse:

- SPS reproducible;
- seller/precio/disponibilidad bajo SPS;
- endpoint de listados revalidado;
- facets capturadas;
- sampling conocido;
- árbol estructural identificado;
- identidad product/SKU confirmada;
- casos normal/promoción/agotado/peso/multi-SKU;
- límites de paginación confirmados;
- presupuesto calculado.

La existencia del diagnóstico de navegador no satisface por sí sola estos
criterios; solo elimina la limitación de herramienta a nivel de implementación.

## 16. Criterios de listo para full crawl

Además:

- total raíz SPS estable;
- unión de hojas medida;
- solapamientos cuantificados;
- residuales explicados;
- páginas estables y no repetidas;
- cero 403/429 persistentes;
- umbrales y presupuesto aprobados;
- estrategia de recuperación probada offline;
- autorización explícita nueva.

## 17. Próxima prueba live

No existe una nueva prueba live autorizada.

```text
SPS-context-and-root-facets-001 = consumida; no repetir
SPS-context-and-root-facets-002 = no creada; no autorizada
siguiente ID = Pendiente
prerrequisito = diagnóstico de navegador + autorización explícita nueva
```

Una futura autorización, si se concede, deberá usar el diagnóstico de navegador
para:

- seleccionar SPS exclusivamente por UI pública;
- producir evidencia técnica sanitizada del contexto;
- observar el request GraphQL real;
- ejecutar raíz/facets mínimas;
- repetir una vez;
- detenerse dentro del presupuesto.

## 18. Decisión

```text
estrategia recomendada = híbrida
primer componente = diagnóstico de navegador SPS, preparado offline
siguiente prueba live = Pendiente
autorización de siguiente prueba = inexistente
SPS-context-and-root-facets-001 = consumida
SPS-context-and-root-facets-002 = no creada
full crawl = no autorizado
```
