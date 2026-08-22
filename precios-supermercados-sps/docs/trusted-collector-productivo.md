# Trusted collector productivo — arquitectura Cloudflare vigente

Estado: **IMPLEMENTACIÓN OFFLINE AVANZADA / SONDA CONTROLADA COMPLETA OFFLINE / NO DESPLEGADA / SIN AUTORIDAD PRODUCTIVA**.

Este documento describe la ruta vigente para cerrar provenance física del collector. **No autoriza tráfico live a La Colonia.** La fuente canónica de estado general sigue siendo `docs/arquitectura.md`.

El procedimiento reproducible para la primera prueba externa está en `docs/cloudflare-controlled-probe-runbook.md`.

## Diseño histórico supersedido

La propuesta anterior basada en **Cloud Run + VPC + Secure Web Proxy + Cloud Logging + Cloud KMS** queda **SUPERSEDED**. Fue una alternativa de diseño, no infraestructura desplegada, y ya no debe usarse como descripción de la arquitectura actual ni como condición obligatoria para cerrar los gates.

La ruta activa de ingeniería es:

**Cloudflare Workers + Durable Objects + GitHub OIDC + Ed25519 + Workers Observability.**

## 1. Problema que debe resolver

La aceptación canónica añade deliberadamente:

```text
trusted_collector_provenance_unavailable
```

porque datos, labels, digests o booleanos producidos por el mismo caller no demuestran por sí solos una solicitud física independiente.

La frontera productiva debe demostrar de forma fail-closed que:

1. un runtime externo autorizado realizó el request físico;
2. el caller no eligió arbitrariamente destino, request o identidad de ejecución;
3. la respuesta consumida corresponde exactamente a ese request;
4. la identidad GitHub autorizada está ligada a repo/ref/workflow/environment/commit/run;
5. receipt, respuesta cruda y observability reconcilian uno a uno;
6. replay o sustitución de evidencia no puede crear otra solicitud válida;
7. primary/reconciliation representan evidencias físicas independientes;
8. ausencia o inconsistencia de evidencia mantiene la aceptación cerrada.

## 2. Arquitectura vigente

```text
GitHub Actions en main protegido
        |
        | GitHub OIDC
        v
Cloudflare Worker productivo
        |
        | auth + request validation
        v
Durable Object AuthorizationGateway
        |
        | budget / pacing / single-flight / replay / fencing
        v
request físico exacto permitido
        |
        v
respuesta cruda
        |
        +-> SHA-256
        +-> receipt Ed25519
        +-> Workers Observability span
        |
        v
verificadores Python
        |
        +-> firma/public key
        +-> body exacto
        +-> request/receipt/run binding
        +-> observability reconciliation
        v
manifest estructural / catálogo
        |
        v
readiness técnica
```

La última salida **no** es autoridad productiva mientras Worker/DO/llaves/spans no hayan sido observados en un despliegue real autorizado.

## 3. Worker productivo

La implementación vive en `edge/cloudflare/`.

Política cerrada actual:

- repo: `Jchernand3z19/Portafolio`;
- repository ID fijo;
- ref: `refs/heads/main`;
- workflow productivo fijado en código;
- environment: `la-colonia-live`;
- event: `workflow_dispatch`;
- audience propia del collector;
- destino GraphQL de La Colonia fijado por código;
- método, path, parámetros y variables relevantes validados;
- órdenes permitidas cerradas;
- página máxima 50;
- pacing mínimo 1.5 s;
- ruta canónica con `max_retries = 0`.

El caller no puede sustituir repo/ref/workflow/environment/audience, host/path, hash GraphQL, collector release, signing key ID, orden arbitrario ni IDs canónicos de traversal.

## 4. Durable Object

`AuthorizationGateway` implementa la frontera durable de ejecución:

- presupuesto de requests;
- expiración/deadline;
- reservas one-shot;
- single-flight;
- pacing;
- replay idempotente;
- fencing por autorización y por `run_id:run_attempt` real del OIDC;
- persistencia SQLite;
- recuperación de bytes/evidencia ya completados sin repetir fetch físico.

Una respuesta `WAIT`, `DENY`, estado fallido o evidencia inconsistente no habilita retry oculto.

## 5. Receipt Ed25519

El Worker productivo emite receipts v2 con dominio criptográfico versionado. El receipt liga como mínimo:

- autorización/run/request/reservation;
- commit aprobado;
- traversal/role/order/partition/ventana;
- request digest y request canónico;
- target scheme/host/path;
- SHA-256 de respuesta cruda, status y tamaño;
- tiempos físicos;
- repo/ref/workflow/environment/run/attempt OIDC;
- subject/jti;
- collector provider/principal/execution/release/code SHA;
- algoritmo/key ID;
- nonce.

La private key no debe abandonar Cloudflare. GitHub no debe recibirla. Python utiliza únicamente la public key confiada.

Una firma criptográfica válida demuestra integridad/autenticidad respecto de la clave, **no** `production_authority` por sí sola.

## 6. Workers Observability

La capa Python reconcilia los receipts contra evidencia de Workers Observability.

Se valida, entre otros:

- span exacto esperado;
- request/receipt/evidence IDs;
- release y commit;
- run y autorización;
- target y status;
- tiempos físicos;
- unicidad de evidencia;
- identidad exacta de la página criptográfica que fue observada.

No se acepta sustituir una página válida por otra página también válida que comparta metadatos parciales.

El transporte HTTP compartido para telemetría está cerrado a:

```text
https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/observability/telemetry/query
```

con `POST`, HTTPS, host/path exactos, sin redirects ni retries ocultos. El token de Observability se mantiene separado del job que solicita OIDC.

## 7. Structural discovery

La cadena estructural vigente puede producir offline una `VerifiedStructuralDiscovery` mediante:

```text
structural request plan
-> edge structural gateway
-> signed structural receipt
-> body validation
-> structural observability
-> structural manifest/finalizer
```

Esta salida fija la estructura que luego usa el catálogo. No concede autoridad productiva mientras la evidencia física sea sólo simulada/offline.

## 8. Catálogo autenticado

Después de structural discovery:

1. `canonical_authenticated_provenance_plan.py` deriva page size, límites, órdenes e IDs canónicos.
2. `VerifiedCatalogEdgeCollector` reconstruye internamente las URLs exactas y obtiene páginas sólo mediante gateway + crypto.
3. Cada página se convierte en `RawPageEvidence` sólo después de verificar firma/body/contexto.
4. `VerifiedCatalogProvenanceFinalizer` reconcilia cada página con Workers Observability y construye el manifest completo de run.
5. La identidad entre observación y página criptográfica se exige por objeto exacto, evitando sustituciones.
6. El manifest exige el conjunto exacto de páginas y unicidad de request/reservation/nonce/receipt/evidence/span.

## 9. Readiness técnica versus autoridad

`la_colonia_catalog_acceptance_readiness.py` existe para evitar una falsa equivalencia entre “todo lo demostrable offline está completo” y “catálogo productivamente aceptado”.

Puede retornar:

```text
technical_catalog_complete = true
ready_for_productive_authority_evidence = true
catalog_accepted = false
production_authority = false
```

El reason `trusted_collector_provenance_unavailable` se mantiene. No se elimina hasta una prueba productiva real y una frontera explícita de autoridad.

No se aceptan sustitutos como:

- `trusted=True`;
- `provenance_ok=True`;
- `catalog_accepted=True` enviado por caller;
- un marker/archivo/comentario;
- HMAC o firma generada por el mismo proceso caller;
- receipt offline sin reconciliación física real.

## 10. Sonda controlada previa a La Colonia

La sonda aislada no-La-Colonia ya está **integrada en `main` y completa offline**. PR #84 añadió la infraestructura base; PR #88 añadió verificación criptográfica independiente fuera del Worker emisor; PR #89 añadió reconciliación con Workers Observability. El último CI observado para esta cadena pasó **1231/1231 pruebas** más `compileall`.

Diseño integrado:

```text
GitHub workflow manual
-> job controlled-probe
   -> environment cloudflare-probe
   -> GitHub OIDC, sin checkout del repositorio
   -> Worker gateway de sonda
   -> Durable Object ProbeLedger
   -> PROBE_ORIGIN_URL fijado en Cloudflare
   -> Worker de origen controlado *.workers.dev
   -> challenge exacto
   -> receipt Ed25519 probe-1
-> artifact sanitizado
-> job verify-evidence, sin id-token: write
   -> checkout inmutable
   -> verificación Ed25519 con public key confiada desde GitHub Environment
   -> consulta Workers Observability con token separado
   -> custom span único + child fetch único
   -> reconciliación release/URL/status/body/timestamps/commit/run
```

Separaciones obligatorias ya probadas offline:

- Worker/DO distintos a producción;
- llaves distintas;
- signing key ID distinto;
- OIDC audience/environment distintos;
- schema distinto;
- dominio criptográfico distinto;
- caller sin input de origin URL;
- destino sólo HTTPS `*.workers.dev` y path exacto;
- La Colonia rechazada antes de cualquier fetch;
- job OIDC sin checkout;
- job verificador sin capacidad OIDC;
- token de Observability separado del job OIDC;
- un receipt de sonda no verifica como receipt productivo;
- tracing fail-closed si el custom span no está muestreado;
- cero `catalog_accepted` y cero `production_authority`.

La sonda integrada **todavía no está desplegada ni se ha ejecutado remotamente**. Su existencia en `main` no cambia GATE-06/GATE-18.

## 11. Pruebas productivas necesarias

### Etapa A — sonda no-La-Colonia

El procedimiento exacto vive en `docs/cloudflare-controlled-probe-runbook.md`. La secuencia externa es:

1. desplegar `precios-sps-controlled-origin` con `wrangler.probe-origin.json`;
2. generar un par Ed25519 exclusivo de sonda;
3. guardar `PROBE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL` y `PROBE_RECEIPT_PUBLIC_KEY_SPKI_B64URL` en el Worker de sonda; la private key nunca se copia a GitHub;
4. fijar `PROBE_ORIGIN_URL` al Worker de origen controlado;
5. desplegar `precios-sps-controlled-probe` con `wrangler.probe.json` y su `ProbeLedger` propio;
6. configurar GitHub Environment `cloudflare-probe` con la URL del gateway, la public key, account ID y un token mínimo para Workers Observability;
7. ejecutar manualmente `.github/workflows/precios-supermercados-sps-cloudflare-probe.yml` una sola vez;
8. exigir PASS de verificación Ed25519 externa y PASS de reconciliación Workers Observability;
9. confirmar release/version metadata, OIDC, DO, único fetch físico y **0 requests a La Colonia**.

La sonda exitosa valida infraestructura Cloudflare, **no** autoridad de catálogo.

### Etapa B — collector productivo sin live

Antes de cualquier request a La Colonia deben demostrarse, donde sea posible sin contactar la fuente:

- despliegue inmutable de Worker/DO productivos;
- private key productiva alojada únicamente en Cloudflare;
- public key y code/release bindings correctos;
- OIDC productivo rechazando workflow/environment incorrectos;
- replay/fencing/presupuesto fail-closed;
- Observability accesible y reconciliable;
- destino alternativo no permitido rechazado antes de fetch.

### Etapa C — live mínimo SPS

Requiere **nueva autorización humana explícita**. Sólo entonces se ejecuta una observación mínima bajo presupuesto cerrado para resolver SPS.

### Etapa D — validación exacta de catálogo

Con SPS y autoridad productiva demostrados, se ejecuta la validación exacta de catálogo. Sólo una decisión autoritativa derivada de esa cadena puede permitir persistencia comercial.

## 12. Gates

La mera existencia del código no cambia gates productivos.

```text
GATE-17 = PASS_PRODUCTIVE_EVIDENCE
GATE-06 = OPEN_PRODUCTIVE
GATE-18 = OPEN_PRODUCTIVE
SPS = UNCONFIRMED
```

GATE-06 requiere evidencia física productiva. GATE-18 requiere además validación exacta autorizada del catálogo.

## 13. Secretos y datos prohibidos

Nunca publicar ni persistir sin sanitizar:

- private keys;
- JWT/OIDC tokens;
- `Authorization`;
- Cloudflare API tokens;
- cookies/session IDs;
- orderForm IDs;
- direcciones/coordenadas personales;
- credenciales de Cloudflare/GitHub.

Los artefactos pueden contener receipts y evidencia sanitizada, nunca secretos.

## 14. Criterio de cierre

El trusted collector se considera productivo únicamente cuando exista evidencia observable de que la infraestructura real cumple las mismas invariantes que hoy pasan offline. Hasta entonces:

```text
catalog_accepted = false
production_authority = false
```

El siguiente hito correcto es desplegar y ejecutar la sonda controlada no-La-Colonia descrita en el runbook. No existe motivo técnico para contactar La Colonia antes de completar ese paso, y aun después cualquier tráfico a La Colonia seguirá requiriendo una autorización humana nueva y separada.