# Registro histórico — Extractor controlado de La Colonia

## Estado del documento

**SNAPSHOT HISTÓRICO DE LA FASE INICIAL (PR #6). NO ES LA FUENTE DE ESTADO ACTUAL NI UNA AUTORIZACIÓN LIVE.**

Este documento conserva la evidencia técnica de la primera prueba controlada del extractor. El estado vigente del proyecto, autorizaciones, Cloudflare, SPS, cobertura y gates se consulta únicamente en [`../PROJECT_STATE.md`](../PROJECT_STATE.md).

La arquitectura estable vive en [`../arquitectura.md`](../arquitectura.md).

Reglas al leer este snapshot:

- una autorización histórica consumida no puede reutilizarse;
- no asumir que los conteos, bloqueos o componentes descritos aquí siguen siendo los actuales;
- no ejecutar los comandos históricos de este archivo sin una nueva autorización humana explícita;
- el estado SPS/binding/granularidad vigente se toma de `PROJECT_STATE.md`, no de esta evidencia antigua.

## Fuente observada en la fase histórica

La tienda utiliza VTEX Store Framework. El extractor consultó la operación pública `productSearchV3` en:

```text
https://www.lacolonia.com/_v/segment/graphql/v1
```

La consulta explícita se derivó de `QueryProductSearchV3` del paquete oficial `vtex.store-resources` y solicitó únicamente los campos necesarios. El primer hash persistido evaluado respondió `PERSISTED_QUERY_NOT_FOUND`, por lo que fue eliminado y no se realizaron intentos de enumeración.

No se utilizaron las rutas `/api*`, `/busca*` o `/buscapagina*`, excluidas por `robots.txt`. Tampoco se utilizó `mobile.lacolonia.com`.

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

## Ubicación provisional histórica

```text
location_id = la_colonia_online
location_status = unknown
location_evidence = Catálogo público en línea sin selección obligatoria de ciudad o sucursal.
location_confidence = null
```

El extractor de aquella fase no relacionó el catálogo con una tienda física, seller regional ni `regionId`.

Esto se conserva como evidencia histórica. La granularidad y el binding técnico actuales de SPS se consultan en `PROJECT_STATE.md`.

## Contrato

Cada SKU válido produce el `RawProduct` existente. Precio, precio regular informado, promoción, disponibilidad, unidad comercial y valores originales de auditoría se conservan en `raw_values`; no se crean contratos comerciales paralelos.

## Reglas de disponibilidad

- precio positivo y cantidad positiva: `in_stock`;
- precio ausente y cantidad explícitamente cero: `out_of_stock`;
- precio positivo y cantidad cero: `unknown`, con evento `quality:availability_conflict_price_with_zero_quantity`;
- falta de precio, seller o evidencia concluyente: `unknown`;
- una ausencia en una página parcial nunca produce `not_listed`.

La cantidad cero junto a un precio positivo no se considera evidencia inequívoca de agotado cuando no existe contexto regional confirmado.

## Pruebas offline de aquella fase

GitHub Actions ejecutó entonces:

```bash
python -m compileall precios-supermercados-sps/src
pytest precios-supermercados-sps/tests
```

Resultado histórico:

```text
67 passed in 0.35s
```

Ese conteo **no representa la suite actual**. Se conserva únicamente como evidencia de la fase PR #6. El conteo vigente está documentado en `../PROJECT_STATE.md`.

## Prueba live histórica de diez productos

En una autorización histórica ya consumida, la muestra principal solicitó diez productos y procesó todos sus SKU:

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

Esta evidencia describe lo que ocurrió en aquella ejecución; **no concede permiso para repetirla**.

## Búsquedas dirigidas históricas

Se ejecutaron tres consultas adicionales de tres productos como máximo cada una:

- `fresa`: no produjo un SKU que la fuente identificara como pesable mediante unidad o nombre.
- `churros`: produjo tres SKU y confirmó dos SKU promocionales.
- `coca cola`: produjo tres SKU, pero no se encontró un producto con varios SKU.

Promociones observadas en aquella consulta:

| SKU | Producto | Precio actual | Precio regular informado |
|---|---|---:|---:|
| `18142` | Churro Zambos Camote Con Sal Marina 100 Gr | 36.85 | 40.95 |
| `18141` | Churro Yummies Taqueritos Lava Extra Picante 180Gr | 35.05 | 38.95 |

Los precios son evidencia histórica de esa observación, no precios actuales.

## Comando histórico — no ejecutar sin autorización nueva

El comando usado en aquella fase fue:

```bash
PYTHONPATH=precios-supermercados-sps/src \
python precios-supermercados-sps/scripts/probar_la_colonia.py \
  --products 10 \
  --directed-limit 3
```

Se conserva sólo para reproducibilidad histórica. La existencia de `workflow_dispatch`, un archivo de comando, un comentario o este documento no crea autoridad live.

## Fuera de alcance de aquella fase

- recorrido completo;
- persistencia e historial;
- validación regional de inventario;
- almacenamiento productivo;
- scraping diario;
- comparación entre supermercados;
- Power BI.

Varias de esas áreas avanzaron posteriormente. Consultar `../PROJECT_STATE.md` para el estado real actual.
