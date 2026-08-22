# Cloudflare edge provenance

Estado en `main`: **IMPLEMENTADO OFFLINE / NO DESPLEGADO / NO LIVE LA-COLONIA / SIN AUTORIDAD PRODUCTIVA**.

Este directorio contiene la frontera edge seleccionada para Cloudflare Workers y la sonda aislada previa contra origen controlado. Las pruebas offline no contactan La Colonia, no crean recursos remotos y no conceden `production_authority` ni `catalog_accepted`.

CI observada tras PR #89:

```text
1231/1231 tests PASS
compileall PASS
```

## Worker productivo preparado

`wrangler.json` declara:

- Worker `precios-sps-provenance`;
- entrypoint `src/index.mjs`;
- Durable Object `AuthorizationGateway` con SQLite;
- binding `AUTHORIZATION_GATEWAY`;
- `CF_VERSION_METADATA`;
- tracing/observability habilitado;
- preview URLs deshabilitadas.

Secret names requeridos, sin valores en Git:

- `EDGE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL`
- `EDGE_RECEIPT_PUBLIC_KEY_SPKI_B64URL`
- `EDGE_COLLECTOR_CODE_SHA256`

La private key de receipts debe existir únicamente en Cloudflare. **No debe copiarse a GitHub Secrets.**

## Fronteras productivas implementadas offline

- JSON y timestamps canónicos;
- SHA-256 y base64url canónico;
- Ed25519 para receipts v2;
- GitHub OIDC RS256 con issuer/audience/exp/nbf/iat/jti;
- repo, repository ID, ref, workflow, environment, event, commit, run y attempt cerrados;
- JWKS únicamente desde GitHub, body acotado, caché y refresh por `kid`;
- URL GraphQL productiva con scheme/host/path/query/variables cerrados;
- `hideUnavailableItems=false`, `skusFilter=ALL`, órdenes allowlisted y página <= 50;
- Durable Object con presupuesto, expiración, pacing mínimo 1.5 s, single-flight, replay e idempotencia;
- fencing entre autorización, DO y `run_id:run_attempt` real;
- replay con bytes persistidos y evidencia revalidada sin refetch;
- runtime fail-closed para redirect, HTTP inesperado, HTML, body vacío/sobredimensionado y firma inválida;
- preflight de par Ed25519;
- release ligada a `CF_VERSION_METADATA.id`;
- spans de Workers Observability con atributos de provenance;
- rutas estructurales separadas para root total/category tree;
- evidencia estructural firmada y reconciliable;
- runtime de catálogo y structural discovery sin authority implícita.

## Cadena Python conectada

Fuera de este directorio, la aplicación Python completa la cadena offline:

```text
Cloudflare receipt/body
-> verificación Ed25519
-> EdgeCatalogPage / StructuralObservation
-> Workers Observability verifier
-> VerifiedStructuralDiscovery
-> canonical authenticated catalog plan
-> VerifiedCatalogEdgeCollector
-> VerifiedCatalogProvenanceFinalizer
-> run manifest
-> CatalogAcceptanceReadiness
```

`CatalogAcceptanceReadiness` puede afirmar completitud técnica, pero por diseño conserva:

```text
catalog_accepted = false
production_authority = false
```

mientras falte evidencia productiva real.

## Contrato productivo preparado

La identidad OIDC queda fijada a:

- repositorio `Jchernand3z19/Portafolio`;
- repository ID esperado;
- ref `refs/heads/main`;
- workflow live canónico en `main`;
- environment `la-colonia-live`;
- evento `workflow_dispatch`;
- audience `urn:precios-sps:cloudflare:collector:v1`.

El caller no puede sustituir:

- hash GraphQL esperado;
- repo/ref/workflow/environment/audience;
- collector principal/release/code SHA;
- signing key ID;
- destino físico;
- page size/orden/IDs canónicos derivados por la aplicación;
- pacing por debajo del mínimo.

El allowlist productivo de La Colonia **no se amplía para pruebas**.

## Sonda controlada no-La-Colonia

La sonda está integrada offline mediante PR #84, #88 y #89. Su objetivo es probar Cloudflare físicamente antes de cualquier request a La Colonia.

### Workers y configuración

`wrangler.probe-origin.json`:

```text
name = precios-sps-controlled-origin
entrypoint = src/probe-origin.mjs
```

`wrangler.probe.json`:

```text
name = precios-sps-controlled-probe
entrypoint = src/probe-worker.mjs
Durable Object = ProbeLedger
version metadata = CF_VERSION_METADATA
tracing = enabled / head_sampling_rate 1
```

Secrets Cloudflare de sonda:

```text
PROBE_ORIGIN_URL
PROBE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL
PROBE_RECEIPT_PUBLIC_KEY_SPKI_B64URL
```

La private key de sonda también queda exclusivamente en Cloudflare.

### Separación del contrato productivo

La sonda usa:

- Worker de origen controlado `workers.dev`;
- gateway distinto;
- Durable Object `ProbeLedger` distinto;
- environment `cloudflare-probe`;
- audience `urn:precios-sps:cloudflare:probe:v1`;
- llaves Ed25519 y signing key ID distintos;
- schema `probe-1`;
- dominio criptográfico distinto;
- origen fijado en Cloudflare, nunca por input del caller.

La Colonia se rechaza antes de cualquier fetch. Un receipt de sonda no puede validarse como receipt productivo.

### Evidencia de sonda

Cadena:

```text
GitHub OIDC job sin checkout
-> ProbeLedger
-> custom span obligatorio
-> fetch al Worker controlado
-> body/challenge exactos
-> receipt Ed25519
-> artifact sanitizado
-> verifier job sin OIDC
-> public key confiable
-> Workers Observability
-> custom span único + child fetch único
-> reconciliación contra receipt
```

`probe-trace-context.mjs` exige `span.isTraced === true` antes de permitir el fetch.

`cloudflare_controlled_probe_verifier.py` verifica fuera del Worker:

- firma Ed25519;
- SHA/tamaño/body;
- request canónico;
- evidence ID;
- repo/ref/workflow/environment/commit/run/attempt;
- Durable Object name;
- destino `workers.dev`.

`cloudflare_controlled_probe_observability.py` exige:

- trace único;
- custom span único;
- único child `fetch`;
- service/version Cloudflare consistentes;
- URL exacta del origen controlado;
- `GET`, HTTP 200 y body size exacto;
- timestamps compatibles con el receipt.

`cloudflare_observability_http_transport.py` limita la consulta externa a:

```text
https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/observability/telemetry/query
```

sin redirects ni retries y con payload/respuesta acotados.

Ninguna salida de sonda puede establecer `catalog_accepted` o `production_authority`.

## GitHub Environment de sonda

Environment:

```text
cloudflare-probe
```

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

El token de Observability debe estar separado de cualquier credencial de deploy y no tener `Workers Scripts Write`.

## Workflow de sonda

`.github/workflows/precios-supermercados-sps-cloudflare-probe.yml` es sólo `workflow_dispatch`.

- `controlled-probe` tiene `id-token: write` pero **no hace checkout**;
- `verify-evidence` hace checkout inmutable pero **no tiene OIDC**;
- el token de Workers Observability sólo llega al paso de reconciliación del segundo job;
- no existen inputs de origin URL o autoridad;
- el workflow no invoca ningún script live de La Colonia.

## Validación offline

La suite Python ejecuta también la suite Node y cruza Python/JavaScript para:

- URL GraphQL y hashes;
- timestamps canónicos;
- receipts/firmas;
- Durable Object/ledger/replay;
- OIDC/JWKS/front door/fencing;
- structural runtime;
- observability attributes;
- configuración Wrangler;
- sonda aislada y rechazo de La Colonia;
- firma de sonda verificada fuera del Worker;
- tracing fail-closed;
- reconciliation de Workers Observability;
- transporte fijo de API Cloudflare;
- invariantes de no-authority.

## Estado externo pendiente

No se ha demostrado todavía:

- Workers/DO desplegados remotamente;
- private key real de sonda alojada en Cloudflare;
- OIDC real desde GitHub consumido por el Worker de sonda;
- `CF_VERSION_METADATA` real observado;
- receipt de sonda emitido por runtime remoto;
- spans reales de Workers Observability reconciliados;
- Worker/DO productivos desplegados;
- enforcement productivo completo;
- SPS técnico;
- autorización live nueva;
- catálogo productivamente aceptado.

Por eso `trusted_collector_provenance_unavailable` continúa cerrando la aceptación canónica.

El siguiente hito es seguir `docs/cloudflare-controlled-probe-runbook.md`: desplegar y ejecutar exclusivamente la sonda contra el origen controlado. Sólo después se prepara el despliegue productivo; cualquier request a La Colonia seguirá requiriendo autorización humana explícita separada.
