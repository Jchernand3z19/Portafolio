# Paiz — adquisición completa y cierre productivo

Estado final: `PAIZ_COMPLETE_IN_PRODUCTION`.

La fuente pública VTEX quedó demostrada para dos contextos activos de Tegucigalpa: `paiz_tgu_multiplaza` y `paiz_tgu_proceres`. No se observó un contexto selector activo equivalente para San Pedro Sula, por lo que no se inventó una ubicación SPS ni un precio universal de ciudad.

## Captura aceptada y reproducible

La evidencia versionada cerró el catálogo mediante partición exhaustiva de `category-1`, con facetas antes/después, totales raíz estables y reconciliación exacta de membresía por producto y SKU. La fase completa registró 199 requests contando el intento fail-closed previo; 198 respuestas quedaron aceptadas, con cero retries automáticos. La recuperación reutilizó 68 respuestas RAW válidas byte por byte y solicitó únicamente 130 respuestas faltantes o inválidas.

| Contexto | Producto fuente | SKU |
| --- | ---: | ---: |
| Paiz Multiplaza | 8,864 | 8,868 |
| Paiz Próceres | 8,567 | 8,571 |

Los snapshots, requests, hashes, archivos RAW y el intento fallido preservado están en este directorio. `evidence.json` describe la completitud y `raw-archives.sha256` fija las huellas de los RAW archivados.

## Persistencia productiva

La carga productiva usó una captura posterior del runner definitivo, con las mismas cardinalidades de catálogo/SKU. Multiplaza se persistió correctamente en el run `33837881993`. Próceres se recuperó sin recrawl: se reutilizó el mismo artifact `9924053887`, se verificaron los SHA-256 de ambos snapshots, se migró únicamente la restricción necesaria para múltiples contextos Paiz en una misma ciudad y se persistió sólo Próceres.

Postflight productivo:

- `paiz_tgu_multiplaza`: 8,868 periodos actuales.
- `paiz_tgu_proceres`: 8,571 periodos actuales.
- 9,299 productos Paiz únicos en `products`.
- 0 periodos actuales duplicados.
- 0 violaciones de claves foráneas.
- `PRAGMA integrity_check = ok`.
- el índice legado de `locations` permite Paiz multi-contexto sin reconstruir la tabla ni alterar las FKs.
- `price_history` permite precio/promoción nulos únicamente para las ofertas Paiz agotadas bajo la excepción controlada ya usada por las cadenas compatibles.

La evidencia compacta del estado productivo está en `production-evidence.json`. La recuperación final fue el workflow run `33839180713`, artifact `9924313921`, y no volvió a descargar los catálogos.

## Operación recurrente

Paiz quedó integrado al workflow diario existente del MVP. El runner definitivo captura los dos contextos, valida completitud y binding, aplica la migración idempotente de esquema, persiste cada contexto por separado y ejecuta verificaciones de estado, duplicados, FK e integridad.

La disponibilidad no se usa para decidir que dos tiendas sean equivalentes ni para inferir un precio de ciudad. Los estados sin precio se conservan como ofertas agotadas sin inventar precio cero, precio regular ni promoción.

## Criterio de cierre

La fase Paiz se considera terminada cuando el PR #372 queda con CI verde y fusionado a `main`. No iniciar visualización, matching entre cadenas ni otra expansión dentro de este cierre.
