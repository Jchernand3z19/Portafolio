# Power BI — Retail Price Intelligence B2B

Este modelo consume `rpi-business-mart/v1`, producido por
`scripts/exportar_rpi_marts.py`. No consulta supermercados, no escribe en Turso
y no repite homologación, freshness, cobertura, ranking ni PCI.

## Carga local reproducible

1. Descargar el artifact RPI generado por el pipeline autorizado.
2. Crear un parámetro texto `BusinessMartPath` con la ruta absoluta de
   `business-mart.json`.
3. Crear `BusinessMart` desde `queries/BusinessMart.pq`.
4. Crear las consultas restantes con el nombre de cada archivo `.pq`.
5. Aplicar las relaciones de `model-spec.md`, las medidas de `measures.dax` y el
   tema `../theme.json`.

Sólo `BusinessMart` lee un archivo. Las demás consultas referencian el documento
en memoria y validan sus columnas aun cuando una tabla esté vacía.

No se incluye un PBIX fabricado. El binario final debe construirse en Power BI
Desktop y debe conservar esta definición versionable como fuente de verdad.

## Freshness y estado vacío

Todas las páginas muestran `as_of`, ventana y freshness. Cuando
`comparison_status` es `INSUFFICIENT_FRESH_COMPARISON`, rank, PCI y métricas de
mercado permanecen en blanco; los precios last-known-good pueden mostrarse con
su alerta stale. Un universo o canasta vacíos no producen ganador.

## Alcance actual

El mart comparable vigente es La Colonia SPS + Walmart SPS. Cobertura de scraping
de otras cadenas no equivale a cobertura comparable. Las páginas históricas y
de respuesta competitiva sólo deben activar sus visuales cuando el mart publique
los facts históricos correspondientes.
