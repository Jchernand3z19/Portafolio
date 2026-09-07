# Power BI — Precios de Supermercados SPS

Esta carpeta contiene activos versionables para construir el dashboard sobre la capa analítica segura.

## Fuente de verdad

La lógica de identidad, comparabilidad, ahorro, canasta común e histórico vive en Python y sus tests. Power BI consume el dataset de publicación; no vuelve a homologar productos por nombre, marca o presentación.

Documentación relacionada:

- `../docs/COMPARATOR-METHODOLOGY.md`
- `../docs/PUBLICATION-DATA-DICTIONARY.md`
- `../docs/BI-IMPLEMENTATION-GUIDE.md`

## Fuente estática para refresh

Después de cada publicación analítica válida, el workflow de sincronización reutiliza **el mismo artifact seguro ya generado** y materializa una copia pública estable en la rama `portfolio-data`.

Fuente Web recomendada para Power BI:

```text
https://raw.githubusercontent.com/Jchernand3z19/Portafolio/portfolio-data/precios-supermercados-sps/published/bi/la-colonia-walmart-sps/dataset.json
```

Ese archivo contiene el contrato `precios-sps-static-bi-dataset/v1` con:

- `publication.offers`;
- `publication.products`;
- `publication.common_basket`;
- `publication.scope`;
- `source_descriptors` para nombres, marca, presentación y categoría ya verificados;
- `manifest` y procedencia (`source_workflow_run_id`, `source_head_sha`, timestamps).

La actualización de esta fuente **no ejecuta una consulta adicional a Turso**: copia y valida el artifact creado por `Precios SPS - Publicar analítica segura`. De esta forma Power BI y el portafolio reutilizan la misma publicación y las visitas o refresh del dashboard no consumen Turso.

## Activos

- `theme.json`: tema base importable en Power BI.

Los artefactos binarios `.pbix` no se consideran la definición reproducible del modelo. Cuando se publique un PBIX, debe poder reconstruirse usando el contrato de datos y la guía conservados en Git.

## Páginas sugeridas

1. Resumen ejecutivo.
2. Comparador de producto.
3. Canasta común.
4. Cambios desde la ejecución anterior.
5. Histórico y variabilidad.
6. Cobertura y exclusiones del matching.

## Regla visual crítica

Una selección con cero productos comparables debe mostrar un estado vacío. No se debe convertir un total cero en “supermercado más barato”.
