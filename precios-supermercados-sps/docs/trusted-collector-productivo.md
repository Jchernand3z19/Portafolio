# Trusted collector productivo — arquitectura Cloudflare

> Estado operativo mutable: [`PROJECT_STATE.md`](PROJECT_STATE.md).  
> Este documento define la **frontera de provenance productiva**; no afirma que todos sus gates estén cerrados y no autoriza tráfico a La Colonia.

El diseño anterior basado en Cloud Run/VPC/Secure Web Proxy/Cloud Logging/KMS está supersedido. La ruta seleccionada es:

```text
Cloudflare Workers
+ Durable Objects
+ GitHub OIDC
+ Ed25519
+ Workers Observability
```

## 1. Problema

Datos, labels, digests o booleanos producidos por el mismo caller no demuestran por sí solos una solicitud física independiente.

La frontera productiva debe demostrar de forma fail-closed que:

1. un runtime externo autorizado realizó el request físico;
2. el caller no eligió arbitrariamente destino/request/identidad;
3. la respuesta consumida corresponde exactamente al request permitido;
4. la identidad GitHub está ligada a repo/ref/workflow/environment/commit/run;
5. receipt, respuesta y evidencia de plataforma reconcilian según el contrato;
6. replay/sustitución no crean una nueva observación válida;
7. recorridos que deban ser físicamente independientes tengan evidencias distintas.

## 2. Cadena

```text
GitHub Actions
-> OIDC
-> Worker productivo
-> AuthorizationGateway (Durable Object)
-> request allowlisted
-> bytes exactos + SHA-256
-> receipt Ed25519
-> verifier externo
-> Workers Observability
-> manifest
-> readiness técnica
-> autoridad/aceptación separadas
```

## 3. Trust boundary GitHub/OIDC

OIDC autentica una ejecución GitHub concreta. La política debe cerrar repositorio, ref, workflow, environment, event, audience y contexto de run según la implementación vigente.

No convertir estos campos en inputs libres del caller.

OIDC **no es una autorización humana para contactar La Colonia**.

## 4. Request físico

La ruta productiva sólo permite el request canónico previamente validado para la fuente:

- scheme/host/path/método exactos;
- query/variables permitidos;
- límites de ventana/page size;
- órdenes/traversals allowlisted;
- redirects rechazados;
- destino derivado internamente, no arbitrario.

El allowlist productivo nunca se relaja para ejecutar una prueba diagnóstica.

## 5. Durable Object

El estado durable protege:

- presupuesto;
- deadline/expiración;
- reservas;
- pacing;
- single-flight;
- replay idempotente;
- IDs/nonces únicos;
- fencing por autorización y run attempt;
- fail-closed ante inconsistencias o pérdida de estado.

Una reejecución lógica del mismo request no debe provocar otro fetch físico si el contrato define replay.

## 6. Receipt Ed25519

El receipt liga request y respuesta a la ejecución autorizada e incluye suficientes campos para revalidar identidad, digest, target, status/tamaño/hash, tiempos, release y key ID.

La private key productiva sólo vive en Cloudflare. El verifier externo utiliza material público confiable.

## 7. Verificador independiente

El verifier debe comprobar, como mínimo:

- firma;
- schema/dominio criptográfico;
- request digest/identidad;
- repo/ref/workflow/environment/commit/run/attempt;
- release/collector identity;
- status/tamaño/hash de respuesta;
- pertenencia exacta de la evidencia al plan/traversal esperado.

No se aceptan como sustitutos `trusted=true`, `provenance_ok=true`, markers, comentarios o booleanos controlados por caller.

## 8. Workers Observability

La intención de la segunda evidencia es demostrar de forma independiente el fetch que originó el receipt.

El contrato estricto se documenta en [`cloudflare-tracing-provenance.md`](cloudflare-tracing-provenance.md).

La evidencia física ya obtenida y la limitación actual de la API pública de Observability se clasifican en `PROJECT_STATE.md`. Si la API no expone los campos necesarios, la reconciliación permanece abierta; no se infiere un PASS.

## 9. Structural discovery y catálogo

La provenance productiva alimenta capas separadas:

```text
verified structural discovery
-> plan canónico
-> páginas verificadas
-> manifest exacto del run
-> evaluación de completitud/readiness
-> decisión de autoridad
```

Readiness técnica y autoridad comercial no son sinónimos.

## 10. Sonda controlada

La sonda no-La-Colonia usa infraestructura, llaves, audience, environment, schema y Durable Object separados.

Su propósito es demostrar capacidades de la plataforma sin ampliar el destino productivo. El resultado histórico y la política de rerun están en:

- [`PROJECT_STATE.md`](PROJECT_STATE.md);
- [`cloudflare-controlled-probe-runbook.md`](cloudflare-controlled-probe-runbook.md).

Un PASS de sonda nunca autoriza un request posterior a La Colonia.

## 11. Autoridad de catálogo

El sistema debe poder representar estados como:

```text
technical_catalog_complete = true
production_authority = false
catalog_accepted = false
```

Eso es válido y preferible a fabricar autoridad faltante.

La decisión productiva que permita mutar current/history debe ser tipada, verificable y derivada de provenance/completitud suficientes; nunca un booleano libre pasado al backend.

## 12. Estado

Este documento no fija SHA, PR, test count, authorization IDs ni estado de despliegue. Todo dato mutable vive en [`PROJECT_STATE.md`](PROJECT_STATE.md).
