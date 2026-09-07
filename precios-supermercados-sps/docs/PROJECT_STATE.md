# Estado actual — Precios de Supermercados SPS

GitHub `main`, Pull Requests, Actions, artifacts y Turso son la fuente de verdad técnica. Este archivo resume el estado **vigente** del proyecto. El snapshot histórico anterior al cierre de Los Andes y Paiz se conserva en [`PROJECT_STATE_HISTORY_2026-09-02.md`](PROJECT_STATE_HISTORY_2026-09-02.md).

## Estado vigente — 2026-09-07

El proyecto mantiene seis cadenas productivas y once ubicaciones demostradas:

| Cadena | Ubicaciones productivas demostradas |
| --- | --- |
| La Colonia | SPS, Tegucigalpa |
| Colonial | SPS |
| Walmart | SPS, TGU FFAA, TGU El Sauce |
| PriceSmart | SPS 6603, Florencia 6602 |
| Comisariato Los Andes | SPS |
| Paiz | TGU Multiplaza, TGU Próceres |

La última lectura productiva independiente previa a la corrida #13 confirmó esquema listo e integridad correcta en Turso, con **6 supermercados, 11 ubicaciones, 56,815 productos, 114,017 periodos de `price_history` y 437 `scrape_runs`**. `PRAGMA integrity_check` devolvió `ok`.

No se inventan ubicaciones cuando la fuente no las demuestra. Paiz no tiene un contexto selector SPS aceptado; sus dos contextos demostrados siguen siendo Multiplaza y Próceres en Tegucigalpa. PriceSmart El Sauce 6604 permanece excluido. Maxi Despensa y Despensa Familiar continúan en **NO-GO TEMPORAL PARA PRICE TRACKING WEB**.

## Operación recurrente vigente

El workflow `.github/workflows/precios-supermercados-sps-la-colonia-mvp-update.yml` corre a `17 11 * * *`, equivalente a **05:17 America/Tegucigalpa**, y actualmente incluye las seis cadenas productivas:

1. La Colonia SPS.
2. La Colonia TGU.
3. Comisariato Los Andes SPS.
4. Paiz Multiplaza TGU y Próceres TGU.
5. Colonial SPS.
6. Walmart SPS, TGU FFAA y TGU El Sauce.
7. PriceSmart SPS 6603 y TGU Florencia 6602.

El workflow es **fail-closed**: todas las descargas pueden terminar y publicar evidencia, pero ninguna persistencia ocurre si una sola fuente no supera sus validaciones de completitud, identidad y cobertura.

## Última corrida productiva completa intentada — run #13

Workflow: `La Colonia - Actualización MVP`  
Run ID: `34148356089`  
Job ID: `101825767064`  
Evento: `workflow_dispatch`  
Commit ejecutado: `177853625b4383a63c98ade74e47b02e9960427c`  
Resultado final: **failure controlado en la compuerta de aceptación**.

Todos los colectores llegaron a ejecutarse. Resultado por fuente:

| Fuente | Resultado live |
| --- | --- |
| La Colonia SPS | **FAIL** — `unique_product_coverage_mismatch` |
| La Colonia TGU | **FAIL** — `unique_product_coverage_mismatch` |
| Comisariato Los Andes SPS | **PASS** — 6,688 productos únicos, cobertura completa |
| Paiz | **FAIL** — `product_membership_overlap:walmarthnsp4010/category-1/abarrotes/page-017` |
| Colonial SPS | **PASS** — 9,232 productos fuente, cobertura completa |
| Walmart SPS | **PASS** — 14,163 productos fuente |
| Walmart TGU FFAA | **PASS** — 14,773 productos fuente |
| Walmart TGU El Sauce | **PASS** — 14,643 productos fuente |
| PriceSmart SPS 6603 | **PASS** — 2,776 productos reportados por catálogo |
| PriceSmart TGU Florencia 6602 | **PASS** — 2,776 productos reportados por catálogo |

La compuerta `Aceptar sólo snapshots completos` falló porque los códigos de salida fueron:

```text
SPS_EXIT=3
TGU_EXIT=3
LOS_ANDES_EXIT=0
PAIZ_EXIT=1
COLONIAL_EXIT=0
WALMART_EXIT=0
PRICESMART_EXIT=0
```

Como consecuencia correcta del diseño fail-closed, quedaron **skipped** todas las etapas de persistencia y postflight:

- persistencia de La Colonia, Los Andes, Colonial, Walmart y PriceSmart;
- migración/persistencia de Paiz;
- verificación exacta de commits en Turso;
- verificación de retailers, duplicados, FKs e integridad posterior.

Por lo tanto, la corrida #13 **no escribió un snapshot parcial en Turso**. La evidencia se conservó en el artifact `supermercados-mvp-34148356089`, artifact ID `10029869985`.

## Bloqueo técnico actual

La prioridad inmediata es cerrar dos problemas live sin relajar contratos de seguridad:

### 1. La Colonia SPS/TGU

Los recorridos terminaron con `unique_product_coverage_mismatch`. La corrección debe distinguir cambios reales del catálogo durante el crawl frente a páginas faltantes/repetidas, recuperar únicamente lo necesario cuando exista evidencia suficiente y seguir rechazando cualquier snapshot cuya cobertura única no pueda demostrarse.

No se debe sustituir la validación estricta por tolerancias numéricas arbitrarias ni aceptar `catalog_complete=true` si el conjunto único no concuerda con la evidencia fuente.

### 2. Paiz

El recorrido falló por `product_membership_overlap` en `walmarthnsp4010/category-1/abarrotes/page-017`. La solución debe reconciliar de forma determinista membresía repetida entre páginas/categorías sin perder productos ni aceptar identidad ambigua. Walmart ya demuestra un patrón útil de recuperación estricta que puede reutilizarse como referencia, pero Paiz debe conservar sus propios invariantes y bindings de tienda.

## Criterio para declarar la adquisición nuevamente verde

No se considera cerrado el incidente hasta observar una nueva corrida donde:

1. las seis cadenas terminen con código de salida `0`;
2. todos los snapshots pasen la compuerta de completitud;
3. la persistencia se ejecute únicamente después de esa aceptación global;
4. los commits/run IDs persistidos correspondan exactamente a la corrida fuente;
5. no existan periodos actuales duplicados;
6. no existan violaciones de claves foráneas;
7. `PRAGMA integrity_check` sea `ok`;
8. la homologación derivada posterior complete correctamente;
9. la publicación analítica segura posterior complete correctamente;
10. la sincronización estática de portafolio/Power BI consuma exactamente el artifact de esa publicación segura.

No iniciar una segunda corrida productiva mientras exista otra activa. Si una corrida falla, revisar primero logs y artifact del run exacto antes de modificar código.

## Homologación productiva

La capa `product_homologation_profiles` continúa siendo derivada y separada del histórico comercial. El backfill y el refresh diferencial son fail-closed, comparan `profile_hash` + `normalization_version`, escriben sólo deltas reales y convierten una recalculación sin cambios en un no-op verificable.

El último cierre productivo previamente demostrado cubrió todos los productos existentes en ese checkpoint, sin modificar `products`, `price_history` ni `scrape_runs`, con cero periodos actuales duplicados, cero FKs inválidas e integridad correcta.

Después de una ejecución exitosa de `La Colonia - Actualización MVP` sobre `main`, `.github/workflows/precios-supermercados-sps-homologation-refresh.yml` debe procesar el commit exacto de la corrida fuente antes de permitir la publicación analítica segura.

## Publicación analítica segura y portafolio

La analítica pública sigue una política estricta:

```text
fail_closed_strong_identity_and_commercial_consistency
```

El alcance público comparativo vigente está limitado a **La Colonia SPS + Walmart SPS** y sólo publica equivalencias con identidad fuerte y consistencia comercial. No se fuerzan matches para aumentar el número de comparaciones.

PR #399 incorporó la muestra web estática en la rama dedicada `portfolio-data`.

PR [#401](https://github.com/Jchernand3z19/Portafolio/pull/401), merge commit `21c3471bf8ad4ebfd1c290a3ae5dbe9b15b50ad7`, extendió esa sincronización para que portafolio y Power BI reutilicen **el mismo artifact de analítica segura**, sin nuevas consultas a Turso. El flujo valida schemas, policy, scope, conteos, identidades y ausencia de secretos antes de publicar.

El dataset BI estable se publica en:

```text
https://raw.githubusercontent.com/Jchernand3z19/Portafolio/portfolio-data/precios-supermercados-sps/published/bi/la-colonia-walmart-sps/dataset.json
```

Su schema es:

```text
precios-sps-static-bi-dataset/v1
```

La muestra del portafolio se publica en:

```text
https://raw.githubusercontent.com/Jchernand3z19/Portafolio/portfolio-data/precios-supermercados-sps/portfolio/sample-data.json
```

Las visitas a la página y los refreshes de Power BI consumen archivos estáticos y agregan **0 lecturas adicionales a Turso**.

## Power BI reproducible

PR [#402](https://github.com/Jchernand3z19/Portafolio/pull/402), merge commit `d719c6f577d3a4b638399194a08a82a8d68b41f4`, dejó versionados los activos Power Query/DAX del modelo estático.

Sólo `powerbi/queries/StaticDataset.pq` realiza una llamada Web. Las tablas derivadas `Offers`, `Products`, `CommonBasket`, `Scope`, `SourceDescriptors` y `RefreshMetadata` reutilizan esa carga en memoria y no consultan Turso.

Las relaciones se construyen con IDs estables y `scope_key`, nunca con matching textual de nombre, marca o presentación. Las medidas DAX son fail-closed y devuelven vacío cuando no existe universo comparable suficiente.

PR [#403](https://github.com/Jchernand3z19/Portafolio/pull/403), merge commit `027e9a1eae69a3e918a45de0cb63ae970984abfd`, cerró la especificación semántica reproducible del dashboard: grano de tablas, claves funcionales, relaciones unidireccionales, fuente Web única y prohibición de simular histórico mientras no exista un contrato público histórico probado.

El dashboard actual debe limitarse al snapshot seguro publicado. Páginas de cambios/histórico permanecen fuera del alcance hasta que exista un dataset histórico público, versionado y validado explícitamente.

## CI y seguridad recientes

Los cambios de publicación y modelo BI se integraron mediante PRs separados y suites de CI verdes antes del merge. Entre las verificaciones ya demostradas están:

- PR #401: publicación estática BI sin nuevas lecturas Turso;
- PR #402: activos Power Query/DAX reproducibles y tests de seguridad;
- PR #403: contrato semántico del modelo Power BI.

Se mantienen acciones fijadas por SHA, checkout inmutable donde corresponde, permisos mínimos y ausencia de secretos Turso en los workflows de publicación estática y consumo BI.

## Seguridad y autoridad live

El fingerprint productivo canónico de la región SPS de La Colonia se conserva para contratos offline/fallback:

```text
SPS_REGION_FINGERPRINT = d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
```

Las autorizaciones one-shot se consideran válidas únicamente dentro de su ventana explícita. Un schedule configurado no amplía por sí solo la autoridad live a nuevas cadenas, ubicaciones o fuentes. Cualquier tráfico live fuera del alcance ya autorizado requiere autorización humana explícita vigente.

## Siguiente trabajo obligatorio

Orden recomendado, sin saltos:

1. auditar el código actual de La Colonia y Paiz antes de editar;
2. reproducir offline con la evidencia/artifact de run `34148356089` cuando sea suficiente;
3. implementar una corrección mínima y generalizable para La Colonia `unique_product_coverage_mismatch`;
4. implementar una reconciliación estricta para Paiz `product_membership_overlap`;
5. añadir/ajustar tests que reproduzcan ambos fallos y preserven fail-closed;
6. ejecutar suite completa y auditoría de workflows;
7. fusionar sólo con CI verde;
8. lanzar una nueva corrida productiva de las seis cadenas usando el mecanismo autorizado vigente;
9. verificar persistencia, exactitud de run/commit, duplicados, FKs e integridad;
10. verificar la cadena downstream: homologación → analítica segura → sincronización `portfolio-data`;
11. comprobar `sample-data.json` y `dataset.json` finales con provenance exacta;
12. actualizar este documento y el README únicamente con métricas productivas observadas en esa corrida exitosa.

## Fronteras actuales

- Seis cadenas y once ubicaciones ya tienen contratos productivos demostrados, pero la **última corrida conjunta no está verde**.
- No debe afirmarse que el ciclo diario completo de las seis cadenas quedó validado hasta cerrar La Colonia y Paiz y observar una corrida exitosa end-to-end.
- La homologación es derivada; nunca debe contaminar o reescribir el histórico comercial.
- Un estado `review_required` no equivale a match confirmado.
- Disponibilidad no se convierte en inventario exacto.
- Precio ausente no se inventa como cero, regular ni promoción.
- El portafolio y Power BI consumen publicación estática segura; no deben conectarse directamente a Turso.
- Histórico público para Power BI permanece pendiente de un contrato explícito y probado.

## Metodología reusable

Las reglas reutilizables que siguen vigentes son: evidencia durable antes de replay, hashes antes de reutilización, recaptura sólo de particiones demostrablemente faltantes, validación global antes de persistencia, no-op real cuando no hay deltas y publicación derivada desde un único artifact seguro para evitar lecturas duplicadas y divergencia entre consumidores.
