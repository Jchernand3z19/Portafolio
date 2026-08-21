# Evidencia física mediante Cloudflare Workers Tracing

Estado: **diseño implementado offline; no desplegado; no live**.

## Objetivo

No tratar una firma del propio collector como prueba suficiente de que ocurrió el request físico. El Worker firma receipts, pero la segunda evidencia debe provenir de telemetría generada por la plataforma Cloudflare y consultada fuera del código del collector.

## Evidencia de plataforma elegida

Cloudflare Workers Tracing instrumenta automáticamente los `fetch()` salientes. Según la documentación oficial, los spans de `fetch` incluyen, entre otros:

- `url.full`, `url.scheme`, `url.path` y `url.query`;
- `http.request.method`;
- `http.response.status_code`;
- `http.response.body.size`.

Todos los spans incluyen además identidad de plataforma y deployment, como `cloud.provider=cloudflare`, `cloud.platform=cloudflare.workers`, `faas.name`, `faas.invocation_id`, `faas.version` y `cloudflare.script_version.id`.

Fuentes oficiales:

- https://developers.cloudflare.com/workers/observability/traces/
- https://developers.cloudflare.com/workers/observability/traces/spans-and-attributes/
- https://developers.cloudflare.com/workers/observability/traces/custom-spans/

## Correlación determinista

Cada ejecución física se envuelve en el custom span:

`precios_sps_origin_execution`

Antes de permitir el `fetch` físico, el span debe estar siendo trazado (`span.isTraced === true`). Si no lo está, la operación falla con `origin_trace_not_sampled` y no se continúa al request de origen.

El custom span registra:

- `precios.trace_contract_version`;
- `precios.collector_provider`;
- `precios.authorization_id`;
- `precios.run_id`;
- `precios.approved_commit_sha`;
- `precios.reservation_id`;
- `precios.request_id`;
- `precios.request_digest`;
- `precios.traversal_role`;
- `precios.traversal_id`;
- `precios.partition_id`.

El `fetch()` saliente ocurre dentro de ese span. La instrumentación automática de Cloudflare crea el span hijo de red. Así, un verifier externo puede localizar el custom span por `reservation_id`/`request_digest`, obtener su `traceId` y reconciliar el span hijo de `fetch` con el receipt firmado.

## Configuración fail-closed

`edge/cloudflare/wrangler.json` exige:

```json
{
  "observability": {
    "traces": {
      "enabled": true,
      "head_sampling_rate": 1
    }
  }
}
```

El muestreo al 100 % no es sólo observabilidad: es parte del contrato de provenance. Una configuración inferior a `1` vuelve imposible demostrar exhaustivamente todos los requests y debe bloquear aceptación productiva.

## Verificación externa prevista

El verifier consultará la API de Workers Observability, no el Durable Object del collector. La API oficial permite consultas de telemetría en:

`POST /accounts/{account_id}/workers/observability/telemetry/query`

Fuente:

- https://developers.cloudflare.com/api/resources/workers/subresources/observability/subresources/telemetry/methods/query/

La respuesta aceptable deberá demostrar, uno a uno, para cada receipt físico:

1. exactamente un custom span correlacionado;
2. exactamente un span hijo de `fetch` hacia la URL canónica esperada;
3. método `GET`;
4. HTTP 200;
5. `http.response.body.size` coherente con `response_body_bytes` del receipt;
6. versión de Worker coherente con `collector_release_id`;
7. ventana temporal compatible con `physical_started_at_utc` / `response_completed_at_utc`;
8. ausencia de un segundo `fetch` físico inesperado para la misma reserva;
9. evidencia distinta para traversal `primary` y `reconciliation`.

El ID persistente de evidencia física se derivará de los IDs de trace/span de Cloudflare y del contenido normalizado reconciliado; no de un valor declarado por el caller.

## Separación de credenciales

El token que consulta Observability debe estar separado del token de despliegue del Worker y no debe poseer `Workers Scripts Write`. La documentación actual del endpoint de telemetría exige el permiso denominado `Workers Observability Write`; por ello no debe describirse engañosamente como un token puramente read-only. Se limitará al único account requerido y se usará sólo en la fase verifier.

No se almacenará ningún token Cloudflare en el repositorio.

## Coste y retención observados al 21 de agosto de 2026

Cloudflare documenta que Workers Tracing está gratis durante su beta inicial. Desde el **1 de octubre de 2026** sus spans compartirán cuota/precio con Workers Logs. En Workers Free la documentación actual indica **200,000 eventos por día** y **3 días de retención**. Workers Trace Events Logpush, en cambio, requiere Workers Paid; esta arquitectura no depende de Logpush.

Fuentes oficiales:

- https://developers.cloudflare.com/workers/observability/traces/
- https://developers.cloudflare.com/workers/platform/pricing/
- https://developers.cloudflare.com/workers/observability/logs/logpush/

La retención de tres días implica que la reconciliación debe ejecutarse inmediatamente después del collector y persistir una attestation normalizada; no se dependerá de Cloudflare como archivo histórico.

## Límite de autoridad actual

Este cambio todavía **no** convierte la evidencia en productiva:

- el Worker no está desplegado;
- no existe todavía una respuesta real de la API de Observability validada contra el parser;
- no se ha creado ni probado el token de verifier;
- no existe attestation productiva firmada por un segundo principal;
- no se ha realizado ningún request live a La Colonia.

Hasta cerrar esos puntos:

- `production_authority = false`;
- `trusted_collector_provenance_unavailable` permanece obligatorio;
- SPS sigue `UNCONFIRMED`;
- `READY_FOR_LIVE = NO`.
