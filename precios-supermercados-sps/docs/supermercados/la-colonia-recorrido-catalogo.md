# La Colonia — recorrido y diagnóstico de paginación

## Estado y alcance

Esta fase valida el recorrido secuencial del catálogo público de La Colonia sin persistir productos, precios ni historial.

Estado verificado el 5 de agosto de 2026:

- PR `#7` abierto, en borrador y sin fusionar.
- Rama `feature/la-colonia-full-crawl-validation`.
- `page_size = 20`.
- Concurrencia fija en `1`.
- Pausa de `1.5` segundos.
- Workflow live exclusivamente bajo `workflow_dispatch`.
- `allow_full = false`.
- Ninguna página parcial es aceptable.
- No existe persistencia, historial, ejecución diaria, Google Sheets, BigQuery ni Power BI.
- No se publican productos, SKU individuales, nombres, marcas, URLs ni precios.
- Validation de 500 bloqueada.
- `full` no ejecutado.
- No se autorizó ni ejecutó una tercera repetición normal del baseline de 500.

## Etapas completadas

| Etapa | Resultado |
|---|---|
| Smokes `page_size` 10, 20, 30 y 50 | aceptados |
| Baseline de 200 productos | aceptado |
| Validation de 200 productos | aceptada |
| Primer baseline de 500 | rechazado en rango `380–399` |
| Única repetición diagnóstica de 500 | rechazado en el mismo rango |

## Dos rechazos reproducibles

### Primer intento

```text
request_id = la-colonia-baseline-products-500-001
commit_sha = 2ec8d4c0a9bfebf88a3402281b3129f3ebdbf696
controller_run_id = 31035067808
observer_run_id = 31035101626
live_run_id = 31035091894
live_job_id = 92405070961
artifact_id = 8942244270
exit_code = 2
accepted = false
```

### Segunda y única repetición diagnóstica

```text
request_id = la-colonia-baseline-products-500-002
commit_sha = 5c1ecb81eb8efb1c4f9043ee65614b8b93136861
controller_run_id = 31037185265
observer_run_id = 31037217937
live_run_id = 31037207732
live_job_id = 92412185299
artifact_id = 8943081061
exit_code = 2
accepted = false
```

### Resultado común

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

Las páginas 1–19 coincidieron exactamente entre los dos artefactos, salvo tiempos:

- mismos rangos;
- 20 productos y 20 SKU por página;
- mismos bytes;
- mismas firmas de página;
- mismo total `9291`;
- sin errores HTTP, reintentos ni duplicados.

La página 20 coincidió exactamente:

```text
rango = 380–399
productos esperados = 20
productos devueltos por GraphQL = 19
productos observados por el runner = 19
SKU devueltos = 19
SKU extraídos por el extractor = 19
bytes = 20957
firma = c86ae16a7b54543c8c7e68422b70fb7dbe5eb06a27395f0f76b1c65f0e3ef5ca
accepted = false
```

Solo cambió el tiempo de respuesta:

```text
primer intento = 2.362169 s
segunda ejecución = 0.357741 s
```

## Evidencia del código

### Construcción de la ventana

El código calcula:

```text
from = (page - 1) * page_size
to = from + page_size - 1
```

Para `page = 20` y `page_size = 20`:

```text
from = 380
to = 399
tamaño = to - from + 1 = 20
```

El runner valida además:

- primera página en `from = 0`;
- `to - from + 1 == page_size`;
- siguiente `from == previous_to + 1`;
- ausencia de solapamientos y huecos;
- ordenamiento constante durante el run.

No se observó error en la construcción o continuidad de `from/to`.

### Productos entregados, observados y aceptados

El runner lee primero `data.productSearch.products` directamente del JSON mediante `_read_raw_page`. Esa función:

- exige que `products` sea una secuencia;
- exige que todos sus elementos sean objetos;
- no elimina silenciosamente productos;
- devuelve la lista y el `recordsFiltered` exacto.

Después, el extractor vuelve a leer el mismo payload y establece:

```text
products_returned = len(data.productSearch.products)
```

En ambos runs, las dos capas observaron `19`.

Distinción vigente:

| Concepto | Página 20 | Explicación |
|---|---:|---|
| Productos entregados por GraphQL | 19 | longitud de `data.productSearch.products` |
| Productos observados por el runner | 19 | `_read_raw_page` |
| Productos observados por el extractor | 19 | `_read_product_search` |
| Productos aceptados para el agregado | 0 | página parcial rechazada |
| SKU entregados | 19 | suma de `items` de los 19 productos |
| SKU extraídos en la página | 19 | parsing local exitoso |
| SKU agregados al resultado global | 0 | la página inválida no se acumula |

Por eso el resumen global muestra:

```text
products_returned = 399
products_processed = 380
skus_returned = 399
skus_extracted = 380
```

Los 19 productos y SKU de la página rechazada se contabilizan como entregados/observados, pero no se agregan al resultado aceptado.

### Página parcial

El tamaño esperado se calcula como:

```text
min(page_size, max(products_reported_initial - from, 0))
```

Con total inicial `9291`, `from = 380` y `page_size = 20`, el esperado es `20`.

La página es parcial cuando:

```text
len(raw_products) < expected_products
```

La regla genera `partial_product_page`, marca la página como inválida y detiene el recorrido. La regla no se modificó.

### Firma e identidad

La firma de página es SHA-256 sobre la lista ordenada de claves de producto de la respuesta GraphQL.

La clave de producto usa, por precedencia:

```text
productId
productReference
linkText
productName
```

La identidad de cada `RawProduct`/SKU usa la selección estable existente:

```text
itemId
referenceId o productReference
EAN
productId
URL estable
```

No se publican esas identidades en este documento.

### Ordenamientos permitidos

La capa GraphQL permite:

```text
OrderByReleaseDateDESC
OrderByNameASC
OrderByNameDESC
OrderByPriceASC
OrderByPriceDESC
```

El script live normal expone únicamente:

```text
OrderByNameASC
OrderByReleaseDateDESC
```

No existe en el contrato utilizado un argumento separado para una segunda llave de ordenamiento. El código tampoco agrega una llave secundaria.

### `hideUnavailableItems` y `skusFilter`

La solicitud usa:

```text
hideUnavailableItems = false
skusFilter = ALL
```

`hideUnavailableItems = false` evita solicitar que la búsqueda oculte productos no disponibles. `skusFilter = ALL` controla los SKU materializados dentro de cada producto y solicita todos los SKU, no solo los disponibles. Este segundo parámetro no define cuántos productos hay en la ventana.

## Contrato oficial de VTEX

Fuentes primarias consultadas:

- [Search GraphQL — VTEX](https://developers.vtex.com/docs/apps/vtex.search-graphql)
- [Search Result — VTEX](https://developers.vtex.com/docs/apps/vtex.search-result%403.x)
- [search-resolver — repositorio oficial](https://github.com/vtex-apps/search-resolver)

Hechos documentados:

- `from` es el índice inicial de paginación; valor predeterminado `0`.
- `to` es el índice final de paginación; valor predeterminado `9`.
- La combinación predeterminada `0–9` y una página predeterminada de 10 demuestra la semántica operacional inclusiva.
- El máximo documentado por página es `50`.
- `recordsFiltered` es el número total de productos del resultado filtrado.
- `OrderByNameASC` ordena alfabéticamente por nombre.
- `orderBy` es un único argumento de texto.
- `hideUnavailableItems = false` no solicita ocultar productos no disponibles.
- `skusFilter = ALL` devuelve todos los SKU de cada producto.

No está documentado oficialmente:

- una garantía de orden total estable cuando varios productos empatan por nombre;
- una segunda llave de ordenamiento;
- que VTEX filtre productos después de aplicar `from/to`;
- que `recordsFiltered` incluya registros que luego no puedan materializarse;
- una incidencia oficial donde una ventana válida devuelva menos elementos;
- el mecanismo interno exacto que produjo `19` en `380–399`.

## Clasificación de evidencia

| Afirmación | Clasificación | Estado |
|---|---|---|
| La respuesta GraphQL de la ventana contenía 19 productos | Hecho comprobado en los runs | demostrado |
| El parser observó 19 | Hecho comprobado en código y runs | demostrado |
| El runner observó 19 | Hecho comprobado en código y runs | demostrado |
| La página fue excluida del agregado por ser parcial | Hecho comprobado en código | demostrado |
| `from = 380`, `to = 399`, tamaño 20 | Hecho comprobado en código | demostrado |
| `to` opera de forma inclusiva | Hecho comprobado en código y contrato operacional oficial | demostrado |
| `recordsFiltered = 9291` representa el total reportado | Hecho comprobado en runs y documentación oficial | demostrado |
| `OrderByNameASC` tiene empates posibles | Inferencia razonable | no confirmado para esta frontera |
| VTEX filtra después de paginar | Hipótesis | no demostrado |
| Existe un registro contado pero no materializable | Hipótesis | no demostrado |
| El parser eliminó un producto | Hipótesis contradicha | sin evidencia |
| El runner perdió un producto antes del agregado | Hipótesis contradicha | sin evidencia |
| La causa raíz interna de VTEX | Dato no disponible | no demostrada |

## Matriz de hipótesis

| Hipótesis | Evidencia a favor | Evidencia en contra | Qué explica | Qué no explica | Confianza | Prueba necesaria |
|---|---|---|---|---|---|---|
| H1 — `recordsFiltered` incluye un registro que no puede materializarse | total estable `9291`; ventana entrega 19 de forma idéntica | no hay documentación ni payload del registro ausente | diferencia entre total y lista | por qué afecta exactamente `380–399` | media | ventanas solapadas y consulta más pequeña alrededor de la frontera |
| H2 — el backend filtra un producto después de aplicar `from/to` | encaja directamente con una ventana de 20 que materializa 19 | VTEX no documenta ese orden interno | hueco de una posición sin errores HTTP | criterio exacto del filtro | media | comparar B/C/D, F/G y H; revisar uniones e intersecciones |
| H3 — `OrderByNameASC` no es único y produce una frontera ambigua | VTEX solo documenta orden por nombre; no garantiza desempate; runner advierte orden no estrictamente único | dos runs fueron deterministas, sin duplicados en páginas 1–19 | posible movimiento o empate en la frontera | por sí sola no obliga a devolver solo 19 | media-baja | repetir el diagnóstico de ventanas con el mismo orden y, bajo autorización separada, con `OrderByReleaseDateDESC` |
| H4 — error en cálculo de `from/to` | ninguno | fórmula, validaciones y páginas 1–19 son correctas; rango tiene tamaño 20 | nada observado | la respuesta estable de 19 | muy baja | no requiere live; ya contradicha por código y artefactos |
| H5 — el parser elimina un producto | ninguno | la lista cruda y el extractor observaron 19; no hubo error de producto inválido | nada observado | el conteo crudo de 19 | muy baja | no requiere nueva prueba; contradicha |
| H6 — el runner pierde un producto antes del agregado | el agregado global contiene 380 | los 19 se registran como devueltos; se excluyen únicamente después del rechazo | diferencia 399/380 como conducta intencional | origen de los 19 | muy baja | no requiere nueva prueba; contradicha |
| H7 — un producto tiene estructura especial y no aparece en `products` | compatible con un registro contado pero no materializado | no hay objeto especial ni error GraphQL visible en el artefacto | H1 desde la perspectiva de hidratación | naturaleza de la estructura | baja-media | ventanas pequeñas y evidencia interna sanitizada de posición/solapamiento |
| H8 — desajuste determinista entre el conteo del índice y la materialización/hidratación de productos | misma ventana, bytes y firma; total estable; sin red, retries o cambios | no se dispone de trazas internas de VTEX | todos los hechos observables sin culpar al parser | mecanismo interno preciso | media-alta para el desajuste; baja para el mecanismo | diagnóstico solapado; soporte o telemetría interna de VTEX para causa raíz |

## Conclusión técnica

1. No está demostrado un error del parser; la evidencia lo contradice.
2. No está demostrado un error del runner; la exclusión de los 19 productos es intencional al rechazar la página.
3. No está demostrado un error de construcción de `from/to`; el rango es correcto e inclusivo.
4. No está demostrado que `OrderByNameASC` sea la causa.
5. No está demostrado que VTEX filtre después de paginar.
6. La hipótesis más fuerte es un desajuste determinista del backend entre el total contado y la lista materializada para esa ventana.
7. Falta observar cómo se distribuyen los elementos alrededor de la frontera mediante ventanas solapadas y, para una causa interna definitiva, telemetría de VTEX.
8. La arquitectura normal no debe aceptar ni ocultar el problema. Debe conservarse y, antes de otra prueba, añadirse instrumentación diagnóstica aislada y sanitizada.

La causa raíz no está demostrada.

## Instrumentación

En esta investigación no se modificó código ejecutable.

Motivo:

- la evidencia existente ya permite descartar pérdida del parser, pérdida del runner y cálculo incorrecto de `from/to`;
- la siguiente evidencia discriminante requiere un modo dedicado de ventanas solapadas;
- ese modo debe implementarse junto con sus pruebas offline antes de cualquier nueva ejecución live;
- no es correcto introducir una instrumentación sin ejecutar su conjunto de regresión completo.

La instrumentación futura debe:

- permanecer dentro del PR `#7`;
- ser un modo separado, no una modificación del runner normal;
- usar identidades solo en memoria;
- publicar únicamente conteos, intersecciones, uniones y firmas de ventana;
- omitir identificadores y hashes individuales;
- conservar el rechazo de páginas parciales;
- no modificar el archivo operacional durante su desarrollo;
- no disparar ninguna ejecución live automáticamente.

## Diseño de diagnóstico de ventanas solapadas

Ventanas principales:

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

Solapamientos esperados:

```text
A ∩ B = 10
B ∩ C = 10
C ∩ D = 10
D ∩ E = 10
F ∩ G = 0
F ∪ G = 20
A ∪ B ∪ C ∪ D ∪ E = 60, si no hay pérdidas ni desplazamientos
H = 50, si la ventana completa se materializa
```

Interpretación mínima:

- `C = 19`, pero `F = 10`, `G = 10` y `F ∪ G = 20`: anomalía dependiente del tamaño o de la ventana exacta.
- `F = 10`, `G = 9`: el faltante se localiza en `390–399`.
- intersecciones inferiores o superiores a las esperadas: desplazamiento, duplicado o inestabilidad del orden.
- unión de A–E inferior a 60: elemento ausente no recuperado.
- unión superior a 60 o duplicados inesperados: frontera inestable o movimiento de orden.
- H completa pero C parcial: comportamiento dependiente de la ventana.
- mismo defecto bajo otro ordenamiento autorizado: reduce la probabilidad de que `OrderByNameASC` sea la única causa.
- defecto que desaparece bajo otro ordenamiento: aumenta la evidencia de dependencia del orden, sin demostrar por sí solo el mecanismo.

## Próxima prueba diagnóstica

```text
NO AUTORIZADA TODAVÍA
```

Objetivo: distinguir pérdida sistemática de posición, filtrado/materialización posterior, frontera ambigua y dependencia del tamaño de ventana.

Configuración propuesta:

```text
request_id = la-colonia-diagnostic-overlap-380-419-001
ordenamiento primario = OrderByNameASC
ventanas = A, B, C, D, E, F, G, H
máximo de solicitudes = 8
concurrencia = 1
pausa = 1.5 segundos
persistencia = ninguna
publicación de identificadores = prohibida
```

Criterios de detención:

- HTTP 403 del sitio;
- HTTP 429 persistente;
- HTTP 5xx no recuperado;
- error GraphQL o estructural;
- cambio de `recordsFiltered` durante la secuencia;
- intento de publicar datos individuales;
- artefacto por encima del límite definido;
- más de 8 solicitudes.

Criterios de éxito:

- se generan las ocho métricas de ventana;
- se calculan solapamientos e intersecciones esperadas/observadas;
- se calcula la cantidad de productos únicos en las uniones;
- se detectan duplicados y ausencias sin publicar identidades;
- el resumen no contiene datos comerciales ni hashes individuales;
- el runner normal permanece sin cambios;
- una página parcial sigue siendo un hallazgo y nunca una aceptación.

Métricas sanitizadas:

```text
ventana
from
to
productos esperados
productos devueltos
SKU devueltos
recordsFiltered
firma de ventana
solapamiento esperado
solapamiento observado
productos únicos en la unión
duplicados entre ventanas
total inicial
total final
eventos de calidad
```

Segundo ordenamiento: no incluirlo en las primeras ocho solicitudes. Si los resultados no distinguen las hipótesis, una segunda ejecución separada y también no autorizada podría usar `OrderByReleaseDateDESC`, con las mismas ocho ventanas y límites.

JSON conceptual, no operacional:

```json
{
  "request_id": "la-colonia-diagnostic-overlap-380-419-001",
  "supermarket": "la_colonia",
  "mode": "diagnostic_overlap",
  "order_by": "OrderByNameASC",
  "windows": [
    {"name": "A", "from": 360, "to": 379},
    {"name": "B", "from": 370, "to": 389},
    {"name": "C", "from": 380, "to": 399},
    {"name": "D", "from": 390, "to": 409},
    {"name": "E", "from": 400, "to": 419},
    {"name": "F", "from": 380, "to": 389},
    {"name": "G", "from": 390, "to": 399},
    {"name": "H", "from": 350, "to": 399}
  ],
  "max_requests": 8,
  "concurrency": 1,
  "delay_seconds": 1.5,
  "publish_individual_identifiers": false,
  "allow_full": false
}
```

Cambios futuros necesarios antes de autorizar:

- controlador: validar un modo `diagnostic_overlap`, lista cerrada de ventanas, máximo 8, `allow_full = false` y prohibición de identificadores publicados;
- workflow: entrada manual separada o parámetros cerrados, mismo `workflow_dispatch`, artefacto sanitizado y sin disparadores automáticos;
- código: comparador en memoria de conjuntos, resumen agregado y límite de artefacto;
- pruebas: escenarios sintéticos de ventana completa, parcial, filtro posterior, orden no único, solapamiento inesperado, ausencia, duplicado y total cambiante.

## Pruebas y compilación

Head inspeccionado antes de esta actualización:

```text
2da8af8fea2816f4970629d4082f02d0baca3abc
```

CI de GitHub:

```text
workflow = Precios Supermercados SPS - Pruebas base
run_id = 31037813733
conclusion = success
compilación = success
pruebas = 149 passed
```

No se agregaron pruebas porque no se implementó instrumentación ejecutable. No se ejecutó ningún workflow live durante esta investigación.

## Archivo operacional

Permanece sin cambios:

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

## Decisión

- Mantener PR `#7` abierto, en borrador y sin fusionar.
- Mantener auto-merge deshabilitado.
- Mantener bloqueadas validation de 500 y `full`.
- No realizar una tercera repetición normal.
- No aceptar páginas parciales.
- No cambiar automáticamente `OrderByNameASC`.
- No modificar la arquitectura normal.
- Implementar y probar offline la instrumentación de ventanas solapadas antes de solicitar autorización para la prueba diagnóstica.
