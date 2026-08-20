# Arquitectura y estado canónico — Precios Supermercados SPS

Este documento es la **fuente canónica única** del estado técnico actual del proyecto. Los documentos bajo `docs/supermercados/`, cuerpos de PR, comentarios, logs y artefactos conservan evidencia e historia, pero no conceden autoridad ni sustituyen este estado.

## Última auditoría clean-room

Fecha: **2026-08-20**.

Base auditada de `main`:

`1c6aca3318fc1f830f2d43a77cc27c4ba845ab26`

Ese commit es el merge de **PR #7 — La Colonia full crawl validation (fail-closed)**. **PR #17 — observabilidad del facet discovery** ya había sido integrado antes. Los textos históricos que todavía describen esos PR como abiertos, draft o pendientes son obsoletos.

Evidencia productiva verificada durante la auditoría:

- `main` existe y apunta al SHA anterior;
- `main` está actualmente **sin branch protection**;
- no hay required status checks configurados sobre la rama;
- los entrypoints live de La Colonia continúan globalmente bloqueados con `if: ${{ false }}`;
- no hay autorización live nueva;
- no se realizó tráfico live durante esta auditoría.

Última suite histórica verificada antes de esta actualización: **770/770 pruebas aprobadas** en GitHub Actions sobre el head integrado mediante PR #7, con Python 3.12. El workflow de CI debe validar también esta actualización antes de integrarse.

## Estado operativo resumido

| Área | Estado | Evidencia / consecuencia |
|---|---|---|
| Contratos `RawProduct` / `NormalizedOffer` / `ValidatedOffer` | DONE | Implementados y protegidos en `models.py`. |
| Identidad fuente común | DONE | IDs deterministas y reglas conservadoras implementadas. |
| Extractor La Colonia / GraphQL VTEX | DONE_OFFLINE | Implementado y cubierto por fixtures/tests; red real cerrada. |
| Identidad VTEX producto/SKU | DONE_OFFLINE | Producto `productId -> productReference -> linkText`; SKU `itemId`. |
| Particiones / facets / cobertura / reconciliación | DONE_OFFLINE_FAIL_CLOSED | Evaluador adversarial implementado; no concede aceptación autoritativa sin provenance confiable. |
| Runner / CLI / métricas / artefactos sanitizados | DONE_OFFLINE | Implementados; aceptación comercial permanece cerrada. |
| SPS technical context | BLOCKED_LIVE | `UNCONFIRMED`; requiere evidencia live autorizada. |
| Autorizaciones live | BLOCKED_HUMAN_DECISION | Ninguna activa. `001` consumida; `002` no autorizada. |
| Workflows live | DONE_FAIL_CLOSED | Entry points presentes pero jobs cerrados globalmente. |
| Workflow supply chain | DONE_OFFLINE | Actions externas fijadas a SHA completo y permisos mínimos auditados. |
| CI del proyecto | PARTIAL -> HARDENING | Suite completa existe; se corrige cobertura para que también corra en pushes a `main`. |
| GATE-17 | BLOCKED_EXTERNAL | `FAIL_PRODUCTIVE_EVIDENCE`; `main` sin protección/ruleset efectivo. |
| Trusted collector con provenance física | MISSING / BLOCKED_EXTERNAL | El collector local marca evidencia internamente, pero no es un observador productivo independiente. |
| `live_safety.py` | DONE_OFFLINE_MODEL | Modelo linealizable/adversarial; no es enforcement físico productivo. |
| Persistencia / histórico | PARTIAL | Modelo de datos y reglas documentados; backend/engine productivo todavía no conectado. |
| Automatización diaria | BLOCKED_DEPENDENCIES | No debe activarse antes de aceptación/persistencia confiables y readiness live. |
| Power BI / analítica | BLOCKED_DEPENDENCIES | Espera estado comercial confiable. |
| Segundo supermercado | BLOCKED_DEPENDENCIES | No iniciar si heredaría los mismos bloqueos comunes. |

## Flujo funcional objetivo

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

La frontera crítica es entre **ejecución técnica** y **ejecución comercialmente aceptada**. Una ejecución incompleta, fallida o no autoritativa puede producir métricas y evidencia diagnóstica, pero no puede modificar precios actuales ni histórico.

## Contratos y regla comercial

`RawProduct`, `NormalizedOffer` y `ValidatedOffer` permanecen protegidos e intactos.

Una oferta `in_stock` exige `current_price > 0`. Los estados `out_of_stock`, `not_listed` y `unknown` pueden conservar `current_price = null`. Campos de normalización no demostrables pueden permanecer nulos y generar `needs_review`; no se inventan datos.

La regla de histórico permanece:

- `reported_regular_price` es lo informado por el supermercado;
- no prueba ahorro real;
- la reducción real se compara contra el último `current_price` de una ejecución histórica **aceptada**;
- una ejecución `rejected`, `failed` o `abandoned` no altera estado comercial ni crea falsos cambios.

## La Colonia — extracción, identidad y completitud

La ubicación de las observaciones de La Colonia continúa `LocationStatus.UNKNOWN`. El estado técnico SPS vive por separado como `SpsTechnicalContextStatus(CONFIRMED, UNCONFIRMED, UNAVAILABLE)`.

Identidad VTEX:

```text
Producto: productId -> productReference -> linkText
SKU:      itemId
```

Ruta de completitud offline:

```text
facets sintéticos / evidencia estructural
-> árbol
-> hojas deterministas
-> plan cerrado
-> ventanas primarias
-> recovery/overlap cuando corresponde
-> segunda travesía independiente
-> reconciliación de producto, SKU y mapping producto-SKU
-> unión global
-> COMPLETE o INCOMPLETE (fail-closed)
```

`COMPLETE` lógico exige simultáneamente, entre otros controles:

- árbol y hojas estructuralmente válidos;
- ausencia de positive leaves malformadas o faltantes;
- membership válido;
- totales estables;
- ventanas planificadas y continuas;
- respuestas no truncadas;
- ausencia de repeated windows y gaps;
- recuperación completa de omisiones cuando aplica;
- reconciliación por otra traversal y otro orden;
- igualdad de uniones de productos;
- igualdad de uniones de SKU;
- igualdad del mapping producto-SKU;
- ausencia de conflictos de owner de SKU;
- unión global igual al total estructural.

**Deduplicar nunca demuestra completitud.**

### Frontera del trusted collector

El módulo `la_colonia_catalog_coverage.py` deriva totales y productos desde respuestas crudas y emite objetos internos de evidencia. Sin embargo, el evaluador canónico añade deliberadamente:

`trusted_collector_provenance_unavailable`

por lo que `accepted=True` no es alcanzable hoy desde evidencia caller-controlled/offline. El issuer privado del módulo impide falsificaciones triviales dentro del proceso, pero **no demuestra provenance física independiente** ni que dos traversals provengan realmente de solicitudes distintas observadas por un enforcer productivo.

Por tanto:

`GATE-18 = FAIL_CLOSED`

hasta que exista un collector ligado a observaciones físicas independientes y a la identidad runtime/request correspondiente. Cambiar labels, digests, orden o extensiones aportadas por el caller no concede autoridad.

## Autoridad y frontera física — modelo offline

`live_safety.py` es un modelo linealizable en memoria, no infraestructura productiva. Canonical JSON UTF-8 versionado y domain-separated liga `request_id`, SHA aprobado inmutable, plan, presupuesto cerrado y epoch.

Transiciones principales:

```text
Grant: ACTIVE -> CONSUMED | REVOKED
Reservation: RESERVED -> ACTIVATED -> CLOSING -> CLOSED
                         -> UNCERTAIN -> FENCING_REQUIRED -> FENCED
```

El modelo offline cubre consumo one-shot, reserva global, deadlines monotónicos, pacing start-to-start, cierre/fencing CAS, evidencia ligada a reserva/epoch/request/fase y estados de incertidumbre. El pacing mínimo es 1.5 s y la implementación de runner usa 0 retries, más estricta que el máximo histórico permitido de 1.

El contrato DNS/TLS offline es cerrado: peer dentro de resolución controlada, host/SNI/Host exactos, puerto 443 y verificación TLS; niega fallback DNS, Happy Eyeballs, proxies, redirects, pooling/reuse, HTTP/2, HTTP/3, QUIC, retries ocultos y red auxiliar conocida. Esto sigue siendo `PASS_OFFLINE_MODEL`, no evidencia de firewall/egress real.

Adapters reales legacy niegan red por defecto; wrappers de test operan sólo con fixtures/local/loopback. Playwright live también permanece globalmente bloqueado. Ningún harness se presenta como aislamiento físico productivo.

## Autorización live — default deny

Estado vigente:

- `SPS-context-and-root-facets-001`: consumida;
- `SPS-context-and-root-facets-002`: no creada/no autorizada;
- `ACTIVE_AUTHORIZATION_IDS`: vacío;
- `READY_FOR_LIVE = NO`.

Sin autorización humana explícita nueva están prohibidos HTTP/VTEX/GraphQL/Playwright/crawler/diagnostics/facet discovery/smoke/full crawl y cualquier otro tráfico hacia La Colonia.

Comentarios, issue comments, PR comments, archivos de comando, markers, logs y artefactos son **observabilidad solamente**. No crean Request, Approval, Grant, Claim, Capability, Reservation ni autoridad física.

## Workflows y CI

Workflows SPS auditados:

- `precios-supermercados-sps-tests.yml` — CI offline;
- `precios-supermercados-sps-la-colonia-command.yml` — controlador por archivo, bloqueado;
- `precios-supermercados-sps-la-colonia-dispatch-recovery.yml` — recuperación observable, bloqueada;
- `precios-supermercados-sps-la-colonia-diagnostic.yml` — diagnóstico live, bloqueado;
- `precios-supermercados-sps-la-colonia-facet-discovery.yml` — discovery live, bloqueado;
- `precios-supermercados-sps-la-colonia-live.yml` — crawl live, bloqueado.

Controles vigentes:

- Actions externas fijadas a SHA completo conocido;
- `persist-credentials: false` en checkout;
- permisos explícitos y mínimos;
- `pull_request_target` no hace checkout del PR head y su job está cerrado;
- no existe `issue_comment` como autoridad;
- scripts capaces de red sólo aparecen en jobs live bloqueados;
- CI compila `src` y `scripts` y ejecuta toda la suite con Python 3.12.

Hallazgo de auditoría 2026-08-20: la CI sólo tenía `pull_request` y `workflow_dispatch`. Como `main` no está protegida, un push directo podía evitar la suite. La corrección versionada añade `push` sobre `main` con los mismos paths y una prueba estática que obliga a conservar esa cobertura.

## Persistencia e histórico

El contrato de datos sigue definiendo, entre otras entidades:

- `cfg_supermarkets`;
- `cfg_locations`;
- `dim_products`;
- `map_source_products`;
- `fact_scrape_runs`;
- `fact_offers_current`;
- `fact_offer_history`;
- `fact_quality_events`.

Hoy esto es principalmente **modelo/documentación**, no un backend comercial conectado. La regla `commercial_update_allowed` está definida conceptualmente en el modelo de datos, pero todavía falta una frontera de aplicación persistente que garantice de forma idempotente que sólo ejecuciones aceptadas muten current/history.

Trabajo offline permitido y prioritario una vez cerrada la canonicalización/CI: implementar la **mínima máquina de transición de estado comercial e histórico** reutilizando `ValidatedOffer`, sin elegir aún Google Sheets, BigQuery, SQLite o PostgreSQL como backend definitivo. Debe probar idempotencia y rechazo de runs no aceptados antes de conectar cualquier almacenamiento externo.

## Matriz de gates canónicos

| Gate | Significado canónico | Estado actual |
|---|---|---|
| GATE-01 | DEFAULT DENY | PASS_OFFLINE_MODEL integrado en `main`; live sigue cerrado |
| GATE-02 | UNIQUE LIVE ENTRY / BLOCK ALTERNATIVES | PASS_OFFLINE_MODEL integrado; productivo depende de enforcement externo |
| GATE-03 | AUTHORIZATION SEPARATE FROM CONTRACT VALIDITY | PASS_OFFLINE_MODEL |
| GATE-04 | IMMUTABLE SHA / REQUEST IDENTITY | PASS_OFFLINE_MODEL |
| GATE-05 | ONE-SHOT ATOMIC CONSUMPTION / REPLAY | PASS_OFFLINE_MODEL |
| GATE-06 | PHYSICAL EGRESS GUARD | PASS_OFFLINE_MODEL; **FAIL productivo / pendiente** |
| GATE-07 | GLOBAL LIVE EXCLUSION | PASS_OFFLINE_MODEL y workflows cerrados |
| GATE-08 | PHYSICAL DELAY >= 1.5s | PASS_OFFLINE_MODEL |
| GATE-09 | PHYSICAL RETRIES <= 1 | PASS_OFFLINE_MODEL; runner vigente usa 0 |
| GATE-10 | CLOSED FAIL-CLOSED BUDGET | PASS_OFFLINE_MODEL |
| GATE-11 | STOP ON 403 | PASS_OFFLINE_MODEL |
| GATE-12 | STOP ON 429 | PASS_OFFLINE_MODEL |
| GATE-13 | STOP ON CAPTCHA / ANTIBOT | PASS_OFFLINE_MODEL |
| GATE-14 | STOP ON AUTH / ADDRESS / GPS REQUIREMENT | PASS_OFFLINE_MODEL |
| GATE-15 | EXCESSIVE LOAD STOP | PASS_OFFLINE_MODEL |
| GATE-16 | TRUSTED WORKFLOW / CODE / SUPPLY CHAIN | PASS_OFFLINE_MODEL integrado; GATE-17 impide readiness productivo |
| GATE-17 | PRODUCTIVE RULESET / PROTECTION EVIDENCE | **FAIL_PRODUCTIVE_EVIDENCE** (`main` sin protección) |
| GATE-18 | EXACT FINAL VALIDATION | **FAIL-CLOSED**; trusted collector productivo pendiente |
| GATE-19 | ADVERSARIAL OFFLINE COVERAGE | PASS_OFFLINE_MODEL; aceptación autoritativa bloqueada |
| GATE-20 | COMMENTS NON-AUTHORITATIVE | PASS_OFFLINE_MODEL |

Ningún `PASS_OFFLINE_MODEL` autoriza live.

## Backlog dependency-driven actual

### DONE / integrado

- contratos comunes e identidad;
- extractor/GraphQL/runner La Colonia offline;
- facets/partitions/coverage/reconciliation adversarial;
- SPS diagnostics offline;
- live safety state machine offline;
- observabilidad/dispatcher sin autoridad;
- workflow pinning y auditoría de seguridad;
- PR #17 y PR #7 integrados.

### READY_TO_IMPLEMENT offline

1. terminar canonicalización documental y CI sobre `main`;
2. implementar frontera mínima de aceptación/persistencia comercial en memoria, desacoplada del backend, con idempotencia e histórico sólo para runs aceptados;
3. añadir pruebas adversariales del histórico: reintento, mismo hash, cambio de precio, reported regular price sin ahorro real, rejected/failed/abandoned sin mutación.

### BLOCKED_EXTERNAL / BLOCKED_LIVE

- GATE-17 productivo;
- trusted collector con provenance física independiente;
- egress/claim/fencing productivo;
- confirmación técnica SPS;
- cualquier nueva ejecución live;
- backend productivo externo y scheduling diario mientras no exista aceptación comercial autoritativa.

### STALE / OBSOLETE

- cuerpos históricos de PR #7/#17 que los describen como abiertos o draft;
- ramas históricas ya integradas que estén detrás de `main` y no contengan trabajo canónico nuevo;
- estructura antigua del README que omitía la mayor parte del runtime La Colonia.

## Criterio de avance

Orden canónico:

`CORRECTNESS -> COMMERCIAL ACCEPTANCE/PERSISTENCE -> AUTOMATION -> ANALYTICS`.

Un bloqueo live no impide desarrollar interfaces y lógica puramente offline que no inventen evidencia ni muten estado comercial real. No se introduce infraestructura paga o distribuida para satisfacer un modelo teórico; cada nueva dependencia debe resolver un problema real del proyecto.
