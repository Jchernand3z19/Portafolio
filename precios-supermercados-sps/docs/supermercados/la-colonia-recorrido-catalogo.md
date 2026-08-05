# La Colonia — recorrido y validación del catálogo

## Alcance

Esta fase valida el recorrido secuencial del catálogo público de La Colonia sin persistir productos, precios ni historial.

Fuente aprobada:

```text
https://www.lacolonia.com/_v/segment/graphql/v1
```

La operación continúa siendo `productSearchV3`, con `hideUnavailableItems = false` y `skusFilter = ALL`.

Ubicación provisional:

```text
location_id = la_colonia_online
location_status = unknown
location_evidence = "Catálogo público en línea sin selección obligatoria de ciudad o sucursal."
location_confidence = null
```

## Arquitectura y seguridad

`LaColoniaCatalogRunner` orquesta el recorrido sin duplicar `LaColoniaExtractor.parse_payload()`.

Controles vigentes:

- concurrencia fija en `1`;
- pausa de `1.5` segundos entre solicitudes;
- workflow live exclusivamente bajo `workflow_dispatch`;
- controlador por archivo ejecutado con código confiable de `main`;
- observador de solo lectura para recuperar identificadores cuando GitHub bloquea comentarios;
- productos mantenidos únicamente en memoria;
- artefactos sanitizados `run-summary.json` y `run-summary.md`;
- ningún producto, nombre comercial, URL o precio individual publicado;
- `full` requiere perfil validation, umbrales explícitos, confirmación y preflight aceptado.

## Tamaño de página seleccionado

Los smokes de `page_size` 10, 20, 30 y 50 fueron aceptados. Se mantiene:

```text
page_size = 20
```

Es el menor tamaño probado que reduce 50 % las solicitudes estimadas frente a tamaño 10, de 930 a 465 páginas, sin errores, páginas parciales, duplicados, reintentos, bloqueos HTTP ni eventos estructurales.

## Baseline de diez páginas

Trazabilidad:

```text
request_id = la-colonia-staged-pages-20-001
commit_sha = 6185ac4671694784d5d0c0becabfaae340f0dd7d
controller_run_id = 31032502746
observer_run_id = 31032530290
live_run_id = 31032519694
artifact_id = 8941246437
profile = baseline
exit_code = 0
accepted = true
```

Resultado principal:

```text
pages_expected = 10
pages_attempted = 10
pages_completed = 10
page_coverage = 1.0
products_reported_initial = 9291
products_reported_final = 9291
products_returned = 200
products_processed = 200
skus_returned = 200
skus_extracted = 200
skus_with_price = 200
skus_without_price = 0
skus_pending_review = 200
promotional_skus = 17
weighted_skus = 0
duplicate_skus = 0
duplicate_products = 0
response_bytes = 226635
duration_seconds = 20.344055
average_response_seconds = 0.6815969079000009
average_response_bytes = 22663.5
delay_seconds_applied = 13.5
http_403 = 0
http_429 = 0
persistent_http_429 = 0
http_5xx = 0
retries = 0
errors = 0
structural_events = 0
total_change_absolute = 0
total_change_ratio = 0.0
missing_price_ratio = 0.0
duplicate_sku_ratio = 0.0
duplicate_product_ratio = 0.0
warnings = ["ordering_is_not_strictly_unique"]
rejection_reasons = []
full_started = false
```

## Validation de diez páginas

Solicitud operacional:

```json
{
  "request_id": "la-colonia-validation-pages-20-001",
  "supermarket": "la_colonia",
  "mode": "staged",
  "page_size": 20,
  "max_pages": 10,
  "max_products": 0,
  "delay_seconds": 1.5,
  "profile": "validation",
  "thresholds": {
    "max_missing_price_ratio": 0.01,
    "max_duplicate_sku_ratio": 0.005,
    "max_duplicate_product_ratio": 0.005,
    "max_total_change_ratio": 0.002
  },
  "allow_full": false
}
```

Trazabilidad verificada:

```text
commit_sha = c6401d475a35ac48a1f538f19d95db034651b771
controller_run_id = 31033860206
controller_artifact_id = 8941755904
observer_run_id = 31033899368
live_run_id = 31033885905
run_number = 28
live_artifact_id = 8941767177
live_artifact_digest = sha256:0de1813d3a684d7c2b5fba75a9f1c8053083ca56f0b5def37d4ebe84c051b8c8
exit_code = 0
```

Resultado global:

| Métrica | Validation |
|---|---:|
| `accepted` | `true` |
| `mode` | `staged` |
| `profile` | `validation` |
| `page_size` | 20 |
| `pages_expected` | 10 |
| `pages_attempted` | 10 |
| `pages_completed` | 10 |
| `page_coverage` | 1.0 |
| `products_reported_initial` | 9291 |
| `products_reported_final` | 9291 |
| `catalog_pages_reported` | 465 |
| `products_returned` | 200 |
| `products_processed` | 200 |
| `skus_returned` | 200 |
| `skus_extracted` | 200 |
| `skus_with_price` | 200 |
| `skus_without_price` | 0 |
| `skus_pending_review` | 200 |
| `promotional_skus` | 17 |
| `weighted_skus` | 0 |
| `duplicate_skus` | 0 |
| `duplicate_products` | 0 |
| `response_bytes` | 226635 |
| `duration_seconds` | 14.081743 |
| `average_response_seconds` | 0.0552162359999997 |
| `average_response_bytes` | 22663.5 |
| `delay_seconds_applied` | 13.5 |
| `http_403` | 0 |
| `http_429` | 0 |
| `persistent_http_429` | 0 |
| `http_5xx` | 0 |
| `retries` | 0 |
| `errors` | 0 |
| `structural_events` | 0 |
| `total_change_absolute` | 0 |
| `total_change_ratio` | 0.0 |
| `missing_price_ratio` | 0.0 |
| `duplicate_sku_ratio` | 0.0 |
| `duplicate_product_ratio` | 0.0 |
| `warnings` | `["ordering_is_not_strictly_unique"]` |
| `rejection_reasons` | `[]` |
| `quality_events` | `[]` |
| `full_started` | `false` |

## Resultado por página de validation

| Página | Rango | Esperados | Devueltos | SKU devueltos | SKU extraídos | Bytes | Respuesta (s) | Accepted | Evento de calidad |
|---:|---|---:|---:|---:|---:|---:|---:|---|---|
| 1 | 0–19 | 20 | 20 | 20 | 20 | 21631 | 0.268136 | true | disponibilidad/precio con cantidad cero |
| 2 | 20–39 | 20 | 20 | 20 | 20 | 20889 | 0.031627 | true | disponibilidad/precio con cantidad cero |
| 3 | 40–59 | 20 | 20 | 20 | 20 | 19681 | 0.032504 | true | disponibilidad/precio con cantidad cero |
| 4 | 60–79 | 20 | 20 | 20 | 20 | 22947 | 0.036618 | true | disponibilidad/precio con cantidad cero |
| 5 | 80–99 | 20 | 20 | 20 | 20 | 21261 | 0.028095 | true | disponibilidad/precio con cantidad cero |
| 6 | 100–119 | 20 | 20 | 20 | 20 | 22037 | 0.031317 | true | disponibilidad/precio con cantidad cero |
| 7 | 120–139 | 20 | 20 | 20 | 20 | 19879 | 0.031638 | true | disponibilidad/precio con cantidad cero |
| 8 | 140–159 | 20 | 20 | 20 | 20 | 24620 | 0.032772 | true | disponibilidad/precio con cantidad cero |
| 9 | 160–179 | 20 | 20 | 20 | 20 | 27509 | 0.030727 | true | disponibilidad/precio con cantidad cero |
| 10 | 180–199 | 20 | 20 | 20 | 20 | 26181 | 0.028727 | true | disponibilidad/precio con cantidad cero |

El resumen no desglosa `skus_with_price` por página. El único valor derivable es 20 por página, porque cada página contiene 20 SKU extraídos y el agregado confirma `200/200` SKU con precio.

## Comparación baseline y validation

| Métrica | Baseline | Validation | Diferencia absoluta | Decisión |
|---|---:|---:|---:|---|
| `products_reported_initial` | 9291 | 9291 | 0 | estable |
| `products_reported_final` | 9291 | 9291 | 0 | estable |
| `products_returned` | 200 | 200 | 0 | coincide |
| `skus_extracted` | 200 | 200 | 0 | coincide |
| `skus_with_price` | 200 | 200 | 0 | coincide |
| `skus_without_price` | 0 | 0 | 0 | cumple |
| `skus_pending_review` | 200 | 200 | 0 | limitación sin cambio |
| `promotional_skus` | 17 | 17 | 0 | coincide |
| `duplicate_skus` | 0 | 0 | 0 | cumple |
| `duplicate_products` | 0 | 0 | 0 | cumple |
| `response_bytes` | 226635 | 226635 | 0 | contenido agregado equivalente |
| `duration_seconds` | 20.344055 | 14.081743 | -6.262312 | validation más rápida |
| `average_response_seconds` | 0.6815969079 | 0.0552162360 | -0.6263806719 | mejora observada, no garantía futura |
| `missing_price_ratio` | 0.0 | 0.0 | 0.0 | cumple |
| `duplicate_sku_ratio` | 0.0 | 0.0 | 0.0 | cumple |
| `duplicate_product_ratio` | 0.0 | 0.0 | 0.0 | cumple |
| `total_change_ratio` | 0.0 | 0.0 | 0.0 | cumple |
| `errors` | 0 | 0 | 0 | cumple |
| `structural_events` | 0 | 0 | 0 | cumple |
| `http_403` | 0 | 0 | 0 | sin bloqueo del sitio |
| `http_429` | 0 | 0 | 0 | cumple |
| `http_5xx` | 0 | 0 | 0 | cumple |
| `retries` | 0 | 0 | 0 | cumple |
| `warnings` | orden no estrictamente único | orden no estrictamente único | sin cambio | advertencia permanece |

Las diez firmas de página de validation coinciden con las del baseline. Esto confirma la misma muestra observable durante ambas ejecuciones, sin afirmar estabilidad estricta del orden a largo plazo.

## Cumplimiento de umbrales

| Umbral | Observado | Límite aplicado | Margen restante | Cumple |
|---|---:|---:|---:|---|
| `max_missing_price_ratio` | 0.0 | 0.01 | 0.01 | true |
| `max_duplicate_sku_ratio` | 0.0 | 0.005 | 0.005 | true |
| `max_duplicate_product_ratio` | 0.0 | 0.005 | 0.005 | true |
| `max_total_change_ratio` | 0.0 | 0.002 | 0.002 | true |

Los límites se aplicaron antes de observar el resultado y no fueron modificados.

## Continuidad y ordenamiento

Validation confirmó:

- rangos consecutivos desde `0–19` hasta `180–199`;
- diez páginas completas;
- ninguna página vacía o parcial;
- ningún salto ni solapamiento;
- ninguna página repetida;
- diez firmas distintas dentro de la ejecución;
- orden constante `OrderByNameASC`;
- ninguna detención anticipada;
- total inicial y final iguales;
- cero duplicados globales.

La advertencia `ordering_is_not_strictly_unique` permanece. No hubo evidencia observable de repetición, ausencia, movimiento, solapamiento, cambio del total o firmas duplicadas durante esta ejecución, pero no se declara que el orden sea estrictamente estable.

## Disponibilidad

Las diez páginas volvieron a registrar:

```text
quality:availability_conflict_price_with_zero_quantity
```

```text
páginas afectadas = 10 de 10
skus_pending_review = 200
skus_extracted = 200
proporción = 1.0 = 100 %
diferencia contra baseline = 0
```

La validation fue aceptada porque este conflicto sigue definido como advertencia no estructural. Los cuatro umbrales actuales no lo validan y continúa como limitación independiente. No se cambia la regla en esta etapa.

## Decisión

La validation de diez páginas queda aprobada.

El baseline de 200 productos y su validation sustituyen una etapa separada y redundante de cien productos: ambos superan la muestra mínima anterior de cien SKU y validan dos veces la misma cobertura de 200 productos. No existe una razón técnica observada para repetir una prueba aislada de cien productos.

La siguiente etapa propuesta es un baseline de 500 productos. No fue ejecutado.

```json
{
  "request_id": "la-colonia-baseline-products-500-001",
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

## Estado de etapas live

```text
Smokes de page size                     completados y aceptados
Baseline 10 páginas / 200 productos    completado y aceptado
Validation 10 páginas / 200 productos  completada y aceptada
Etapa separada de 100 productos         superada por las dos muestras de 200
Baseline 500 productos                  pendiente
Validation 500 productos                pendiente
Full                                    no ejecutado
```

## Pruebas offline y estado del PR

La actualización operacional no modificó código ejecutable. El head anterior tenía compilación correcta y `149 passed in 0.50s`. Después de esta actualización documental debe conservarse la suite completa en verde.

El PR #7 debe permanecer:

- abierto;
- en borrador;
- sin fusionar;
- sin auto-merge;
- con limpieza operacional pendiente antes de una futura fusión.

No se implementan persistencia, historial, ejecución diaria, Google Sheets, BigQuery, Power BI ni segundo supermercado.
