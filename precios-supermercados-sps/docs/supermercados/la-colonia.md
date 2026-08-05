# Extractor controlado — La Colonia

## Estado

Primera prueba técnica funcional, sin extracción completa ni persistencia.

## Fuente

La tienda utiliza VTEX Store Framework. El extractor consulta la operación pública `productSearchV3` en:

```text
https://www.lacolonia.com/_v/segment/graphql/v1
```

La consulta explícita se deriva de `QueryProductSearchV3` del paquete oficial `vtex.store-resources` y solicita únicamente los campos necesarios. El primer hash persistido evaluado respondió `PERSISTED_QUERY_NOT_FOUND`, por lo que fue eliminado y no se realizan intentos de enumeración.

Cada ejecución live queda limitada a una página y entre tres y cinco SKU.

No se utilizan las rutas `/api*`, `/busca*` o `/buscapagina*`, excluidas por `robots.txt`. Tampoco se utiliza `mobile.lacolonia.com`.

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

## Reglas

- `current_price`: `Price` positivo de la oferta pública.
- `reported_regular_price`: solo se conserva cuando `ListPrice` es mayor que `Price`.
- `is_promotion`: diferencia estructurada de precios o evidencia promocional explícita.
- `in_stock`: precio positivo y cantidad positiva.
- `out_of_stock`: precio ausente y cantidad explícitamente cero.
- precio positivo y cantidad cero: `unknown`, con evento `quality:availability_conflict_price_with_zero_quantity`.
- falta de precio, seller o evidencia concluyente: `unknown`.
- una ausencia en una página parcial nunca produce `not_listed`.

La cantidad cero junto a un precio positivo no se considera evidencia inequívoca de agotado porque el catálogo se consulta sin contexto regional confirmado.

## Prueba live validada

La muestra controlada obtuvo cinco productos de una sola página:

- cinco IDs internos estables;
- cinco nombres y URLs individuales;
- cinco marcas, presentaciones y categorías;
- cinco precios actuales;
- cero errores HTTP;
- cero duplicados;
- cero eventos estructurales.

La disponibilidad quedó `unknown` en los cinco casos por el conflicto precio positivo/cantidad cero. Esto no impide validar la extracción de catálogo y precios, pero bloquea una afirmación de inventario confiable hasta una investigación posterior.

## Ejecución

```bash
PYTHONPATH=precios-supermercados-sps/src \
python precios-supermercados-sps/scripts/probar_la_colonia.py --limit 5
```

El comando no escribe en almacenamiento. Termina con código distinto de cero ante bloqueo, `429` persistente, estructura inesperada, respuesta vacía o ausencia total de precios.

## Fuera de alcance

- recorrido completo;
- persistencia e historial;
- validación regional de inventario;
- Google Sheets;
- scraping diario;
- comparación entre supermercados;
- Power BI, BigQuery o Cloud Run.
