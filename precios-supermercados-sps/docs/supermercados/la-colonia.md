# Extractor controlado — La Colonia

## Estado

Prueba técnica funcional y corregida después de la revisión del PR #6. No incluye extracción completa, persistencia ni programación diaria.

## Fuente

La tienda utiliza VTEX Store Framework. El extractor consulta la operación pública `productSearchV3` en:

```text
https://www.lacolonia.com/_v/segment/graphql/v1
```

La consulta explícita se deriva de `QueryProductSearchV3` del paquete oficial `vtex.store-resources` y solicita únicamente los campos necesarios. El primer hash persistido evaluado respondió `PERSISTED_QUERY_NOT_FOUND`, por lo que fue eliminado y no se realizan intentos de enumeración.

No se utilizan las rutas `/api*`, `/busca*` o `/buscapagina*`, excluidas por `robots.txt`. Tampoco se utiliza `mobile.lacolonia.com`.

## Productos y SKU

La paginación `from`/`to` controla exclusivamente la cantidad de **productos** solicitados. Después de recibir esos productos, el parser recorre todos los SKU incluidos en cada uno.

```text
products_requested
→ cantidad de productos pedida mediante from/to

products_returned
→ elementos devueltos en productSearch.products

skus_returned
→ elementos devueltos en products[].items

skus_extracted
→ SKU válidos convertidos a RawProduct después de deduplicar
```

Un producto con varios SKU produce un `RawProduct` por cada SKU. El parser no se detiene cuando la cantidad de `RawProduct` alcanza el número de productos solicitados.

`recordsFiltered` representa el total de productos de la búsqueda y nunca se interpreta como total de SKU.

## Inclusión de productos y SKU no disponibles

La consulta utiliza simultáneamente:

```text
hideUnavailableItems = false
skusFilter = ALL
```

Estos parámetros tienen responsabilidades diferentes:

- `hideUnavailableItems = false` evita que la búsqueda oculte productos por disponibilidad.
- `skusFilter = ALL` solicita todos los SKU asociados a cada producto, incluidos SKU sin precio o no disponibles cuando la fuente los devuelve.

`ALL_AVAILABLE` no permanece como valor predeterminado ni como variable del extractor.

## Ubicación provisional

```text
location_id = la_colonia_online
location_status = unknown
location_evidence = Catálogo público en línea sin selección obligatoria de ciudad o sucursal.
location_confidence = null
```

El extractor no relaciona el catálogo con una tienda física, seller regional ni `regionId`.

## Contrato

Cada SKU válido produce el `RawProduct` existente. Precio, precio regular informado, promoción, disponibilidad, unidad comercial y valores originales de auditoría se conservan en `raw_values`; no se crean contratos comerciales paralelos.

## Reglas de disponibilidad

- precio positivo y cantidad positiva: `in_stock`;
- precio ausente y cantidad explícitamente cero: `out_of_stock`;
- precio positivo y cantidad cero: `unknown`, con evento `quality:availability_conflict_price_with_zero_quantity`;
- falta de precio, seller o evidencia concluyente: `unknown`;
- una ausencia en una página parcial nunca produce `not_listed`.

La cantidad cero junto a un precio positivo no se considera evidencia inequívoca de agotado porque el catálogo se consulta sin contexto regional confirmado.

## Pruebas offline

GitHub Actions ejecutó:

```bash
python -m compileall precios-supermercados-sps/src
pytest precios-supermercados-sps/tests
```

Resultado:

```text
67 passed in 0.35s
```

Las pruebas incluyen productos de un SKU y varios SKU, cinco productos con el primero mult SKU, preservación de productos posteriores, SKU disponible, sin precio y agotado, deduplicación por llave estable, filtro `ALL` y métricas separadas.

## Prueba live de diez productos

La muestra principal solicitó diez productos y procesó todos sus SKU:

```text
products_requested: 10
products_returned: 10
skus_returned: 10
skus_extracted: 10
skus_with_price: 10
weighted_skus: 0
promotional_skus: 0
duplicate_skus: 0
errors: 0
structural_events: 0
```

Los diez SKU conservaron identificador interno, nombre, URL individual, marca, presentación, categoría y precio. Los diez quedaron con disponibilidad `unknown` por la combinación precio positivo/cantidad cero.

## Búsquedas dirigidas limitadas

Se ejecutaron tres consultas adicionales de tres productos como máximo cada una:

- `fresa`: no produjo un SKU que la fuente identificara como pesable mediante unidad o nombre.
- `churros`: produjo tres SKU y confirmó dos SKU promocionales.
- `coca cola`: produjo tres SKU, pero no se encontró un producto con varios SKU.

Promociones confirmadas en la consulta dirigida:

| SKU | Producto | Precio actual | Precio regular informado |
|---|---|---:|---:|
| `18142` | Churro Zambos Camote Con Sal Marina 100 Gr | 36.85 | 40.95 |
| `18141` | Churro Yummies Taqueritos Lava Extra Picante 180Gr | 35.05 | 38.95 |

La ausencia de un caso pesable o mult SKU en estas búsquedas se registra como limitación; no se amplió la búsqueda ni se recorrió el catálogo.

## Ejecución

```bash
PYTHONPATH=precios-supermercados-sps/src \
python precios-supermercados-sps/scripts/probar_la_colonia.py \
  --products 10 \
  --directed-limit 3
```

El workflow live queda exclusivamente bajo `workflow_dispatch`. No se ejecuta diariamente ni automáticamente con cada cambio.

## Fuera de alcance

- recorrido completo;
- persistencia e historial;
- validación regional de inventario;
- Google Sheets;
- scraping diario;
- comparación entre supermercados;
- Power BI, BigQuery o Cloud Run.
