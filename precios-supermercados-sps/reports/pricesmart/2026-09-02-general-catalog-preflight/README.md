# PriceSmart Honduras — preflight offline del catálogo general

> Estado posterior: el probe autorizado ya demostró 26 categorías raíz. La
> evidencia live y el siguiente gate están en
> [`../2026-09-02-taxonomy-probe/README.md`](../2026-09-02-taxonomy-probe/README.md).

## Resultado

Este preflight no hizo tráfico nuevo a PriceSmart ni operaciones Turso. Recorrió
los siete archivos RAW PriceSmart ya versionados, el parser vigente y el código
cliente capturado previamente.

La conclusión es cerrada:

```text
PRICESMART G10D03 / ALIMENTOS COMPLETO
CATÁLOGO GENERAL PRICESMART INCOMPLETO
```

El snapshot existente de Alimentos sigue siendo reutilizable: 1,124 productos y
1,127 SKU por club para SPS 6603 y Florencia 6602. No hay razón técnica para
recrawlearlo durante el descubrimiento del resto del catálogo.

## Qué demuestra el RAW existente

Se localizaron 194 requests y 194 respuestas Discovery con productos. Todas las
requests, sin excepción, tienen el mismo alcance:

```text
q = G10D03
search_type = category
url = /es-hn/categoria/Alimentos-G10D03/G10D03
rows = 12
view_id = HN
```

Las respuestas reportan siempre `numFound=1124`: 192 páginas tienen 12 productos
y las dos últimas tienen ocho. No existe en el RAW una consulta sin categoría,
una consulta de raíz ni una respuesta de otro departamento.

El facet `category` sí entrega una jerarquía estructurada completa, pero sólo para
el subárbol consultado. Tiene 117 nodos: una raíz `G10D03 / Alimentos`, 19 nodos
padre, 98 hojas y profundidad máxima 3. Cada nodo declara `cat_id`, `cat_name`,
`crumb`, `tree_path`, `count` y `parent`. La estructura fue idéntica en las 194
respuestas. Hubo tres snapshots de conteos por pequeños cambios temporales en dos
ramas; el total raíz permaneció en 1,124.

Los documentos Discovery no traen campos de categoría o membership. La ficha
capturada del SKU de control `516411` sólo declara su hoja
`G10D53001003 / Soft Drinks`; no contiene sus ancestros ni otros departamentos.
Esto impide reconstruir el catálogo general uniendo las páginas de Alimentos o
infiriendo IDs por prefijo.

La lista visual aportada por el usuario confirma que existen departamentos fuera
de Alimentos, pero no se usa como prueba de completitud ni para inventar IDs.

## Fuente estructurada preparada para el probe

El bundle público ya capturado demuestra que el cliente tiene una operación de
lectura `getFacetCategories`. El cliente configura `middlewareUrl=/api/` y envía
operaciones como `POST /<tag>/<operation>`; la integración se expone como `$ct`.
Por ello la ruta derivada es:

```text
POST https://www.pricesmart.com/api/ct/getFacetCategories
```

El contrato capturado admite `onlyParent`, `ancestor`, `catIds`, `key`, `slug` y
`slugs`. `onlyParent` se traduce a `parent is not defined`; la respuesta incluye
identidad, key, nombre, slug, ancestros y padres. La configuración pública fija
`categoriesQueryLimit=200`.

La ruta y el body siguientes están derivados de código cliente capturado, pero aún
no fueron ejecutados. No se presentan como endpoint live demostrado:

```json
[{"onlyParent": true, "limit": 200, "offset": 0}]
```

## Frontera exacta

Sin una observación nueva de `getFacetCategories` no se pueden demostrar los IDs
de las categorías raíz, su cantidad ni su jerarquía completa. En consecuencia
tampoco se pueden emitir todavía las consultas Discovery por padre, obtener sus
`numFound`, detectar si alguna partición requiere hijos o calcular un presupuesto
full exacto.

El probe mínimo siguiente necesita como máximo cuatro POST totales:

1. un POST raíz con `onlyParent=true`, `limit=200`, `offset=0`;
2. un POST con `offset=200` sólo si la primera página devuelve exactamente 200
   categorías;
3. hasta dos retries incluidos en el máximo total.

Concurrencia 1, duración máxima 5 minutos, sólo lectura y sin assets. Se usaría
únicamente contexto público HN/es-HN; no login, membresía, carrito, checkout,
mutaciones, El Sauce, Discovery de productos, full crawl, Turso ni recurrencia.
Se detendría ante 403, 429, CAPTCHA, autenticación inesperada, esquema distinto o
necesidad de otra ruta.

Después de ese probe se calculará, con el número real de raíces, el segundo tramo
mínimo para medir `numFound` por padre mediante el endpoint Discovery ya demostrado.
No se pedirá presupuesto full antes de conocer esos totales.

## Reproducción

```bash
python reports/pricesmart/2026-09-02-general-catalog-preflight/verify.py
```

El verificador comprueba los SHA-256 de los siete archivos RAW, reextrae las 194
requests/respuestas, prueba que todas están limitadas a `G10D03`, reconcilia el
árbol explícito de 117 nodos y valida contra el bundle capturado el contrato del
probe. El árbol completo y los valores de count observados están en
[`evidence.json`](evidence.json).
