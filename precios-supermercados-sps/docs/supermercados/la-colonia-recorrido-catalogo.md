# La Colonia — recorrido y validación del catálogo

## Alcance y controles

Esta fase valida el recorrido secuencial del catálogo público de La Colonia sin persistir productos, precios ni historial.

Controles vigentes:

- `page_size = 20`;
- concurrencia fija en `1`;
- pausa de `1.5` segundos;
- productos mantenidos solo en memoria;
- workflow live exclusivamente bajo `workflow_dispatch`;
- controlador por archivo ejecutado desde código confiable de `main`;
- observador de solo lectura para recuperar identificadores;
- artefactos sanitizados `run-summary.json` y `run-summary.md`;
- `allow_full = false`;
- ningún producto, SKU individual, nombre comercial, URL o precio publicado.

## Etapas anteriores aprobadas

| Etapa | Live run | Artefacto | Productos | Perfil | Resultado |
|---|---:|---:|---:|---|---|
| Baseline de diez páginas | `31032519694` | `8941246437` | 200 | baseline | aceptado |
| Validation de diez páginas | `31033885905` | `8941767177` | 200 | validation | aceptada |

Ambas ejecuciones completaron diez páginas, 200 productos y 200 SKU con precio; registraron cero duplicados, errores, eventos estructurales, HTTP 403 del sitio, HTTP 429, HTTP 5xx y reintentos. Los cuatro ratios observados fueron `0.0`.

## Baseline solicitado de 500 productos

Solicitud operacional:

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

Trazabilidad:

```text
commit_sha = 2ec8d4c0a9bfebf88a3402281b3129f3ebdbf696
controller_run_id = 31035067808
controller_job_id = 92404979751
controller_artifact_id = 8942217742
controller_artifact_digest = sha256:b168bc235371057d0c0f44305fff1300b366cb58e095fd48fe33a352e7c19d03
observer_run_id = 31035101626
observer_job_id = 92405095589
live_run_id = 31035091894
live_job_id = 92405070961
run_number = 29
live_artifact_id = 8942244270
live_artifact_digest = sha256:9f4592d15b73be641125fde7675078eaced07da6ac5a6feac2798fed130ddc14
exit_code = 2
```

El controlador terminó correctamente y despachó una sola ejecución. El observador falló de forma intencional para exponer los identificadores después de que GitHub bloqueara el comentario del `GITHUB_TOKEN`. Ese HTTP 403 fue operacional de GitHub, no del sitio de La Colonia.

## Resultado global

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
| `duration_seconds` | 43.700291 |
| `average_response_seconds` | 0.7571339955500005 |
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

## Resultado por página

| Página | Rango | Esperados | Devueltos | SKU devueltos | SKU extraídos | Bytes | Respuesta (s) | Accepted | Eventos de calidad | Firma repetida |
|---:|---|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | 0–19 | 20 | 20 | 20 | 20 | 21631 | 0.847033 | true | disponibilidad/precio con cantidad cero | no |
| 2 | 20–39 | 20 | 20 | 20 | 20 | 20889 | 0.328329 | true | disponibilidad/precio con cantidad cero | no |
| 3 | 40–59 | 20 | 20 | 20 | 20 | 19681 | 0.104574 | true | disponibilidad/precio con cantidad cero | no |
| 4 | 60–79 | 20 | 20 | 20 | 20 | 22947 | 1.122780 | true | disponibilidad/precio con cantidad cero | no |
| 5 | 80–99 | 20 | 20 | 20 | 20 | 21261 | 0.324365 | true | disponibilidad/precio con cantidad cero | no |
| 6 | 100–119 | 20 | 20 | 20 | 20 | 22037 | 0.305892 | true | disponibilidad/precio con cantidad cero | no |
| 7 | 120–139 | 20 | 20 | 20 | 20 | 19879 | 1.126288 | true | disponibilidad/precio con cantidad cero | no |
| 8 | 140–159 | 20 | 20 | 20 | 20 | 24620 | 0.319887 | true | disponibilidad/precio con cantidad cero | no |
| 9 | 160–179 | 20 | 20 | 20 | 20 | 27509 | 0.070862 | true | disponibilidad/precio con cantidad cero | no |
| 10 | 180–199 | 20 | 20 | 20 | 20 | 26181 | 0.297943 | true | disponibilidad/precio con cantidad cero | no |
| 11 | 200–219 | 20 | 20 | 20 | 20 | 24163 | 0.945739 | true | disponibilidad/precio con cantidad cero | no |
| 12 | 220–239 | 20 | 20 | 20 | 20 | 22810 | 0.576145 | true | disponibilidad/precio con cantidad cero | no |
| 13 | 240–259 | 20 | 20 | 20 | 20 | 22416 | 0.699540 | true | disponibilidad/precio con cantidad cero | no |
| 14 | 260–279 | 20 | 20 | 20 | 20 | 24736 | 1.408019 | true | disponibilidad/precio con cantidad cero | no |
| 15 | 280–299 | 20 | 20 | 20 | 20 | 25020 | 1.283125 | true | disponibilidad/precio con cantidad cero | no |
| 16 | 300–319 | 20 | 20 | 20 | 20 | 20448 | 0.846833 | true | disponibilidad/precio con cantidad cero | no |
| 17 | 320–339 | 20 | 20 | 20 | 20 | 22082 | 0.722370 | true | disponibilidad/precio con cantidad cero | no |
| 18 | 340–359 | 20 | 20 | 20 | 20 | 21929 | 0.654179 | true | disponibilidad/precio con cantidad cero | no |
| 19 | 360–379 | 20 | 20 | 20 | 20 | 24848 | 0.796609 | true | disponibilidad/precio con cantidad cero | no |
| 20 | 380–399 | 20 | 19 | 19 | 19 | 20957 | 2.362169 | false | disponibilidad/precio con cantidad cero; página parcial local y global | no |
| 21 | 400–419 | 20 | No intentada | No intentada | No intentada | No disponible | No disponible | No evaluada | detención tras página parcial | No evaluada |
| 22 | 420–439 | 20 | No intentada | No intentada | No intentada | No disponible | No disponible | No evaluada | detención tras página parcial | No evaluada |
| 23 | 440–459 | 20 | No intentada | No intentada | No intentada | No disponible | No disponible | No evaluada | detención tras página parcial | No evaluada |
| 24 | 460–479 | 20 | No intentada | No intentada | No intentada | No disponible | No disponible | No evaluada | detención tras página parcial | No evaluada |
| 25 | 480–499 | 20 | No intentada | No intentada | No intentada | No disponible | No disponible | No evaluada | detención tras página parcial | No evaluada |

Las primeras 19 páginas fueron completas y aceptadas. La página 20, rango `380–399`, devolvió 19 productos en vez de 20. Las páginas 21–25 no fueron intentadas porque el runner detuvo correctamente la ejecución después del rechazo.

## Causa y clasificación

La página parcial no era una última página legítima:

```text
products_reported_initial = 9291
products_reported_final = 9291
rango parcial = 380–399
productos esperados = 20
productos devueltos = 19
```

La respuesta fuente contenía 19 productos y 19 SKU. No hubo pérdida adicional durante el parseo. El extractor detectó la diferencia y rechazó la página, por lo que la evidencia disponible indica:

- controlador: correcto;
- observador: recuperación controlada correcta;
- workflow live: reflejó correctamente el código de salida `2`;
- red: sin HTTP 403 del sitio, HTTP 429, HTTP 5xx o reintentos;
- parser: sin evidencia de pérdida, pues productos y SKU retornados fueron 19;
- runner y regla de aceptación: comportamiento correcto;
- causa observable: respuesta parcial o inestabilidad de paginación del sitio/API pública;
- relación posible con `ordering_is_not_strictly_unique`: no demostrada, pero permanece como riesgo.

No se modifica código ni se flexibiliza la regla.

## Continuidad y ordenamiento

Para las páginas completas 1–19 se observó:

- rangos consecutivos desde `0–19` hasta `360–379`;
- tamaño constante de 20;
- ninguna página vacía;
- ningún salto ni solapamiento;
- 19 firmas distintas;
- cero duplicados globales;
- orden constante `OrderByNameASC`.

La página 20 tuvo una firma distinta, pero fue parcial. En total se observaron 20 firmas diferentes y ninguna repetida. No puede confirmarse continuidad de las 25 páginas porque el recorrido se detuvo antes de `400–419`.

No se declara que `OrderByNameASC` sea estrictamente estable.

## Pausa aplicada

Se intentaron 20 páginas. La pausa esperada antes de detenerse era:

```text
19 intervalos × 1.5 segundos = 28.5 segundos
```

El artefacto reportó exactamente `delay_seconds_applied = 28.5`. Los 36 segundos previstos para 25 páginas no se aplicaron porque las páginas 21–25 no se intentaron.

## Disponibilidad

Las 20 respuestas intentadas registraron:

```text
quality:availability_conflict_price_with_zero_quantity
```

```text
páginas afectadas = 20 de 20 intentadas
skus_pending_review = 380
skus_extracted = 380
proporción pendiente = 100 %
baseline 200 = 100 %
validation 200 = 100 %
diferencia = 0 puntos porcentuales
```

La regla de disponibilidad no se modifica. Los cuatro ratios actuales no cubren este conflicto.

## Ratios y umbrales propuestos

| Ratio | Baseline 200 | Validation 200 | Baseline 500 rechazado | Umbral anterior | Propuesta del run | Decisión |
|---|---:|---:|---:|---:|---:|---|
| `missing_price_ratio` | 0.0 | 0.0 | 0.0 | 0.01 | 0.01 | sin cambio, pero no autoriza validation |
| `duplicate_sku_ratio` | 0.0 | 0.0 | 0.0 | 0.005 | 0.005 | sin cambio, pero no autoriza validation |
| `duplicate_product_ratio` | 0.0 | 0.0 | 0.0 | 0.005 | 0.005 | sin cambio, pero no autoriza validation |
| `total_change_ratio` | 0.0 | 0.0 | 0.0 | 0.002 | 0.002 | sin cambio, pero no autoriza validation |

Los umbrales propuestos coinciden con los anteriores. No se activan ni se ejecuta validation de 500 porque el baseline no completó la muestra.

## Comparación de ejecuciones

| Métrica | Baseline 200 | Validation 200 | Baseline 500 rechazado | Diferencia 500 vs baseline 200 | Decisión |
|---|---:|---:|---:|---:|---|
| `products_reported_initial` | 9291 | 9291 | 9291 | 0 | total estable |
| `products_reported_final` | 9291 | 9291 | 9291 | 0 | total estable |
| `products_returned` | 200 | 200 | 399 | +199 | ejecución incompleta |
| `products_processed` | 200 | 200 | 380 | +180 | ejecución incompleta |
| `skus_returned` | 200 | 200 | 399 | +199 | ejecución incompleta |
| `skus_extracted` | 200 | 200 | 380 | +180 | ejecución incompleta |
| `skus_with_price` | 200 | 200 | 380 | +180 | 100 % de lo procesado |
| `skus_without_price` | 0 | 0 | 0 | 0 | sin faltantes |
| `skus_pending_review` | 200 | 200 | 380 | +180 | 100 % de lo procesado |
| `promotional_skus` | 17 | 17 | 42 | +25 | muestra mayor e incompleta |
| `weighted_skus` | 0 | 0 | 0 | 0 | sin cambio |
| `duplicate_skus` | 0 | 0 | 0 | 0 | sin duplicados |
| `duplicate_products` | 0 | 0 | 0 | 0 | sin duplicados |
| `response_bytes` | 226635 | 226635 | 456044 | +229409 | muestra mayor e incompleta |
| `duration_seconds` | 20.344055 | 14.081743 | 43.700291 | +23.356236 | incluye 20 intentos |
| `average_response_seconds` | 0.6815969079 | 0.0552162360 | 0.7571339956 | +0.0755370877 | mayor promedio |
| `average_response_bytes` | 22663.5 | 22663.5 | 22802.2 | +138.7 | diferencia menor |
| `missing_price_ratio` | 0.0 | 0.0 | 0.0 | 0.0 | sin cambio |
| `duplicate_sku_ratio` | 0.0 | 0.0 | 0.0 | 0.0 | sin cambio |
| `duplicate_product_ratio` | 0.0 | 0.0 | 0.0 | 0.0 | sin cambio |
| `total_change_ratio` | 0.0 | 0.0 | 0.0 | 0.0 | sin cambio |
| `errors` | 0 | 0 | 1 | +1 | rechazo |
| `structural_events` | 0 | 0 | 0 | 0 | sin cambio |
| `http_403` | 0 | 0 | 0 | 0 | sin bloqueo del sitio |
| `http_429` | 0 | 0 | 0 | 0 | sin bloqueo |
| `persistent_http_429` | 0 | 0 | 0 | 0 | sin bloqueo |
| `http_5xx` | 0 | 0 | 0 | 0 | sin fallo de servidor |
| `retries` | 0 | 0 | 0 | 0 | sin reintentos |
| `warnings` | orden no único | orden no único | orden no único | sin cambio | riesgo permanece |
| `rejection_reasons` | [] | [] | 5 razones | +5 | baseline rechazado |

Ratios normalizados:

```text
promociones por 100 SKU:
- baseline 200 = 8.5
- baseline 500 incompleto = 11.0526

bytes por SKU extraído:
- baseline 200 = 1133.175
- baseline 500 incompleto = 1200.1158

pendientes por 100 SKU:
- baseline 200 = 100
- validation 200 = 100
- baseline 500 incompleto = 100
```

La diferencia promocional no se interpreta como error.

## Decisión

El baseline de 500 productos queda rechazado.

No se ejecutan:

- una repetición automática;
- validation de 500;
- `full`.

No existe evidencia de defecto de código que justifique modificar runner, parser, workflows, controlador, observador, contratos, modelos o pruebas. Antes de cualquier repetición debe revisarse y documentarse una estrategia explícita para confirmar si la página parcial fue una anomalía transitoria del sitio o un efecto reproducible de la paginación no estrictamente única.

## Estado del PR y restricciones

- PR #7 abierto.
- PR #7 en borrador.
- PR #7 no fusionado.
- Auto-merge deshabilitado.
- `full` no ejecutado.
- Validation de 500 no ejecutada.
- Archivo operacional conservado.
- Limpieza operacional pendiente antes de una futura fusión.
- Sin persistencia, historial, ejecución diaria, Google Sheets, BigQuery, Power BI ni segundo supermercado.
