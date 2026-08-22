# Evidencia física mediante Cloudflare Workers Tracing

> Estado operativo mutable: [`PROJECT_STATE.md`](PROJECT_STATE.md).  
> Este documento conserva el **contrato de diseño** de tracing/provenance y no autoriza tráfico a La Colonia.

## Objetivo

No tratar una firma del propio collector como prueba suficiente de que ocurrió un request físico. El receipt Ed25519 demuestra integridad/autenticidad bajo la llave del Worker; la segunda evidencia pretendida proviene de telemetría generada por la plataforma Cloudflare y consultada fuera del collector.

## Contrato de evidencia

Cada ejecución física se envuelve en el custom span:

```text
precios_sps_origin_execution
```

Antes del fetch, el runtime debe exigir tracing activo. El custom span registra identificadores de correlación cerrados (`authorization_id`, `run_id`, commit aprobado, reservation/request digest, traversal/partition), y el fetch físico ocurre dentro de ese span para que la instrumentación de Cloudflare pueda generar evidencia de red asociada.

La configuración edge exige tracing habilitado y sampling al 100 % para la ruta de provenance. Reducir el sampling impide una reconciliación exhaustiva y no debe interpretarse como evidencia equivalente.

## Reconciliación estricta esperada

El reconciliador externo intenta demostrar, uno a uno:

1. custom span único correspondiente al receipt;
2. child fetch único al destino canónico esperado;
3. método/status esperados;
4. tamaño de respuesta coherente con el receipt;
5. identidad/version del Worker;
6. ventana temporal compatible;
7. ausencia de fetch físico duplicado para la misma reserva;
8. separación de evidencia entre recorridos cuando corresponda.

Los IDs de plataforma son evidencia; no son parámetros controlables por el caller.

## Resultado físico observado

La afirmación histórica “no desplegado / no probado” ya no es correcta.

El run físico `32551882793` demostró la cadena de sonda hasta el fetch controlado y receipt Ed25519. El verifier-only `32552932554` revalidó firma, bytes e identidad sin capacidad de ejecutar el gateway.

Posteriormente se consultó la API pública de Workers Observability con varias estrategias (`traces`, `events`, `invocations` y diagnósticos sanitizados). Se confirmó un trace candidato real, pero la forma pública disponible no expuso el custom span y child fetch con el detalle necesario para satisfacer el reconciliador estricto.

Por diseño, el proyecto **no convirtió esa ausencia de detalle en un PASS**. PR #134 retiró la maquinaria diagnóstica temporal y conservó el verificador fail-closed.

La situación vigente y su clasificación (`DONE_PRODUCTIVE`, `PARTIAL_PRODUCTIVE`, etc.) se mantiene únicamente en `PROJECT_STATE.md`.

## API y credenciales

El verifier usa el endpoint de Workers Observability de Cloudflare y una credencial separada de cualquier credencial de despliegue. No debe poseer permisos para modificar Workers Scripts.

El nombre exacto del permiso requerido por la API es un dato mutable del proveedor y debe comprobarse contra la documentación vigente en el momento de una nueva ejecución; no se debe copiar ciegamente un nombre histórico de este documento.

Nunca almacenar tokens Cloudflare en el repositorio, artifacts o logs.

## Retención

Cloudflare no se usa como archivo histórico de provenance. Cualquier evidencia que pueda reconciliarse debe normalizarse/persistirse oportunamente dentro de la frontera del proyecto.

Las cuotas, retención y pricing de Workers Observability/Tracing son información mutable del proveedor y deben verificarse antes de diseñar una nueva dependencia operativa.

## Límite de autoridad

Incluso una reconciliación completa de la sonda controlada no concede por sí sola:

```text
production_authority = true
catalog_accepted = true
READY_FOR_LIVE = YES
```

La sonda prueba infraestructura propia. El acceso a La Colonia, el binding SPS y la aceptación del catálogo son fronteras separadas.
