# Cloudflare edge provenance

Estado: **IMPLEMENTADO OFFLINE / NO DESPLEGADO / NO LIVE**.

Este directorio contiene la frontera edge preparada para un futuro despliegue controlado en Cloudflare Workers. Las pruebas no contactan La Colonia, no crean recursos Cloudflare, no cargan secretos reales y no conceden `production_authority` ni `catalog_accepted`.

## Fronteras implementadas

- JSON canónico, SHA-256 y base64url canónico;
- Ed25519 para receipts v2;
- verificación RS256 del OIDC de GitHub;
- issuer, audience, expiración, `nbf`, `iat`, `jti`, repo, repository ID, ref, workflow, environment, event, commit, run y attempt;
- JWKS únicamente desde `https://token.actions.githubusercontent.com/.well-known/jwks`;
- caché corta del JWKS y refresh ante un `kid` desconocido;
- política OIDC y hash GraphQL fijados en código, no elegibles por el caller;
- URL GET de La Colonia con scheme/host/path/params/variables cerrados;
- `hideUnavailableItems=false`, `skusFilter=ALL`, orden allowlisted y página <= 50;
- ledger durable con presupuesto, expiración, pacing mínimo de 1.5 s, replay e idempotencia;
- single-flight: como máximo una reserva física en vuelo por autorización;
- Durable Object SQLite mediante `ctx.storage.kv` y `transactionSync`;
- replay con bytes persistidos, SHA-256, firma Ed25519 y `evidence_id` revalidados antes de responder;
- runtime físico fail-closed para redirect, HTTP != 200, HTML, body vacío/sobredimensionado y firma inválida;
- router público autenticado antes de seleccionar el Durable Object;
- fence adicional entre el nombre del Durable Object y `authorization_id`;
- fence entre autorización y el par real `run_id:run_attempt` del token OIDC;
- preflight del par Ed25519 antes de permitir que un request llegue a reserva/fetch;
- release del collector ligado a `CF_VERSION_METADATA.id`.

## Contrato público preparado

El Worker sólo acepta:

- `POST /v1/initialize`
- `POST /v1/execute`

Ambas rutas requieren `Authorization: Bearer <GitHub OIDC JWT>`, `Content-Type: application/json`, body acotado y sin query string.

La identidad OIDC admitida queda fijada a:

- repositorio: `Jchernand3z19/Portafolio`;
- repository ID: `1282475205`;
- ref: `refs/heads/main`;
- workflow: `.github/workflows/precios-supermercados-sps-la-colonia-live.yml@refs/heads/main`;
- environment: `la-colonia-live`;
- evento: `workflow_dispatch`;
- audience: `urn:precios-sps:cloudflare:collector:v1`.

El campo lógico `runId` de la autorización y de cada request debe ser exactamente:

```text
<GITHUB_RUN_ID>:<GITHUB_RUN_ATTEMPT>
```

Un rerun (`run_attempt` distinto) o cualquier otro workflow run no puede consumir el presupuesto de una autorización anterior.

El caller **no puede** enviar ni sustituir:

- el hash esperado de la query GraphQL;
- repo/ref/workflow/environment/audience;
- collector principal/release/code SHA;
- signing key ID;
- pacing por debajo de 1.5 s.

## Configuración Cloudflare declarada

`wrangler.json` define:

- Worker `precios-sps-provenance`;
- entrypoint `src/index.mjs`;
- Durable Object `AuthorizationGateway`;
- storage SQLite mediante `exports` declarativo;
- binding `AUTHORIZATION_GATEWAY`;
- version metadata `CF_VERSION_METADATA`;
- preview URLs deshabilitadas.

Secret bindings requeridos, **sin valores en Git**:

- `EDGE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL`
- `EDGE_RECEIPT_PUBLIC_KEY_SPKI_B64URL`
- `EDGE_COLLECTOR_CODE_SHA256`

La clave privada de receipt debe existir únicamente en Cloudflare. No se debe copiar a GitHub Secrets: el collector debe seguir siendo una autoridad separada del caller.

## Validación offline

No hay dependencias npm de runtime. La suite Node usa APIs estándar de Node 22+ y Web Crypto. `pytest` ejecuta también la suite Node y valida de forma cruzada:

- URL GraphQL Python -> JavaScript;
- timestamps canónicos Python <-> JavaScript;
- hash fijado en el Worker == SHA-256 de `PRODUCT_SEARCH_QUERY` de Python;
- shape de `wrangler.json`;
- router/JWKS/OIDC/fencing/store/runtime/replay.

## Lo que sigue prohibido o pendiente

- no se ha desplegado el Worker;
- no se han creado Durable Objects remotos;
- no se han creado ni cargado claves reales;
- no se ha solicitado OIDC desde un workflow live;
- no se ha hecho tráfico a La Colonia;
- no existe autorización live humana activa;
- SPS sigue `UNCONFIRMED`;
- el workflow live sigue bloqueado y no debe habilitarse sólo porque este código exista;
- falta integrar y verificar la autoridad productiva completa antes de permitir `catalog_accepted`.
