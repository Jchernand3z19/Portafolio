# Estado actual — Precios de Supermercados SPS

GitHub `main`, Pull Requests, Actions, artifacts y Turso son la fuente de verdad técnica. Este archivo resume el estado **vigente**; el snapshot detallado anterior al cierre de Los Andes y Paiz se conserva sin modificaciones en [`PROJECT_STATE_HISTORY_2026-09-02.md`](PROJECT_STATE_HISTORY_2026-09-02.md).

## Estado productivo verificado — 2026-09-05

La fase de adquisición permanece cerrada con seis cadenas productivas y once ubicaciones aceptadas en Turso:

| Cadena | Ubicaciones productivas aceptadas |
| --- | --- |
| La Colonia | SPS, Tegucigalpa |
| Colonial | SPS |
| Walmart | SPS, TGU FFAA, TGU El Sauce |
| PriceSmart | SPS 6603, Florencia 6602 |
| Comisariato Los Andes | SPS |
| Paiz | TGU Multiplaza, TGU Próceres |

Checkpoint productivo reconciliado después de las ejecuciones recurrentes y del cierre de homologación: **6 supermercados, 11 ubicaciones, 56,779 productos, 110,002 periodos de `price_history`, 21 `scrape_runs` y 56,779 perfiles en `product_homologation_profiles`**. El último postflight de homologación reporta cero periodos actuales duplicados, cero violaciones de claves foráneas e `integrity_check=ok`.

No se inventaron ubicaciones cuando la fuente no las demostró. Paiz no tiene contexto selector SPS aceptado; sus dos contextos demostrados son Multiplaza y Próceres en Tegucigalpa. PriceSmart El Sauce 6604 permanece excluido. Maxi Despensa y Despensa Familiar continúan en **NO-GO TEMPORAL PARA PRICE TRACKING WEB**.

## Homologación productiva y recurrente

La capa derivada de homologación quedó productiva sin mezclar datos descriptivos con el histórico comercial.

PR #382 incorporó `product_homologation_profiles`, el backfill fail-closed y la compatibilidad de los persistidores con la sexta tabla. La carga inicial productiva cubrió exactamente **56,779/56,779 productos** y no modificó `products`, `price_history` ni `scrape_runs`.

PR [#383](https://github.com/Jchernand3z19/Portafolio/pull/383) quedó fusionado en `main` mediante el commit `1b427026f1383ca5087a5617fae34f1ae15cfad3` y añadió el mantenimiento diferencial recurrente:

- compara `profile_hash` + `normalization_version` contra el perfil existente;
- sólo lleva a staging perfiles nuevos o realmente modificados;
- si todos coinciden, ejecuta un no-op real sin crear ni escribir staging;
- falla cerrado si aparece un perfil persistido cuyo `product_id` ya no pertenece al conjunto fuente;
- conserva cobertura total y valida FKs, periodos actuales duplicados e integridad después de cada ejecución.

La verificación productiva independiente del código ya fusionado procesó **56,779 perfiles** con `inserted=0`, `updated=0`, `unchanged=56,779`, `no_op=true` y `staging_written=false`; los conteos de `products`, `price_history` y `scrape_runs` fueron idénticos antes y después.

Estado derivado actual:

- 34,365 perfiles con GTIN válido.
- 18,748 perfiles con `product_type` clasificado.
- 18,773 `ready`.
- 2,558 `review_required`.
- 13,034 `single_source`.
- 22,414 `unmapped`.
- 8,126 grupos canónicos `ready`.
- 961 grupos canónicos retenidos para revisión.

`review_required` no se interpreta como equivalencia confirmada entre productos. La capa canónica produce candidatos y estados auditables; no fuerza un match definitivo cuando la evidencia no alcanza el umbral aceptado.

Evidencia: [`reports/homologation/2026-09-05-production/README.md`](../reports/homologation/2026-09-05-production/README.md) y [`production-evidence.json`](../reports/homologation/2026-09-05-production/production-evidence.json).

## Cierre final de Paiz

PR [#372](https://github.com/Jchernand3z19/Portafolio/pull/372) fusionado a `main` en el merge commit `7f9b10b18445184f3dbfba49d25a6375d7a87b4f`.

Paiz usa una fuente pública VTEX ligada a contexto de tienda, no un precio universal de ciudad. El full reconciliado demostró:

- `paiz_tgu_multiplaza`: 8,864 productos fuente / 8,868 SKU.
- `paiz_tgu_proceres`: 8,567 productos fuente / 8,571 SKU.
- 9,299 identidades Paiz únicas en `products` después de persistir ambos contextos.
- 8,868 y 8,571 periodos actuales respectivamente en la carga inicial.
- 0 duplicados actuales, 0 violaciones FK, `integrity_check=ok` en el cierre.

La recuperación de Próceres reutilizó el artifact aceptado y verificado por SHA-256; no repitió el recrawl. La migración idempotente amplió únicamente las excepciones necesarias para ofertas Paiz agotadas sin precio y para múltiples contextos Paiz en una misma ciudad, preservando las FKs y los datos existentes.

Evidencia: [`reports/paiz/2026-09-04-full/README.md`](../reports/paiz/2026-09-04-full/README.md) y [`production-evidence.json`](../reports/paiz/2026-09-04-full/production-evidence.json).

## Comisariato Los Andes

Comisariato Los Andes SPS quedó integrado mediante PR #371 y persiste el catálogo público aceptado. Su postflight productivo quedó sin duplicados actuales y la operación diaria utiliza binding explícito de la tienda SPS demostrada.

Evidencia: [`reports/comisariato-los-andes/2026-09-04-full/README.md`](../reports/comisariato-los-andes/2026-09-04-full/README.md) y [`evidence.json`](../reports/comisariato-los-andes/2026-09-04-full/evidence.json).

## Operación recurrente vigente

El workflow `.github/workflows/precios-supermercados-sps-la-colonia-mvp-update.yml` corre a `17 11 * * *`, equivalente a **05:17 America/Tegucigalpa**, y actualmente cubre:

1. La Colonia SPS.
2. La Colonia TGU.
3. Comisariato Los Andes SPS.
4. Paiz Multiplaza TGU.
5. Paiz Próceres TGU.

Cada fuente se valida antes de persistir. Paiz asegura además la migración idempotente de esquema y verifica por separado ambos contextos, duplicados, FKs e integridad. Colonial, Walmart y PriceSmart conservan sus cierres productivos demostrados; no se amplía su recurrencia por esta fase.

Después de una ejecución exitosa de `La Colonia - Actualización MVP` sobre `main` originada por `schedule` o `workflow_dispatch`, el workflow permanente `.github/workflows/precios-supermercados-sps-homologation-refresh.yml` recalcula la capa derivada. También admite `workflow_dispatch` directo. El refresh usa checkout inmutable del commit de la ejecución fuente, permisos `contents: read`, acciones fijadas por SHA y sólo persiste deltas reales de homologación.

## CI vigente

El cierre de refresh diferencial pasó la suite completa y la auditoría de seguridad de workflows:

- PR #383: run `33946205303` — **2,123 passed en 190.41 s**.
- `main` después del merge, commit exacto `1b427026f1383ca5087a5617fae34f1ae15cfad3`: run `33946387842` — **2,123 passed en 173.22 s**.

La verificación productiva de no-op corresponde al run `33946558257`, artifact `9963520883`, y dejó la base comercial sin cambios.

## Seguridad y autoridad live

El fingerprint productivo canónico de la región SPS de La Colonia se conserva explícitamente para los contratos offline y de fallback:

```text
SPS_REGION_FINGERPRINT = d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
ACTIVE_AUTHORIZATION_IDS = []
```

`ACTIVE_AUTHORIZATION_IDS` registra únicamente autorizaciones puntuales one-shot; no representa ni revoca la operación recurrente expresamente autorizada y documentada arriba. Las autorizaciones temporales one-shot registradas en la evidencia histórica siguen siendo hechos auditables, pero **no se interpreta como autorización abierta** ninguna autorización temporal ya consumida o vencida. La existencia de un schedule técnicamente configurado tampoco amplía por sí sola la autoridad live fuera del alcance expresamente autorizado. Cualquier tráfico live fuera de ese alcance **requiere autorización humana explícita vigente**.

## Fronteras actuales

- Fase de adquisición: **cerrada** para las cadenas y ubicaciones demostradas arriba.
- Homologación/identidad derivada: **productiva y recurrente**.
- Comparador y dashboard orientados al usuario final: no iniciados en este cierre.
- Un candidato canónico o estado `review_required` no equivale por sí solo a un match humano confirmado entre cadenas.
- Disponibilidad por sí sola no justifica fusionar o separar contextos ni se convierte en inventario exacto.
- Precio ausente no se inventa como cero, precio regular ni promoción.
- Nuevas cadenas, nuevas ubicaciones o reaperturas de NO-GO requieren una fuente pública y un contrato de evidencia nuevos.

## Metodología reusable

La recuperación de Paiz demostró una mejora genérica para `idempotency-replay`: distinguir replay de evidencia durable frente a una nueva observación, verificar hashes antes de reutilizar artifacts y recapturar sólo particiones faltantes/incorrectas cuando la semántica temporal lo permite. La homologación añadió el mismo principio a una capa derivada: comparar fingerprints deterministas antes de escribir y convertir una recalculación sin cambios en un no-op verificable, sin contaminar el histórico comercial.
