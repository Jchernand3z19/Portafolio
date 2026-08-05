# La Colonia — recorrido y validación del catálogo

## Alcance y controles

Esta fase valida el recorrido secuencial del catálogo público de La Colonia sin persistir productos, precios ni historial.

Controles vigentes:

- `page_size = 20`;
- concurrencia fija en `1`;
- pausa de `1.5` segundos;
- recorrido desde el índice inicial, sin omitir páginas anteriores;
- productos mantenidos únicamente en memoria;
- workflow live exclusivamente bajo `workflow_dispatch`;
- controlador por archivo ejecutado desde código confiable de `main`;
- observador de solo lectura para recuperar identificadores;
- artefactos sanitizados `run-summary.json` y `run-summary.md`;
- `allow_full = false`;
- ninguna página parcial es aceptable;
- no se publican productos, SKU individuales, nombres comerciales, marcas, URLs ni precios.

## Etapas anteriores

| Etapa | Live run | Artefacto | Resultado |
|---|---:|---:|---|
| Baseline de 200 productos | `31032519694` | `8941246437` | aceptado |
| Validation de 200 productos | `31033885905` | `8941767177` | aceptada |
| Primer baseline de 500 | `31035091894` | `8942244270` | rechazado en página 20 |

Los recorridos de 200 productos completaron diez páginas y observaron cero faltantes de precio, duplicados, cambio del total, errores, eventos estructurales, HTTP 403 del sitio, HTTP 429, HTTP 5xx y reintentos.

## Primer baseline de 500 rechazado

```text
request_id = la-colonia-baseline-products-500-001
commit_sha = 2ec8d4c0a9bfebf88a3402281b3129f3ebdbf696
controller_run_id = 31035067808
observer_run_id = 31035101626
live_run_id = 31035091894
artifact_id = 8942244270
exit_code = 2
accepted = false
pages_attempted = 20
pages_completed = 19
products_returned = 399
products_processed = 380
```

La página 20, rango `380–399`, devolvió 19 de 20 productos. El catálogo permaneció en 9291 productos. La hipótesis previa fue una respuesta parcial transitoria o una inestabilidad de paginación.

## Única repetición diagnóstica autorizada

Objetivo: determinar si la página parcial era transitoria, reproducible en el mismo rango o una inestabilidad general en otro rango. No se modificó código, regla de página completa, ordenamiento, pausa ni reintentos antes de ejecutar.

Solicitud exacta:

```json
{
  "request_id": "la-colonia-baseline-products-500-002",
  "supermarket": "la_colonia",
  "mode": "staged",
  "page_size": 20,
  "max_pages": 0,
  "max_products": 500,
  "delay_seconds": 1.5,
  "profile": "baseline",
  "thresholds": null,
  "allow_full": false
}
```

### Trazabilidad

```text
commit_sha = 5c1ecb81eb8efb1c4f9043ee65614b8b93136861
controller_run_id = 31037185265
controller_job_id = 92412095565
controller_conclusion = success
controller_artifact_id = 8943052236
controller_artifact_name = la-colonia-file-dispatch-31037185265
controller_artifact_digest = sha256:d1a3e9d18c498dac24ded4777d39ccd7b9312d5ae52f822568fd759d55215fb1
observer_run_id = 31037217937
observer_job_id = 92412214724
observer_conclusion = failure controlado de recuperación
live_run_id = 31037207732
live_job_id = 92412185299
live_conclusion = failure
run_number = 30
internal_run_id = live_la_colonia_staged_20260805T185814Z
artifact_id = 8943081061
artifact_name = la-colonia-staged-summary
artifact_digest = sha256:a8a8a8cca0a511323be8997d2a07f422087759a547709637a50416925228607d
artifact_size = 3173 bytes
exit_code = 2
```

El controlador despachó una sola ejecución sobre `feature/la-colonia-full-crawl-validation` y el commit exacto `5c1ecb81...`. El observador falló intencionalmente para exponer los IDs porque GitHub bloqueó los comentarios del `GITHUB_TOKEN`. Ese HTTP 403 pertenece a GitHub; el sitio de La Colonia registró `http_403 = 0`.

## Resultado global de la repetición

| Métrica | Valor |
|---|---:|
| `accepted` | `false` |
| `mode` | `staged` |
| `profile` | `baseline` |
| `page_size` | 20 |
| `pages_expected` | 25 |
| `pages_attempted` | 20 |
| `pages_completed` | 19 |
| `page_coverage` | 0.76 |
| `products_reported_initial` | 9291 |
| `products_reported_final` | 9291 |
| `catalog_pages_reported` | 465 |
| `products_returned` | 399 |
| `products_processed` | 380 |
| `skus_returned` | 399 |
| `skus_extracted` | 380 |
| `skus_with_price` | 380 |
| `skus_without_price` | 0 |
| `skus_pending_review` | 380 |
| `promotional_skus` | 42 |
| `weighted_skus` | 0 |
| `duplicate_skus` | 0 |
| `duplicate_products` | 0 |
| `response_bytes` | 456044 |
| `duration_seconds` | 38.478367 |
| `average_response_seconds` | 0.49567525860000006 |
| `average_response_bytes` | 22802.2 |
| `delay_seconds_applied` | 28.5 |
| `http_403` | 0 |
| `http_429` | 0 |
| `persistent_http_429` | 0 |
| `http_5xx` | 0 |
| `retries` | 0 |
| `errors` | 1 |
| `structural_events` | 0 |
| `total_change_absolute` | 0 |
| `total_change_ratio` | 0.0 |
| `missing_price_ratio` | 0.0 |
| `duplicate_sku_ratio` | 0.0 |
| `duplicate_product_ratio` | 0.0 |
| `warnings` | `["ordering_is_not_strictly_unique"]` |
| `quality_events` | `["partial_product_page", "page_rejected_by_extractor"]` |
| `full_started` | `false` |

Razones de rechazo:

```text
partial_product_page
page_rejected_by_extractor
pages_incomplete
page_coverage_below_100_percent
errors_present
```

## Comparación página por página

| Página | Rango | Intentada | Esperados | Devueltos | SKU devueltos | SKU extraídos | Bytes | Tiempo (s) | Accepted | Eventos de calidad | Firma repetida en el run | Comparación con primer intento |
|---:|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|
| 1 | 0–19 | sí | 20 | 20 | 20 | 20 | 21631 | 0.725924 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 2 | 20–39 | sí | 20 | 20 | 20 | 20 | 20889 | 0.369187 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 3 | 40–59 | sí | 20 | 20 | 20 | 20 | 19681 | 0.339813 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 4 | 60–79 | sí | 20 | 20 | 20 | 20 | 22947 | 0.336677 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 5 | 80–99 | sí | 20 | 20 | 20 | 20 | 21261 | 0.336303 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 6 | 100–119 | sí | 20 | 20 | 20 | 20 | 22037 | 0.334386 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 7 | 120–139 | sí | 20 | 20 | 20 | 20 | 19879 | 0.363469 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 8 | 140–159 | sí | 20 | 20 | 20 | 20 | 24620 | 1.156876 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 9 | 160–179 | sí | 20 | 20 | 20 | 20 | 27509 | 0.477060 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 10 | 180–199 | sí | 20 | 20 | 20 | 20 | 26181 | 0.516007 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 11 | 200–219 | sí | 20 | 20 | 20 | 20 | 24163 | 0.363555 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 12 | 220–239 | sí | 20 | 20 | 20 | 20 | 22810 | 0.574707 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 13 | 240–259 | sí | 20 | 20 | 20 | 20 | 22416 | 0.352841 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 14 | 260–279 | sí | 20 | 20 | 20 | 20 | 24736 | 0.344121 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 15 | 280–299 | sí | 20 | 20 | 20 | 20 | 25020 | 1.173714 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 16 | 300–319 | sí | 20 | 20 | 20 | 20 | 20448 | 0.357352 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 17 | 320–339 | sí | 20 | 20 | 20 | 20 | 22082 | 0.711416 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 18 | 340–359 | sí | 20 | 20 | 20 | 20 | 21929 | 0.364226 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 19 | 360–379 | sí | 20 | 20 | 20 | 20 | 24848 | 0.358129 | true | availability_conflict_price_with_zero_quantity | no | conteo igual, bytes iguales, firma igual |
| 20 | 380–399 | sí | 20 | 19 | 19 | 19 | 20957 | 0.357741 | false | availability_conflict_price_with_zero_quantity; partial_product_page; partial_product_page_global | no | conteo igual, bytes iguales, firma igual |
| 21 | 400–419 | no | 20 | — | — | — | — | — | — | detención tras rechazo reproducido en página 20 | — | no comparable; no intentada en ambos runs |
| 22 | 420–439 | no | 20 | — | — | — | — | — | — | detención tras rechazo reproducido en página 20 | — | no comparable; no intentada en ambos runs |
| 23 | 440–459 | no | 20 | — | — | — | — | — | — | detención tras rechazo reproducido en página 20 | — | no comparable; no intentada en ambos runs |
| 24 | 460–479 | no | 20 | — | — | — | — | — | — | detención tras rechazo reproducido en página 20 | — | no comparable; no intentada en ambos runs |
| 25 | 480–499 | no | 20 | — | — | — | — | — | — | detención tras rechazo reproducido en página 20 | — | no comparable; no intentada en ambos runs |

## Comparación diagnóstica

### Páginas 1–19

- mismos rangos consecutivos `0–19` a `360–379`;
- 20 productos y 20 SKU en cada página;
- bytes exactamente iguales en las 19 páginas;
- firmas sanitizadas exactamente iguales en las 19 páginas;
- total reportado de 9291 en todas las páginas;
- sin saltos, solapamientos, páginas vacías, páginas repetidas ni duplicados globales;
- los tiempos de respuesta variaron, sin alterar el contenido sanitizado.

### Página 20 — rango 380–399

| Métrica | Primer intento | Repetición | Comparación |
|---|---:|---:|---|
| esperados | 20 | 20 | igual |
| devueltos | 19 | 19 | igual |
| SKU devueltos | 19 | 19 | igual |
| SKU observados por extractor | 19 | 19 | igual |
| bytes | 20957 | 20957 | igual |
| tiempo de respuesta | 2.362169 s | 0.357741 s | distinto, contenido igual |
| accepted | false | false | igual |
| firma | `c86ae16...ef5ca` | `c86ae16...ef5ca` | exactamente igual |
| eventos | disponibilidad + página parcial local/global | disponibilidad + página parcial local/global | igual |

## Clasificación

**Resultado B — inestabilidad reproducible del rango o de la paginación bajo estas condiciones.**

La página parcial no fue una anomalía transitoria: se reprodujo en el mismo rango con el mismo conteo, bytes y firma sanitizada. La evidencia no demuestra pérdida del parser ni un problema de red. El runner y la regla de aceptación funcionaron correctamente al rechazar y detener el recorrido.

Clasificación por componente:

- sitio/API o paginación pública: causa observable reproducible;
- controlador: correcto;
- observador: recuperación controlada correcta;
- workflow live: correcto, reflejó código de salida 2;
- red/HTTP: sin 403 del sitio, 429, 5xx ni reintentos;
- parser: sin evidencia de pérdida, porque respuesta y extractor observaron 19;
- continuidad: válida hasta `360–379`, rechazada en `380–399`;
- duplicados: cero globales;
- cambio del total: cero;
- regla de aceptación: correcta y no se flexibiliza.

## Disponibilidad

Las 20 páginas intentadas registraron `quality:availability_conflict_price_with_zero_quantity`.

```text
páginas afectadas = 20/20
skus_pending_review = 380
skus_extracted = 380
proporción = 100 %
baseline 200 = 100 %
validation 200 = 100 %
primer baseline 500 procesado = 100 %
repetición diagnóstica = 100 %
diferencia = 0 puntos porcentuales
```

Este conflicto no causó la página parcial. La regla permanece sin cambios y los cuatro ratios actuales no lo cubren.

## Ratios y umbrales propuestos

| Ratio | Baseline 200 | Validation 200 | Primer intento 500 | Repetición 500 | Umbral anterior | Propuesta | Decisión |
|---|---:|---:|---:|---:|---:|---:|---|
| `missing_price_ratio` | 0.0 | 0.0 | 0.0 | 0.0 | 0.01 | 0.01 | sin cambio; no autoriza validation |
| `duplicate_sku_ratio` | 0.0 | 0.0 | 0.0 | 0.0 | 0.005 | 0.005 | sin cambio; no autoriza validation |
| `duplicate_product_ratio` | 0.0 | 0.0 | 0.0 | 0.0 | 0.005 | 0.005 | sin cambio; no autoriza validation |
| `total_change_ratio` | 0.0 | 0.0 | 0.0 | 0.0 | 0.002 | 0.002 | sin cambio; no autoriza validation |

Umbrales propuestos, no activados:

```json
{
  "max_missing_price_ratio": 0.01,
  "max_duplicate_sku_ratio": 0.005,
  "max_duplicate_product_ratio": 0.005,
  "max_total_change_ratio": 0.002
}
```

## Decisión y siguiente trabajo

- Baseline de 500: rechazado por segunda vez.
- Anomalía: reproducible en el mismo rango.
- Tercera repetición: prohibida y no ejecutada.
- Validation de 500: no ejecutada.
- `full`: no ejecutado.
- Código ejecutable: sin modificaciones.
- Regla de página completa: sin flexibilizar.
- Ordenamiento: sin cambios; `ordering_is_not_strictly_unique` permanece como advertencia.
- Siguiente trabajo: revisión de estrategia de paginación con una hipótesis técnica concreta y pruebas de regresión antes de autorizar otra ejecución live.

Hipótesis a estudiar, sin implementar todavía: el endpoint puede construir la página ordenada por un campo no estrictamente único y omitir de forma determinista un elemento alrededor del límite `380–399`. La revisión debe inspeccionar el contrato de paginación, los parámetros `from/to`, el criterio secundario de orden y la posibilidad de validar continuidad mediante identificadores sanitizados, sin aceptar páginas parciales.

## Estado del PR y restricciones

- PR #7 abierto, en borrador, fusionable y no fusionado.
- Auto-merge deshabilitado.
- Archivo operacional conservado con `la-colonia-baseline-products-500-002`.
- Limpieza operacional pendiente antes de una futura fusión.
- Sin persistencia, historial, ejecución diaria, Google Sheets, BigQuery, Power BI ni segundo supermercado.
