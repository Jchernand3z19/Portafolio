# Trusted collector con Cloudflare Workers

> El nombre histórico de este archivo incluye `cloudflare-free` porque la evaluación inicial buscaba una alternativa de coste bajo/cero. Cloudflare es la arquitectura edge seleccionada.  
> Estado operativo mutable: [`PROJECT_STATE.md`](PROJECT_STATE.md).  
> Arquitectura general: [`arquitectura.md`](arquitectura.md).  
> Este documento conserva el **rationale de seguridad** y no autoriza tráfico live a La Colonia.

## 1. Motivo

La frontera no consiste únicamente en poder hacer HTTP. Debe poder demostrarse que una respuesta concreta provino de una solicitud física real y que el caller no pudo fabricar, sustituir o repetir la evidencia fuera del contrato.

La arquitectura usa:

```text
GitHub Actions protegido
-> GitHub OIDC
-> Cloudflare Worker
-> Durable Object
-> fetch HTTPS allowlisted
-> bytes exactos + SHA-256
-> receipt Ed25519
-> verificación externa Python
-> Workers Observability
-> manifest / readiness
```

Una firma del mismo Worker es necesaria, pero no se considera suficiente por sí sola para demostrar toda la provenance física.

## 2. Transporte productivo de La Colonia

La ruta productiva se restringe a la consulta VTEX canónica que el proyecto haya validado. El Worker debe cerrar como mínimo:

- HTTPS;
- host exacto;
- path exacto;
- método exacto;
- redirects rechazados;
- operación/query/variables canónicas;
- ventanas y orden dentro de límites;
- destino no controlable libremente por el caller.

El allowlist productivo **no se amplía para facilitar diagnósticos**.

## 3. Identidad OIDC

La política OIDC liga la ejecución a identidad GitHub verificable: repositorio, ref, workflow, environment, evento, commit, run y attempt según el contrato vigente.

OIDC no sustituye la autorización humana de La Colonia. Autenticar a GitHub como caller confiable no significa que exista permiso para iniciar una observación live específica.

## 4. Receipt y llaves

El receipt liga la solicitud física con autorización/run/request, commit, traversal/partition, digest del request, target, hash/status/tamaño de respuesta, tiempos, release del collector y key ID.

Reglas:

- private key Ed25519 sólo en Cloudflare;
- GitHub/verificadores usan material público;
- no publicar private keys en chat, logs, artifacts ni repositorio;
- la firma se verifica fuera del Worker emisor.

## 5. Durable Object

`AuthorizationGateway`/su equivalente versionado protege:

- presupuesto;
- expiración/deadline;
- reservas one-shot;
- unicidad de request/reservation/nonce;
- pacing;
- single-flight;
- replay idempotente sin refetch;
- fencing por autorización/run attempt;
- estado durable;
- fail-closed ante error de estado.

## 6. Workers Observability

La telemetría de plataforma es la segunda evidencia prevista para reconciliar un receipt con el fetch físico.

El diseño requiere correlación exacta entre receipt, custom span y child fetch cuando la API de plataforma exponga los campos necesarios.

El resultado físico actual y la limitación observada de la API pública se documentan en:

- [`PROJECT_STATE.md`](PROJECT_STATE.md);
- [`cloudflare-tracing-provenance.md`](cloudflare-tracing-provenance.md).

No se rebaja el reconciliador para convertir una ausencia de datos de plataforma en un PASS.

## 7. Structural discovery y catálogo

La cadena de catálogo separa:

```text
structural discovery autenticado
-> plan canónico
-> transporte de páginas
-> verificación receipt/body
-> reconciliación de evidencia
-> manifest exacto del run
-> readiness técnica
-> decisión de autoridad separada
```

El caller no elige libremente URL, page size, order, traversal IDs o particiones canónicas.

`technical_catalog_complete=true` no implica automáticamente:

```text
catalog_accepted=true
production_authority=true
```

## 8. Sonda controlada no-La-Colonia

La sonda usa infraestructura separada:

- Worker `precios-sps-controlled-origin`;
- Worker `precios-sps-controlled-probe`;
- `ProbeLedger`;
- audience/environment propios;
- llaves/key ID propios;
- schema/dominio criptográfico propios;
- origen limitado a `*.workers.dev`;
- caller sin origin URL arbitraria.

La Colonia debe ser rechazada antes de cualquier fetch desde esa sonda.

La prueba física de sonda **ya ocurrió**; no se mantiene aquí un estado mutable de runs o conteos. Consultar `PROJECT_STATE.md` para la evidencia vigente y `cloudflare-controlled-probe-runbook.md` para la política de un eventual rerun.

## 9. Amenazas y controles

| Amenaza | Control |
|---|---|
| caller inventa autoridad | autoridad no se deriva de un booleano libre |
| caller fabrica receipt | no posee private signing key |
| código no confiable invoca collector | OIDC + workflow/ref/environment cerrados |
| replay | estado durable + IDs/nonces + fencing |
| destino arbitrario | host/path/método/query allowlisted |
| redirect | manual + fail-closed |
| respuesta modificada | hash + firma + body verification |
| Worker afirma fetch inexistente | evidencia de plataforma externa cuando esté disponible |
| trace sustituido | correlación exacta + unicidad |
| pérdida/error de estado | deny |
| observability insuficiente | reconciliación no se declara cerrada |

## 10. Autoridad

Una sonda contra infraestructura propia, un receipt válido o una suite offline no autoriza La Colonia ni acepta su catálogo.

Las fronteras permanecen separadas:

```text
infraestructura física
!= autorización live de La Colonia
!= binding SPS
!= completitud de catálogo
!= autoridad productiva
!= aceptación comercial
```

El estado actual de cada frontera se consulta exclusivamente en `PROJECT_STATE.md`.
