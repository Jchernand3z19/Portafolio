# Homologación de productos — fundación validada

Fecha de auditoría: 2026-09-04.

## Alcance

Esta fase construye una capa descriptiva y de identidad para comparar productos entre supermercados sin alterar el estado comercial ni el histórico de precios.

La separación es deliberada:

```text
identidad / taxonomía / presentación
!=
precio / promoción / disponibilidad / histórico
```

Una mejora posterior de `category`, `subcategory`, `product_type`, marca o presentación no debe abrir ni cerrar un periodo de `price_history` por sí sola.

## Reglas de confianza

1. Un GTIN GS1 válido e idéntico es la única identidad automática fuerte cross-supermercado en esta fase.
2. La identidad GTIN se conserva aunque exista una contradicción descriptiva, pero esos grupos quedan `review_required` para comparación cuando la presentación o taxonomía no es suficientemente consistente.
3. Dos GTIN válidos distintos nunca se unen por similitud textual.
4. Sin GTIN exacto, marca + `product_type` + presentación compatible + similitud de nombre sólo generan candidatos `review_required`; nunca una unión automática.
5. Marcas placeholder de fuente (`RMS`, `Marca COMANDES`, `SIN MARCA`, etc.) se normalizan como marca desconocida y no sirven para matching.
6. `oz` sin indicador de onza fluida no se convierte silenciosamente a masa o volumen.
7. Multipacks se mantienen separados de unidades individuales; notaciones ambiguas fallan cerradas.
8. Expresiones de empaque como `Doy Pack` y `Tetra Pack` no se interpretan como conteo multipack por sí solas.
9. Para Paiz, la auditoría demostró que el campo de presentación fuente puede contradecir sistemáticamente el nombre comercial. Cuando ambos difieren, se conserva la contradicción y se usa el tamaño anunciado en el nombre para la firma descriptiva.

## Auditoría real de producción

La auditoría final fue ejecutada contra Turso exclusivamente mediante `SELECT`. No realizó `INSERT`, `UPDATE`, `DELETE`, cambios de esquema ni tráfico hacia sitios de supermercados.

Productos evaluados: **56,779**.

| Supermercado | Productos |
| --- | ---: |
| Colonial | 9,205 |
| Comisariato Los Andes | 6,646 |
| La Colonia | 9,519 |
| Paiz | 9,299 |
| PriceSmart | 6,078 |
| Walmart | 16,032 |

Resultados finales:

- 34,365 productos fuente contienen un GTIN válido.
- 9,087 grupos GTIN aparecen en al menos dos supermercados.
- 21,331 productos fuente forman parte de esos grupos cross-supermercado.
- 8,126 grupos GTIN están listos para comparación bajo las guardas actuales.
- 961 grupos conservan identidad GTIN pero requieren revisión descriptiva antes de una comparación automática.
- 18,748 productos recibieron `product_type` con las reglas de la fundación.
- 16,290 valores de marca fueron reconocidos como placeholders genéricos y descartados para matching.
- Sólo quedaron 2 candidatos sin GTIN exacto con el umbral conservador actual; ambos permanecen `review_required`.
- Uniones automáticas sin GTIN: **0**.

Los motivos de revisión no son excluyentes: un mismo grupo puede tener más de uno. En la auditoría final aparecieron 509 grupos con conflicto de presentación entre fuentes, 397 con multipack ambiguo, 60 con conflicto de `product_type` y 7 con conflicto directo de presentación fuente.

## Presentaciones

Estado sobre los 56,779 productos:

| Estado | Productos |
| --- | ---: |
| `confirmed` | 13,077 |
| `name_only` | 23,063 |
| `source_only` | 370 |
| `name_preferred_source_conflict` | 778 |
| `ambiguous_multipack` | 1,561 |
| `conflict` | 28 |
| `missing` | 17,902 |

Estos conteos describen calidad de metadata, no disponibilidad comercial.

## Candidatos sin GTIN exacto

Los dos candidatos más fuertes encontrados fueron:

1. `Aceite Vegetal Ideal Girasol Y Soya 3750 Ml` (La Colonia) ↔ `Ideal Aceite Vegetal de Girasol y Soya 3.75 L` (PriceSmart).
2. `Arroz Progreso Blanco 25 Lb` (La Colonia) ↔ `Progreso Arroz Blanco 95% / 11.3 kg / 25 lb` (PriceSmart).

Ambos obtuvieron score `1.0000`, marca y tipo compatibles y presentación equivalente. Ninguno fue unido automáticamente porque falta GTIN exacto compartido.

## Evidencia reproducible

Auditoría read-only final:

- GitHub Actions run: `33917069107`
- artifact: `9953558639`
- SHA-256 del artifact: `692bdc53f6bf851580c8ed66f4c03da6da67a28f8d9badf3781c41b0d881ae38`

Resumen estructurado: `audit-summary.json`.

El artifact temporal contiene la salida completa de perfiles y candidatos utilizada para la revisión de esta fase.

## No realizado en esta fase

- No se escribieron campos de homologación en Turso.
- No se modificó `price_history`.
- No se crearon periodos históricos nuevos.
- No se realizaron consultas nuevas contra ningún supermercado.
- No se fusionaron candidatos sin GTIN.
- No se pretende que la taxonomía actual cubra todo el catálogo; los productos no demostrables quedan sin clasificar antes que forzar una categoría.
