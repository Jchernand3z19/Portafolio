# Modelo semántico RPI B2B

## Relaciones

```text
DimProduct[canonical_product_id] 1 -> * FactCurrentComparison[canonical_product_id]
DimRetailer[supermarket_id]      1 -> * FactCurrentComparison[supermarket_id]
DimLocation[location_id]         1 -> * FactCurrentComparison[location_id]
DimCategory[category]            1 -> * FactCurrentComparison[category]
DimBrand[brand]                  1 -> * FactCurrentComparison[brand]

DimProduct[canonical_product_id] 1 -> * FactPriceHistory[canonical_product_id]
DimRetailer[supermarket_id]      1 -> * FactPriceHistory[supermarket_id]
DimLocation[location_id]         1 -> * FactPriceHistory[location_id]
DimCategory[category]            1 -> * FactPriceHistory[category]
DimBrand[brand]                  1 -> * FactPriceHistory[brand]

DimProduct[canonical_product_id] 1 -> * FactPromotionAnalysis[canonical_product_id]
DimRetailer[supermarket_id]      1 -> * FactPromotionAnalysis[supermarket_id]
DimLocation[location_id]         1 -> * FactPromotionAnalysis[location_id]
DimCategory[category]            1 -> * FactPromotionAnalysis[category]
DimBrand[brand]                  1 -> * FactPromotionAnalysis[brand]

DimRetailer[supermarket_id]      1 -> * FactBasketCost[supermarket_id]
DimLocation[location_id]         1 -> * FactBasketCost[location_id]
```

Todas son `single direction` desde dimensión a hecho. No crear relaciones por
nombre ni presentación y no habilitar many-to-many para aumentar cobertura.
`period_start` y `as_of` son timestamps UTC del mart y pueden usarse como eje o
filtro temporal sin reconstruir periodos a partir de precios en Power Query.

## Granos

| Tabla | Grano |
| --- | --- |
| DimProduct | producto canónico seguro |
| DimRetailer | cadena del scope |
| DimLocation | ubicación comercial del scope |
| DimCategory | categoría presente |
| DimBrand | marca presente |
| FactCurrentComparison | oferta comparable actual por producto/retailer/ubicación |
| FactPriceHistory | periodo comercial observado por oferta segura |
| FactPromotionAnalysis | oferta segura evaluada en el corte `as_of` |
| FactBasketCost | misma canasta común por retailer/ubicación |
| FactMetricCoverage | un corte analítico |
| SourceFreshness | una fuente/ubicación por corte |
| BusinessMetadata | un corte y estado global de comparación |

`FactPriceHistory` conserva el precio efectivo observado, precio regular sólo como
referencia, señal de promoción, precio previo, cambio absoluto/porcentual,
dirección e indicador de periodo actual. No interpola días faltantes ni convierte
el precio regular declarado en histórico.

`FactPromotionAnalysis` mantiene separadas `source_reports_promotion` y
`historical_price_reduction`, además de profundidad declarada, comparación contra
30/90 días, eventos, duración y posición histórica calculadas en Python.

Los campos monetarios se tipan como Fixed decimal number. `pci`, `spread_pct`,
`coverage_pct` y los porcentajes históricos/promocionales se publican en escala
0–100; las medidas los dividen entre 100 sólo para formato porcentual.

## Filtros obligatorios

Antes de mostrar ranking/PCI, la página exige `Estado comparación = COMPARABLE`.
Precios stale pueden aparecer en tablas de observabilidad e historia, con
timestamp y badge, pero no compiten. Los nulos no se transforman a cero.
