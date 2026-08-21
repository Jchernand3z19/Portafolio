# Arquitectura y estado canónico — Precios Supermercados SPS

Este documento es la **fuente canónica única** del estado técnico actual del proyecto. Los documentos bajo `docs/supermercados/`, cuerpos de PR, comentarios, logs y artefactos conservan evidencia e historia, pero no conceden autoridad ni sustituyen este estado.

## Última auditoría clean-room

Fecha: **2026-08-20**.

Base de `main` auditada:

`1c6aca3318fc1f830f2d43a77cc27c4ba845ab26`

Ese commit integra **PR #7 — La Colonia full crawl validation (fail-closed)**. **PR #17 — observabilidad del facet discovery** ya estaba integrado. Los textos históricos que todavía describen esos PR como abiertos, draft o pendientes son obsoletos como estado operativo.

Evidencia productiva verificada:

- `main` estaba sin branch protection/ruleset efectivo;
- no había required status checks sobre la rama;
- todos los entrypoints live de La Colonia seguían globalmente bloqueados con `if: ${{ false }}`;
- no existía autorización live nueva;
- `SPS-context-and-root-facets-001` estaba consumida;
- no existe evidencia de creación/autorización de `002`;
- SPS technical context seguía `UNCONFIRMED`;
- `trusted_collector_provenance_unavailable` seguía cerrando la aceptación canónica;
- `live_safety.py` seguía siendo un modelo offline, no enforcement físico productivo;
- no se realizó tráfico live durante la auditoría ni durante los cambios derivados de ella.

Validaciones verificadas:

- baseline previo integrado por PR #7: **770/770** pruebas;
- revisión de canonicalización, CI y frontera comercial: **796/796** pruebas, más `compileall`, en GitHub Actions con Python 3.12.14.

## Estado operativo resumido

| Área | Estado | Evidencia / consecuencia |
|---|---|---|
| `RawProduct` / `NormalizedOffer` / `ValidatedOffer` | DONE | Contratos existentes preservados sin cambios. |
| Identificadores y `state_hash` | DONE | Deterministas y cubiertos por tests. |
| Extractor / GraphQL VTEX de La Colonia | DONE_OFFLINE | Fixtures/tests; transporte externo niega red por defecto. |
| Identidad VTEX | DONE_OFFLINE | Producto `productId -> productReference -> linkText`; SKU `itemId`. |
| Particiones / facets / cobertura / reconciliación | DONE_OFFLINE_FAIL_CLOSED | Amplia cobertura adversarial; no concede aceptación autoritativa sin provenance. |
| Runner / CLI / métricas / diagnósticos | DONE_OFFLINE | No habilitan actualización comercial por sí solos. |
| SPS technical context | BLOCKED_LIVE | `UNCONFIRMED`; requiere observación live autorizada. |
| Autorización live | BLOCKED_HUMAN_DECISION | Ninguna activa. |
| Workflows live | DONE_FAIL_CLOSED | Jobs capaces de live permanecen `if: false`. |
| Workflow supply chain | DONE_OFFLINE | Actions por SHA, permisos mínimos, checkout inmutable. |
| CI | DONE_VERSIONED | Pull requests, manual y pushes a `main`; auditoría estática impide perder esa cobertura silenciosamente. |
| Frontera current/history | DONE_OFFLINE | `commercial_state.py` aplica runs aceptados de forma atómica/idempotente y conserva histórico. |
| Backend comercial productivo | BLOCKED_DEPENDENCIES | No se conecta mientras la aceptación autoritativa/productive readiness siga abierta. |
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
- la reducción real se compara contra el último `current_price` de una ejecución histórica aceptada;
- `rejected`, `failed` y `abandoned` no alteran current/history.

## Frontera comercial offline

`src/precios_supermercados/commercial_state.py` implementa la mínima máquina de transición desacoplada del backend.

Propiedades verificadas:

- sólo `success`/`warning` con `catalog_accepted = true` permiten mutación;
- `running`, `rejected`, `failed`, `abandoned` y `catalog_accepted = false` son no-op comercial;
- el `state_hash` se recalcula antes de aplicar;
- la cronología exige `observed_at_utc <= validated_at_utc <= decided_at_utc`;
- el payload de un run no admite `offer_id` duplicado ni ofertas de otro `scrape_run_id`;
- el replay exacto es idempotente;
- reutilizar el mismo `scrape_run_id` con otra decisión, timestamp o contenido falla cerrado;
- el mismo hash confirma el periodo abierto sin crear otro;
- un cambio exige tiempo monotónico, cierra un periodo y abre exactamente uno;
- `reported_regular_price` puede abrir `REGULAR_PRICE` sin confundirse con cambio de `current_price`;
- la aplicación es atómica: un error posterior no deja mutaciones parciales;
- una oferta ausente de un payload posterior **no** se infiere como `not_listed`, `out_of_stock` ni eliminación; esos estados requieren evidencia explícita.

Esta capa **no concede autoridad live**. Su `catalog_accepted` deberá provenir, en producción, del collector autoritativo. Mientras esa provenance no exista, no debe conectarse a un backend comercial productivo.

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

El presupuesto canónico offline actual es más estricto que el máximo histórico en retries: `max_retries = 0`. El pacing mínimo sigue 1.5 s.

El modelo DNS/TLS niega comportamientos auxiliares conocidos, pero no constituye firewall/egress real. `IndependentFencingObserver` es explícitamente un simulador offline; no cierra GATE-17 ni GATE-06 productivo.

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

Hallazgo corregido: la CI sólo corría en PR/manual. Dado que `main` no está protegida, un push directo podía evadir la suite. El workflow ahora cubre también pushes a `main` para `precios-supermercados-sps/**` y `.github/workflows/**`, y `test_workflow_security_audit.py` exige esa cobertura.

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

La lógica current/history ya existe offline; **el backend productivo no está seleccionado ni conectado**. No se introduce Sheets, BigQuery, SQLite o PostgreSQL sólo para avanzar artificialmente.

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
- pruebas de replay, mismo hash, cronología, cambio de precio, precio regular reportado, estados no aceptados, atomicidad y ausencia sin inferencia;
- canonicalización de README/AGENTS/arquitectura.

### STALE / OBSOLETE

- cuerpos de PR #7/#17 como descripción del estado actual;
- ramas ya integradas y detrás de `main` como posible fuente canónica;
- gobernanza que exigía mantener PR #7/#17 abiertos;
- README antiguo que omitía gran parte del runtime.

### READY_TO_IMPLEMENT

`0` tareas técnicas independientes de las fronteras siguientes.

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
