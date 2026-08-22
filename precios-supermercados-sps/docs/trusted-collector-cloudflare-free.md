# Trusted collector con Cloudflare Workers

Estado: **ARQUITECTURA SELECCIONADA / IMPLEMENTADA OFFLINE / NO DESPLEGADA / NO LIVE**.

> El nombre histórico de este archivo incluye `cloudflare-free` porque la primera evaluación buscaba una alternativa de coste cero. Cloudflare dejó de ser una alternativa experimental: es la ruta de ingeniería seleccionada. El estado canónico general vive en `docs/arquitectura.md` y el cierre productivo en `docs/trusted-collector-productivo.md`.

Este documento conserva el rationale técnico de la selección de Cloudflare. No autoriza tráfico live, no demuestra un despliegue y no cambia por sí solo GATE-06/GATE-18.

## 1. Motivo

La frontera que falta no es capacidad de hacer HTTP: el extractor ya existe. Lo que debe demostrarse productivamente es que una respuesta concreta provino de una solicitud física real y que el caller no pudo fabricar esa evidencia.

La arquitectura seleccionada usa Cloudflare Workers como collector/proxy físico independiente:

1. GitHub Actions presenta identidad OIDC;
2. el Worker valida claims y request canónico;
3. un Durable Object controla presupuesto, pacing, single-flight, replay y fencing;
4. el Worker realiza el `fetch()` HTTPS únicamente al destino productivo allowlisted;
5. lee los bytes exactos de la respuesta y calcula SHA-256;
6. firma un receipt con una private key Ed25519 que sólo debe existir en Cloudflare;
7. devuelve bytes + receipt + firma;
8. Python verifica criptografía y body;
9. un verifier externo reconcilia cada request con Workers Observability.

GitHub puede solicitar una observación autorizada, pero no posee la private key y no puede fabricar por sí solo un receipt productivo válido.

## 2. Capacidad y coste

La selección se hizo buscando una frontera con coste operativo bajo y suficiente capacidad para el proyecto. Los límites/precios de Cloudflare pueden cambiar y deben verificarse antes de un despliegue real; no forman parte de la semántica de seguridad del código.

Referencias oficiales usadas durante el diseño:

- https://developers.cloudflare.com/workers/platform/limits/
- https://developers.cloudflare.com/workers/platform/pricing/
- https://developers.cloudflare.com/workers/runtime-apis/fetch/
- https://developers.cloudflare.com/workers/runtime-apis/web-crypto/
- https://developers.cloudflare.com/workers/configuration/secrets/
- https://developers.cloudflare.com/durable-objects/platform/pricing/

El criterio productivo no es “cabe en el plan Free”, sino que la infraestructura real respete todos los límites de seguridad y falle cerrado si un límite de plataforma impide continuar.

## 3. Arquitectura productiva preparada

```text
GitHub Actions protegido
        |
        | GitHub OIDC
        v
Cloudflare Worker: precios-sps-provenance
        |
        | valida identidad + request
        v
Durable Object: AuthorizationGateway
        |
        | budget / pacing / replay / fencing
        v
fetch HTTPS allowlisted
        |
        v
La Colonia / VTEX
        |
        v
bytes exactos de respuesta
        |
        +--> SHA-256
        +--> receipt v2 Ed25519
        +--> Workers Observability
        |
        v
verificadores Python
        |
        v
manifest estructural / catálogo
        |
        v
readiness técnica
```

La última salida sigue sin ser autoridad productiva mientras no exista evidencia de un despliegue real.

## 4. Transporte canónico de La Colonia

El extractor versionado construye una consulta **GET** a:

```text
https://www.lacolonia.com/_v/segment/graphql/v1
```

La implementación productiva fija y valida:

```text
scheme: https
host: www.lacolonia.com
path: /_v/segment/graphql/v1
method: GET
redirect: manual + reject 3xx
```

También valida operación/query/variables permitidas, `hideUnavailableItems=false`, `skusFilter=ALL`, órdenes allowlisted y ventanas dentro de límites. No reenvía cookies, Authorization, GPS, dirección ni otros datos personales del caller.

El allowlist productivo **no se amplía para hacer pruebas**.

## 5. Autenticación del controller

El Worker productivo exige un token OIDC emitido por GitHub Actions con identidad fijada en código. Entre los claims relevantes están:

```text
iss == https://token.actions.githubusercontent.com
aud == urn:precios-sps:cloudflare:collector:v1
repository == Jchernand3z19/Portafolio
repository_id == 1282475205
ref == refs/heads/main
workflow_ref == workflow live canónico en main
environment == la-colonia-live
event_name == workflow_dispatch
sha == commit aprobado
```

También se validan firma JWT, `kid`, `exp`, `nbf`, `iat`, `jti`, `run_id` y `run_attempt` según el contrato implementado.

OIDC no sustituye la autorización humana para live. El workflow live sigue globalmente bloqueado mientras no exista una autorización explícita vigente.

## 6. Receipt físico v2

La forma canónica se mantiene en los contratos edge del proyecto. Cada receipt liga, entre otros:

```text
schema_version
run_id
request_id
reservation_id
authorization_id
approved_commit_sha
request_digest
traversal_id / traversal_role
order_by / partition_id / from_index / to_index
http_method / target_scheme / target_host / target_path
canonical_request_sha256
raw_response_sha256
response_status / response_body_bytes
physical_started_at_utc / response_completed_at_utc
github_repository / repository_id / ref / workflow_ref / environment
github_run_id / run_attempt
oidc_subject / oidc_jti
collector_provider / collector_principal / collector_execution
collector_release_id / collector_code_sha256
signing_algorithm / signing_key_id
nonce
```

La respuesta se verifica contra su hash antes de convertirse en evidencia de catálogo.

`physical_provenance.py` v1 conserva un prototipo anterior y no es el contrato nuevo para la ruta productiva Cloudflare.

## 7. Clave de firma

La private key Ed25519 se guarda como **Worker Secret**, nunca como `vars`, archivo de repositorio, GitHub Secret, log o artefacto.

La public key puede distribuirse al verifier. `signing_key_id` versiona la confianza y permite rotación sin reescribir evidencia histórica.

Una firma válida demuestra integridad/autenticidad respecto de la clave; no demuestra por sí sola que el request físico ocurrió ni concede `production_authority`.

## 8. Durable Object

`AuthorizationGateway` usa almacenamiento SQLite y serializa la ejecución autorizada.

Reglas implementadas offline incluyen:

- presupuesto cerrado;
- deadline/expiración;
- reservas one-shot;
- unicidad de request/reservation/nonce;
- pacing mínimo;
- single-flight;
- replay idempotente sin refetch físico;
- fencing por autorización y por `run_id:run_attempt` OIDC;
- error de estado => deny, nunca bypass directo;
- ruta canónica con `max_retries = 0`.

## 9. Workers Observability

Una firma del mismo Worker no se considera evidencia física suficiente. La segunda evidencia proviene de Workers Observability y se consulta desde fuera del collector.

El proyecto ya implementa offline:

- custom spans versionados;
- atributos de correlación;
- parsers/verifiers de telemetría;
- reconciliación exacta de request/receipt/evidence IDs;
- release/commit/run/target/status/timestamps;
- identidad exacta entre la página criptográfica y la observación reconciliada;
- manifest completo del run.

La especificación detallada está en `docs/cloudflare-tracing-provenance.md`.

## 10. Structural discovery y catálogo

La cadena offline ya no termina en el receipt individual.

### Structural discovery

```text
plan estructural
-> gateway edge
-> receipt firmado
-> body validado
-> Workers Observability
-> VerifiedStructuralDiscovery
```

### Catálogo

```text
VerifiedStructuralDiscovery
-> canonical_authenticated_provenance_plan
-> VerifiedCatalogEdgeCollector
-> receipt/body verificados por página
-> Workers Observability por página
-> VerifiedCatalogProvenanceFinalizer
-> manifest del run
-> CatalogAcceptanceReadiness
```

El caller no elige URL, page size, orden, traversal IDs ni particiones canónicas arbitrarias en esa ruta.

## 11. Readiness técnica no es autoridad

La cadena puede alcanzar offline:

```text
technical_catalog_complete = true
ready_for_productive_authority_evidence = true
catalog_accepted = false
production_authority = false
```

El reason `trusted_collector_provenance_unavailable` permanece obligatorio hasta evidencia productiva real.

No se aceptan como sustituto:

- `trusted=true`;
- `provenance_ok=true`;
- un `catalog_accepted=true` del caller;
- markers/archivos/comentarios;
- HMAC local;
- receipt firmado únicamente en pruebas offline.

## 12. Amenazas y controles

| Amenaza | Control |
|---|---|
| caller inventa autoridad | no existe un parámetro productivo que la conceda |
| caller fabrica receipt | no posee private signing key |
| PR malicioso invoca Worker | OIDC exige identidad productiva exacta |
| replay | Durable Object + IDs/nonces únicos |
| ejecución reutilizada | fencing run/attempt + estado durable |
| destino arbitrario | host/path/método productivos allowlisted |
| redirect | `redirect: manual` + 3xx fail-closed |
| GraphQL arbitrario | operación/query/variables validadas |
| response modificada | hash firmado + verificación de body |
| primary sustituye reconciliation | traversals/evidencias independientes y manifest exacto |
| pérdida de estado | Durable Object error => deny |
| observability ausente/inconsistente | no existe provenance productiva aceptable |

## 13. Sonda controlada antes de La Colonia

Cloudflare debe probarse físicamente primero contra un origen propio **no-La-Colonia**.

PR #84 prepara una sonda separada con:

- Worker de origen controlado;
- gateway de sonda independiente;
- Durable Object `ProbeLedger` independiente;
- environment `cloudflare-probe`;
- audience OIDC exclusiva;
- llaves Ed25519 y signing key ID distintos;
- schema `probe-1` y dominio criptográfico distintos;
- origen fijado por binding Cloudflare, nunca por input del caller;
- sólo HTTPS `*.workers.dev` y path exacto;
- rechazo de La Colonia antes de cualquier fetch.

Su CI está verde, pero mientras #84 siga fuera de `main` se clasifica `READY_TO_INTEGRATE`, no como infraestructura disponible.

Un receipt de sonda no verifica como receipt productivo y nunca concede `catalog_accepted`.

## 14. Pruebas obligatorias

### Offline

Ya se exige en CI, entre otros:

- canonicalización Worker ↔ Python;
- Ed25519 válido/inválido;
- body/receipt alterado rechazado;
- OIDC/JWKS claims incorrectos rechazados;
- host/path/method fuera de allowlist rechazados;
- redirect fail-closed;
- duplicate nonce/request/reservation rechazado;
- presupuesto/replay/fencing;
- Workers Observability y sustitución de evidencia;
- manifests completos;
- `production_authority=false` en fronteras offline.

### Edge sin La Colonia

Pendiente externamente:

1. integrar la sonda preparada;
2. desplegar origen controlado;
3. generar llaves exclusivas de sonda y guardar private key sólo en Cloudflare;
4. desplegar gateway/DO de sonda;
5. ejecutar OIDC real desde el workflow manual;
6. comprobar version metadata, firma, replay y observability reales;
7. confirmar **0 requests a La Colonia**.

### Live La Colonia

Requiere una nueva autorización humana explícita. Primero sólo se ejecutará la observación mínima necesaria para resolver SPS. Desplegar Cloudflare o aprobar la sonda no autoriza ese tráfico.

## 15. Estado actual

- Cloudflare: arquitectura seleccionada;
- Worker/DO productivos: implementados offline, no desplegados;
- OIDC/JWKS/Ed25519/replay/fencing: implementados offline;
- Workers Observability: adapters/verifiers implementados offline;
- structural discovery autenticado: implementado offline;
- transporte/finalización de catálogo: implementado offline;
- readiness técnica: implementada offline, sin authority;
- sonda controlada: PR #84 preparado y verde, todavía fuera de `main`;
- Google Cloud: diseño histórico supersedido, no ruta actual;
- tráfico live a La Colonia: 0;
- autorización live activa: ninguna;
- GATE-06: abierto productivamente;
- GATE-18: abierto productivamente;
- SPS: `UNCONFIRMED`.

El siguiente hito externo correcto es probar Cloudflare contra el origen controlado. No se debe contactar La Colonia antes de completar esa frontera y obtener después una autorización humana separada.