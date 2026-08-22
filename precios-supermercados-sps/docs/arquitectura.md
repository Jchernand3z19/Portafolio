# Arquitectura y estado canónico — Precios Supermercados SPS

Este documento es la **fuente canónica única** del estado técnico actual del proyecto. Los cuerpos de PR, comentarios, logs, artefactos y documentos históricos conservan evidencia, pero no conceden autoridad ni sustituyen este estado.

## Corte de estado

Estado verificado al **2026-08-21 (America/Tegucigalpa)**.

La revisión integrada más reciente usada para este corte es **PR #83 — separación de readiness técnica y autoridad productiva**. No se fija aquí el SHA mutable de `main`, porque el propio merge de documentación lo cambiaría.

La suite integrada en `main` hasta PR #83 contiene **1209/1209 pruebas aprobadas**, además de `compileall`. El **PR #84** prepara una sonda Cloudflare contra origen controlado no-La-Colonia y obtuvo **1212/1212** en CI, pero mientras siga sin integrar no forma parte del estado ejecutable de `main`.

Durante este corte:

- `main` continúa protegida y GATE-17 permanece `PASS_PRODUCTIVE_EVIDENCE`;
- no existe autorización live activa;
- `SPS-context-and-root-facets-001` está consumida;
- no existe autorización `002`;
- SPS technical context continúa `UNCONFIRMED`;
- todos los entrypoints capaces de tráfico live hacia La Colonia siguen globalmente cerrados;
- Cloudflare no está desplegado;
- no existe autoridad productiva del catálogo;
- no existe backend comercial productivo conectado;
- **requests live a La Colonia realizados durante estas fases: 0**.

## Estados usados

| Estado | Significado |
|---|---|
| `DONE` | Contrato o lógica estable integrada. |
| `DONE_OFFLINE` | Implementado y probado sin afirmar despliegue ni autoridad productiva. |
| `DONE_PRODUCTIVE` | Verificado contra enforcement productivo real. |
| `PARTIAL` | Existe una parte útil, pero la frontera completa no está cerrada. |
| `READY_TO_INTEGRATE` | Implementación terminada y validada, aún fuera de `main`. |
| `BLOCKED_EXTERNAL` | Requiere cuenta, despliegue, credencial o infraestructura externa. |
| `BLOCKED_LIVE` | Requiere observación real autorizada de la fuente. |
| `BLOCKED_HUMAN_DECISION` | Requiere autorización humana explícita. |
| `BLOCKED_DEPENDENCIES` | No debe activarse hasta cerrar dependencias previas. |

## Estado operativo resumido

| Área | Estado | Consecuencia |
|---|---|---|
| `RawProduct` / `NormalizedOffer` / `ValidatedOffer` | DONE | Contratos protegidos y preservados. |
| Identificadores / `state_hash` | DONE | Deterministas y revalidados en fronteras comerciales. |
| Extractor VTEX La Colonia | DONE_OFFLINE | Fixtures y contratos; la red externa permanece denegada por defecto. |
| Facets / particiones / cobertura / reconciliación | DONE_OFFLINE | Completitud adversarial implementada, sin autoridad productiva. |
| Cloudflare Worker + Durable Object | DONE_OFFLINE | OIDC, pacing, presupuesto, replay, Ed25519, fencing y version metadata implementados; no desplegados. |
| Observability Cloudflare | DONE_OFFLINE | Evidencia de spans y reconciliación estructural/catálogo implementada y probada offline. |
| Structural discovery autenticado | DONE_OFFLINE | Puede cerrar una `VerifiedStructuralDiscovery` bajo evidencia offline verificada. |
| Plan canónico autenticado de catálogo | DONE_OFFLINE | Page size, órdenes, IDs y recorrido derivados internamente; no elegibles por caller. |
| Transporte autenticado de páginas | DONE_OFFLINE | Gateway -> firma -> body -> cobertura con binding exacto a discovery/plan. |
| Finalización de provenance del catálogo | DONE_OFFLINE | Reconciliación observability por página + manifest de run completo. |
| Readiness técnica del catálogo | DONE_OFFLINE | Distingue completitud técnica de autoridad productiva; nunca produce `catalog_accepted=true`. |
| Sonda Cloudflare no-La-Colonia | READY_TO_INTEGRATE | PR #84 verde 1212/1212; no desplegada y aún fuera de `main`. |
| Despliegue Cloudflare real | BLOCKED_EXTERNAL | Requiere cuenta/configuración externa y prueba física controlada. |
| Autoridad productiva del collector | BLOCKED_EXTERNAL | No se concede con firmas/logs simulados u offline. |
| SPS technical context | BLOCKED_LIVE | `UNCONFIRMED`; requiere observación live autorizada. |
| Autorización La Colonia | BLOCKED_HUMAN_DECISION | Ninguna activa. |
| GATE-17 / protección de `main` | DONE_PRODUCTIVE | Enforcement verificado productivamente. |
| Current/history | DONE_OFFLINE | Máquina atómica/idempotente y evidencia defensiva. |
| Pricing histórico | DONE_OFFLINE | Ahorro real contra precio aceptado anterior, fail-closed. |
| Backend comercial productivo | BLOCKED_DEPENDENCIES | Espera autoridad productiva y decisión de almacenamiento. |
| Scraping diario | BLOCKED_DEPENDENCIES | Espera live estable + autoridad + persistencia. |
| Power BI | BLOCKED_DEPENDENCIES | Espera datos comerciales autoritativos persistidos. |
| Segundo supermercado | BLOCKED_DEPENDENCIES | Espera cerrar la plataforma común antes de replicar. |

## Orden de avance

```text
CORRECTNESS
-> AUTHORITATIVE ACCEPTANCE
-> PERSISTENCE
-> AUTOMATION
-> ANALYTICS
-> MÁS SUPERMERCADOS
```

Una ejecución técnicamente válida puede producir diagnóstico y evidencia sin ser comercialmente aceptada. **Nunca se salta la frontera de autoridad para alimentar current/history.**

## Contratos y regla comercial

`RawProduct`, `NormalizedOffer` y `ValidatedOffer` permanecen protegidos.

Una oferta `in_stock` exige `current_price > 0`; `out_of_stock`, `not_listed` y `unknown` pueden conservar precio nulo. Marca, categoría, subcategoría y presentación pueden quedar pendientes cuando la fuente no los demuestra.

Regla histórica vigente:

- `reported_regular_price` es un dato informado por el supermercado;
- no demuestra ahorro real;
- la reducción real se compara contra el `current_price` del periodo histórico **aceptado inmediatamente anterior**;
- `reported_regular_price` e `is_promotion` no participan en la fórmula de ahorro real;
- si falta precio actual o baseline, no se inventa reducción;
- igualdad o subida producen reducción cero;
- `rejected`, `failed`, `abandoned` o una ejecución no autoritativa no alteran current/history.

## Frontera comercial

`commercial_state.py` implementa la máquina de transición backend-neutral y offline. Sus invariantes incluyen:

- mutación únicamente para una decisión comercial aceptada;
- replay terminal idempotente y `running` transitorio;
- IDs deterministas revalidados antes de aplicar;
- continuidad de identidad, ubicación, producto fuente y moneda;
- `state_hash` recalculado;
- cronología cerrada;
- ausencia de una oferta en un payload posterior **no** implica `not_listed`, `out_of_stock` ni baja;
- snapshots defensivos de evidencia;
- cambios atómicos: un fallo no deja estado parcial;
- un mismo hash confirma el periodo abierto sin duplicar histórico;
- un cambio real cierra un periodo y abre exactamente uno.

El parámetro histórico `catalog_accepted` sigue siendo una **decisión upstream**, no una autoridad que el caller pueda inventar. La integración productiva debe obtener esa decisión de una frontera de evidencia productiva no controlable por el caller.

`commercial_pricing.py` revalida identidad, hashes, cronología, contigüidad y relación current/history antes de producir una reducción. Una inconsistencia falla cerrado.

## La Colonia — identidad y completitud

Identidad VTEX vigente:

```text
Producto: productId -> productReference -> linkText
SKU:      itemId
```

Deduplicar nunca demuestra completitud. El recorrido exige estructura, membership, totales, ventanas, ausencia de gaps/truncamiento/repeticiones, reconciliación independiente, unión producto/SKU y consistencia de owner.

Las observaciones conservan `LocationStatus.UNKNOWN` mientras SPS no sea técnicamente demostrado.

## Cadena Cloudflare integrada offline

La arquitectura productiva seleccionada ya no es el diseño histórico de Google Cloud Run/Secure Web Proxy/KMS. La ruta activa de ingeniería es **Cloudflare Workers + Durable Objects + GitHub OIDC + Ed25519 + Workers Observability**.

Cadena lógica actual:

```text
GitHub Actions autorizado
    -> GitHub OIDC fijado a repo/ref/workflow/environment/run
    -> Cloudflare Worker
    -> Durable Object de autorización/presupuesto/replay
    -> request exacto permitido
    -> respuesta cruda + SHA-256
    -> receipt Ed25519 ligado a release/commit/run/request
    -> verificación criptográfica Python
    -> reconciliación con Workers Observability
    -> manifest estructural o de catálogo
    -> readiness técnica
```

### Fronteras ya implementadas

- política OIDC fijada en código: repo, repository ID, `main`, workflow, environment, event, audience, commit, run y attempt;
- GitHub JWKS con origen fijo, body acotado y caché corta;
- URL/host/path/método/query GraphQL de La Colonia cerrados en el Worker productivo;
- `page_size <= 50`, órdenes allowlisted y parámetros estructurales canónicos;
- Durable Object SQLite para presupuesto, reserva, pacing, single-flight, replay y fencing;
- `max_retries = 0` en la ruta canónica;
- receipts Ed25519 y hash de respuesta cruda;
- release del Worker ligada a `CF_VERSION_METADATA`;
- collectors Python que no aceptan URL, page size, orden ni IDs de traversal arbitrarios del caller;
- verificación exacta de identidad entre página criptográfica y observación de Workers Observability;
- manifest de run que exige el conjunto exacto esperado de páginas y unicidad de evidencias físicas;
- finalizador de structural discovery autenticado;
- readiness de catálogo que puede afirmar **completitud técnica** pero conserva `catalog_accepted=false` y `production_authority=false`.

### Lo que la implementación offline no demuestra

No demuestra que exista un Worker realmente desplegado, un Durable Object remoto, claves privadas alojadas en Cloudflare, un token OIDC real consumido por ese Worker, spans reales de Workers Observability ni un request físico autorizado. Por eso la firma y los manifests offline **no son autoridad productiva**.

El evaluador canónico mantiene deliberadamente el reason:

```text
trusted_collector_provenance_unavailable
```

Hasta una prueba productiva real, ese reason no debe eliminarse ni sustituirse por un booleano controlado por caller.

## Sonda controlada no-La-Colonia

Para validar Cloudflare antes de cualquier contacto con La Colonia, el PR #84 prepara una sonda aislada con dos Workers separados:

```text
GitHub workflow manual de sonda
    -> OIDC audience/environment exclusivos de sonda
    -> Worker gateway de sonda + Durable Object propio
    -> origen controlado workers.dev
    -> challenge exacto
    -> receipt Ed25519 con schema/dominio criptográfico de sonda
```

Propiedades de diseño:

- no modifica el allowlist del Worker productivo de La Colonia;
- el caller no puede inyectar el origen;
- el origen de sonda debe ser HTTPS `*.workers.dev` y path exacto;
- La Colonia es rechazada antes de cualquier fetch;
- claves, OIDC audience, environment, signing key ID, schema y dominio de firma son distintos a producción;
- un receipt de sonda no verifica bajo el dominio de receipt productivo;
- no concede `catalog_accepted` ni `production_authority`.

Mientras PR #84 no esté integrado, esta sonda es `READY_TO_INTEGRATE`, no `DONE_OFFLINE` de `main`. Incluso integrada seguirá siendo `NO DESPLEGADA` hasta completar la frontera externa de Cloudflare.

## SPS y autorización live

Estado canónico:

```text
ACTIVE_AUTHORIZATION_IDS = []
READY_FOR_LIVE = NO
SPS_TECHNICAL_CONTEXT = UNCONFIRMED
```

Sin autorización humana explícita nueva están prohibidos HTTP/VTEX/GraphQL/Playwright/crawler/diagnostics/facet discovery/smoke/full crawl y cualquier otro tráfico hacia La Colonia.

Comentarios, PR comments, issue comments, archivos de comando, markers, logs y artefactos son observabilidad; **no crean autoridad**.

## Workflows y CI

Los workflows de La Colonia capaces de live permanecen globalmente bloqueados con `if: ${{ false }}`. `test_workflow_security_audit.py` clasifica todos los workflows SPS y falla si aparece uno nuevo sin política explícita.

Controles actuales:

- Actions externas por SHA completo allowlisted;
- permisos mínimos explícitos;
- checkout inmutable y `persist-credentials: false` cuando corresponde;
- `pull_request_target` no ejecuta código no confiable;
- `issue_comment` no concede autoridad;
- scripts capaces de tráfico La Colonia sólo pueden aparecer en entrypoints bloqueados;
- CI cubre PRs y pushes a `main` que afecten proyecto/workflows;
- el ruleset productivo exige PR, `tests` y resolución de conversaciones.

GATE-17 permanece `DONE_PRODUCTIVE`; la evidencia específica está en `docs/gate-17-verification.md`.

## Persistencia

El modelo lógico sigue definiendo, entre otras entidades:

- `cfg_supermarkets`;
- `cfg_locations`;
- `dim_products`;
- `map_source_products`;
- `fact_scrape_runs`;
- `fact_offers_current`;
- `fact_offer_history`;
- `fact_quality_events`.

La lógica current/history y pricing ya existe offline. **No hay backend productivo seleccionado ni conectado.** Google Sheets y BigQuery siguen siendo opciones de arquitectura histórica/evolutiva, no una declaración de infraestructura activa.

No se debe implementar un adaptador productivo que reciba un `catalog_accepted` caller-controlled. La siguiente integración de persistencia debe consumir una decisión de autoridad tipada y verificada cuando esa frontera exista.

## Gates principales

| Gate | Estado | Evidencia faltante |
|---|---|---|
| GATE-17 — gobernanza/protección de `main` | `PASS_PRODUCTIVE_EVIDENCE` | Ninguna para este gate. |
| GATE-06 — enforcement físico/collector | `OPEN_PRODUCTIVE` | Despliegue y prueba física real. |
| GATE-18 — aceptación exacta de catálogo | `OPEN_PRODUCTIVE` | Autoridad productiva + validación live exacta autorizada. |
| SPS technical context | `UNCONFIRMED` | Observación live mínima autorizada. |

## Backlog clasificado

### DONE / DONE_OFFLINE

- contratos e identidad;
- extracción/normalización/validación offline;
- facets, particiones, coverage y reconciliación;
- current/history/pricing;
- Cloudflare Worker/DO/OIDC/Ed25519/replay/fencing;
- Workers Observability y verificadores;
- structural discovery autenticado;
- plan, transporte y finalización autenticados del catálogo;
- readiness técnica separada de autoridad productiva;
- GATE-17 productivo.

### READY_TO_INTEGRATE

- PR #84: sonda Cloudflare contra origen controlado no-La-Colonia; CI 1212/1212. No contar como integrado hasta merge.

### BLOCKED_EXTERNAL

- desplegar origen controlado y gateway de sonda en una cuenta Cloudflare;
- crear/cargar las llaves de sonda únicamente en Cloudflare;
- validar OIDC, Durable Object, Version Metadata, Ed25519 y Workers Observability físicamente;
- después preparar/desplegar la frontera productiva real de collector sin conceder autoridad por configuración.

### BLOCKED_HUMAN_DECISION / BLOCKED_LIVE

- una autorización humana nueva para cualquier request a La Colonia;
- diagnóstico mínimo de SPS;
- validación live exacta de catálogo bajo presupuesto cerrado.

### BLOCKED_DEPENDENCIES

- backend comercial productivo;
- scraping diario;
- Power BI sobre histórico autoritativo;
- siguiente supermercado.

## Criterio para el siguiente paso

No se usa un bloqueo live como excusa para omitir trabajo offline disponible, y tampoco se representa una simulación como producción. El siguiente hito externo correcto es **probar Cloudflare físicamente contra un origen controlado que no sea La Colonia**. Sólo después se evalúa la frontera productiva real; el acceso live a La Colonia continúa requiriendo autorización humana separada.