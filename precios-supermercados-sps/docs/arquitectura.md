# Arquitectura y estado canónico — Precios Supermercados SPS

Este documento es la **fuente canónica única** del estado técnico actual del proyecto. Los documentos bajo `docs/supermercados/`, cuerpos de PR, comentarios, logs y artefactos conservan evidencia e historia, pero no conceden autoridad ni sustituyen este estado.

## Última auditoría clean-room

Fecha: **2026-08-20**.

Base histórica originalmente auditada de `main`:

`1c6aca3318fc1f830f2d43a77cc27c4ba845ab26`

Ese SHA es evidencia histórica estable, no una declaración del HEAD mutable actual. El HEAD de `main` debe verificarse directamente en GitHub; no se fija como “SHA actual” dentro de este documento porque el propio merge que modifica esta fuente cambiaría ese valor.

Desde esa base se integraron las revisiones de canonicalización y CI, frontera current/history, coherencia de evidencia `current`, canonicalización de `changed_fields`, replay terminal, identidad determinista, snapshots defensivos de evidencia y pricing histórico fail-closed.

Evidencia productiva verificada:

- `main` continúa sin branch protection/ruleset efectivo;
- no hay required status checks productivamente exigidos sobre la rama;
- todos los entrypoints live de La Colonia siguen globalmente bloqueados con `if: ${{ false }}`;
- no existe autorización live nueva;
- `SPS-context-and-root-facets-001` está consumida;
- no existe evidencia de creación/autorización de `002`;
- SPS technical context sigue `UNCONFIRMED`;
- `trusted_collector_provenance_unavailable` sigue cerrando la aceptación canónica;
- `live_safety.py` sigue siendo un modelo offline, no enforcement físico productivo;
- no se realizó tráfico live durante la auditoría ni durante los cambios derivados de ella;
- no existe backend comercial productivo conectado.

Validaciones verificadas:

- baseline previo integrado por PR #7: **770/770** pruebas;
- PR #19 — canonicalización, CI y frontera comercial: **796/796** + `compileall`;
- PR #20 — coherencia de evidencia `current` y `changed_fields`: **798/798** + `compileall`;
- PR #22 — replay persistible y `running` transitorio: **801/801** + `compileall`;
- PR #23 — continuidad de identidad de oferta: **810/810** + `compileall`;
- PR #24 — IDs deterministas en frontera comercial: **808/808** + `compileall`;
- PR #25 — snapshots defensivos de evidencia: **812/812** + `compileall`;
- PR #26 — reducción real contra histórico aceptado: **844/844** + `compileall`;
- PR #27 — integridad fail-closed de evidencia para pricing: **850/850** + `compileall`, GitHub Actions, Python 3.12.14.

Las variaciones de conteo entre revisiones corresponden a adición o reemplazo de regresiones, no a relajación de gates.

## Estado operativo resumido

| Área | Estado | Evidencia / consecuencia |
|---|---|---|
| `RawProduct` / `NormalizedOffer` / `ValidatedOffer` | DONE | Contratos existentes preservados sin cambios. |
| Identificadores y `state_hash` | DONE | Deterministas; revalidados también en la frontera comercial y pricing. |
| Extractor / GraphQL VTEX de La Colonia | DONE_OFFLINE | Fixtures/tests; transporte externo niega red por defecto. |
| Identidad VTEX | DONE_OFFLINE | Producto `productId -> productReference -> linkText`; SKU `itemId`. |
| Particiones / facets / cobertura / reconciliación | DONE_OFFLINE_FAIL_CLOSED | Cobertura adversarial; no concede aceptación autoritativa sin provenance. |
| Runner / CLI / métricas / diagnósticos | DONE_OFFLINE | No habilitan actualización comercial por sí solos. |
| SPS technical context | BLOCKED_LIVE | `UNCONFIRMED`; requiere observación live autorizada. |
| Autorización live | BLOCKED_HUMAN_DECISION | Ninguna activa. |
| Workflows live | DONE_FAIL_CLOSED | Jobs capaces de live permanecen `if: false`. |
| Workflow supply chain | DONE_OFFLINE | Actions por SHA, permisos mínimos, checkout inmutable. |
| CI | DONE_VERSIONED | PR, manual y pushes a `main`; auditoría estática protege esta cobertura. |
| Frontera current/history | DONE_OFFLINE | Atómica/idempotente, IDs deterministas, evidencia defensiva y replay terminal ligado. |
| Pricing histórico | DONE_OFFLINE | Reducción real contra periodo aceptado anterior; reconciliación fail-closed. |
| Backend comercial productivo | BLOCKED_DEPENDENCIES | No se conecta mientras aceptación/enforcement productivos sigan abiertos. |
| GATE-17 | BLOCKED_EXTERNAL | `FAIL_PRODUCTIVE_EVIDENCE`: `main` sin protección/ruleset. |
| Trusted collector físico | BLOCKED_EXTERNAL | No existe observer productivo independiente ligado a requests físicos. |
| Egress/claim/fencing productivo | BLOCKED_EXTERNAL | El modelo offline no reemplaza enforcement real. |
| Automatización diaria | BLOCKED_DEPENDENCIES | Espera readiness live + aceptación + backend comercial. |
| Power BI | BLOCKED_DEPENDENCIES | Espera estado comercial confiable. |
| Segundo supermercado | BLOCKED_DEPENDENCIES | No debe heredar estos bloqueos comunes. |

## Flujo funcional

```text
EXTRACCIÓN CONFIABLE
-> VALIDACIÓN DE COMPLETITUD
-> NORMALIZACIÓN
-> ACEPTACIÓN / RECHAZO DE LA EJECUCIÓN
-> ESTADO ACTUAL
-> HISTÓRICO
-> DETECCIÓN DE CAMBIOS
-> DERIVACIONES DE PRECIO
-> AUTOMATIZACIÓN
-> ANALÍTICA
-> MÁS SUPERMERCADOS
```

La frontera crítica es **ejecución técnica vs. ejecución comercialmente aceptada**. Una ejecución incompleta, fallida o no autoritativa puede producir diagnóstico, pero nunca debe modificar precios actuales ni histórico.

## Contratos y regla comercial

`RawProduct`, `NormalizedOffer` y `ValidatedOffer` permanecen protegidos.

Una oferta `in_stock` exige `current_price > 0`; `out_of_stock`, `not_listed` y `unknown` pueden conservar precio nulo. La normalización puede dejar campos nulos si la fuente no los demuestra.

Regla histórica vigente:

- `reported_regular_price` es un dato informado por el supermercado;
- no demuestra ahorro real;
- la reducción real se compara contra el `current_price` del periodo histórico aceptado inmediatamente anterior;
- `reported_regular_price` e `is_promotion` nunca participan en la fórmula de ahorro real;
- si falta precio actual o baseline no se inventa una reducción;
- una igualdad o subida produce reducción cero;
- `rejected`, `failed` y `abandoned` no alteran current/history y por tanto no crean baselines comerciales falsos.

## Frontera comercial offline

`src/precios_supermercados/commercial_state.py` implementa la máquina de transición desacoplada del backend.

Propiedades verificadas:

- sólo `success`/`warning` con `catalog_accepted = true` permiten mutación;
- `running`, `rejected`, `failed`, `abandoned` y `catalog_accepted = false` son no-op comercial;
- `running` es transitorio y no consume el fingerprint terminal de `scrape_run_id`;
- decisiones terminales no comerciales sí consumen la identidad del run y no pueden reescribirse como otra decisión;
- `source_product_id` y `offer_id` se recalculan con los generadores canónicos antes de aplicar;
- una identidad lógica de oferta no puede pertenecer a dos `offer_id` ni migrar de ubicación/producto fuente;
- un producto fuente mantiene una llave fuente estable incluso entre ubicaciones;
- la moneda permanece estable para una oferta existente; `product_id` puede cambiar por corrección legítima de mapeo normalizado;
- el `state_hash` se recalcula antes de aplicar;
- la cronología exige `observed_at_utc <= validated_at_utc <= decided_at_utc`;
- el payload no admite `offer_id` duplicado ni ofertas de otro `scrape_run_id`;
- el replay exacto es idempotente;
- el fingerprint terminal liga decisión, identidad, `state_hash`, timestamps, `source_url`, versiones, trazabilidad explícita, ubicación, review/pending y `quality_events`;
- `raw_values` no forma parte del fingerprint terminal porque es un contenedor crudo arbitrario y no la identidad persistible definida por esta frontera;
- `raw_values` sí se copia recursivamente al almacenar y al devolver current/history para impedir mutaciones por referencia;
- evidencia no copiable falla cerrado antes del commit;
- reutilizar un `scrape_run_id` terminal con otra decisión o evidencia persistible/auditable falla cerrado;
- el mismo hash confirma el periodo abierto sin crear otro;
- cuando el hash no cambia, `current.validated_offer` se refresca a la última evidencia aceptada;
- el periodo histórico abierto conserva la evidencia que lo abrió y sólo avanza `last_confirmed_by_scrape_run_id`/`last_observed_at_utc`;
- `changed_fields` usa la misma canonicalización textual que `generate_state_hash`;
- un cambio exige tiempo monotónico, cierra un periodo y abre exactamente uno;
- `reported_regular_price` puede abrir `REGULAR_PRICE` sin confundirse con cambio de `current_price`;
- la aplicación es atómica: un error posterior no deja mutaciones parciales;
- una oferta ausente de un payload posterior **no** se infiere como `not_listed`, `out_of_stock` ni eliminación.

Esta capa **no concede autoridad live**. Su `catalog_accepted` deberá provenir, en producción, del collector autoritativo. Mientras esa provenance no exista, no debe conectarse a un backend comercial productivo.

## Derivación de reducción real

`src/precios_supermercados/commercial_pricing.py` es una capa pura y backend-neutral sobre `CurrentCommercialOffer` y `OfferHistoryPeriod`.

Antes de calcular revalida fail-closed:

- `source_product_id` y `offer_id` deterministas;
- `state_hash` contra el contenido de la oferta;
- `validated_at_utc >= observed_at_utc`;
- mismo `offer_id` y moneda a lo largo de la cadena;
- evidencia de apertura coherente con `valid_from_utc` y `opened_by_scrape_run_id`;
- un único periodo abierto al final;
- periodos cerrados con intervalo positivo y `closed_by_scrape_run_id` presente;
- periodo abierto sin run de cierre;
- periodos contiguos;
- `closed_by_scrape_run_id` del periodo anterior igual al `opened_by_scrape_run_id` del siguiente;
- reconciliación entre current y periodo abierto para hash, apertura, última observación y último run confirmado.

Una incoherencia produce `CommercialPricingError`; no se devuelve una cifra potencialmente falsa.

## La Colonia — identidad y completitud

Las observaciones siguen con `LocationStatus.UNKNOWN`; la certeza de ciudad técnica vive por separado.

Identidad VTEX:

```text
Producto: productId -> productReference -> linkText
SKU:      itemId
```

El recorrido offline valida árbol, hojas, membership, totals, ventanas, gaps, truncamiento, repeated windows, recovery, segunda travesía, unión de producto/SKU, mapping producto-SKU y conflictos de owner.

**Deduplicar nunca demuestra completitud.**

### Trusted collector

`la_colonia_catalog_coverage.py` construye evidencia desde respuestas crudas y evita falsificaciones triviales dentro del proceso, pero el evaluador canónico añade deliberadamente:

`trusted_collector_provenance_unavailable`

El issuer local no demuestra que dos traversals procedan de solicitudes físicas distintas observadas por un enforcer independiente. Por eso la aceptación final continúa fail-closed y GATE-18 no puede cerrarse con datos caller-controlled, labels, digests u orden declarados por el caller.

## SPS y autorización live

La evidencia histórica de `SPS-context-and-root-facets-001` concluyó sin establecer contexto SPS técnico. El total previo observado sin tienda seleccionada no es un total SPS. La autorización `001` está consumida.

Estado:

```text
ACTIVE_AUTHORIZATION_IDS = []
READY_FOR_LIVE = NO
SPS_TECHNICAL_CONTEXT = UNCONFIRMED
```

Sin autorización humana explícita nueva están prohibidos HTTP/VTEX/GraphQL/Playwright/crawler/diagnostics/facet discovery/smoke/full crawl y cualquier otro tráfico hacia La Colonia.

Comentarios, PR comments, issue comments, archivos de comando, markers, logs y artefactos son observabilidad; no crean autoridad.

## Frontera física

`live_safety.py` es un modelo linealizable en memoria y no infraestructura productiva. Modela Request/Grant/Reservation, consumo one-shot, exclusión, deadlines, pacing, cierre/fencing y evidencia sellada para tests adversariales.

El presupuesto canónico offline actual usa `max_retries = 0`. El pacing mínimo sigue 1.5 s.

El modelo DNS/TLS niega comportamientos auxiliares conocidos, pero no constituye firewall/egress real. `IndependentFencingObserver` es un simulador offline; no cierra GATE-17 ni GATE-06 productivo.

## Workflows y CI

Workflows auditados:

- `precios-supermercados-sps-tests.yml`;
- `precios-supermercados-sps-la-colonia-command.yml`;
- `precios-supermercados-sps-la-colonia-dispatch-recovery.yml`;
- `precios-supermercados-sps-la-colonia-diagnostic.yml`;
- `precios-supermercados-sps-la-colonia-facet-discovery.yml`;
- `precios-supermercados-sps-la-colonia-live.yml`.

Controles:

- Actions externas por SHA completo conocido;
- `persist-credentials: false`;
- permisos explícitos/mínimos;
- `pull_request_target` no hace checkout de código no confiable;
- `issue_comment` no es autoridad;
- scripts capaces de red sólo viven en jobs globalmente bloqueados;
- CI usa Python 3.12, compila `src`/`scripts` y ejecuta toda la suite.

La CI cubre PR/manual y pushes a `main` para `precios-supermercados-sps/**` y `.github/workflows/**`; `test_workflow_security_audit.py` exige esa cobertura. Esto no sustituye GATE-17: un push directo todavía puede entrar porque la rama no está protegida, aunque después ejecute CI.

## Persistencia e histórico

El modelo lógico sigue definiendo:

- `cfg_supermarkets`;
- `cfg_locations`;
- `dim_products`;
- `map_source_products`;
- `fact_scrape_runs`;
- `fact_offers_current`;
- `fact_offer_history`;
- `fact_quality_events`.

La lógica current/history y pricing ya existe offline; **el backend productivo no está seleccionado ni conectado**. No se introduce Sheets, BigQuery, SQLite o PostgreSQL sólo para avanzar artificialmente.

Conectar almacenamiento real queda bloqueado hasta que `catalog_accepted` pueda provenir de una frontera autoritativa y GATE-17/productive enforcement estén resueltos. Esto evita construir una ruta donde un booleano caller-controlled pueda actualizar precios comerciales.

## Matriz de gates

| Gate | Estado actual |
|---|---|
| GATE-01 — DEFAULT DENY | PASS_OFFLINE_MODEL; live cerrado |
| GATE-02 — UNIQUE LIVE ENTRY / BLOCK ALTERNATIVES | PASS_OFFLINE_MODEL; productivo depende de enforcement |
| GATE-03 — AUTHORIZATION SEPARATE FROM CONTRACT VALIDITY | PASS_OFFLINE_MODEL |
| GATE-04 — IMMUTABLE SHA / REQUEST IDENTITY | PASS_OFFLINE_MODEL |
| GATE-05 — ONE-SHOT ATOMIC CONSUMPTION / REPLAY | PASS_OFFLINE_MODEL |
| GATE-06 — PHYSICAL EGRESS GUARD | FAIL productivo / PASS_OFFLINE_MODEL |
| GATE-07 — GLOBAL LIVE EXCLUSION | PASS_OFFLINE_MODEL + workflows bloqueados |
| GATE-08 — PHYSICAL DELAY >= 1.5s | PASS_OFFLINE_MODEL |
| GATE-09 — PHYSICAL RETRIES <= 1 | PASS_OFFLINE_MODEL; runtime usa 0 |
| GATE-10 — CLOSED FAIL-CLOSED BUDGET | PASS_OFFLINE_MODEL |
| GATE-11 — STOP ON 403 | PASS_OFFLINE_MODEL |
| GATE-12 — STOP ON 429 | PASS_OFFLINE_MODEL |
| GATE-13 — STOP ON CAPTCHA / ANTIBOT | PASS_OFFLINE_MODEL |
| GATE-14 — STOP ON AUTH / ADDRESS / GPS REQUIREMENT | PASS_OFFLINE_MODEL |
| GATE-15 — EXCESSIVE LOAD STOP | PASS_OFFLINE_MODEL |
| GATE-16 — TRUSTED WORKFLOW / CODE / SUPPLY CHAIN | PASS_OFFLINE_MODEL; readiness productivo bloqueado por GATE-17 |
| GATE-17 — PRODUCTIVE RULESET / PROTECTION EVIDENCE | **FAIL_PRODUCTIVE_EVIDENCE** |
| GATE-18 — EXACT FINAL VALIDATION | **FAIL_CLOSED**; trusted collector pendiente |
| GATE-19 — ADVERSARIAL OFFLINE COVERAGE | PASS_OFFLINE_MODEL |
| GATE-20 — COMMENTS NON-AUTHORITATIVE | PASS_OFFLINE_MODEL |

Ningún `PASS_OFFLINE_MODEL` autoriza live.

## Inventario canónico y backlog

### DONE / DONE_OFFLINE

- contratos comunes e identidad;
- extractor/GraphQL/runner La Colonia;
- facets/partitions/coverage/reconciliation adversarial;
- diagnósticos SPS offline;
- live safety state machine offline;
- observabilidad/dispatcher sin autoridad;
- supply-chain/workflow audit;
- CI en PR + `main`;
- frontera comercial current/history atómica e idempotente;
- continuidad y determinismo de identidad de oferta/producto fuente;
- snapshots defensivos de evidencia mutable;
- `current` coherente con la última evidencia aceptada del mismo estado;
- `changed_fields` alineado con la canonicalización del `state_hash`;
- fingerprint terminal ligado a evidencia persistible/auditable;
- transición `running -> terminal` sin consumir anticipadamente `scrape_run_id`;
- derivación de reducción real contra histórico aceptado;
- reconciliación fail-closed de current/history antes de pricing;
- pruebas adversariales de replay, cronología, identidad, cambios, snapshots, pricing, ausencia sin inferencia y auditoría de workflows;
- canonicalización de README/AGENTS/arquitectura/decisiones.

### STALE / OBSOLETE

- cuerpos históricos de PR como descripción del estado actual;
- ramas ya integradas y detrás de `main` como posible fuente canónica;
- gobernanza que exigía mantener PR #7/#17 abiertos;
- publicar un SHA mutable de `main` dentro de documentación como si pudiera mantenerse autorreferencialmente actualizado.

### READY_TO_IMPLEMENT

`0` tareas técnicas independientes de las fronteras siguientes, sujeto a nuevos bugs concretos que una revisión adversarial reproduzca.

### BLOCKED_EXTERNAL / BLOCKED_LIVE / BLOCKED_HUMAN_DECISION

- configurar protección/ruleset productivo de `main` y required CI (GATE-17);
- disponer de trusted collector con provenance física independiente;
- disponer de enforcement productivo de egress/claim/fencing;
- obtener autorización humana nueva para cualquier prueba live;
- confirmar SPS técnicamente mediante prueba live autorizada;
- sólo después conectar backend productivo, scheduling diario y analítica comercial.

## Criterio de avance

Orden canónico:

`CORRECTNESS -> AUTHORITATIVE ACCEPTANCE -> PERSISTENCE -> AUTOMATION -> ANALYTICS`.

No se usa un bloqueo live como excusa para omitir trabajo offline necesario, pero tampoco se construye infraestructura productiva alrededor de una aceptación que aún puede ser controlada por el caller.
