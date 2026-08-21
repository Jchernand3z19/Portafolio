# Diseño alternativo — Trusted collector gratuito con Cloudflare Workers

Estado: **DISEÑO SELECCIONADO PARA PROTOTIPO OFFLINE/EDGE, NO DESPLEGADO**.

Este documento define una alternativa sin infraestructura de coste continuo para la provenance física del collector. No autoriza tráfico live, no despliega recursos y no cambia GATE-06/GATE-18.

La arquitectura Google Cloud documentada en `trusted-collector-productivo.md` permanece como fallback de mayor aislamiento operativo. Esta alternativa busca demostrar si el mismo objetivo de seguridad puede lograrse con Cloudflare Workers Free antes de asumir costes de infraestructura.

## 1. Motivo

La frontera que falta no es capacidad de hacer HTTP: el extractor ya existe. Lo que falta es evidencia independiente de que una respuesta concreta provino de una solicitud física real y que el caller no pudo fabricar esa evidencia.

Cloudflare Workers puede actuar como **collector/proxy físico independiente**:

1. el caller no contacta directamente a La Colonia;
2. el Worker recibe una solicitud canónica autorizada;
3. el Worker realiza el `fetch()` HTTPS hacia el origen permitido;
4. el Worker lee los bytes exactos de la respuesta;
5. calcula SHA-256 sobre esos bytes;
6. firma un receipt con una clave privada que sólo existe como Worker Secret;
7. devuelve los bytes originales y el receipt firmado;
8. el repositorio/verifier sólo conoce la clave pública.

A diferencia de un HMAC compartido con GitHub, la clave privada de provenance **no vive en GitHub**. GitHub puede solicitar una observación, pero no puede fabricar una firma válida sin que el Worker la emita.

## 2. Capacidad y coste objetivo

Según documentación oficial de Cloudflare verificada en agosto de 2026:

- Workers Free permite hasta 100,000 requests por día;
- el runtime expone Web Crypto con SHA-256 y Ed25519;
- Durable Objects con backend SQLite están disponibles en Workers Free;
- si se exceden límites del plan Free, las operaciones fallan en vez de convertirse automáticamente en uso ilimitado de pago.

Referencias oficiales:

- https://developers.cloudflare.com/workers/platform/limits/
- https://developers.cloudflare.com/workers/platform/pricing/
- https://developers.cloudflare.com/workers/runtime-apis/fetch/
- https://developers.cloudflare.com/workers/runtime-apis/web-crypto/
- https://developers.cloudflare.com/workers/configuration/secrets/
- https://developers.cloudflare.com/durable-objects/platform/pricing/

La carga esperada del proyecto está muy por debajo del límite diario. Antes de declarar aptitud para un recorrido completo se medirá CPU y consumo real en un origen controlado, sin usar La Colonia.

## 3. Arquitectura

```text
GitHub Actions (controller protegido)
        |
        | GitHub OIDC token
        | Environment humana: la-colonia-live
        v
Cloudflare Worker: provenance-gateway
        |
        | valida OIDC + claims + presupuesto
        | serializa por Durable Object
        v
fetch HTTPS hardcoded/allowlisted
        |
        v
La Colonia / VTEX
        |
        v
Worker lee bytes exactos
        |
        +--> SHA-256(response bytes)
        +--> receipt canónico v2
        +--> firma Ed25519 con Worker Secret
        |
        v
response bytes + receipt + signature
        |
        v
verifier con PUBLIC KEY
        |
        v
reconciliación primary + reconciliation
```

## 4. Transporte canónico de La Colonia

El extractor versionado actual construye una consulta **GET** a:

```text
https://www.lacolonia.com/_v/segment/graphql/v1
```

con `workspace`, `maxAge`, `appsEtag`, `domain`, `locale`, `operationName`, `query` y `variables` en el query string.

Por tanto, el primer gateway Cloudflare debe preservar **GET**. No se cambia a POST por conveniencia arquitectónica porque POST no ha sido validado live dentro de la autorización actual.

La regla productiva inicial será:

```text
scheme: https
host: www.lacolonia.com
path: /_v/segment/graphql/v1
method: GET
redirect: manual + reject 3xx
```

El contrato `edge_provenance.py` admite únicamente GET o POST para mantenerse neutral al proveedor/origen. Eso **no** significa que el caller pueda elegir libremente el método. Cada adapter/gateway productivo debe fijar uno. Para La Colonia, el método actual es GET hasta que una revisión técnica autorizada demuestre lo contrario.

## 5. Autenticación del controller

No se añadirá una API pública que firme cualquier request.

El Worker debe exigir un token OIDC emitido por GitHub Actions y validar como mínimo:

```text
iss == https://token.actions.githubusercontent.com
aud == audiencia dedicada del provenance-gateway
repository == Jchernand3z19/Portafolio
repository_id == 1282475205
ref == refs/heads/main
workflow_ref == workflow live canónico esperado
environment == la-colonia-live
sha == commit aprobado/protegido
event_name == workflow_dispatch durante la fase live manual
```

También se validan `exp`, `nbf`, `iat`, `jti`, firma JWT y `kid` contra el JWKS oficial de GitHub.

GitHub documenta `repository_id`, `ref`, `workflow_ref`, `environment`, `run_id`, `run_attempt` y demás claims dentro del token OIDC. El repositorio fue creado antes del rollout automático de subjects inmutables de julio de 2026, por lo que la política debe basarse además en `repository_id` y no sólo en el texto de `sub`.

El workflow live deberá usar un **GitHub Environment con aprobación humana requerida**. La presencia de OIDC no sustituye la autorización humana.

## 6. Allowlist física y consulta GraphQL

El Worker no acepta URL arbitraria del caller.

La versión inicial fija en código/configuración versionada:

```text
scheme: https
host: www.lacolonia.com
path: /_v/segment/graphql/v1
method: GET
```

El gateway debe construir o validar los parámetros de búsqueda a partir de campos permitidos, no reenviar una URL completa suministrada por el caller.

Controles mínimos:

- `operationName = productSearchV3`;
- query GraphQL equivalente a la consulta versionada en `la_colonia_graphql.py`;
- `hideUnavailableItems = false`;
- `skusFilter = ALL`;
- `orderBy` dentro del allowlist canónico;
- `from` y `to` coherentes con el presupuesto autorizado;
- redirects rechazados;
- no reenvío de cookies, Authorization, GPS, dirección ni otros headers/datos personales del caller.

## 7. Receipt físico v2

La forma canónica vive en `src/precios_supermercados/edge_provenance.py`.

Cada receipt liga al menos:

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

La respuesta se devuelve sin reserializar para que `raw_response_sha256` corresponda exactamente a los bytes consumidos por el crawler.

`physical_provenance.py` v1 conserva el prototipo GCP anterior. No debe convertirse en contrato productivo nuevo; la ruta edge se construye sobre v2.

## 8. Clave de firma

La clave privada Ed25519 se guarda como **Worker Secret**, nunca como `vars`, archivo del repositorio ni GitHub Secret.

La clave pública/verificador sí puede vivir versionada en el repositorio.

Rotación:

- `signing_key_id` incluido en cada receipt;
- varias claves públicas pueden mantenerse durante una ventana de transición;
- una clave revocada nunca acepta receipts nuevos;
- evidencia histórica firmada no se reescribe.

## 9. One-shot / presupuesto / pacing con Durable Object

Un Durable Object SQLite serializa el estado de cada ejecución autorizada.

Estado mínimo:

```text
authorization_id
run_id
approved_commit_sha
created_at
expires_at
max_requests
requests_used
min_start_interval_seconds
last_physical_start
request_digests_used[]
nonces_used[]
state = active | consumed | rejected | expired
```

Reglas:

- presupuesto cerrado antes del primer request;
- ningún request puede incrementarlo;
- cada `request_digest`, `request_id`, `reservation_id` y nonce es único;
- el Durable Object serializa reservas para evitar carreras;
- pacing mínimo se aplica antes del inicio físico;
- al alcanzar presupuesto queda `consumed`;
- al expirar falla cerrado;
- 403/429/captcha/auth/location/redirect inesperado detiene la ejecución según la política de seguridad;
- pérdida/error de Durable Object => deny, nunca bypass directo.

## 10. Flujo por request

1. validar método de entrada y tamaño;
2. verificar JWT OIDC y claims exactos;
3. validar parámetros GraphQL permitidos;
4. construir URL GET canónica;
5. calcular `canonical_request_sha256` y `request_digest`;
6. reservar request en Durable Object;
7. aplicar pacing;
8. hacer exactamente un `fetch` al origen allowlisted con `redirect: manual`;
9. rechazar 3xx y señales stop;
10. leer `ArrayBuffer` de respuesta;
11. SHA-256 de bytes exactos;
12. construir receipt v2;
13. firmarlo con clave privada Worker Secret;
14. cerrar reserva/evidencia en Durable Object;
15. devolver bytes exactos + receipt + firma;
16. el caller verifica firma antes de parsear o usar la evidencia.

Si cualquier paso 8–15 queda incierto, no existe receipt aceptable.

## 11. Formato de retorno

Preferido mientras el receipt permanezca debajo de límites seguros de headers:

```text
HTTP body: bytes exactos de La Colonia
X-PSPS-Receipt: base64url(canonical receipt JSON)
X-PSPS-Signature: base64url(signature)
X-PSPS-Key-Id: versión pública
```

Antes de fijarlo definitivamente se prueba el tamaño máximo. Si crece, se usa un envelope explícito o evidence-id; nunca se trunca silenciosamente.

## 12. Amenazas y controles

| Amenaza | Control |
|---|---|
| caller inventa `trusted=true` | no existe ese parámetro |
| caller fabrica receipt | no posee private signing key |
| PR malicioso invoca Worker | OIDC exige repo ID + main + workflow/environment canónicos |
| replay | nonce/request digest + Durable Object |
| ejecución reutilizada | run/authorization consumidos/expirados |
| destino arbitrario | host/path/method allowlisted |
| redirect | `redirect: manual` + 3xx fail-closed |
| consulta GraphQL arbitraria | operación/query/variables validadas |
| GitHub modifica response | hash firmado deja de coincidir |
| GitHub inventa status/body | receipt firmado cubre status/hash/bytes |
| primary = reconciliation | traversals, orderings, requests y nonces distintos |
| pérdida de estado | Durable Object error => deny |
| límite Free alcanzado | error/deny; no degradar a ruta directa |

## 13. Lo que esta arquitectura NO demuestra

- que Cloudflare sea inmune a compromiso administrativo;
- que la fuente represente específicamente SPS;
- que el catálogo esté completo;
- que el sitio autorice un recorrido full;
- que un receipt firmado sea automáticamente `catalog_accepted`.

SPS sigue `UNCONFIRMED` y la completitud depende de la reconciliación canónica.

## 14. Pruebas obligatorias antes de live

### Offline

- canonicalización Worker ↔ Python idéntica;
- vectores Ed25519 válidos/inválidos;
- response alterada rompe hash;
- receipt alterado rompe firma;
- JWT OIDC inválido o claims incorrectos se rechazan;
- host/path/method fuera de allowlist se rechazan;
- GET canónico de La Colonia se construye exactamente desde variables permitidas;
- POST no se usa para La Colonia sin evidencia/autorización nueva;
- redirect se rechaza;
- duplicate nonce/request digest se rechaza;
- presupuesto agotado se rechaza;
- concurrencia no excede pacing/budget;
- `production_authority` local permanece false.

### Edge sin La Colonia

- desplegar Worker contra origen de prueba controlado;
- comprobar firma sobre bytes exactos;
- comprobar Durable Object/replay;
- comprobar límites/CPU del plan Free;
- comprobar OIDC real de GitHub contra el Worker.

### Live

Requiere autorización humana explícita nueva. Primero sólo observación mínima. Ningún full crawl se habilita por desplegar el Worker.

## 15. Criterio de preferencia frente a GCP

Cloudflare pasa a ser ruta preferida sólo si las pruebas offline + edge demuestran:

```text
coste = 0 dentro del plan Free
firma asimétrica independiente = PASS
OIDC main/environment = PASS
one-shot/budget/pacing = PASS
response hash físico = PASS
redirect/allowlist fail-closed = PASS
sin bypass directo aceptable = PASS
```

Si cualquiera falla, la arquitectura GCP permanece como fallback y GATE-06/GATE-18 siguen cerrados.

## 16. Estado actual

- diseño: definido;
- contrato Python v2 provider-neutral: implementado offline;
- transporte canónico La Colonia: GET, documentado desde código versionado;
- Worker: no implementado todavía;
- Cloudflare account/deploy: no configurado;
- Google Cloud: proyecto creado, Billing no activado por prepago requerido;
- tráfico live: 0;
- autorización live activa: ninguna;
- GATE-06: abierto;
- GATE-18: fail-closed;
- SPS: `UNCONFIRMED`.
