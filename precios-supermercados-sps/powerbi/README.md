# Power BI — Precios de Supermercados SPS

Esta carpeta contiene activos versionables para construir el dashboard sobre la capa analítica segura.

## Fuente de verdad

La lógica de identidad, comparabilidad, ahorro, canasta común e histórico vive en Python y sus tests. Power BI consume el dataset de publicación; no vuelve a homologar productos por nombre, marca o presentación.

Documentación relacionada:

- `../docs/COMPARATOR-METHODOLOGY.md`
- `../docs/PUBLICATION-DATA-DICTIONARY.md`
- `../docs/BI-IMPLEMENTATION-GUIDE.md`

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