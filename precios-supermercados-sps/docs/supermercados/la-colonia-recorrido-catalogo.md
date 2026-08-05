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

`LaColoniaCatalogRunner` orquesta el recorrido sin duplicar el parser existente:

```text
LaColoniaCatalogRunner
  -> construye la URL pública GraphQL
  -> realiza solicitudes secuenciales
  -> mide respuesta y reintentos
  -> llama LaColoniaExtractor.parse_payload()
  -> valida continuidad global
  -> deduplica transversalmente por llave fuente
  -> calcula métricas y aceptación
  -> mantiene RawProduct en memoria
  -> genera solamente resúmenes sanitizados
```

Controles vigentes:

- concurrencia fija en `1`;
- pausa de `1.5` segundos entre solicitudes;
- workflow live exclusivamente bajo `workflow_dispatch`;
- controlador por archivo ejecutado desde código confiable de `main`;
- observador de solo lectura para recuperar identificadores cuando GitHub bloquea comentarios;
- ningún producto, nombre comercial, URL de producto o precio individual se publica en los informes;
- `full` requiere confirmación, perfil validation, umbrales explícitos y preflight aceptado.

## Evaluación live del tamaño de página

Los cuatro smokes utilizaron dos páginas, perfil `baseline`, concurrencia `1`, pausa de `1.5` segundos y `allow_full = false`.

| Page size | Request ID | Commit | Controller run | Live run | Artifact | Productos | Bytes | Duración (s) | Promedio respuesta (s) | Resultado |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 10 | `la-colonia-smoke-10-004` | `16216fcd55336b5626796e56a853edf95a4e9cbc` | `31029403314` | `31029426216` | `8940008559` | 20 | 21695 | 1.733578 | 0.114573 | aceptado |
| 20 | `la-colonia-smoke-20-001` | `747b950c0b048b2e3f1993dd8a7cf16ad72f578d` | `31029708366` | `31029728345` | `8940131295` | 40 | 42520 | 2.784899 | 0.639207 | aceptado |
| 30 | `la-colonia-smoke-30-001` | `e19b4170d2072a4cd51cc95b5d34a9bbabcd7668` | `31030837848` | `31030854363` | `8940583167` | 60 | 62137 | 3.312173 | 0.901944 | aceptado |
| 50 | `la-colonia-smoke-50-001` | `b9fee4d49f27e957f191c1ccd21ebf6b0b0cd308` | `31031105558` | `31031119831` | `8940690642` | 100 | 106217 | 2.994802 | 0.740312 | aceptado |

En los cuatro smokes hubo cobertura completa, cero errores, cero eventos estructurales, cero duplicados, cero reintentos y cero bloqueos HTTP. El total permaneció en `9291`.

Se recomienda `page_size = 20`: es el menor tamaño probado que reduce las solicitudes estimadas un 50 % frente a tamaño 10, de 930 a 465 páginas, sin aumentar el riesgo observado. Los tamaños 30 y 50 también fueron aceptados, pero incrementan el payload por petición.

## Staged baseline de diez páginas

Solicitud operacional:

```json
{
  "request_id": "la-colonia-staged-pages-20-001",
  "supermarket": "la_colonia",
  "mode": "staged",
  "page_size": 20,
  "max_pages": 10,
  "max_products": 0,
  "delay_seconds": 1.5,
  "profile": "baseline",
  "thresholds": null,
  "allow_full": false
}
```

Trazabilidad:

```text
commit_sha = 6185ac4671694784d5d0c0becabfaae340f0dd7d
controller_run_id = 31032502746
live_run_id = 31032519694
artifact_id = 8941246437
exit_code = 0
```

Resultado global:

| Métrica | Valor |
|---|---:|
| `accepted` | `true` |
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
| `duration_seconds` | 20.344055 |
| `average_response_seconds` | 0.6815969079 |
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
| `full_started` | `false` |

Resultado por página:

| Página | Rango | Esperados | Devueltos | SKU devueltos | SKU extraídos | SKU con precio | Bytes | Respuesta (s) | Accepted | Eventos de calidad |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | 0–19 | 20 | 20 | 20 | 20 | 20 | 21631 | 0.164400 | true | disponibilidad/precio con cantidad cero |
| 2 | 20–39 | 20 | 20 | 20 | 20 | 20 | 20889 | 0.031345 | true | disponibilidad/precio con cantidad cero |
| 3 | 40–59 | 20 | 20 | 20 | 20 | 20 | 19681 | 0.442693 | true | disponibilidad/precio con cantidad cero |
| 4 | 60–79 | 20 | 20 | 20 | 20 | 20 | 22947 | 0.659116 | true | disponibilidad/precio con cantidad cero |
| 5 | 80–99 | 20 | 20 | 20 | 20 | 20 | 21261 | 0.511892 | true | disponibilidad/precio con cantidad cero |
| 6 | 100–119 | 20 | 20 | 20 | 20 | 20 | 22037 | 0.844520 | true | disponibilidad/precio con cantidad cero |
| 7 | 120–139 | 20 | 20 | 20 | 20 | 20 | 19879 | 0.480741 | true | disponibilidad/precio con cantidad cero |
| 8 | 140–159 | 20 | 20 | 20 | 20 | 20 | 24620 | 2.231997 | true | disponibilidad/precio con cantidad cero |
| 9 | 160–179 | 20 | 20 | 20 | 20 | 20 | 27509 | 0.818855 | true | disponibilidad/precio con cantidad cero |
| 10 | 180–199 | 20 | 20 | 20 | 20 | 20 | 26181 | 0.630410 | true | disponibilidad/precio con cantidad cero |

El desglose por página no incluye un campo independiente `skus_with_price`; el valor 20 por página se deriva necesariamente de 20 SKU extraídos en cada página y `200/200` SKU con precio en el agregado.

## Continuidad y ordenamiento

La ejecución staged confirmó:

- rangos consecutivos desde `0–19` hasta `180–199`;
- ausencia de saltos y solapamientos;
- diez tamaños de página completos y constantes;
- orden constante `OrderByNameASC`;
- diez firmas de página diferentes;
- ninguna página repetida;
- ninguna detención anticipada;
- total inicial y final iguales a `9291`;
- cero duplicados globales de SKU y producto.

La advertencia `ordering_is_not_strictly_unique` continúa documentada porque el orden público no incluye una llave secundaria única. En este staged no hubo evidencia observable de movimiento entre páginas, repetición, ausencia, solapamiento ni cambio del total relacionado con el ordenamiento.

## Disponibilidad

Las diez páginas registraron:

```text
quality:availability_conflict_price_with_zero_quantity
```

Los `200` SKU quedaron pendientes de revisión: proporción `200 / 200 = 1.0` o `100 %`.

La proporción no cambió respecto a los smokes, donde también todos los SKU de cada muestra quedaron pendientes. Continúa siendo una advertencia de calidad no estructural: no provocó rechazo, pérdida de precios, errores, duplicados ni interrupción del recorrido. Esta ejecución por sí sola no justifica modificar la regla de disponibilidad.

## Baseline y umbrales

Ratios observados en el staged:

```text
missing_price_ratio = 0.0
duplicate_sku_ratio = 0.0
duplicate_product_ratio = 0.0
total_change_ratio = 0.0
```

Umbrales propuestos:

```json
{
  "max_missing_price_ratio": 0.01,
  "max_duplicate_sku_ratio": 0.005,
  "max_duplicate_product_ratio": 0.005,
  "max_total_change_ratio": 0.002
}
```

La propuesta coincide exactamente con el smoke de `page_size = 50`.

Márgenes sobre los ratios observados:

- precios faltantes: `+0.01`, equivalente a 1 punto porcentual;
- SKU duplicados: `+0.005`, equivalente a 0.5 puntos porcentuales;
- productos duplicados: `+0.005`, equivalente a 0.5 puntos porcentuales;
- cambio del total: `+0.002`, equivalente a 0.2 puntos porcentuales.

La muestra staged de 200 SKU puede funcionar como baseline principal para definir estos cuatro umbrales porque duplica la muestra mínima y confirma los mismos valores observados en el smoke de 100 SKU. Los umbrales siguen sin activarse automáticamente y no cubren el conflicto de disponibilidad ni demuestran todavía estabilidad en recorridos de 500 productos o del catálogo completo.

## Siguiente ejecución propuesta

La siguiente etapa, todavía no ejecutada, debe repetir las mismas diez páginas con perfil `validation` y umbrales explícitos:

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

Esta solicitud no debe iniciarse hasta revisar y aprobar formalmente el staged baseline.

## Estado de etapas live

```text
Smoke       -> 2 páginas: completado para 10, 20, 30 y 50
Staged 1    -> 10 páginas con page_size 20, baseline: completado y aceptado
Validation  -> 10 páginas con page_size 20 y umbrales explícitos: pendiente
500 SKU     -> baseline y validation: pendiente
Full        -> no ejecutado; solo después de todas las etapas y preflight seguro
```

## Pruebas offline

Estado anterior al staged:

```text
Python 3.12.13
compilación correcta
149 passed in 0.49s
```

La solicitud staged y esta actualización documental no modifican código ejecutable.

## Informes

El workflow genera temporalmente:

```text
run-artifacts/run-summary.json
run-artifacts/run-summary.md
```

Los informes contienen métricas, hashes limitados y resúmenes de página. No contienen el catálogo completo.

## Limpieza y fuera de alcance

El archivo operacional conserva la última solicitud procesada y se limpiará antes de una futura fusión del PR.

No se implementan en esta fase:

- Google Sheets;
- BigQuery;
- base de datos;
- historial;
- tablas `current` o `history`;
- `not_listed` definitivo;
- workflow diario;
- comparación entre supermercados;
- Power BI;
- segundo supermercado.

El PR debe permanecer abierto, en borrador y sin fusionar hasta completar las etapas de validación autorizadas.
