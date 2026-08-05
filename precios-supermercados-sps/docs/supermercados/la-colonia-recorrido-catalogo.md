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

Los tamaños live permitidos para evaluación son:

```text
10
20
30
50
```

No se asume que `50` sea seguro. Cada tamaño debe evaluarse con una muestra pequeña antes de utilizarlo en etapas mayores.

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
Smoke       -> 2 páginas
Staged 1    -> 10 páginas
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
