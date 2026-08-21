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

A diferencia de un HMAC compartido con GitHub, la clave privada de provenance **no vive en GitHub**. Por tanto, GitHub puede solicitar una observación, pero no puede fabricar una firma válida sin que el Worker la emita.

## 2. Capacidad y coste objetivo

Según la documentación oficial de Cloudflare verificada en agosto de 2026:

- Workers Free permite hasta 100,000 requests por día;
- cada invocación Free dispone de 10 ms de CPU;
- cada invocación permite hasta 50 subrequests externos;
- el cuerpo de respuesta no tiene un límite de tamaño impuesto por Workers;
- el runtime expone Web Crypto con `SHA-256`, ECDSA y Ed25519;
- Durable Objects con backend SQLite están disponibles en Workers Free;
- al exceder límites del plan Free, las operaciones fallan en lugar de convertirse automáticamente en uso ilimitado de pago.

Referencias oficiales:

- https://developers.cloudflare.com/workers/platform/limits/
- https://developers.cloudflare.com/workers/platform/pricing/
- https://developers.cloudflare.com/workers/runtime-apis/fetch/
- https://developers.cloudflare.com/workers/runtime-apis/web-crypto/
- https://developers.cloudflare.com/workers/configuration/secrets/
- https://developers.cloudflare.com/durable-objects/platform/pricing/

La carga esperada del proyecto está varios órdenes de magnitud por debajo del límite diario. La validación productiva deberá medir CPU real antes de declarar que el plan Free basta para el recorrido completo.

## 3. Arquitectura

```text
GitHub Actions (controller protegido)
        |
        | GitHub OIDC token
        | environment humana: la-colonia-live
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
        +--> receipt canónico
        +--> firma asimétrica con Worker Secret
        |
        v
response bytes + receipt + signature
        |
        v
verifier local/productivo con PUBLIC KEY
        |
        v
SignedPhysicalReceipt
        |
        v
reconciliación primary + reconciliation
```

## 4. Autenticación del controller

No se añadirá una API pública que firme cualquier request.

El Worker debe exigir un token OIDC emitido por GitHub Actions y validar, como mínimo:

```text
iss == https://token.actions.githubusercontent.com
aud == valor dedicado para provenance-gateway
repository == Jchernand3z19/Portafolio
ref == refs/heads/main
sha == commit aprobado/protegido
workflow_ref == workflow live canónico esperado
environment == la-colonia-live
```

El workflow live deberá usar un **GitHub Environment con aprobación humana requerida**. El job sólo obtiene el token y los secretos después de esa aprobación. Esto convierte cada ejecución live en una acción humana observable y evita que un PR o comentario sea autoridad.

El Worker también valida expiración (`exp`), not-before (`nbf`) y subject/actor esperados según la política final.

## 5. Allowlist física

El Worker no acepta URL arbitraria del caller.

La versión inicial fija en código/configuración versionada:

```text
scheme: https
host: www.lacolonia.com
path: /_v/segment/graphql/v1
method: POST
redirects: reject/fail-closed
```

Cualquier host, esquema, path o método distinto se rechaza antes del `fetch`.

No se reenvían cookies, tokens de sesión, GPS, dirección, auth headers ni datos personales suministrados por el caller.

## 6. Receipt físico

El Worker debe generar un receipt compatible con `physical_provenance.py`, ligando como mínimo:

```text
schema_version
run_id
request_id
reservation_id
authorization_id
approved_commit_sha
immutable_image_digest/requested code identity
request_digest
traversal_id
traversal_role
order_by
partition_id
from_index
to_index
http_method
target_scheme
target_host
target_path
canonical_request_sha256
raw_response_sha256
response_status
response_body_bytes
physical_started_at_utc
response_completed_at_utc
collector_execution
nonce
key_version
```

Para la variante Cloudflare, `collector_service_account` del contrato GCP no se reutiliza literalmente como identidad falsa. Antes de integrar el adapter productivo, el contrato de provenance deberá versionarse o añadir una identidad de runtime neutral (`collector_principal`) fuera de los contratos protegidos `RawProduct`, `NormalizedOffer`, `ValidatedOffer`.

La firma cubre el receipt canónico completo. La respuesta se devuelve sin reserializar para que `raw_response_sha256` corresponda exactamente a los bytes consumidos por el crawler.

## 7. Clave de firma

La clave privada asimétrica se guarda como **Worker Secret**, nunca como `vars`, archivo del repositorio ni GitHub Secret.

La clave pública/verificador sí puede vivir versionada en el repositorio.

Algoritmo candidato:

```text
Ed25519
```

Cloudflare Workers soporta `sign()`/`verify()` para Ed25519 mediante Web Crypto. La elección final se congela con vectores de prueba cruzados Worker ↔ verifier antes de deploy.

Rotación:

- `key_id`/versión incluida en cada receipt;
- varias claves públicas pueden mantenerse durante una ventana de transición;
- una clave revocada nunca vuelve a aceptar receipts nuevos;
- no se reescribe evidencia histórica ya firmada.

## 8. One-shot / presupuesto / pacing con Durable Object

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

- `max_requests` cerrado antes del primer request;
- ningún request puede incrementar el presupuesto;
- cada `request_digest` y nonce es único;
- el Durable Object serializa reservas para evitar carreras;
- mínimo 1.5 s entre inicios físicos mientras ese pacing siga siendo la política canónica;
- al alcanzar presupuesto, queda `consumed`;
- al expirar, falla cerrado;
- un 403/429/captcha/auth/location/redirect inesperado detiene la ejecución y marca el estado no reutilizable según la política de seguridad.

El Worker Free dispone de Durable Objects SQLite dentro de límites gratuitos. La validación previa al live debe confirmar que el consumo esperado queda dentro del plan Free.

## 9. Flujo por request

1. validar método de entrada y tamaño;
2. verificar JWT OIDC y claims exactos;
3. calcular request canónico y `request_digest`;
4. reservar request en Durable Object;
5. esperar/rechazar según pacing sin exceder la ventana autorizada;
6. hacer exactamente un `fetch` al host/path allowlisted;
7. rechazar redirects y señales stop;
8. leer `ArrayBuffer` de respuesta;
9. SHA-256 de bytes exactos;
10. construir receipt;
11. firmar receipt con clave privada Worker Secret;
12. cerrar reserva en Durable Object;
13. devolver bytes exactos + receipt + firma;
14. el caller verifica firma antes de parsear/usar la evidencia.

Si cualquier paso 6–13 queda incierto, no existe receipt aceptable.

## 10. Formato de retorno

Preferido para no alterar los bytes del origen:

```text
HTTP body: bytes exactos de La Colonia
X-PSPS-Receipt: base64url(canonical receipt JSON)
X-PSPS-Signature: base64url(signature)
X-PSPS-Key-Id: versión pública
```

Antes de fijar esta forma se debe comprobar el tamaño máximo del receipt respecto a límites de headers. Si la evidencia crece, se usa un envelope multipart o una segunda respuesta de evidence-id; nunca se trunca silenciosamente.

## 11. Amenazas y controles

| Amenaza | Control |
|---|---|
| caller inventa `trusted=true` | no existe ese parámetro |
| caller fabrica receipt | no posee private signing key |
| PR malicioso invoca Worker | OIDC exige `main` + workflow/environment canónicos |
| replay de receipt | nonce/request digest + Durable Object |
| replay de ejecución | run/authorization consumidos/expirados |
| destino arbitrario | host/path/method allowlisted en Worker |
| redirect a otro host | redirects fail-closed |
| Worker devuelve evidencia sin request | implementación sólo firma después de `fetch` + hash de bytes; pruebas negativas obligatorias |
| GitHub modifica response | hash firmado deja de coincidir |
| GitHub inventa status/body | receipt firmado cubre status/hash/bytes |
| primary=reconciliation | traversals, requests, nonces y receipts distintos |
| pérdida de estado | Durable Object ausente/error => deny |
| límite Free alcanzado | error/deny; no degradar a ruta directa |

## 12. Lo que esta arquitectura NO demuestra por sí sola

- que Cloudflare sea inmune a compromiso de cuenta/administrador;
- que la fuente represente específicamente SPS;
- que el catálogo esté completo;
- que el sitio autorice un recorrido full;
- que un receipt firmado sea automáticamente `catalog_accepted`.

SPS sigue `UNCONFIRMED` y la completitud sigue dependiendo de la reconciliación canónica.

## 13. Pruebas obligatorias antes de live

### Offline

- canonicalización Worker ↔ Python produce bytes idénticos;
- vectores Ed25519 válidos/inválidos;
- response alterada rompe hash;
- receipt alterado rompe firma;
- OIDC con repo/ref/workflow/environment incorrectos se rechaza;
- URL/host/path/method fuera de allowlist se rechaza;
- redirect se rechaza;
- duplicate nonce/request digest se rechaza;
- presupuesto agotado se rechaza;
- concurrencia no excede pacing/budget;
- `production_authority` del modelo local permanece false.

### Edge sin La Colonia

- desplegar Worker con origen de prueba controlado;
- comprobar firma sobre bytes exactos;
- comprobar Durable Object/replay;
- comprobar límites/CPU del plan Free;
- comprobar que GitHub sólo entra mediante OIDC esperado.

### Live

Requiere autorización humana explícita nueva. Primero sólo una observación mínima. Ningún full crawl se habilita por el mero hecho de desplegar el Worker.

## 14. Criterio para preferir Cloudflare frente a GCP

Cloudflare pasa a ser la ruta preferida únicamente si las pruebas offline + edge demuestran simultáneamente:

```text
coste = 0 dentro del plan Free
firma asimétrica independiente = PASS
OIDC main/environment = PASS
one-shot/budget/pacing = PASS
response hash físico = PASS
redirect/allowlist fail-closed = PASS
sin bypass directo aceptable = PASS
```

Si cualquiera falla, se conserva la arquitectura GCP como fallback y GATE-06/GATE-18 permanecen cerrados.

## 15. Estado actual

- diseño: definido;
- código de contratos Python: disponible en `physical_provenance.py`;
- Worker: no implementado todavía;
- Cloudflare account/deploy: no configurado;
- tráfico live: 0;
- autorización live activa: ninguna;
- GATE-06: abierto;
- GATE-18: fail-closed;
- SPS: `UNCONFIRMED`.
