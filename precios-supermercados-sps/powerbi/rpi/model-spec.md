# Modelo semántico RPI B2B

## Relaciones

```text
DimProduct[canonical_product_id] 1 -> * FactCurrentComparison[canonical_product_id]
DimRetailer[supermarket_id]      1 -> * FactCurrentComparison[supermarket_id]
DimLocation[location_id]         1 -> * FactCurrentComparison[location_id]
DimCategory[category]            1 -> * FactCurrentComparison[category]
DimBrand[brand]                  1 -> * FactCurrentComparison[brand]
DimRetailer[supermarket_id]      1 -> * FactBasketCost[supermarket_id]
DimLocation[location_id]         1 -> * FactBasketCost[location_id]
```

Todas son `single direction` desde dimensión a hecho. No crear relaciones por
nombre ni presentación y no habilitar many-to-many para aumentar cobertura.

## Granos

| Tabla | Grano |
| --- | --- |
| DimProduct | producto canónico seguro |
| DimRetailer | cadena del scope |
| DimLocation | ubicación comercial del scope |
| DimCategory | categoría presente |
| DimBrand | marca presente |
| FactCurrentComparison | oferta comparable actual por producto/retailer/ubicación |
| FactBasketCost | misma canasta común por retailer/ubicación |
| FactMetricCoverage | un corte analítico |
| SourceFreshness | una fuente/ubicación por corte |
| BusinessMetadata | un corte y estado global de comparación |

Los campos monetarios se tipan como Fixed decimal number. `pci`, `spread_pct` y
`coverage_pct` son porcentajes expresados en escala 0–100; las medidas los
dividen entre 100 sólo para formato porcentual.

## Filtros obligatorios

Antes de mostrar ranking/PCI, la página exige `Estado comparación = COMPARABLE`.
Precios stale pueden aparecer en tablas de observabilidad, con timestamp y badge,
pero no compiten. Los nulos no se transforman a cero.
