# Estado actual — Precios de Supermercados SPS

GitHub `main`, Pull Requests, Actions, artifacts y Turso son la fuente de verdad técnica. Este archivo resume el estado **vigente**; el snapshot detallado anterior al cierre de Los Andes y Paiz se conserva sin modificaciones en [`PROJECT_STATE_HISTORY_2026-09-02.md`](PROJECT_STATE_HISTORY_2026-09-02.md).

## Estado productivo verificado — 2026-09-04

La fase de adquisición quedó cerrada con seis cadenas productivas y once ubicaciones aceptadas en Turso:

| Cadena | Ubicaciones productivas aceptadas |
| --- | --- |
| La Colonia | SPS, Tegucigalpa |
| Colonial | SPS |
| Walmart | SPS, TGU FFAA, TGU El Sauce |
| PriceSmart | SPS 6603, Florencia 6602 |
| Comisariato Los Andes | SPS |
| Paiz | TGU Multiplaza, TGU Próceres |

Checkpoint reconciliado después del cierre de Paiz: **6 supermercados, 11 ubicaciones, 56,769 productos, 108,315 periodos de `price_history` y 18 `scrape_runs`**. Los postflights productivos más recientes reportan cero periodos actuales duplicados, cero violaciones de claves foráneas e `integrity_check=ok`.

No se inventaron ubicaciones cuando la fuente no las demostró. Paiz no tiene contexto selector SPS aceptado; sus dos contextos demostrados son Multiplaza y Próceres en Tegucigalpa. PriceSmart El Sauce 6604 permanece excluido. Maxi Despensa y Despensa Familiar continúan en **NO-GO TEMPORAL PARA PRICE TRACKING WEB**.

## Cierre final de Paiz

PR [#372](https://github.com/Jchernand3z19/Portafolio/pull/372) fusionado a `main` en el merge commit `7f9b10b18445184f3dbfba49d25a6375d7a87b4f`.

Paiz usa una fuente pública VTEX ligada a contexto de tienda, no un precio universal de ciudad. El full reconciliado demostró:

- `paiz_tgu_multiplaza`: 8,864 productos fuente / 8,868 SKU.
- `paiz_tgu_proceres`: 8,567 productos fuente / 8,571 SKU.
- 9,299 identidades Paiz únicas en `products` después de persistir ambos contextos.
- 8,868 y 8,571 periodos actuales respectivamente.
- 0 duplicados actuales, 0 violaciones FK, `integrity_check=ok`.

La recuperación de Próceres reutilizó el artifact aceptado y verificado por SHA-256; no repitió el recrawl. La migración idempotente amplió únicamente las excepciones necesarias para ofertas Paiz agotadas sin precio y para múltiples contextos Paiz en una misma ciudad, preservando las FKs y los datos existentes.

Evidencia: [`reports/paiz/2026-09-04-full/README.md`](../reports/paiz/2026-09-04-full/README.md) y [`production-evidence.json`](../reports/paiz/2026-09-04-full/production-evidence.json).

## Comisariato Los Andes

Comisariato Los Andes SPS quedó integrado previamente mediante PR #371 y persiste 6,646 productos del catálogo público aceptado. Su postflight productivo quedó sin duplicados actuales y la operación diaria utiliza binding explícito de la tienda SPS demostrada.

Evidencia: [`reports/comisariato-los-andes/2026-09-04-full/README.md`](../reports/comisariato-los-andes/2026-09-04-full/README.md) y [`evidence.json`](../reports/comisariato-los-andes/2026-09-04-full/evidence.json).

## Operación recurrente vigente

El workflow existente `.github/workflows/precios-supermercados-sps-la-colonia-mvp-update.yml` corre a `17 11 * * *`, equivalente a **05:17 America/Tegucigalpa**, y actualmente cubre:

1. La Colonia SPS.
2. La Colonia TGU.
3. Comisariato Los Andes SPS.
4. Paiz Multiplaza TGU.
5. Paiz Próceres TGU.

Cada fuente se valida antes de persistir. Paiz asegura además la migración idempotente de esquema y verifica por separado ambos contextos, duplicados, FKs e integridad. Los workflows temporales usados para carga/recovery de Paiz fueron retirados antes del merge.

Colonial, Walmart y PriceSmart conservan sus cierres productivos demostrados; no se amplía su recurrencia por este cierre.

## CI vigente

La suite sobre el PR final pasó **2,088 pruebas**. Después del merge, el workflow de `main` [run 33902732635](https://github.com/Jchernand3z19/Portafolio/actions/runs/33902732635) volvió a ejecutar el commit exacto `7f9b10b18445184f3dbfba49d25a6375d7a87b4f` y terminó **2,088 passed en 177.25 s**, incluyendo la auditoría de seguridad de workflows.

## Fronteras actuales

- Fase de adquisición: **cerrada** para las cadenas demostradas arriba.
- Dashboard/visualización: fuera de este cierre; no iniciado aquí.
- Matching entre cadenas: fuera de este cierre; no iniciado aquí.
- Disponibilidad por sí sola no justifica fusionar o separar contextos ni se convierte en inventario exacto.
- Precio ausente no se inventa como cero, precio regular ni promoción.
- Nuevas cadenas, nuevas ubicaciones o reaperturas de NO-GO requieren una fuente pública y un contrato de evidencia nuevos.

## Metodología reusable

La recuperación de Paiz demostró una mejora genérica para `idempotency-replay`: distinguir replay de evidencia durable frente a una nueva observación, verificar hashes antes de reutilizar artifacts y recapturar sólo particiones faltantes/incorrectas cuando la semántica temporal lo permite. La mejora se registró en `Jchernand3z19/reusable-engineering-skills` sin incluir detalles específicos del proyecto.
