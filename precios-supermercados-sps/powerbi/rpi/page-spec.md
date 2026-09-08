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
4. **Price Movements** — estado vacío documentado hasta publicar
   `fact_price_changes`; después mostrará magnitud, fecha y dirección.
5. **Promotion Intelligence** — promociones declaradas actuales separadas de
   reducción histórica. La segunda señal queda vacía hasta publicar su fact.
6. **Brand Intelligence** — cobertura, precio relativo y promoción por marca
   dentro del universo seguro.
7. **Geographic Intelligence** — retailer/ubicación sólo para contextos
   demostrados; no agrega ciudades o clubes por inferencia.
8. **Assortment / Coverage** — observados, comparables, precios válidos,
   exclusiones, `out_of_stock`, `unknown` y `ABSENT` como conceptos distintos.
9. **Opportunities & Alerts** — PCI alto/bajo, spreads y freshness; toda alerta
   declara cobertura y no implica causalidad o recomendación automática.

En mobile layout de Power BI se priorizan tarjetas, filtros, alertas y tablas
cortas. Ninguna página construye matching, PCI o freshness en DAX.
