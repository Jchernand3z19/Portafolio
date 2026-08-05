# La Colonia — recorrido y diagnóstico de paginación

## Estado verificado

La investigación se realizó sobre el PR `#7`, rama `feature/la-colonia-full-crawl-validation`.

- PR abierto, en borrador y no fusionado.
- Head inicial verificado: `2da8af8fea2816f4970629d4082f02d0baca3abc`.
- No existía una tercera repetición del baseline de 500.
- La validation de 500 no se había ejecutado.
- `full` no se había ejecutado.
- El workflow live continuaba únicamente bajo `workflow_dispatch`.
- El archivo operacional conservaba `la-colonia-baseline-products-500-002` y no fue modificado durante el diagnóstico.

La fase continúa sin persistencia, historial, ejecución diaria, Google Sheets, BigQuery ni Power BI. Ninguna página parcial es aceptable.

## Ejecuciones existentes inspeccionadas

| Intento | Live run | Job | Artefacto | Resultado |
|---|---:|---:|---:|---|
| Baseline 500 #1 | `31035091894` | `92405070961` | `8942244270` | rechazado, exit code 2 |
| Baseline 500 #2 | `31037207732` | `92412185299` | `8943081061` | rechazado, exit code 2 |

En ambos runs:

```text
pages_expected = 25
pages_attempted = 20
pages_completed = 19
page_coverage = 0.76
products_reported_initial = 9291
products_reported_final = 9291
products_returned = 399
products_processed = 380
skus_returned = 399
skus_extracted = 380
errors = 1
structural_events = 0
http_403 = 0
http_429 = 0
persistent_http_429 = 0
http_5xx = 0
retries = 0
duplicate_skus = 0
duplicate_products = 0
total_change_ratio = 0.0
```

Las páginas `1–19` coincidieron exactamente en rangos, conteos, bytes, firmas sanitizadas y total del catálogo. La página `20`, rango `380–399`, coincidió exactamente en ambos artefactos:

```text
productos esperados = 20
productos entregados por GraphQL = 19
productos observados por el runner = 19
SKU entregados = 19
SKU extraídos = 19
bytes = 20957
firma = c86ae16a7b54543c8c7e68422b70fb7dbe5eb06a27395f0f76b1c65f0e3ef5ca
accepted = false
```

Solo cambiaron tiempos e identificadores de ejecución. Los archivos `run-summary.json` difieren únicamente en tiempos, timestamps e IDs; el contenido diagnóstico restante es idéntico.

## Contrato comprobado en el código

### Ventanas

`build_product_search_url` calcula:

```text
from = (page - 1) * page_size
to = from + page_size - 1
```

Para página `20` y `page_size = 20`:

```text
from = 380
to = 399
ancho = to - from + 1 = 20
```

El código trata `to` como inclusivo. Las primeras 19 páginas completas también son coherentes con esa semántica.

### Tamaño esperado

El extractor calcula el esperado con el total reportado y el índice `from`:

```text
remaining = recordsFiltered - from
expected = min(page_size, remaining)
```

Con `recordsFiltered = 9291` y `from = 380`, el esperado es `20`.

### `recordsFiltered`

Se obtiene directamente de `data.productSearch.recordsFiltered`. El runner exige que sea un entero válido y no lo deriva del tamaño de `products`.

### Conteos y filtros locales

- `productos entregados por GraphQL`: longitud de `data.productSearch.products` antes del parser.
- `productos observados por el runner`: longitud de la misma lista validada por `_read_raw_page`.
- `productos aceptados para el agregado`: productos de páginas válidas únicamente.
- `SKU entregados`: suma de los elementos de `items` entregados por GraphQL.
- `SKU extraídos`: objetos que el extractor pudo convertir en contratos `RawProduct`.

El parser puede omitir SKU con estructura inválida, pero `products_returned` se cuenta antes de ese procesamiento. `_read_raw_page` no elimina silenciosamente productos no mapeables: una estructura no válida produce un evento estructural.

En los dos runs, GraphQL entregó 19 productos y el runner observó 19. No existe evidencia de que el parser o el runner hayan perdido el vigésimo producto.

### Página parcial y agregado

Una página es parcial cuando:

```text
products_returned < products_expected
```

La página parcial queda rechazada. Con `stop_on_error = true`, el recorrido se detiene. Los 19 SKU observados en la página rechazada no se incorporan al agregado final; por eso `products_processed` y `skus_extracted` permanecen en `380`.

### Firma de página e identidad

La firma es SHA-256 de la lista ordenada de claves de producto observadas en la respuesta GraphQL. La identidad de producto usa, en orden:

```text
productId
productReference
linkText
productName
marcador sintético por posición si todos faltan
```

La identidad de SKU del extractor usa las fuentes deterministas existentes del contrato, priorizando identificadores internos, referencias, EAN y URL estable según disponibilidad. La investigación no publicó ninguna identidad individual.

### Ordenamiento

El código permite:

```text
OrderByReleaseDateDESC
OrderByNameASC
OrderByNameDESC
OrderByPriceASC
OrderByPriceDESC
```

La consulta acepta un único valor `orderBy`. No existe una segunda llave de ordenamiento en el contrato utilizado ni en el código actual.

### Disponibilidad y SKU

```text
hideUnavailableItems = false
skusFilter = ALL
```

`hideUnavailableItems = false` evita pedir que la búsqueda oculte productos por disponibilidad. `skusFilter = ALL` solicita todos los SKU asociados a cada producto; no agrega productos ausentes de la lista `products`.

## Contrato oficial de VTEX revisado

Fuentes primarias revisadas: documentación oficial de `vtex.search-graphql`, `vtex.search-result` y la guía oficial de ordenamiento.

- `from`: inicio de paginación; valor predeterminado `0`.
- `to`: final de paginación; valor predeterminado `9`.
- La combinación predeterminada `0–9` y el comportamiento documentado por página son consistentes con un extremo final inclusivo.
- Máximo documentado por página: `50`.
- `recordsFiltered`: total de productos del resultado de búsqueda.
- `products`: lista de productos filtrada y ordenada.
- `OrderByNameASC`: orden alfabético ascendente por nombre.
- Solo se admite un parámetro de ordenamiento a la vez; no se documenta una llave secundaria.
- `ItemsFilter.ALL`: devuelve todos los items, equivalente a no filtrar items.
- `hideUnavailableItems = true` activa filtrado por disponibilidad; con `false` no se solicita ese ocultamiento.

La documentación oficial no garantiza que `OrderByNameASC` sea estrictamente único, no define cómo resuelve empates, no documenta filtrado posterior a la ventana y no documenta una incidencia específica que explique una respuesta determinista de 19 elementos para una ventana de 20. Esos puntos permanecen como datos no disponibles.

## Matriz de hipótesis

| Hipótesis | Evidencia a favor | Evidencia en contra | Qué explica | Qué no explica | Confianza | Evidencia necesaria |
|---|---|---|---|---|---|---|
| H1 — `recordsFiltered` incluye un registro que no puede materializarse | total 9291 estable y lista raw de 19 | no se conoce el registro ni la regla interna | inconsistencia conteo/lista | por qué ocurre justo en esa frontera | media | ventanas solapadas y traza interna de VTEX |
| H2 — el backend filtra después de aplicar `from/to` | la lista GraphQL ya llega con 19 | VTEX no documenta ese orden de operaciones; `hideUnavailableItems=false` | ventana parcial sin pérdida local | mecanismo exacto | media-baja | comparar C, D, F, G y H |
| H3 — `OrderByNameASC` no es único y crea frontera ambigua | un solo criterio y sin llave secundaria | ambas respuestas fueron idénticas, no fluctuantes | desplazamiento o duplicación entre ventanas | ausencia determinista sin solapamientos medidos | media | solapamientos y segunda pasada controlada con otro orden permitido |
| H4 — cálculo incorrecto de `from/to` | ninguna | fórmula correcta; páginas 1–19 completas y consecutivas | nada observado | respuesta raw de 19 | muy baja | no requiere nueva prueba salvo regresión offline |
| H5 — el parser elimina un producto | ninguna | GraphQL y runner ya observan 19 | nada | origen del faltante | descartada para este conteo | no aplica |
| H6 — el runner pierde un producto antes del agregado | explica por qué el agregado no suma 19, pero eso es intencional | el runner observa 19 y rechaza la página según diseño | `380` aceptados | origen del vigésimo faltante | descartada como causa | no aplica |
| H7 — producto con estructura especial no aparece en `products` | compatible con diferencia entre total y lista | no existe payload ni traza del elemento ausente | 19 materializados | tipo de estructura y etapa de exclusión | media-baja | solapamientos y evidencia de backend |
| H8 — inconsistencia determinista entre índice/conteo y materialización en la capa VTEX | mismos bytes, firma, total y conteos; sin errores HTTP ni reintentos | no existe acceso a trazas internas | reproducibilidad completa y frontera estable | mecanismo interno preciso | media-alta | diagnóstico de ventanas solapadas; soporte o traza primaria de VTEX |

## Conclusión técnica

1. No está demostrado un error del parser.
2. No está demostrado un error del runner; el rechazo y la detención son correctos.
3. No está demostrado un error en la construcción de `from/to`.
4. No está demostrado que `OrderByNameASC` sea la causa.
5. No está demostrado que VTEX filtre después de paginar.
6. La hipótesis más fuerte es una inconsistencia determinista dentro de la capa VTEX entre el total/índice de búsqueda y la lista de productos materializados para la frontera `380–399`.
7. Falta observar identidades de forma privada entre ventanas solapadas y disponer de una explicación o traza primaria del backend.
8. La arquitectura normal no debe flexibilizarse. Debe instrumentarse de forma aislada y sanitizada para obtener evidencia discriminante.

La causa raíz no está demostrada.

## Instrumentación implementada

Se agregó un módulo aislado de diagnóstico de ventanas. No modifica el runner normal, no acepta páginas parciales y no está conectado a ningún trigger live.

Capacidades:

- valida ventanas inclusivas de hasta 50 posiciones;
- construye consultas exactas por `from/to`;
- observa conteos antes del parser de SKU;
- calcula firma completa de ventana;
- mantiene identidades únicamente en memoria;
- calcula solapamiento esperado y observado;
- calcula productos únicos en la unión;
- detecta faltantes, duplicados, desplazamientos y cambios de total;
- serializa solo agregados sanitizados;
- bloquea identificadores directos y hashes individuales;
- limita el artefacto diagnóstico a 64 KiB.

No se modificaron:

- `la_colonia_runner.py`;
- `probar_la_colonia.py`;
- workflow live;
- controlador operacional;
- archivo `.automation/la-colonia-live-command.json`.

## Pruebas offline

Estado inicial verificado:

```text
149 passed
```

Instrumentación nueva:

```text
22 pruebas sintéticas
```

CI final verificado:

```text
python -m compileall src        éxito
pytest tests                    171 passed in 0.40s
workflow run                    31040296699
job                            92422688396
```

Las pruebas demuestran que la instrumentación distingue escenarios sintéticos; no afirman cuál fue la causa en producción.

## Próxima prueba diagnóstica

```text
NO AUTORIZADA TODAVÍA
```

Objetivo: distinguir entre registro no materializable, filtrado posterior a ventana, desplazamiento por orden no único y anomalía exclusiva de la ventana exacta.

Primera fase, `OrderByNameASC`:

```text
A = 360–379
B = 370–389
C = 380–399
D = 390–409
E = 400–419
F = 380–389
G = 390–399
H = 350–399
```

Segunda fase opcional, únicamente si la primera mantiene total estable y resultado ambiguo:

```text
C, F, G y H con OrderByReleaseDateDESC
```

Límite máximo: 12 solicitudes. Concurrencia: 1. Pausa: 1.5 segundos.

Criterios de detención:

- cualquier HTTP 403, 429 persistente o 5xx;
- cambio del total;
- evento estructural;
- tamaño de artefacto superior al límite;
- intento de publicar datos prohibidos.

Métricas permitidas:

```text
ventana
from
to
productos esperados
productos devueltos
SKU devueltos
recordsFiltered
bytes
firma de ventana
solapamiento esperado
solapamiento observado
productos únicos en la unión
duplicados agregados
total inicial
total final
eventos de calidad
```

Request ID propuesto:

```text
la-colonia-window-diagnostic-380-399-001
```

Antes de autorizarla se requieren cambios separados y revisados en el controlador y workflow para aceptar únicamente el modo diagnóstico, una lista fija de ventanas, máximo 12 solicitudes y artefactos sanitizados. El archivo operacional vigente no debe cambiar hasta que la prueba sea autorizada expresamente.

## Bloqueos vigentes

- Tercera repetición normal de 500: bloqueada.
- Validation de 500: bloqueada.
- `full`: no ejecutado y bloqueado.
- PR: debe permanecer abierto, en borrador, sin auto-merge y sin fusionar.
