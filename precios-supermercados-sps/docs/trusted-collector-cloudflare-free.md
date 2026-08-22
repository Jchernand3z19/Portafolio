# Trusted collector con Cloudflare Workers

Estado: **ARQUITECTURA SELECCIONADA / IMPLEMENTADA OFFLINE / SONDA READY_FOR_EXTERNAL_DEPLOYMENT / NO LIVE LA-COLONIA**.

> El nombre histórico de este archivo incluye `cloudflare-free` porque la primera evaluación buscaba una alternativa de coste bajo/cero. Cloudflare dejó de ser una alternativa experimental: es la ruta de ingeniería seleccionada. El estado canónico vive en `docs/arquitectura.md`, el cierre productivo en `docs/trusted-collector-productivo.md` y la primera prueba externa en `docs/cloudflare-controlled-probe-runbook.md`.

Este documento conserva el rationale técnico. No autoriza tráfico live a La Colonia ni convierte código offline en autoridad productiva.

## 1. Motivo

La frontera que falta no es capacidad de hacer HTTP. Debe demostrarse productivamente que una respuesta concreta provino de una solicitud física real y que el caller no pudo fabricar o sustituir la evidencia.

La arquitectura seleccionada usa Cloudflare Workers como collector físico independiente:

1. GitHub Actions presenta identidad OIDC;
2. el Worker valida claims y request canónico;
3. Durable Object controla presupuesto, pacing, single-flight, replay y fencing;
4. el Worker realiza un `fetch()` sólo al destino allowlisted;
5. lee los bytes exactos y calcula SHA-256;
6. firma un receipt con private key Ed25519 alojada sólo en Cloudflare;
7. Python verifica firma/body/contexto con public key confiable;
8. un verifier externo consulta Workers Observability;
9. receipt y telemetría deben reconciliar uno a uno.

Una firma del mismo Worker es necesaria, pero no se trata como prueba física suficiente sin evidencia independiente de plataforma.

## 2. Arquitectura productiva preparada

```text
GitHub Actions protegido
        |
        | GitHub OIDC
        v
Cloudflare Worker: precios-sps-provenance
        |
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
        +--> bytes exactos + SHA-256
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

La salida continúa sin autoridad productiva mientras Worker/DO/llaves/spans no hayan sido observados en un despliegue real válido.

## 3. Transporte productivo de La Colonia

El extractor versionado construye una consulta **GET** a:

```text
https://www.lacolonia.com/_v/segment/graphql/v1
```

El Worker productivo fija:

```text
scheme: https
host: www.lacolonia.com
path: /_v/segment/graphql/v1
method: GET
redirect: manual + reject 3xx
```

También valida operación/query/variables, `hideUnavailableItems=false`, `skusFilter=ALL`, órdenes allowlisted y ventanas dentro de límites.

El allowlist productivo **no se amplía para hacer pruebas**.

## 4. Identidad GitHub/OIDC

La política productiva exige identidad fija, entre otros:

```text
iss = https://token.actions.githubusercontent.com
aud = urn:precios-sps:cloudflare:collector:v1
repository = Jchernand3z19/Portafolio
repository_id = 1282475205
ref = refs/heads/main
workflow_ref = workflow live canónico en main
environment = la-colonia-live
event_name = workflow_dispatch
sha/run_id/run_attempt = ejecución real
```

OIDC no sustituye la autorización humana de La Colonia.

## 5. Receipt y clave

El receipt productivo v2 liga autorización, run, request/reservation, commit, traversal/partition/window, request digest, target, response SHA/status/size, tiempos, identidad GitHub, collector release/code SHA, key ID y nonce.

La private key Ed25519 productiva sólo puede vivir en Cloudflare. GitHub recibe únicamente material público necesario para verificar.

`physical_provenance.py` v1 es un prototipo histórico y no es el contrato vigente de Cloudflare.

## 6. Durable Object

`AuthorizationGateway` implementa offline:

- presupuesto cerrado;
- expiración/deadline;
- reservas one-shot;
- unicidad de request/reservation/nonce;
- pacing;
- single-flight;
- replay idempotente sin refetch;
- fencing por autorización y `run_id:run_attempt` OIDC;
- almacenamiento SQLite;
- error de estado => deny;
- ruta canónica con `max_retries=0`.

## 7. Workers Observability

La segunda evidencia proviene de Workers Observability y se consulta fuera del collector.

La ruta productiva ya tiene offline:

- custom spans versionados;
- atributos de correlación;
- parsers/verifiers de telemetría;
- release/commit/run/target/status/timestamps;
- reconciliación exacta con receipt/página;
- identidad exacta entre página criptográfica y observación;
- manifest completo del run.

La especificación detallada está en `docs/cloudflare-tracing-provenance.md`.

## 8. Structural discovery y catálogo

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
-> receipt/body por página
-> Workers Observability por página
-> VerifiedCatalogProvenanceFinalizer
-> manifest exacto del run
-> CatalogAcceptanceReadiness
```

El caller no elige URL, page size, orden, traversal IDs o particiones canónicas arbitrarias.

## 9. Readiness no es autoridad

La cadena puede alcanzar offline:

```text
technical_catalog_complete = true
ready_for_productive_authority_evidence = true
catalog_accepted = false
production_authority = false
```

`trusted_collector_provenance_unavailable` permanece hasta evidencia productiva real.

No se aceptan sustitutos como `trusted=true`, `provenance_ok=true`, un booleano caller-controlled, markers, comentarios, HMAC local o receipts únicamente simulados.

## 10. Sonda controlada antes de La Colonia

La sonda no-La-Colonia está integrada offline mediante PR #84, #88 y #89.

```text
GitHub workflow manual
-> environment/audience cloudflare-probe
-> Worker precios-sps-controlled-probe
-> ProbeLedger
-> custom span obligatorio
-> Worker precios-sps-controlled-origin (*.workers.dev)
-> challenge/body exactos
-> receipt Ed25519 probe-1
-> verifier separado sin OIDC
-> Workers Observability
-> custom span único + child fetch único
-> PlatformReconciledControlledProbe
```

Separaciones:

- Workers y DO distintos de producción;
- llaves/key ID distintos;
- audience/environment distintos;
- schema/dominio criptográfico distintos;
- caller sin origin URL;
- destino sólo HTTPS `*.workers.dev` y path exacto;
- La Colonia rechazada antes del fetch;
- job OIDC sin checkout;
- job verificador sin `id-token: write`;
- Observability token separado;
- toda salida mantiene autoridad falsa.

La sonda también verifica fuera del Worker:

- firma Ed25519;
- body/hash/tamaño;
- request canónico;
- evidence ID;
- repo/ref/workflow/environment/commit/run/attempt;
- DO name;
- target.

Después reconcilia Workers Observability:

- exactamente un trace de sonda;
- exactamente un custom span;
- exactamente un child `fetch`;
- URL/método/status/body size exactos;
- script version coherente con receipt;
- timestamps compatibles.

Estado:

```text
code = DONE_OFFLINE
CI PR #89 = 1231/1231 PASS + compileall
deploy = NOT_DONE
physical run = NOT_DONE
La Colonia requests = 0
```

## 11. Prueba externa de sonda

El procedimiento completo vive en `docs/cloudflare-controlled-probe-runbook.md`.

Orden resumido:

1. conectar/configurar cuenta Cloudflare;
2. desplegar `precios-sps-controlled-origin`;
3. generar par Ed25519 exclusivo de sonda;
4. guardar private key sólo en Cloudflare;
5. desplegar `precios-sps-controlled-probe` + `ProbeLedger`;
6. configurar Environment GitHub `cloudflare-probe`;
7. ejecutar manualmente una sola sonda sobre `main`;
8. exigir PASS criptográfico + PASS Workers Observability;
9. confirmar La Colonia = **0 requests**.

Un PASS de sonda sólo valida la infraestructura de sonda. No cierra GATE-06/GATE-18 ni confirma SPS.

## 12. Amenazas principales

| Amenaza | Control |
|---|---|
| caller inventa autoridad | no existe parámetro que la conceda |
| caller fabrica receipt | no posee private signing key |
| PR malicioso invoca Worker productivo | OIDC exige identidad exacta |
| replay | Durable Object + IDs/nonces únicos |
| destino arbitrario productivo | host/path/método allowlisted |
| destino arbitrario de sonda | sólo binding Cloudflare `*.workers.dev` |
| redirect | `redirect: manual` + fail-closed |
| respuesta modificada | hash + firma + body verification |
| Worker afirma fetch inexistente | Workers Observability externo obligatorio |
| trace sustituido | correlación exacta + unicidad |
| primary sustituye reconciliation | traversals/evidencias independientes |
| pérdida de estado | DO error => deny |
| observability ausente | no existe evidencia aceptable |

## 13. Fuentes de plataforma

Los límites/precios de Cloudflare pueden cambiar y se revalidan antes del despliegue. El código no depende de que un plan sea gratuito para su semántica de seguridad.

Documentación oficial relevante:

- Workers/Wrangler configuration;
- Workers secrets y `secrets.required`;
- Durable Objects;
- Version Metadata;
- Workers Observability/traces;
- Workers Observability telemetry query API.

## 14. Estado final de esta fase

```text
Cloudflare architecture = SELECTED
product worker/DO = DONE_OFFLINE / NOT_DEPLOYED
controlled probe = DONE_OFFLINE / READY_FOR_EXTERNAL_DEPLOYMENT
productive authority = false
catalog_accepted = false
GATE-06 = OPEN_PRODUCTIVE
GATE-18 = OPEN_PRODUCTIVE
SPS = UNCONFIRMED
ACTIVE_AUTHORIZATION_IDS = []
La Colonia live requests = 0
```

El siguiente hito es la prueba física de sonda controlada. No existe motivo técnico para contactar La Colonia antes de completarla.
