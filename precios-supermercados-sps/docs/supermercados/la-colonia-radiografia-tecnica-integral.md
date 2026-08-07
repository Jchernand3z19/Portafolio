# La Colonia — radiografía técnica integral

## 1. Resumen ejecutivo

Fecha de análisis: 2026-08-06 23:00–23:30 America/Tegucigalpa.

Clasificación final de esta etapa: **incompleta**.

La tienda pública usa **VTEX IO** y expone listados mediante una búsqueda GraphQL de catálogo. Esto está confirmado por:

- nombres de clases y recursos `vtex-*` visibles en páginas públicas;
- estructura pública `data.productSearch.products` y `recordsFiltered` ya consumida por el extractor existente;
- URLs con `map`, `category-1`, `productClusterIds` y filtros de especificación;
- assets públicos servidos desde `vtexassets.com`.

El sitio no está listo para autorizar un recorrido completo porque siguen pendientes:

1. confirmar el mecanismo técnico exacto de selección de ciudad/tienda;
2. demostrar que una consulta pública representa San Pedro Sula;
3. confirmar estabilidad del total raíz;
4. medir solapamientos entre categorías hoja;
5. demostrar ausencia de productos sin categoría hoja;
6. confirmar límites y sampling de facets;
7. validar precios y disponibilidad bajo un contexto de ubicación reproducible.

No se ejecutó full crawl, GitHub Actions live, controlador operacional, baseline500-003 ni validation500.

## 2. Alcance y método

Se inspeccionaron superficies públicas mediante solicitudes controladas, concurrencia lógica 1, sin autenticación, sin carrito y sin compras.

Clasificaciones usadas:

- **observado**: visible directamente en una página pública;
- **confirmado por red**: presente en una respuesta pública o código del extractor que refleja una respuesta capturada;
- **documentación oficial**: preguntas frecuentes, robots o términos públicos;
- **inferencia**: explicación razonable todavía no demostrada;
- **hipótesis**: requiere una prueba futura;
- **Pendiente**: no recuperado.

## 3. Contratos existentes

### RawProduct

Campos obligatorios ya esperados:

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

### NormalizedOffer

El contrato espera identidad determinista de producto y oferta, moneda, promoción, disponibilidad, ubicación, precio actual y campos normalizados de marca, categoría, subcategoría y presentación. Los campos pendientes controlados son:

- `normalized_brand`;
- `category`;
- `subcategory`;
- `unit_count`;
- `content_per_unit`;
- `measurement_unit`;
- `total_content`.

### ValidatedOffer

Contiene la oferta normalizada, `state_hash` SHA-256, fecha UTC de validación y eventos de calidad.

No se crearon contratos paralelos ni se modificaron los existentes.

## 4. Mapa funcional del sitio

| Superficie | URL conceptual | Evidencia | Dependencia de ubicación | Utilidad |
|---|---|---|---|---|
| Inicio | `/` | sitio público VTEX | selector visible | navegación y promociones |
| Supermercado raíz | `/supermercado?map=departamento` | total y facets visibles | no confirmada | raíz candidata |
| Categoría | `/supermercado/<slug>?map=c` | productos y facets | no confirmada | partición estructural candidata |
| Búsqueda | `/<texto>/supermercado?map=ft` | productos cruzados | no confirmada | diagnóstico, no partición primaria |
| Colección | `/supermercado/<id>?map=c,productClusterIds` | conjunto promocional/curado | no confirmada | landing, no categoría |
| Marca/landing corta | `/<slug>` | uno o pocos productos | no confirmada | marca o landing; requiere clasificación |
| Producto | `/<linkText>/p` | SKU, atributos, agotado | probablemente dependiente | detalle y validación |
| Preguntas frecuentes | `/preguntas-frecuentes` | selección de ciudad y operación | sí, funcional | evidencia oficial |
| Robots | `/robots.txt` | exclusiones públicas | no | límites operativos |

No todos los enlaces del menú deben tratarse como categorías. Se observaron búsquedas textuales, colecciones y landings que atraviesan varias categorías.

## 5. Ubicación, tienda y San Pedro Sula

### Observado/documentado

La documentación pública indica que el primer paso de compra es seleccionar la ciudad del domicilio. También indica que existe entrega o recogida en Tegucigalpa y San Pedro Sula, y que el punto de recogida de SPS es Plaza Pedregal.

### Confirmado técnicamente

Pendiente:

- nombre de cookie o storage;
- identificador interno de ciudad;
- identificador de tienda o seller;
- región comercial;
- binding o sales channel;
- contexto de checkout;
- efecto reproducible sobre precio y disponibilidad.

El extractor existente usa:

```text
location_id = la_colonia_online
location_status = unknown
```

Esta decisión es correcta con la evidencia actual.

### Conclusión

No se puede garantizar que una consulta sin selección represente San Pedro Sula. Hasta capturar y reproducir el mecanismo público, los precios deben clasificarse como:

```text
location_not_verified
```

## 6. Arquitectura y solicitudes

Plataforma confirmada: VTEX IO.

Catálogo confirmado por el extractor existente:

```text
protocolo = HTTPS
formato = GraphQL JSON
nodo principal = data.productSearch
productos = data.productSearch.products
total = data.productSearch.recordsFiltered
```

Variables observadas/esperadas por el código existente:

- `from`, `to`;
- `orderBy`;
- consulta/ruta;
- `map` o mapa de navegación;
- texto completo cuando aplica.

El extractor interpreta por producto:

- `productId`, `productReference`, `productName`, `linkText`;
- `brand`, `categories`, `categoryTree`;
- `items`.

Por SKU:

- `itemId`, `referenceId`, `ean`;
- `name`, `nameComplete`;
- `measurementUnit`, `unitMultiplier`;
- `images`, `sellers`.

Por oferta:

- `Price`, `ListPrice`, `AvailableQuantity`;
- evidencia promocional pública del `commertialOffer`.

Endpoint exacto sanitizado: documentado en `la-colonia-catalogo-solicitudes.md`.

## 7. Taxonomía observada

Niveles visibles:

1. Departamento: ejemplo `Supermercado`.
2. Categoría: Abarrotes, Belleza y Cuidado Personal, Cuidado del Hogar, Bebidas y Jugos, etc.
3. Sub-Categoría: Snacks, Limpieza del Hogar, Cuidado del Cabello, etc.
4. `Subcategoria`: atributo de especificación más granular, por ejemplo Aceite de Canola o Detergente Líquido.

Clasificación:

- `category-1` / Departamento: estructural;
- Categoría: estructural;
- Sub-Categoría: estructural;
- `Subcategoria`: filtro de especificación; puede parecer hoja, pero su cobertura estructural está pendiente;
- Marca: facet no estructural;
- Landing: promocional/editorial;
- `productClusterIds`: colección;
- `ft`: búsqueda textual;
- `specificationFilter_*`: filtro técnico.

Profundidad máxima confirmada: al menos tres niveles estructurales más una especificación granular. El árbol completo y los IDs internos permanecen pendientes.

## 8. Facets y anomalías

Facets observadas:

- Categoría;
- Sub-Categoría;
- Impuestos;
- Landing;
- Marca;
- Subcategoria.

Se observaron valores anómalos en `Impuestos`, incluyendo fórmulas `VLOOKUP(...)`. Esto es evidencia de calidad deficiente en datos de catálogo y obliga a sanitizar valores y no confiar automáticamente en cada facet.

El total de valores de marca visible supera 1,400 y el de `Subcategoria` supera 260 en páginas indexadas. No se confirmó si estas listas están completas o muestreadas.

Indicadores `sampling`, `children`, `selected`, `quantity`, `type`, `key` y `value`: Pendiente de captura directa de la respuesta de facets.

## 9. Listados y paginación

Totales raíz públicos observados en momentos distintos:

```text
8936 productos
9143 productos
```

Esto demuestra que el total raíz no es estable entre capturas indexadas. Puede deberse a inventario, contexto, índice o actualización; la causa es Pendiente.

Ordenamientos visibles:

- relevancia;
- ventas;
- fecha de release;
- descuento;
- precio ascendente/descendente;
- nombre ascendente/descendente.

El runner actual usa por defecto `OrderByNameASC` para mayor determinismo.

Paginación confirmada en el código:

```text
from = índice inicial inclusivo
to = índice final inclusivo
page_size = to - from + 1
```

El código detecta páginas parciales, páginas repetidas, discontinuidad y cambios de total. Límite máximo de VTEX y sampling: Pendiente de prueba controlada específica.

## 10. Página de producto y campos comerciales

Campos confirmados por la respuesta interpretada por el extractor:

| Concepto | Fuente pública |
|---|---|
| product ID | `productId` |
| referencia de producto | `productReference` |
| SKU ID | `items[].itemId` |
| referencia SKU | `items[].referenceId` |
| EAN | `items[].ean` |
| nombre | `productName`, `nameComplete` |
| marca | `brand` |
| categorías | `categories`, `categoryTree` |
| slug | `linkText` |
| imágenes | `items[].images[].imageUrl` |
| vendedor | `items[].sellers[].sellerId` |
| precio actual | `commertialOffer.Price` |
| precio de lista | `commertialOffer.ListPrice` |
| disponibilidad | seller + `AvailableQuantity` + precio |
| unidad | `measurementUnit` |
| multiplicador | `unitMultiplier` |

Se observaron páginas públicas con `SKU`, atributos de impuestos/subcategoría y mensaje `Produto Esgotado`/`No disponible`.

## 11. Precio, promoción y presentación

Reglas recomendadas con la evidencia actual:

- `selling_price` / `current_price`: `Price` positivo del seller seleccionado;
- `list_price`: `ListPrice` positivo;
- `regular_price`: `ListPrice` solamente cuando es mayor que `Price` y el sitio presenta esa comparación;
- `effective_price`: `Price`, porque es el importe actual ofrecido por el sitio;
- `is_promotion`: `ListPrice > Price` o teaser/evidencia promocional pública;
- `discount_percentage`: derivado solo cuando ambos precios están confirmados;
- moneda: HNL, inferida por operación y precios en lempiras; el campo técnico explícito queda Pendiente;
- presentación: primero SKU/atributos; fallback controlado desde `nameComplete`;
- `measurement_unit`: `measurementUnit`;
- `unit_multiplier`: `unitMultiplier`.

No debe inventarse una promoción comparando únicamente con el histórico del proyecto.

## 12. Identidad y deduplicación

Prioridad existente de `select_source_key`:

1. `itemId`;
2. referencia SKU;
3. EAN;
4. `productId`;
5. URL estable.

Recomendación:

- identidad de producto: `productId`;
- identidad de SKU: `itemId` como clave primaria, con `referenceId` y EAN como evidencia secundaria;
- identidad de oferta: supermercado + ubicación/contexto + seller + SKU;
- estado observado: hash de identidad comercial y campos que cambian.

No usar `productName` como identidad.

La deduplicación debe ocurrir por SKU, no por categoría ni por URL de landing. Un SKU puede aparecer en categoría padre, hija, búsqueda, marca y colección.

## 13. Cobertura y estabilidad

Clasificación de taxonomía actual:

```text
sampled / inconclusive
```

No se ha demostrado:

- unión completa de categorías hoja;
- residuales contra el total raíz;
- solapamiento medido;
- categorías con conjuntos idénticos;
- productos sin hoja;
- estabilidad temporal del orden y total.

No es válido sumar cantidades de facets como prueba de cobertura.

## 14. Riesgos

| Riesgo | Probabilidad | Impacto | Evidencia | Mitigación | Bloquea full |
|---|---:|---:|---|---|---|
| ubicación no verificada | alta | alta | selector y documentación oficial | capturar contexto público SPS | sí |
| total raíz variable | alta | alta | 8936 vs 9143 | repetir con mismo contexto/orden | sí |
| solapamiento de categorías | alta | alta | jerarquía + landings + búsqueda | unión por SKU y residuales | sí |
| facets sucias | alta | media | valores VLOOKUP en Impuestos | allow-list y eventos de calidad | no |
| sampling/límite | media | alta | no confirmado | prueba de fronteras mínima | sí |
| EAN ausente | media | media | contrato permite fallback | identidad por itemId | no |
| presentación solo en nombre | alta | media | parser actual con regex | conservar fuente y revisión | no |
| inventario dinámico | alta | media | total/disponibilidad variables | timestamp y repetición mínima | no |
| 403/429 | baja-media | alta | runner preparado | concurrency 1, delay >=1.5, stop | sí si aparece |

## 15. Revisión legal y operativa

`robots.txt` publica sitemap y desautoriza rutas como `/account`, `/login`, `/checkout`, `/busca`, `/buscapagina` y `/api`. La radiografía no accedió a áreas autenticadas ni de compra.

La documentación oficial confirma que los precios y ofertas web pueden diferir de tiendas físicas y que productos web/físicos no son conjuntos idénticos.

Interpretación legal adicional: Pendiente de revisión humana.

## 16. Mapeo a contratos

El detalle completo está en `la-colonia-inventario-campos.md`.

Hueco principal: el contrato puede representar ubicación desconocida, pero todavía no existe evidencia reproducible para elevarla a `confirmed`. No se propone modificar el contrato hasta conocer el mecanismo público.

## 17. Estrategias evaluadas

| Estrategia | Cobertura | Duplicados | Estabilidad | Recomendación |
|---|---|---|---|---|
| raíz paginada | potencialmente alta | baja por SKU | total variable | baseline de referencia |
| categorías principales | alta, no demostrada | alta | media | control secundario |
| categorías hoja | desconocida | media/alta | Pendiente | candidata tras discovery |
| prefijos/búsqueda | no garantizada | alta | baja | diagnóstico solamente |
| facets combinadas | potencial | alta | riesgo de sampling | no primaria |
| híbrida | mayor verificabilidad | controlable | mejor | recomendada |
| producto conocido | mínima | ninguna | alta | validación de campos |
| sitemap | Pendiente | baja | Pendiente | fuente auxiliar |

## 18. Estrategia recomendada

Estrategia híbrida:

1. fijar y verificar contexto público de San Pedro Sula;
2. obtener total raíz con `OrderByNameASC` y página pequeña;
3. capturar árbol estructural y facets sanitizadas;
4. recorrer categorías hoja únicamente después de medir sampling;
5. deduplicar globalmente por `itemId`;
6. comparar unión de hojas contra raíz paginada en una validación controlada;
7. reportar residuales, solapamientos y conjuntos idénticos;
8. abrir una muestra de productos para validar precio, presentación y disponibilidad;
9. detener en 403, 429, esquema inválido o páginas repetidas.

Solicitudes estimadas: Pendiente hasta confirmar total, page size máximo seguro, cantidad real de hojas y ubicación.

## 19. Preguntas obligatorias — estado

1. Plataforma: VTEX IO, confirmado.
2. Selección SPS: funcionalmente documentada; mecanismo técnico Pendiente.
3. Dependencia de ubicación: probable y operativamente relevante; no cuantificada.
4. Total real: Pendiente; se observaron 8936 y 9143.
5. Niveles: Departamento, Categoría, Sub-Categoría y especificación `Subcategoria`.
6. Diferencias: categorías son jerarquía; landing/colección son conjuntos editoriales; filtro restringe; búsqueda usa texto.
7. Categorías estructurales: Departamento/Categoría/Sub-Categoría.
8. Promocionales: Landing, product clusters y ofertas.
9–11. Cobertura, solapamientos y productos sin hoja: Pendiente.
12. Menú: Pendiente.
13. Facets: endpoint de product search/facets VTEX; operación exacta Pendiente.
14. Listados: GraphQL `productSearch`, confirmado por extractor.
15. Producto: product page + datos VTEX; operación exacta Pendiente.
16. Paginación: `from/to` inclusivos.
17. Límite máximo: Pendiente.
18–19. Estabilidad/repetición: controles implementados, evidencia live Pendiente.
20. Producto: `productId`.
21. SKU: `itemId`.
22. EAN: `items[].ean`.
23. Presentación: atributos SKU; fallback `nameComplete`.
24. Precio actual: `Price`.
25. Precio regular: `ListPrice` cuando mayor.
26. Promoción: diferencia declarada o teasers.
27–28. Disponibilidad: seller, cantidad, precio y mensaje agotado.
29. Duplicados: conjunto global de `itemId`.
30. Cobertura: raíz + hojas + unión/residuales.
31. Solicitudes: Pendiente.
32. Pendientes: ubicación, sampling, límites, unión y estabilidad.
33. Listo para scraper completo: no.
34. Primero: resolver ubicación SPS y capturar facets estructurales.
35. Siguiente prueba: prueba controlada de contexto SPS + raíz/facets, propuesta pero no autorizada.

## 20. Evidencia

Fuentes públicas revisadas:

- `https://www.lacolonia.com/`;
- `https://www.lacolonia.com/robots.txt`;
- `https://www.lacolonia.com/supermercado?map=departamento`;
- páginas de categoría, búsqueda, colección y landings públicas;
- `https://www.lacolonia.com/preguntas-frecuentes`;
- código existente del PR #7: contratos, extractor y runner.

No se conservaron cookies, tokens, headers privados ni datos personales.

## 21. Estado final

```text
PR #7 = abierto, draft, no fusionado
PR #17 = congelado y sin cambios
código ejecutable = sin cambios
contratos = sin cambios
workflows = sin cambios
archivo operacional = sin cambios
full crawl = no ejecutado
productos descargados masivamente = 0
radiografía = incompleta
listo para full crawl = no
```
