# Extractor controlado — La Colonia

## Estado

Primera prueba técnica, sin extracción completa ni persistencia.

## Fuente

La tienda utiliza VTEX Store Framework. El componente oficial de búsqueda consulta `QueryProductSearchV3`; el cliente controlado utiliza la ruta pública `/_v/segment/graphql/v1` y limita cada ejecución live a entre tres y cinco SKU.

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

Cada SKU válido produce el `RawProduct` existente. Precio, precio regular informado, promoción, disponibilidad, unidad comercial y valores de auditoría se conservan en `raw_values`; no se crean modelos comerciales paralelos.

## Reglas

- `current_price`: `Price` positivo de la oferta pública seleccionada.
- `reported_regular_price`: solo se conserva cuando `ListPrice` es mayor que `Price`.
- `is_promotion`: diferencia estructurada de precios o evidencia promocional explícita.
- `in_stock`: precio positivo y cantidad positiva.
- `out_of_stock`: sellers presentes con cantidad explícita cero.
- `unknown`: falta de precio, sellers o evidencia concluyente.
- Una ausencia en esta muestra nunca produce `not_listed`.

## Ejecución

```bash
PYTHONPATH=precios-supermercados-sps/src \
python precios-supermercados-sps/scripts/probar_la_colonia.py --limit 5
```

El comando no escribe en almacenamiento. Termina con código distinto de cero ante bloqueo, `429` persistente, estructura inesperada, respuesta vacía o ausencia total de precios.

## Fuera de alcance

- recorrido completo;
- historial;
- Google Sheets;
- scraping diario;
- comparación entre supermercados;
- Power BI, BigQuery o Cloud Run.
