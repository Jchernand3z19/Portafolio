# Especificación de páginas Power BI B2B

Todas las páginas incluyen `as_of`, ventana de freshness, estado de comparación,
conteos de universo/cobertura y filtros de retailer, ubicación, categoría, marca
y producto cuando apliquen.

1. **Executive Market Overview** — KPI de comparables, cobertura, PCI promedio,
   retailers fresh/stale, canasta comparable y distribución de posición.
2. **Competitive Pricing** — matriz producto/retailer con precio, rank, PCI,
   mínimo, mediana y spread; tooltip con observación y freshness.
3. **Category Intelligence** — cobertura y PCI por categoría, sin promediar
   surtidos no comparables.
4. **Price Movements** — usa `FactPriceHistory`: serie por `period_start`, precio
   efectivo, precio previo, cambio absoluto/porcentual, dirección y periodo
   actual. No interpola días sin observación ni interpreta una promoción como
   causalidad del movimiento.
5. **Promotion Intelligence** — usa `FactPromotionAnalysis` para mostrar por
   separado promoción declarada por la fuente, reducción histórica observada,
   profundidad declarada, posición contra 30/90 días, eventos y duración. El
   precio regular reportado es referencia, no evidencia histórica.
6. **Brand Intelligence** — cobertura, precio relativo y promoción por marca
   dentro del universo seguro.
7. **Geographic Intelligence** — retailer/ubicación sólo para contextos
   demostrados; no agrega ciudades o clubes por inferencia.
8. **Assortment / Coverage** — observados, comparables, precios válidos,
   exclusiones, `out_of_stock`, `unknown` y `ABSENT` como conceptos distintos.
9. **Opportunities & Alerts** — PCI alto/bajo, spreads, movimientos observados,
   promociones sin reducción histórica y freshness; toda alerta declara cobertura
   y no implica causalidad ni recomendación automática.

Si el universo seguro no produce filas para un fact, la página muestra un
**estado vacío** explícito con el estado de comparación/freshness disponible; no
convierte ausencia en cero, ni fabrica una serie o una promoción.

En mobile layout de Power BI se priorizan tarjetas, filtros, alertas y tablas
cortas. Ninguna página construye matching, PCI, freshness, cambios de precio ni
clasificación promocional en DAX/Power Query; sólo agrega campos ya publicados
por Python.
