# Arquitectura y estado canónico — Precios Supermercados SPS

Este documento es la **fuente canónica única** del estado técnico actual del proyecto. Los cuerpos de PR, comentarios, logs, artefactos y documentos históricos conservan evidencia, pero no conceden autoridad ni sustituyen este estado.

## Corte de estado

Estado verificado al **2026-08-21 (America/Tegucigalpa)**.

La última frontera técnica integrada en este corte es **PR #89 — reconciliación Workers Observability de la sonda controlada**. No se fija aquí el SHA mutable de `main`; se consulta en GitHub al iniciar cualquier trabajo.

CI observada para la revisión integrada por PR #89:

```text
compileall = PASS
pytest = 1231/1231 PASS
```

Estado operativo:

- `main` continúa protegida; GATE-17 = `PASS_PRODUCTIVE_EVIDENCE`;
- no existe autorización live activa para La Colonia;
- `SPS-context-and-root-facets-001` está consumida y no puede reutilizarse;
- `SPS-context-and-root-facets-002` no está autorizada;
- `ACTIVE_AUTHORIZATION_IDS = []`;
- SPS technical context = `UNCONFIRMED`;
- los entrypoints capaces de tráfico live hacia La Colonia permanecen globalmente cerrados;
- Cloudflare productivo no está desplegado;
- la sonda Cloudflare no-La-Colonia está completa **offline**, pero no desplegada ni ejecutada;
- no existe autoridad productiva del catálogo;
- no existe backend comercial productivo conectado;
- **requests live a La Colonia durante estas fases: 0**.

## Estados usados

| Estado | Significado |
|---|---|
| `DONE` | Contrato o lógica estable integrada. |
| `DONE_OFFLINE` | Implementado y probado sin afirmar despliegue ni autoridad productiva. |
| `DONE_PRODUCTIVE` | Verificado contra enforcement/producto real. |
| `READY_FOR_EXTERNAL_DEPLOYMENT` | El trabajo versionado previo está cerrado; falta infraestructura externa. |
| `BLOCKED_EXTERNAL` | Requiere cuenta, despliegue, credencial o infraestructura externa. |
| `BLOCKED_LIVE` | Requiere observación real autorizada de la fuente. |
| `BLOCKED_HUMAN_DECISION` | Requiere autorización humana explícita. |
| `BLOCKED_DEPENDENCIES` | No debe activarse hasta cerrar dependencias previas. |

## Estado resumido

| Área | Estado | Consecuencia |
|---|---|---|
| `RawProduct` / `NormalizedOffer` / `ValidatedOffer` | `DONE` | Contratos protegidos y preservados. |
| Identificadores / `state_hash` | `DONE` | Deterministas y revalidados en fronteras comerciales. |
| Extractor VTEX La Colonia | `DONE_OFFLINE` | Fixtures y contratos; red externa denegada por defecto. |
| Facets / particiones / coverage / reconciliación | `DONE_OFFLINE` | Completitud adversarial implementada, sin autoridad productiva. |
| Cloudflare Worker productivo + `AuthorizationGateway` | `DONE_OFFLINE` | OIDC, budget, pacing, replay, Ed25519, fencing y version metadata; no desplegados. |
| Observability productiva | `DONE_OFFLINE` | Parsers/verifiers/reconciliación estructural y catálogo probados offline. |
| Structural discovery autenticado | `DONE_OFFLINE` | `VerifiedStructuralDiscovery` bajo evidencia verificada offline. |
| Plan canónico autenticado de catálogo | `DONE_OFFLINE` | Page size, órdenes, IDs y recorrido derivados internamente. |
| Transporte autenticado de páginas | `DONE_OFFLINE` | Gateway → crypto/body → coverage con binding exacto. |
| Finalización de provenance de catálogo | `DONE_OFFLINE` | Observability por página + manifest de run exacto. |
| Readiness técnica de catálogo | `DONE_OFFLINE` | Puede demostrar completitud técnica sin aceptar catálogo. |
| Sonda Cloudflare no-La-Colonia | `DONE_OFFLINE / READY_FOR_EXTERNAL_DEPLOYMENT` | Origen/gateway/DO/OIDC/firma/verifier/Observability integrados; no desplegada ni ejecutada. |
| Despliegue y prueba física de sonda | `BLOCKED_EXTERNAL` | Requiere cuenta/configuración Cloudflare y credenciales de sonda. |
| Autoridad productiva del collector | `BLOCKED_EXTERNAL` | No se concede con fixtures, firmas o spans simulados. |
| SPS technical context | `BLOCKED_LIVE` | `UNCONFIRMED`; requiere observación live mínima autorizada. |
| Autorización La Colonia | `BLOCKED_HUMAN_DECISION` | Ninguna activa. |
| GATE-17 / protección de `main` | `DONE_PRODUCTIVE` | Enforcement real demostrado. |
| Current/history | `DONE_OFFLINE` | Máquina atómica/idempotente y evidencia defensiva. |
| Pricing histórico | `DONE_OFFLINE` | Ahorro real contra precio aceptado anterior, fail-closed. |
| Backend comercial productivo | `BLOCKED_DEPENDENCIES` | Espera autoridad productiva y luego decisión de almacenamiento. |
| Scraping diario | `BLOCKED_DEPENDENCIES` | Espera live estable + autoridad + persistencia. |
| Power BI | `BLOCKED_DEPENDENCIES` | Espera datos comerciales autoritativos persistidos. |
| Segundo supermercado | `BLOCKED_DEPENDENCIES` | Espera cerrar la plataforma común. |

## Orden de avance

```text
CORRECTNESS
-> PHYSICAL PLATFORM PROOF
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
- la reducción real compara el `current_price` actual contra el `current_price` del periodo histórico **aceptado inmediatamente anterior**;
- `reported_regular_price` e `is_promotion` no participan en la fórmula de ahorro real;
- si falta precio actual o baseline, no se inventa reducción;
- igualdad o subida producen reducción cero;
- `rejected`, `failed`, `abandoned` o una ejecución no autoritativa no alteran current/history.

## Frontera comercial

`commercial_state.py` implementa la máquina de transición backend-neutral y offline. Entre sus invariantes:

- sólo una decisión comercial aceptada puede mutar current/history;
- replay terminal idempotente; `running` es transitorio;
- IDs deterministas y `state_hash` se revalidan;
- continuidad de identidad, ubicación, producto fuente y moneda;
- cronología cerrada;
- ausencia en un payload no implica `not_listed`, `out_of_stock` ni baja;
- snapshots defensivos de evidencia;
- cambios atómicos;
- un mismo hash confirma el periodo abierto sin duplicarlo;
- un cambio real cierra un periodo y abre exactamente uno.

El parámetro histórico `catalog_accepted` de esa frontera es una **decisión upstream**, no una capacidad que el caller pueda inventar. La integración productiva debe derivarla de una autoridad tipada y verificable.

`commercial_pricing.py` revalida identidad, hashes, cronología, contigüidad y relación current/history antes de calcular reducción.

No se implementa un backend productivo sólo para aparentar progreso mientras la autoridad sigue ausente.

## La Colonia — identidad y completitud

Identidad VTEX vigente:

```text
Producto: productId -> productReference -> linkText
SKU:      itemId
```

Deduplicar nunca demuestra completitud. El recorrido exige estructura, membership, totales, ventanas, ausencia de gaps/truncamiento/repeticiones, reconciliación independiente, unión producto/SKU y consistencia de owner.

Las observaciones conservan `LocationStatus.UNKNOWN` mientras SPS no sea demostrado técnicamente.

## Cadena Cloudflare productiva preparada offline

La ruta de ingeniería seleccionada es **Cloudflare Workers + Durable Objects + GitHub OIDC + Ed25519 + Workers Observability**. El diseño histórico Google Cloud Run/Secure Web Proxy/KMS está supersedido.

```text
GitHub Actions autorizado
    -> GitHub OIDC fijado a repo/ref/workflow/environment/run
    -> Cloudflare Worker productivo
    -> AuthorizationGateway
    -> request exacto allowlisted
    -> respuesta cruda + SHA-256
    -> receipt Ed25519 ligado a release/commit/run/request
    -> verificación criptográfica Python
    -> Workers Observability
    -> manifest estructural o de catálogo
    -> readiness técnica
```

Implementado offline:

- política OIDC cerrada a repo, repository ID, `main`, workflow, environment, event, audience, commit, run y attempt;
- GitHub JWKS con origen fijo;
- host/path/método/query GraphQL de La Colonia cerrados en el Worker productivo;
- `page_size <= 50`, órdenes allowlisted y parámetros canónicos;
- Durable Object SQLite para presupuesto, reserva, pacing, single-flight, replay y fencing;
- ruta canónica con `max_retries = 0`;
- receipts Ed25519 y hash de bytes crudos;
- release ligada a `CF_VERSION_METADATA`;
- collectors Python sin URL/page size/order/traversal IDs arbitrarios del caller;
- identidad exacta entre página criptográfica y observación de Workers Observability;
- manifest de run con conjunto exacto de páginas y unicidad de evidencias;
- structural discovery autenticado;
- readiness técnica que puede afirmar completitud sin producir autoridad.

Lo anterior **no** demuestra Worker/DO/llaves/spans reales. El reason canónico permanece:

```text
trusted_collector_provenance_unavailable
```

hasta evidencia productiva real.

## Sonda controlada no-La-Colonia

La primera prueba física de Cloudflare se hace contra infraestructura propia, no contra La Colonia.

Cadena integrada por PR #84, #88 y #89:

```text
workflow manual cloudflare-probe
    -> OIDC de sonda
    -> Worker precios-sps-controlled-probe
    -> ProbeLedger
    -> custom span obligatorio / tracing 100 %
    -> Worker precios-sps-controlled-origin (*.workers.dev)
    -> challenge/body exactos
    -> receipt Ed25519 probe-1
    -> artifact sanitizado
    -> job verificador separado sin OIDC
    -> public key confiable de Environment
    -> Workers Observability API
    -> custom span único + child fetch único
    -> PlatformReconciledControlledProbe
```

Propiedades:

- no modifica ni amplía el allowlist productivo de La Colonia;
- caller no puede inyectar origin URL;
- origen sólo HTTPS `*.workers.dev` y path exacto;
- La Colonia se rechaza antes de cualquier fetch;
- Worker/DO, audience/environment, llaves, signing key ID, schema y dominio de firma son distintos de producción;
- `span.isTraced` debe ser true antes del fetch;
- el job OIDC no hace checkout;
- el job verificador no posee `id-token: write`;
- firma/body/request/evidence ID se verifican fuera del Worker;
- Workers Observability se consulta por transporte fijo a `api.cloudflare.com/client/v4` sin redirects ni retries;
- se exige exactamente un custom span y un child fetch reconciliados por run/commit/release/URL/status/size/timestamps;
- un resultado válido mantiene `catalog_accepted=false` y `production_authority=false`.

Estado:

```text
SONDA_CODE = DONE_OFFLINE
SONDA_DEPLOY = NOT_DONE
SONDA_PHYSICAL_RUN = NOT_DONE
```

El procedimiento externo está en `docs/cloudflare-controlled-probe-runbook.md`.

## Secrets/variables de la sonda

Cloudflare gateway:

```text
PROBE_ORIGIN_URL
PROBE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL
PROBE_RECEIPT_PUBLIC_KEY_SPKI_B64URL
```

La private key sólo puede existir en Cloudflare.

GitHub Environment `cloudflare-probe`:

Secrets:

```text
CLOUDFLARE_PROBE_GATEWAY_URL
CLOUDFLARE_PROBE_OBSERVABILITY_TOKEN
```

Variables:

```text
CLOUDFLARE_PROBE_PUBLIC_KEY_SPKI_B64URL
CLOUDFLARE_ACCOUNT_ID
```

El token de Observability debe limitarse a la cuenta requerida y no poseer `Workers Scripts Write`. La documentación actual de Cloudflare exige un permiso denominado `Workers Observability Write` para el endpoint de consulta; esa denominación no lo convierte en credencial de deploy.

## SPS y autorización live

Estado canónico:

```text
ACTIVE_AUTHORIZATION_IDS = []
READY_FOR_LIVE = NO
SPS_TECHNICAL_CONTEXT = UNCONFIRMED
```

Sin autorización humana explícita nueva están prohibidos HTTP/VTEX/GraphQL/Playwright/crawler/diagnostics/facet discovery/smoke/full crawl y cualquier tráfico hacia La Colonia.

Un PASS de la sonda Cloudflare **no** crea una autorización live.

## Workflows y CI

Los workflows de La Colonia capaces de live permanecen globalmente bloqueados con `if: ${{ false }}`. `test_workflow_security_audit.py` clasifica todo workflow SPS y falla si aparece uno nuevo sin política explícita.

El workflow de sonda es la excepción controlada porque no puede contactar La Colonia:

- sólo `workflow_dispatch`;
- job OIDC sin checkout;
- job verificador sin OIDC;
- secrets y variables allowlisted explícitamente;
- URL de gateway restringida a `workers.dev`;
- no existen inputs de origin/destino;
- no invoca scripts live de La Colonia.

CI cubre PRs y pushes a `main` que afectan el proyecto/workflows. GATE-17 permanece `DONE_PRODUCTIVE`; evidencia en `docs/gate-17-verification.md`.

## Persistencia

El modelo lógico contempla:

- `cfg_supermarkets`;
- `cfg_locations`;
- `dim_products`;
- `map_source_products`;
- `fact_scrape_runs`;
- `fact_offers_current`;
- `fact_offer_history`;
- `fact_quality_events`.

Current/history y pricing existen offline. **No hay backend productivo seleccionado ni conectado.** Google Sheets y BigQuery son opciones históricas/evolutivas, no infraestructura activa.

La siguiente integración productiva de persistencia debe consumir una decisión de autoridad tipada y verificada; no un booleano caller-controlled.

## Gates principales

| Gate | Estado | Evidencia faltante |
|---|---|---|
| GATE-17 — gobernanza/protección de `main` | `PASS_PRODUCTIVE_EVIDENCE` | Ninguna para este gate. |
| Prueba Cloudflare no-La-Colonia | `READY_FOR_EXTERNAL_DEPLOYMENT` | Deploy + ejecución física + firma/Observability reales. |
| GATE-06 — enforcement físico/collector productivo | `OPEN_PRODUCTIVE` | Despliegue y evidencia física productiva. |
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
- sonda controlada completa offline, incluida verificación Ed25519 externa y Workers Observability;
- GATE-17 productivo.

### READY_FOR_EXTERNAL_DEPLOYMENT / BLOCKED_EXTERNAL

- conectar/configurar una cuenta Cloudflare;
- desplegar `precios-sps-controlled-origin`;
- generar/cargar llaves Ed25519 exclusivas de sonda, con private key sólo en Cloudflare;
- desplegar `precios-sps-controlled-probe` y `ProbeLedger`;
- configurar Environment GitHub `cloudflare-probe`;
- ejecutar la sonda y obtener evidencia física de OIDC/DO/version metadata/firma/Observability;
- mantener La Colonia en **0 requests** durante esta etapa.

### Después de un PASS de sonda

- preparar/desplegar la frontera productiva real sin invocarla todavía contra La Colonia;
- demostrar todo lo posible de autenticación/fencing/configuración productiva sin requests a la fuente.

### BLOCKED_HUMAN_DECISION / BLOCKED_LIVE

- nueva autorización humana explícita para cualquier request a La Colonia;
- diagnóstico mínimo de SPS;
- validación live exacta de catálogo bajo presupuesto cerrado.

### BLOCKED_DEPENDENCIES

- backend comercial productivo;
- scraping diario;
- Power BI sobre histórico autoritativo;
- siguiente supermercado.

## Criterio para el siguiente paso

No se usa un bloqueo live como excusa para omitir trabajo offline disponible y tampoco se representa una simulación como producción.

El siguiente hito correcto es **desplegar y ejecutar la sonda Cloudflare contra el origen controlado no-La-Colonia** siguiendo `docs/cloudflare-controlled-probe-runbook.md`.

Sólo después de obtener ese PASS se prepara el collector productivo real. El acceso live a La Colonia continúa requiriendo autorización humana nueva y separada.
