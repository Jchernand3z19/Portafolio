# Descubrimiento técnico — La Colonia

## Alcance

Prueba controlada del catálogo público de La Colonia. No incluye extracción completa, persistencia, carrito, cuenta ni pedidos.

## Estado inicial

- Plataforma: VTEX Store Framework.
- Catálogo público: `https://www.lacolonia.com/supermercado`.
- Operación utilizada por el componente oficial de búsqueda: `QueryProductSearchV3` / `productSearchV3`.
- Ruta pública candidata: `https://www.lacolonia.com/_v/segment/graphql/v1`.
- `robots.txt` excluye `/api*`, `/busca*` y `/buscapagina*`; no excluye `/_v/`.
- La consulta se limita a cinco resultados.

## Ubicación provisional aprobada

```text
location_id = la_colonia_online
location_status = unknown
location_evidence = Catálogo público en línea sin selección obligatoria de ciudad o sucursal.
location_confidence = null
```

## Consulta controlada pendiente de validación

La URL siguiente contiene únicamente una consulta GET pública de cinco productos, sin cookies, tokens ni datos personales. El hash persistido corresponde a `QueryProductSearchV3` de `vtex.store-resources` y debe validarse contra la instalación de La Colonia antes de considerarlo fuente definitiva.

[Ejecutar consulta pública limitada de cinco productos](https://www.lacolonia.com/_v/segment/graphql/v1?workspace=master&maxAge=short&appsEtag=remove&domain=store&locale=es-HN&operationName=productSearchV3&variables=%7B%7D&extensions=%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22sha256Hash%22%3A%22c351315ecde7f473587b710ac8b97f147ac0ac0cd3060c27c695843a72fd3903%22%2C%22sender%22%3A%22vtex.store-resources%400.x%22%2C%22provider%22%3A%22vtex.search-graphql%400.x%22%7D%2C%22variables%22%3A%22eyJoaWRlVW5hdmFpbGFibGVJdGVtcyI6ZmFsc2UsInNrdXNGaWx0ZXIiOiJBTEwiLCJzaW11bGF0aW9uQmVoYXZpb3IiOiJkZWZhdWx0IiwiaW5zdGFsbG1lbnRDcml0ZXJpYSI6Ik1BWF9XSVRIT1VUX0lOVEVSRVNUIiwicHJvZHVjdE9yaWdpblZ0ZXgiOmZhbHNlLCJtYXAiOiJjYXRlZ29yeS0xIiwicXVlcnkiOiJzdXBlcm1lcmNhZG8iLCJvcmRlckJ5IjoiT3JkZXJCeVJlbGVhc2VEYXRlREVTQyIsImZyb20iOjAsInRvIjo0LCJzZWxlY3RlZEZhY2V0cyI6W3sia2V5IjoiY2F0ZWdvcnktMSIsInZhbHVlIjoic3VwZXJtZXJjYWRvIn1dLCJmdWxsVGV4dCI6IiIsImZhY2V0c0JlaGF2aW9yIjoiU3RhdGljIiwiY2F0ZWdvcnlUcmVlQmVoYXZpb3IiOiJkZWZhdWx0Iiwid2l0aEZhY2V0cyI6ZmFsc2V9%22%7D)

## Regla de detención

Si esta fuente o una consulta equivalente observada en los activos públicos no devuelve precios, el desarrollo se detendrá. No se utilizarán rutas excluidas ni se inventarán precios.
