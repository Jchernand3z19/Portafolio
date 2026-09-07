# Guía de implementación en Power BI

## Objetivo

Construir el dashboard sobre el dataset de publicación seguro, sin repetir homologación ni lógica de identidad en Power Query o DAX.

## Fuente recomendada

El modelo semántico debe consumir artefactos generados por el proyecto, no conectarse directamente a páginas de supermercados ni a Turso.

La fuente estable para refresh es:

```text
https://raw.githubusercontent.com/Jchernand3z19/Portafolio/portfolio-data/precios-supermercados-sps/published/bi/la-colonia-walmart-sps/dataset.json
```

El workflow `Precios SPS - Sincronizar datos estáticos del portafolio` crea ese archivo a partir del mismo artifact que ya generó la publicación analítica. La sincronización no ejecuta scraping ni consultas adicionales a Turso. Power BI y la página pública consumen copias estáticas derivadas de una misma ejecución segura.

El documento usa el schema `precios-sps-static-bi-dataset/v1` y conserva procedencia exacta mediante `source_workflow_run_id`, `source_head_sha`, `published_at_utc` y el `manifest` original.

Tablas mínimas a derivar del JSON:

- `Offers`: `publication.offers`, una fila por producto canónico, supermercado y ubicación dentro del alcance comparable.
- `Products`: `publication.products`, una fila por producto canónico con mínimo, máximo y ahorro dentro del alcance.
- `CommonBasket`: `publication.common_basket`, un total por supermercado para el mismo denominador.
- `Scope`: `publication.scope`, supermercados y ubicaciones incluidas.
- `SourceDescriptors`: `source_descriptors`, nombres, marca, presentación y categoría de las filas fuente ya verificadas.

Relacionar `SourceDescriptors[source_record_id]` con `Offers[source_record_id]`; no reconstruir la identidad por texto.

Tablas analíticas adicionales pueden incorporar series históricas y cambios entre ejecuciones, siempre manteniendo `canonical_product_id`, `supermarket_id`, `location_id` y timestamps como claves explícitas.

## Refresh

El refresh del dashboard debe apuntar únicamente al JSON estático de `portfolio-data`.

Flujo:

```text
actualización productiva
  → Turso
  → homologación
  → publicación analítica segura
  → artifact validado
  → dataset.json en portfolio-data
  → Power BI / portafolio
```

Por tanto, abrir la página o refrescar Power BI no consulta Turso. Turso sólo se usa dentro de los workflows controlados que ya forman parte del procesamiento del dato.

Si el workflow analítico falla, la sincronización no corre y el archivo estático conserva el último corte válido.

## Tipos de datos

Al importar JSON:

- `current_price`, `best_price`, `highest_price`, `savings_vs_highest` y `total`: Decimal fijo / moneda HNL.
- porcentajes: número decimal; si el archivo entrega 16.67 significa 16.67 %, no 0.1667.
- IDs: texto, nunca número.
- GTIN: texto para preservar ceros a la izquierda.
- booleanos `is_best_price` / `is_cheapest`: verdadero/falso.

## Modelo

Relaciones sugeridas:

- `Products[canonical_product_id]` 1 → * `Offers[canonical_product_id]`.
- `SourceDescriptors[source_record_id]` 1 → * `Offers[source_record_id]`.
- `Scope[supermarket_id + location_id]` 1 → * `Offers[supermarket_id + location_id]`.
- `Scope[supermarket_id + location_id]` 1 → * `CommonBasket[supermarket_id + location_id]`.

No crear una relación sólo por nombre de producto.

## Medidas base

Ejemplos conceptuales; los nombres finales pueden adaptarse al modelo:

```DAX
Productos comparables = DISTINCTCOUNT(Products[canonical_product_id])

Mejor precio promedio = AVERAGE(Products[best_price])

Ahorro total potencial = SUM(Products[savings_vs_highest])

Precio actual = SUM(Offers[current_price])
```

Para una tarjeta de canasta, usar `CommonBasket[total]` filtrado por supermercado. No sumar `Products[best_price]` para representar el costo de una cadena: ese campo es el mínimo por producto y puede provenir de supermercados distintos.

## Visuales recomendados

### Resumen

- número de supermercados/ubicaciones del alcance;
- productos en el denominador común;
- total de canasta por supermercado;
- diferencia absoluta y porcentual entre total mínimo y máximo.

### Comparador por producto

Tabla con:

- producto canónico/GTIN;
- nombre y presentación fuente;
- supermercado;
- ubicación;
- precio actual;
- indicador de mínimo;
- ahorro contra el máximo del mismo producto.

### Cambios

- variación de precio por producto y cadena;
- productos que entraron o salieron del universo comparable;
- cambio del ganador de una canasta sólo cuando el denominador permanece idéntico.

### Histórico

- series por `canonical_product_id + supermarket_id + location_id`;
- mínimo, máximo, media y cantidad de cambios;
- fecha de primera y última observación aceptada.

## Filtros obligatorios

Mostrar siempre el alcance activo:

- supermercado;
- ubicación;
- producto/categoría cuando exista;
- periodo para histórico.

La ciudad no debe inferirse desde el nombre si existe `location_id` explícito.

## Empates

Si dos supermercados tienen exactamente el mismo mínimo, ambos deben poder presentarse como mejor precio. Un campo singular de “best supermarket” puede usarse sólo como desempate determinista interno; la visualización debe basarse en precio mínimo para reconocer empates.

## Universo vacío

Si una selección deja cero productos en la intersección comparable, mostrar “Sin productos comparables para este alcance”. No presentar un supermercado ganador ni ahorro de L 0 como si fuera un resultado válido.

## Seguridad y publicación

No incluir en PBIX/PBIP, parámetros, consultas o archivos públicos:

- `TURSO_AUTH_TOKEN`;
- URL privada de base de datos;
- cookies;
- encabezados de autenticación;
- secretos de GitHub Actions.

La fuente pública debe ser el dataset derivado y sanitizado de `portfolio-data`.

## Reproducibilidad

El repositorio conserva metodología, diccionario, tema y guía. Un `.pbix` binario no es la fuente de verdad del cálculo; la lógica crítica vive en Python y está cubierta por tests. De esa forma el dashboard puede reconstruirse sin convertir DAX en una segunda implementación del comparador.
