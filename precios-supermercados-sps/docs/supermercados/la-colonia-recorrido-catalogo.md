# La Colonia — recorrido y validación del catálogo

## Alcance

Esta fase valida el recorrido secuencial del catálogo público de La Colonia sin persistir productos, precios ni historial.

Se conserva la fuente ya aprobada:

```text
https://www.lacolonia.com/_v/segment/graphql/v1
```

La operación continúa siendo `productSearchV3`, con `hideUnavailableItems = false` y `skusFilter = ALL`.

La ubicación no cambia:

```text
location_id = la_colonia_online
location_status = unknown
location_evidence = "Catálogo público en línea sin selección obligatoria de ciudad o sucursal."
location_confidence = null
```

## Arquitectura

`LaColoniaCatalogRunner` orquesta el recorrido, pero no duplica el parser.

```text
LaColoniaCatalogRunner
  -> construye URL pública GraphQL
  -> realiza una solicitud secuencial
  -> mide respuesta y reintentos
  -> llama LaColoniaExtractor.parse_payload()
  -> valida continuidad global
  -> deduplica transversalmente por llave fuente
  -> calcula métricas y aceptación
  -> mantiene RawProduct en memoria
  -> genera solamente un resumen sanitizado
```

La concurrencia permanece fija en `1`.

## Configuración

```text
page_size
max_pages
max_products
delay_seconds
max_retries
stop_on_error
order_by
max_duration_seconds
```

`max_products` debe ser múltiplo de `page_size`. Esto evita cambiar el tamaño de página durante una ejecución.

Los tamaños live permitidos y ya evaluados son:

```text
10
20
30
50
```

## Resultados live del tamaño de página

Las cuatro pruebas se ejecutaron en modo `smoke`, con dos páginas, perfil `baseline`, concurrencia `1`, pausa de `1.5` segundos y `allow_full = false`.

### Trazabilidad

| Page size | Request ID | Commit | Controller run | Live run | Artifact |
|---:|---|---|---:|---:|---:|
| 10 | `la-colonia-smoke-10-004` | `16216fcd55336b5626796e56a853edf95a4e9cbc` | `31029403314` | `31029426216` | `8940008559` |
| 20 | `la-colonia-smoke-20-001` | `747b950c0b048b2e3f1993dd8a7cf16ad72f578d` | `31029708366` | `31029728345` | `8940131295` |
| 30 | `la-colonia-smoke-30-001` | `e19b4170d2072a4cd51cc95b5d34a9bbabcd7668` | `31030837848` | `31030854363` | `8940583167` |
| 50 | `la-colonia-smoke-50-001` | `b9fee4d49f27e957f191c1ccd21ebf6b0b0cd308` | `31031105558` | `31031119831` | `8940690642` |

### Comparación

| Métrica | 10 | 20 | 30 | 50 |
|---|---:|---:|---:|---:|
| `accepted` | `true` | `true` | `true` | `true` |
| `pages_attempted` | 2 | 2 | 2 | 2 |
| `pages_completed` | 2 | 2 | 2 | 2 |
| `page_coverage` | 1.0 | 1.0 | 1.0 | 1.0 |
| `products_reported_initial` | 9291 | 9291 | 9291 | 9291 |
| `products_reported_final` | 9291 | 9291 | 9291 | 9291 |
| `catalog_pages_reported` | 930 | 465 | 310 | 186 |
| `products_returned` | 20 | 40 | 60 | 100 |
| `skus_extracted` | 20 | 40 | 60 | 100 |
| `response_bytes` | 21695 | 42520 | 62137 | 106217 |
| `duration_seconds` | 1.733578 | 2.784899 | 3.312173 | 2.994802 |
| `average_response_seconds` | 0.114572803 | 0.639206639 | 0.901944185 | 0.740312122 |
| `average_response_bytes` | 10847.5 | 21260.0 | 31068.5 | 53108.5 |
| `http_403` | 0 | 0 | 0 | 0 |
| `http_429` | 0 | 0 | 0 | 0 |
| `persistent_http_429` | 0 | 0 | 0 | 0 |
| `http_5xx` | 0 | 0 | 0 | 0 |
| `retries` | 0 | 0 | 0 | 0 |
| `errors` | 0 | 0 | 0 | 0 |
| `structural_events` | 0 | 0 | 0 | 0 |
| `duplicate_skus` | 0 | 0 | 0 | 0 |
| `duplicate_products` | 0 | 0 | 0 | 0 |
| `total_change_ratio` | 0.0 | 0.0 | 0.0 | 0.0 |
| `rejection_reasons` | `[]` | `[]` | `[]` | `[]` |

Los tamaños 10, 20 y 30 registraron `ordering_is_not_strictly_unique` y `baseline_too_small_for_thresholds`. El tamaño 50 registró únicamente `ordering_is_not_strictly_unique`, porque sus dos páginas alcanzaron cien SKU y permitieron proponer umbrales.

Todas las páginas registraron `quality:availability_conflict_price_with_zero_quantity`. El evento no fue estructural, no produjo rechazo y no alteró las métricas globales de aceptación.

### Tamaño recomendado

Se recomienda `page_size = 20` para la siguiente etapa.

Es el menor tamaño probado que reduce significativamente las solicitudes estimadas: disminuye de 930 a 465 páginas frente a `page_size = 10`, una reducción del 50 %, sin introducir errores, páginas parciales, cambios del total, duplicados, bloqueos HTTP ni eventos estructurales.

También mantiene un payload medio moderado de 21,260 bytes y un tiempo medio de respuesta de 0.639 segundos. Los tamaños 30 y 50 fueron aceptados, pero aumentan el payload por petición. El tamaño 50 es técnicamente prometedor y alcanzó la muestra mínima para proponer umbrales, pero no se selecciona automáticamente por ser el mayor; primero se prioriza una etapa staged conservadora con el menor tamaño que ya produce una reducción sustancial.

El siguiente paso es un recorrido `staged` de diez páginas con `page_size = 20`, `delay_seconds = 1.5`, perfil `baseline` y concurrencia `1`. Esa ejecución no forma parte de esta etapa de decisión y debe revisarse antes de avanzar.

## Ordenamiento

`OrderByReleaseDateDESC` mueve posiciones cuando se publican productos nuevos durante el recorrido. Para las muestras de esta fase se añade `OrderByNameASC` como alternativa pública menos sensible a nuevas altas al inicio del catálogo.

Ninguno de los órdenes públicos ofrece una llave secundaria única. Por tanto:

- se registra el criterio en cada página;
- se exige que no cambie durante la ejecución;
- se detectan páginas repetidas, solapamientos y saltos;
- se deduplica por SKU;
- se mide duplicación de productos;
- no se interpreta una ausencia como `not_listed`.

## Continuidad

El runner exige:

- primera página con `from = 0`;
- rangos consecutivos e inclusivos;
- `from` siguiente igual a `to` anterior más uno;
- tamaño constante;
- orden constante;
- página intermedia completa;
- última página con exactamente los productos restantes;
- total inicial y final registrados;
- ninguna página repetida.

La primera página define el total y el número de páginas del alcance solicitado. Un cambio posterior de `recordsFiltered` se registra, pero no se inventan páginas ni se corrigen ausencias.

## Detención segura

La ejecución se detiene después del primer error crítico:

- HTTP 403 o CAPTCHA;
- HTTP 429 persistente;
- error HTTP 5xx no recuperado;
- página vacía inesperada;
- página parcial;
- cambio estructural;
- pérdida total de precios;
- total inválido;
- página repetida;
- solapamiento o salto;
- orden o tamaño de página diferente;
- duración máxima excedida;
- más productos que los esperados.

## Métricas

El resumen separa páginas, productos y SKU. Incluye como mínimo:

```text
run_id
started_at_utc
finished_at_utc
duration_seconds
page_size
products_reported_initial
products_reported_final
pages_expected
pages_attempted
pages_completed
page_coverage
products_returned
skus_returned
skus_extracted
skus_with_price
skus_without_price
skus_pending_review
weighted_skus
promotional_skus
duplicate_skus
duplicate_products
errors
structural_events
http_403
http_429
http_5xx
retries
accepted
rejection_reasons
```

También registra duración y bytes aproximados por página, pausas aplicadas y ratios observacionales.

## Baseline y validación

### Baseline

Una muestra baseline puede aceptarse cuando completa íntegramente su alcance y no presenta errores críticos.

Los ratios de precios faltantes, duplicados y cambio del total se observan, pero no se activan automáticamente como límites. Solo se proponen umbrales cuando la muestra contiene al menos cien SKU y dos páginas completas.

El smoke de `page_size = 50` produjo esta propuesta observacional, todavía no activada:

```json
{
  "max_missing_price_ratio": 0.01,
  "max_duplicate_sku_ratio": 0.005,
  "max_duplicate_product_ratio": 0.005,
  "max_total_change_ratio": 0.002
}
```

### Validación

Una ejecución con perfil `validation` requiere los cuatro umbrales explícitos:

```text
max_missing_price_ratio
max_duplicate_sku_ratio
max_duplicate_product_ratio
max_total_change_ratio
```

La propuesta baseline no se activa sola. Debe copiarse y revisarse en una ejecución posterior.

El modo `full` exige:

- confirmación manual adicional;
- perfil `validation`;
- los cuatro umbrales;
- preflight aceptado;
- número de páginas inferior al límite de seguridad.

Si el preflight estima demasiadas solicitudes, el recorrido completo no inicia y se recomienda dividir por categorías o sesiones.

## Etapas live

```text
Smoke       -> 2 páginas: completado para 10, 20, 30 y 50
Staged 1    -> 10 páginas con page_size 20: siguiente paso, no ejecutado
Staged 2    -> 100 productos
Staged 3    -> 500 productos
Full        -> solo después de baseline y validación aceptados
```

Cada etapa debe finalizar con `accepted = true` antes de continuar.

## Informes

El script genera temporalmente:

```text
run-artifacts/run-summary.json
run-artifacts/run-summary.md
```

Los informes contienen métricas, hashes limitados y resúmenes de página. No contienen el catálogo completo.

## Fuera de alcance

No se implementan en esta fase:

- Google Sheets;
- BigQuery;
- base de datos;
- historial;
- tablas `current` o `history`;
- `not_listed` definitivo;
- workflow diario;
- comparación entre supermercados;
- Power BI.

## robots.txt

El recorrido usa únicamente el endpoint GraphQL ya validado. El cliente conserva el bloqueo de rutas excluidas y de hosts distintos de `www.lacolonia.com`, incluido `mobile.lacolonia.com`.
