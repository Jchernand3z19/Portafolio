# Estado actual — Precios de Supermercados SPS

GitHub `main`, Pull Requests, Actions, artifacts y Turso son la fuente de verdad técnica. Este archivo resume el estado **vigente** del proyecto. El snapshot histórico anterior al cierre de Los Andes y Paiz se conserva en [`PROJECT_STATE_HISTORY_2026-09-02.md`](PROJECT_STATE_HISTORY_2026-09-02.md).

## Estado vigente — 2026-09-08

El proyecto mantiene seis cadenas productivas y once ubicaciones demostradas:

| Cadena | Ubicaciones productivas demostradas |
| --- | --- |
| La Colonia | SPS, Tegucigalpa |
| Colonial | SPS |
| Walmart | SPS, TGU FFAA, TGU El Sauce |
| PriceSmart | SPS 6603, Florencia 6602 |
| Comisariato Los Andes | SPS |
| Paiz | TGU Multiplaza, TGU Próceres |

El ciclo productivo completo más reciente dejó **6 supermercados, 11 ubicaciones, 58,114 productos, 127,980 periodos de `price_history` y 463 `scrape_runs`**. La verificación posterior confirmó cero periodos actuales duplicados, cero violaciones de claves foráneas y `PRAGMA integrity_check = ok`.

La evolución de producto vigente está definida en
[`RPI-PRODUCT-SPEC.md`](RPI-PRODUCT-SPEC.md): una sola adquisición y estado
comercial confiable alimentan Retail Price Intelligence B2B (Power BI) y Compra
Inteligente B2C (web responsive). La primera frontera compartida ya está
versionada en `analytics_quality.py`: mantiene completeness separado de health,
clasifica `ACCEPTED/DEGRADED/REJECTED`, selecciona last-known-good y bloquea
comparaciones con fuentes stale, unavailable o temporalmente incompatibles. Su
integración a los marts/publicación sigue siendo incremental. La capa Python
`competitive_analytics.py` ya calcula PCI configurable (mean, median o mínimo),
rank, spread y cobertura sólo cuando la ventana de mercado es comparable. El
dataset público vigente aún conserva el contrato v1 descrito abajo y por eso no
expone todavía esas nuevas métricas.

El módulo histórico conserva observaciones reales sin interpolación y ya deriva
mediana, duración observada, frecuencia de cambios, volatilidad y días desde el
último cambio. Las ventanas 7/30/60/90/365 días exigen una observación baseline
anterior al inicio solicitado; cuando no existe, devuelven
`insufficient_history` en vez de acortar silenciosamente el periodo.

`promotion_analytics.py` mantiene separadas la promoción declarada por la fuente
y la reducción contra el precio efectivo observado anteriormente. Calcula
profundidad declarada, duración, frecuencia, share, comparación contra promedios
30/90 días y mínimo 90 días, y devuelve estados auditables; nunca eleva
`reported_regular_price` a evidencia histórica.

`shopping_analytics.py` fija el contrato monetario B2C antes de la UI:
`unit_price=current_price`, cantidades enteras positivas, líneas y subtotales en
minor units, selección manual inmutable y optimización separada. Una canasta con
un ítem no disponible queda `INCOMPLETE` y su total es `null`; no imputa cero,
no usa el precio regular y no admite impuestos o cargos de checkout dentro de
la oferta.

`rpi_data_marts.py` proyecta la misma salida segura a contratos separados
`rpi-business-mart/v1` y `rpi-consumer-mart/v1`. Ambos comparten scope, freshness
y cobertura; el mart privado conserva hechos competitivos y el público sólo los
descriptores/ofertas necesarios. Si la ventana está bloqueada, el último precio
válido sigue visible con su staleness, mientras `rank`, PCI y métricas de mercado
quedan nulos.

El exportador offline/read-only `scripts/exportar_rpi_marts.py` materializa ambos
contratos en JSON y el Business Mart en CSV, escribe de forma atómica y registra
SHA-256 por archivo. Consulta el último `scrape_runs.run_status='success'` por
scope y excluye runs rechazados de last-known-good. La publicación automática de
estos nuevos artifacts aún no sustituye la publicación v1 vigente.

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

## Última corrida productiva completa — PASS

Workflow: [`La Colonia - Actualización MVP`](https://github.com/Jchernand3z19/Portafolio/actions/runs/34242670410)

Run ID: `34242670410`

Evento: `workflow_dispatch`

Commit ejecutado: `22a9bd6df01f98442ba50bfe8e539f0f331bb43c`

Resultado final: **success**.

Las seis cadenas terminaron con código de salida `0` y la compuerta global aceptó los once snapshots antes de cualquier escritura:

| Ubicación | Productos fuente | SKU procesados | SKU con precio |
| --- | ---: | ---: | ---: |
| La Colonia SPS | 9,473 | 9,475 | 9,475 |
| La Colonia TGU | 9,504 | 9,506 | 9,506 |
| Comisariato Los Andes SPS | 6,688 | 6,688 | 6,688 |
| Colonial SPS | 9,232 | 9,238 | 9,238 |
| Walmart SPS | 14,114 | 14,119 | 13,733 |
| Walmart TGU FFAA | 14,655 | 14,660 | 14,119 |
| Walmart TGU El Sauce | 14,511 | 14,516 | 13,965 |
| PriceSmart SPS 6603 | 2,785 | 6,103 | 5,430 |
| PriceSmart TGU Florencia 6602 | 2,785 | 6,103 | 5,273 |
| Paiz TGU Multiplaza | 8,856 | 8,860 | 8,605 |
| Paiz TGU Próceres | 8,595 | 8,599 | 8,356 |

El preflight Turso clasificó los once `run_id` como `new`. Cada transacción persistió el snapshot completo y el postflight encontró los once runs con estado `success`, SHA fuente exacto y alcance correcto. El estado actual quedó en:

| Ubicación | Periodos actuales abiertos |
| --- | ---: |
| La Colonia SPS | 9,521 |
| La Colonia TGU | 9,550 |
| Comisariato Los Andes SPS | 6,724 |
| Colonial SPS | 9,239 |
| Walmart SPS | 14,772 |
| Walmart TGU FFAA | 15,267 |
| Walmart TGU El Sauce | 15,137 |
| PriceSmart SPS 6603 | 6,261 |
| PriceSmart TGU Florencia 6602 | 6,261 |
| Paiz TGU Multiplaza | 9,007 |
| Paiz TGU Próceres | 8,782 |

Los Andes conserva observaciones previas con disponibilidad `unknown`; por eso su estado actual puede ser un superset del snapshot sin interpretar ausencias como `out_of_stock`. El postflight exige alcance exacto, run/SHA exactos, cero duplicados y un conteo abierto no menor que el snapshot.

La evidencia durable está en el artifact `supermercados-mvp-34242670410`, ID `10065247638`, tamaño `74,492,002` bytes y digest `sha256:6d3b1ea69c13bbf6e6f66cc9ef71a144be473d00bb7b4d8774a5afba07c33894`. Expira el `2026-09-22T16:07:37Z`.

Una ejecución programada que GitHub había dejado en espera comenzó al liberarse la concurrencia. Se canceló como duplicada en el run `34242996370` durante la primera captura SPS; la compuerta, Turso y todos los pasos de persistencia quedaron `skipped`.

## Homologación productiva

La capa `product_homologation_profiles` continúa siendo derivada y separada del histórico comercial. El backfill y el refresh diferencial son fail-closed, comparan `profile_hash` + `normalization_version`, escriben sólo deltas reales y convierten una recalculación sin cambios en un no-op verificable.

El run [`34249578797`](https://github.com/Jchernand3z19/Portafolio/actions/runs/34249578797) procesó los 58,114 productos posteriores al ciclo: insertó 1,335 perfiles, actualizó 1,011 y dejó 55,768 sin cambio. No modificó `products`, `price_history` ni `scrape_runs`; confirmó cero periodos actuales duplicados, cero FKs inválidas e integridad correcta.

Después del ajuste operativo de publicación, el run [`34250440140`](https://github.com/Jchernand3z19/Portafolio/actions/runs/34250440140) repitió el refresh sobre el SHA final `7ae45f1dc39032180c82df10a1bb77e58451995a` y demostró un no-op real: 58,114 perfiles sin cambio, cero inserts, cero updates y sin staging escrito.

Después de una ejecución exitosa de `La Colonia - Actualización MVP` sobre `main`, `.github/workflows/precios-supermercados-sps-homologation-refresh.yml` debe procesar el commit exacto de la corrida fuente antes de permitir la publicación analítica segura.

## Publicación analítica segura y portafolio

La analítica pública sigue una política estricta:

```text
fail_closed_strong_identity_and_commercial_consistency
```

El alcance público comparativo vigente está limitado a **La Colonia SPS + Walmart SPS** y sólo publica equivalencias con identidad fuerte y consistencia comercial. No se fuerzan matches para aumentar el número de comparaciones.

PR #399 incorporó la muestra web estática en la rama dedicada `portfolio-data`.

PR [#401](https://github.com/Jchernand3z19/Portafolio/pull/401), merge commit `21c3471bf8ad4ebfd1c290a3ae5dbe9b15b50ad7`, extendió esa sincronización para que portafolio y Power BI reutilicen **el mismo artifact de analítica segura**, sin nuevas consultas a Turso. El flujo valida schemas, policy, scope, conteos, identidades y ausencia de secretos antes de publicar.

La publicación final [`34250535657`](https://github.com/Jchernand3z19/Portafolio/actions/runs/34250535657) produjo 92 productos comparables, 184 ofertas, una canasta común de 92 productos y una muestra pública de 10 filas. Conservó la política `fail_closed_strong_identity_and_commercial_consistency` y el alcance exacto La Colonia SPS + Walmart SPS. Su artifact `10065801433` tiene digest `sha256:b894e7bd28cb0291549ed51f6d54e5a3eb11926ad306e0687629e45cbb12b6ff`.

La sincronización [`34250590641`](https://github.com/Jchernand3z19/Portafolio/actions/runs/34250590641) terminó `success` y publicó ambos consumidores desde ese mismo artifact. `sample-data.json` y `dataset.json` declaran `source_workflow_run_id=34250535657` y `source_head_sha=7ae45f1dc39032180c82df10a1bb77e58451995a`; sus SHA-256 descargados son, respectivamente, `2fd11c6c94c6e08b75367ac54ecb70ab049b1eb5ee787ad83a07d70a7a5dffc0` y `d076531f2769192d57b4e99b1c3d6b291d0ae2b9626adf80f94b8e259e261f99`.

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
- PR #418: postflight estricto compatible con el superset observado de Los Andes.
- PR #419: solicitud productiva one-shot dentro de la ventana autorizada; suite completa verde.
- PR #420: creación explícita del directorio de salida de analítica antes de `tee`; 35 pruebas locales de seguridad/guard y suite completa verde.

Se mantienen acciones fijadas por SHA, checkout inmutable donde corresponde, permisos mínimos y ausencia de secretos Turso en los workflows de publicación estática y consumo BI.

## Seguridad y autoridad live

El fingerprint productivo canónico de la región SPS de La Colonia se conserva para contratos offline/fallback:

```text
SPS_REGION_FINGERPRINT = d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
ACTIVE_AUTHORIZATION_IDS = []
```

`ACTIVE_AUTHORIZATION_IDS` registra únicamente autorizaciones puntuales one-shot; no representa ni revoca la operación recurrente expresamente autorizada. Las autorizaciones temporales one-shot conservadas en la evidencia histórica siguen siendo hechos auditables, pero **no se interpreta como autorización abierta** ninguna autorización temporal ya consumida o vencida.

Las autorizaciones one-shot se consideran válidas únicamente dentro de su ventana explícita. Un schedule configurado no amplía por sí solo la autoridad live a nuevas cadenas, ubicaciones o fuentes. Cualquier tráfico live fuera del alcance ya autorizado requiere autorización humana explícita vigente.

## Siguiente trabajo obligatorio

El incidente de adquisición y la cadena downstream están cerrados. El siguiente ciclo programado debe conservar las mismas invariantes: una sola corrida activa, adquisición global antes de persistir, once preflights `new`, postflight exacto, homologación idempotente y publicación estática desde un único artifact seguro.

No hay un blocker técnico activo que justifique otro crawl manual. Ante una falla futura, revisar primero el log y artifact del run exacto y reproducir offline antes de modificar el colector.

## Fronteras actuales

- Seis cadenas y once ubicaciones tienen contratos productivos demostrados y la última corrida conjunta está verde.
- El ciclo end-to-end quedó validado hasta `portfolio-data`; el alcance comparativo público sigue limitado a La Colonia SPS + Walmart SPS.
- La homologación es derivada; nunca debe contaminar o reescribir el histórico comercial.
- Un estado `review_required` no equivale a match confirmado.
- Disponibilidad no se convierte en inventario exacto.
- Precio ausente no se inventa como cero, regular ni promoción.
- El portafolio y Power BI consumen publicación estática segura; no deben conectarse directamente a Turso.
- Histórico público para Power BI permanece pendiente de un contrato explícito y probado.

## Metodología reusable

Las reglas reutilizables que siguen vigentes son: evidencia durable antes de replay, hashes antes de reutilización, recaptura sólo de particiones demostrablemente faltantes, validación global antes de persistencia, no-op real cuando no hay deltas y publicación derivada desde un único artifact seguro para evitar lecturas duplicadas y divergencia entre consumidores.
