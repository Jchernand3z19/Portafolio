# Cloudflare edge provenance

Estado en `main`: **IMPLEMENTADO OFFLINE / NO DESPLEGADO / NO LIVE / SIN AUTORIDAD PRODUCTIVA**.

Este directorio contiene la frontera edge seleccionada para Cloudflare Workers. Las pruebas no contactan La Colonia, no crean recursos remotos y no conceden `production_authority` ni `catalog_accepted`.

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

## Fronteras implementadas offline

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

## Contrato público productivo preparado

El Worker productivo acepta rutas autenticadas específicas, entre ellas inicialización/ejecución del gateway y rutas estructurales previstas por la implementación.

La identidad productiva OIDC queda fijada a:

- repositorio `Jchernand3z19/Portafolio`;
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

## Sonda controlada no-La-Colonia

PR #84 prepara una sonda físicamente separada para probar Cloudflare antes de contactar La Colonia. A la fecha de este README, obtuvo **1212/1212** en CI pero todavía no forma parte de `main`.

La sonda propuesta usa:

- Worker de origen controlado `workers.dev`;
- Worker gateway distinto;
- Durable Object `ProbeLedger` distinto;
- environment/audience OIDC distintos;
- llaves Ed25519 y signing key ID distintos;
- schema `probe-1` y dominio de firma distintos;
- origen fijado mediante binding Cloudflare, no input del caller.

La Colonia es rechazada antes de cualquier fetch y un receipt de sonda no puede validarse como receipt productivo.

Integrar o ejecutar esa sonda **no** habilita el workflow live de La Colonia.

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
- invariantes de no-authority.

## Estado productivo pendiente

Todavía no se ha demostrado:

- Worker/DO desplegados remotamente;
- private key real alojada en Cloudflare;
- OIDC real desde GitHub consumido por el Worker;
- `CF_VERSION_METADATA` real observado;
- receipts emitidos por un runtime remoto;
- spans reales de Workers Observability reconciliados;
- enforcement productivo completo;
- SPS técnico;
- autorización live nueva;
- catálogo productivamente aceptado.

Por eso `trusted_collector_provenance_unavailable` continúa cerrando la aceptación canónica.

El siguiente hito externo correcto es una prueba Cloudflare contra **origen controlado no-La-Colonia**. Sólo después se evalúa el despliegue productivo; cualquier request a La Colonia seguirá requiriendo autorización humana explícita aparte.