# Descubrimiento técnico — La Colonia

## Alcance

Prueba controlada del catálogo público de La Colonia. No incluye extracción completa, persistencia, carrito, cuenta, pedidos ni programación diaria.

## Fuente confirmada

- Plataforma: VTEX Store Framework.
- Catálogo público: `https://www.lacolonia.com/supermercado`.
- Operación: `productSearchV3`, derivada de `QueryProductSearchV3` del paquete oficial `vtex.store-resources`.
- Ruta pública: `https://www.lacolonia.com/_v/segment/graphql/v1`.
- Método: consulta GraphQL GET explícita y limitada.
- No utiliza cookies, tokens, cuentas ni datos personales.

Un hash persistido candidato fue descartado después de que La Colonia respondiera `PERSISTED_QUERY_NOT_FOUND`. No se probaron hashes adicionales.

## Cumplimiento de robots.txt

`robots.txt` excluye, entre otras, las rutas `/api*`, `/busca*` y `/buscapagina*`. No excluye `/_v/`.

El cliente bloquea antes de enviar cualquier petición a rutas excluidas, `mobile.lacolonia.com`, hosts diferentes de `www.lacolonia.com` y URLs que no utilicen HTTPS.

## Ubicación provisional aprobada

```text
location_id = la_colonia_online
location_status = unknown
location_evidence = Catálogo público en línea sin selección obligatoria de ciudad o sucursal.
location_confidence = null
```

No se asocia el catálogo con Plaza Pedregal, una tienda física, un seller regional o un `regionId`.

## Corrección de cobertura de SKU

La consulta controlada utiliza:

```text
hideUnavailableItems = false
skusFilter = ALL
```

`hideUnavailableItems = false` controla la inclusión de productos en la búsqueda. `skusFilter = ALL` controla la lista `items` de cada producto y permite auditar todos los SKU devueltos, incluidos SKU no disponibles o sin precio.

El valor `ALL_AVAILABLE` fue eliminado como predeterminado y como variable de ejecución.

## Separación entre productos y SKU

La paginación `from`/`to` solicita productos. El parser procesa después todos los SKU de todos los productos devueltos, sin detenerse al alcanzar el número de productos solicitados.

Métricas implementadas:

```text
products_requested
products_returned
skus_returned
skus_extracted
duplicate_skus
skus_with_price
skus_pending_review
```

`recordsFiltered` se conserva como total de productos (`products_discovered`) y no se utiliza como total de SKU.

## Pruebas offline

Validaciones ejecutadas en GitHub Actions con Python 3.12.13:

```bash
python -m compileall precios-supermercados-sps/src
pytest precios-supermercados-sps/tests
```

Resultado:

```text
compilación: correcta
pruebas: 67 passed in 0.35s
```

Cobertura agregada:

- producto con un SKU;
- producto con varios SKU;
- cinco productos donde el primero tiene varios SKU;
- preservación de todos los productos posteriores;
- SKU disponible;
- SKU sin precio;
- SKU con cantidad cero;
- disponibilidad no inventada;
- deduplicación de SKU por llave fuente estable;
- `skusFilter = ALL`;
- ausencia de `ALL_AVAILABLE` como filtro predeterminado;
- métricas separadas de productos y SKU.

## Resultado live controlado

Fecha UTC de validación: 2026-08-05.

### Muestra principal

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
products_discovered: 9291
```

La fuente devolvió un SKU por cada uno de los diez productos de esta página. El extractor procesó los diez sin omisiones ni duplicados.

Los diez SKU presentaron precio positivo y cantidad cero. Se conservaron con:

```text
availability = unknown
quality:availability_conflict_price_with_zero_quantity
```

### Búsquedas dirigidas

Se realizaron tres consultas independientes, de máximo tres productos cada una:

| Objetivo | Texto | Productos | SKU | Resultado |
|---|---|---:|---:|---|
| Pesable | `fresa` | 3 | 3 | No encontrado |
| Promocional | `churros` | 3 | 3 | 2 SKU promocionales |
| Varios SKU | `coca cola` | 3 | 3 | No encontrado |

Promociones encontradas:

| ID interno | Producto | Precio actual | Precio regular informado |
|---|---|---:|---:|
| `18142` | Churro Zambos Camote Con Sal Marina 100 Gr | 36.85 | 40.95 |
| `18141` | Churro Yummies Taqueritos Lava Extra Picante 180Gr | 35.05 | 38.95 |

No se amplió la búsqueda al no encontrar un producto pesable o mult SKU. Ambos quedan como limitaciones live, aunque el comportamiento mult SKU y pesable está cubierto offline.

## Paginación

La fuente informó 9,291 productos. Con diez productos por página se calculan 930 páginas para esta prueba, sin que esto autorice un recorrido completo.

La paginación usa índices inclusivos:

```text
página 1: 0–9
página 2: 10–19
```

## Campos confirmados

- ID interno del SKU;
- ID interno del producto;
- referencia/SKU cuando existe;
- EAN cuando existe;
- nombre de producto y nombre completo del SKU;
- marca;
- categoría y subcategoría;
- presentación;
- imagen;
- URL individual;
- precio actual;
- precio regular informado cuando supera el actual;
- evidencia estructurada de promoción;
- seller original para auditoría;
- unidad comercial;
- multiplicador;
- cantidad publicada;
- valores originales de auditoría.

## Riesgos y limitaciones

- La disponibilidad pública sin región continúa siendo ambigua.
- La muestra principal de diez productos no contenía productos mult SKU.
- La búsqueda dirigida limitada no encontró un producto mult SKU.
- La búsqueda dirigida `fresa` no devolvió evidencia interpretable de producto pesable.
- El total del catálogo es dinámico.
- La consulta explícita depende del esquema público de `vtex.search-graphql`.
- No se validó recorrido completo, persistencia ni comparación entre ejecuciones.

## Decisión

Las dos observaciones de revisión quedan corregidas. El extractor solicita `ALL`, diferencia productos de SKU y procesa todos los SKU devueltos sin recortes silenciosos. La prueba puede continuar a una siguiente fase controlada, manteniendo la disponibilidad ambigua como `unknown` y sin habilitar todavía extracción completa o diaria.
