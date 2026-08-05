# La Colonia — recorrido, diagnóstico y auditoría offline

## Estado verificado

El trabajo funcional permanece en el PR `#7`, rama `feature/la-colonia-full-crawl-validation`.

```text
PR #7 = abierto
borrador = sí
fusionado = no
auto-merge = deshabilitado
main inicial de esta auditoría = 12bff9918815fe2dc6768f45c54e47281948de66
main posterior al PR técnico #15 = d748b6f6645d227429198694379a8146f1e5c939
merge de main en PR #7 = 4b9dafc6762c29bc78ecd06ac705b351cddccbae
```

Restricciones preservadas:

- ninguna ejecución live durante la auditoría offline;
- ningún segundo diagnóstico;
- no se creó `la-colonia-window-diagnostic-380-399-002`;
- no se ejecutó `la-colonia-baseline-products-500-003`;
- no se ejecutó `la-colonia-validation-products-500-001`;
- no se ejecutó `full`;
- no se modificó el runner normal;
- no se modificó `OrderByNameASC`;
- no se modificó el archivo operacional;
- no se añadió persistencia, historial, ejecución diaria, Google Sheets, BigQuery ni Power BI.

## Evidencia live de referencia

La única ejecución diagnóstica autorizada fue:

```text
controller_run_id = 31048001628
diagnostic_run_id = 31048012566
diagnostic_job_id = 92448236762
exit_code = 2
completed = true
diagnostic_outcome = unexpected_overlap
phase_two_started = false
```

Ventanas completas observadas:

| Ventana | Rango | Productos | Order by |
|---|---:|---:|---|
| A | 360–379 | 20 | OrderByNameASC |
| B | 370–389 | 20 | OrderByNameASC |
| C | 380–399 | 20 | OrderByNameASC |
| D | 390–409 | 20 | OrderByNameASC |
| E | 400–419 | 20 | OrderByNameASC |
| F | 380–389 | 10 | OrderByNameASC |
| G | 390–399 | 10 | OrderByNameASC |
| H | 350–399 | 50 | OrderByNameASC |

Patrones determinantes:

```text
B y C = misma firma y mismos bytes
D y E = misma firma y mismos bytes
A–B = esperado 10, observado 0
B–C = esperado 10, observado 20
C–D = esperado 10, observado 0
D–E = esperado 10, observado 20
```

Agregados:

```text
expected_unique_positions = 70
products_unique_in_union = 70
union_delta = 0
repeated_occurrences = 100
duplicates_within_windows = 0
recordsFiltered = 9291 estable
```

La página parcial histórica de 19 productos no se reprodujo. La causa interna exacta no está demostrada.

## Archivo operacional

El archivo permanece exactamente:

```json
{
  "request_id": "la-colonia-window-diagnostic-380-399-001",
  "supermarket": "la_colonia",
  "mode": "diagnostic_overlap",
  "diagnostic_plan": "frontier_380_399_v1",
  "delay_seconds": 1.5,
  "allow_full": false
}
```

```text
blob SHA = 92146efe01b99ff0cea99fc51967e90807d5b5da
```

La auditoría offline y el PR técnico #15 no cambiaron este archivo.

# Auditoría offline de solicitudes GraphQL

## Objetivo

Descartar un defecto local capaz de explicar `B=C` y `D=E` en:

- construcción de URL;
- serialización GraphQL;
- reutilización o mutación de variables;
- cliente y transporte HTTP;
- caché local;
- reutilización del body anterior;
- firmas;
- solapamientos;
- unión de identidades;
- interpretación del artefacto.

La auditoría se ejecutó exclusivamente con transporte simulado y datos sintéticos.

## Archivos inspeccionados

```text
src/precios_supermercados/scrapers/la_colonia_window_diagnostic.py
src/precios_supermercados/scrapers/la_colonia_window_diagnostic_runtime.py
src/precios_supermercados/scrapers/base.py
src/precios_supermercados/scrapers/la_colonia_graphql.py
tests/test_la_colonia_window_diagnostic.py
tests/test_la_colonia_window_diagnostic_runtime.py
scripts/diagnosticar_ventanas_la_colonia.py
```

Pruebas nuevas:

```text
tests/test_la_colonia_window_request_audit.py
```

Commits funcionales de la auditoría:

```text
b802c5af1e9bbee71239b56c728f397c0dea5574
Audita offline las solicitudes GraphQL del diagnóstico

70366154bd60efca7012a4185e4c8bfdbe2f5194
Corrige la lectura sanitizada de solapamientos en la auditoría
```

El segundo commit corrigió únicamente la prueba para interpretar las etiquetas sanitizadas `OrderByNameASC:A`; no cambió producción.

## Variables exactas demostradas

El transporte simulado recibió en orden A–H:

| Ventana | from | to | orderBy |
|---|---:|---:|---|
| A | 360 | 379 | OrderByNameASC |
| B | 370 | 389 | OrderByNameASC |
| C | 380 | 399 | OrderByNameASC |
| D | 390 | 409 | OrderByNameASC |
| E | 400 | 419 | OrderByNameASC |
| F | 380 | 389 | OrderByNameASC |
| G | 390 | 399 | OrderByNameASC |
| H | 350 | 399 | OrderByNameASC |

Cada request también transmitió exactamente:

```json
{
  "query": "supermercado",
  "fullText": "",
  "selectedFacets": [
    {
      "key": "category-1",
      "value": "supermercado"
    }
  ],
  "hideUnavailableItems": false,
  "skusFilter": "ALL"
}
```

Parámetros GraphQL verificados:

```text
workspace = master
locale = es-HN
operationName = productSearchV3
query = PRODUCT_SEARCH_QUERY
```

## Identidad de cada request

Las pruebas demostraron:

1. se construyen ocho strings de URL distintos;
2. B y C tienen URLs diferentes;
3. D y E tienen URLs diferentes;
4. las variables decodificadas B/C son diferentes;
5. las variables decodificadas D/E son diferentes;
6. el transporte recibe exactamente la URL construida;
7. el transporte `urllib` crea `Request` con el mismo URL sin reescritura local;
8. el orden es exactamente A, B, C, D, E, F, G, H;
9. cada URL se entrega exactamente una vez;
10. `max_retries=0` produce una sola llamada incluso ante HTTP 503;
11. las siete pausas de 1.5 segundos no cambian URLs ni variables;
12. cada respuesta simulada se procesa como body de su propia ventana.

## Inmutabilidad y reutilización

`WindowSpec` es una dataclass congelada. Las pruebas intentaron modificar una ventana y recibieron `FrozenInstanceError`.

`build_window_url()` crea nuevos objetos `variables` y `params` en cada llamada. La tupla completa del plan fue comparada antes y después de construir todas las URLs y permaneció idéntica.

El runtime no conserva el body anterior. Se entregaron respuestas distintas para el mismo URL en dos llamadas consecutivas y `SafeHttpClient` devolvió ambos bodies de forma independiente.

## Cliente HTTP y caché local

`SafeHttpClient` no contiene almacenamiento de respuestas ni atributo de caché. Cada `get()` llama directamente a `transport(url, headers, timeout)`.

Con `max_retries=0`, el bucle contiene un único intento. No existen llamadas ocultas ni reintentos automáticos del cliente local.

Esto descarta una caché local implementada por el proyecto. No demuestra ni descarta cachés intermedias o remotas fuera del proceso.

## Huella segura de request

Se evaluó una huella SHA-256 construida exclusivamente a partir de:

```text
from
to
orderBy
hideUnavailableItems
skusFilter
```

Las ocho huellas fueron distintas. B/C y D/E produjeron huellas distintas.

La huella quedó solo en pruebas. No se agregó al runtime ni al artefacto porque sería información redundante para la auditoría actual y no existe autorización para instrumentación live adicional.

# Reproducción sintética del patrón

## Fixtures

Se construyeron únicamente identidades sintéticas privadas:

```text
H = 50 identidades H00–H49
A = últimas 20 identidades de H
B = primeras 20 identidades de H
C = mismas 20 identidades de B
D = 20 identidades X00–X19 fuera de H
E = mismas 20 identidades de D
F = primeras 10 identidades de B/C
G = últimas 10 identidades de B/C
```

Esto reproduce exactamente:

```text
A ∩ B = 0
B ∩ C = 20
C ∩ D = 0
D ∩ E = 20
B = C
D = E
```

## Resultado sintético

El runtime produjo:

```text
diagnostic_outcome = unexpected_overlap
exit_code = 2
phase_two_started = false
expected_unique_positions = 70
products_unique_in_union = 70
union_delta = 0
repeated_occurrences = 100
duplicates_within_windows = 0
```

Explicación de `repeated_occurrences`:

```text
ocurrencias totales = 20 + 20 + 20 + 20 + 20 + 10 + 10 + 50 = 170
identidades únicas = 70
170 - 70 = 100 repeticiones
```

No existen duplicados dentro de una misma ventana; las repeticiones provienen de identidades compartidas entre ventanas.

F–G no se publica porque:

```text
solapamiento esperado = 0
solapamiento observado = 0
```

El algoritmo omite pares cuando ambos valores son cero.

## Firmas

La firma de una ventana es SHA-256 de la secuencia ordenada de claves privadas en memoria.

Las pruebas demostraron:

- B y C tienen la misma firma cuando sus secuencias privadas son iguales;
- cambiar una sola identidad de C cambia la firma aunque los bytes reportados sean iguales;
- D y E tienen la misma firma cuando sus secuencias son iguales;
- cambiar una identidad de E cambia la firma con el mismo tamaño en bytes;
- respuestas con los mismos bytes pero identidades distintas no adquieren la misma firma;
- la firma se calcula después de observar identidades y no puede causar duplicación en la respuesta.

## Solapamientos y unión

Los solapamientos se calculan mediante intersecciones de `_product_keys`, campo privado que no se serializa.

La unión se calcula a partir de todas las claves privadas y no utiliza firmas ni bytes. Una prueba con dos respuestas de igual tamaño y conjuntos disjuntos produjo:

```text
solapamientos = ninguno
unión = 40 identidades
firmas = diferentes
```

Por tanto, bytes y firmas no sustituyen las identidades utilizadas para solapamientos o unión.

# Decisión sobre fase 2

Funciones revisadas:

```text
_derive_phase_one_findings()
_phase_two_required()
_derive_outcome()
_order_pattern_changed()
```

Conclusiones:

1. La fase 2 no se ejecutó por diseño.
2. `unexpected_overlap` pertenece al conjunto de hallazgos decisivos.
3. Cuando aparece, `_phase_two_required()` devuelve `false`.
4. `_derive_outcome()` lo selecciona como resultado final de fase 1.
5. No existe contradicción entre el código y la documentación: la fase 2 está reservada para anomalías ambiguas.
6. Una fase 2 con `OrderByReleaseDateDESC` podría aportar evidencia sobre dependencia del orden.
7. También agregaría cuatro solicitudes y no resolvería por sí sola si el origen es backend, caché remota o materialización.
8. La regla no fue modificada.
9. No se ejecutó la fase 2 live.

# Matriz de auditoría

| Componente | Riesgo investigado | Prueba | Resultado | Descartado | Evidencia |
|---|---|---|---|---|---|
| WindowSpec | mutación | escritura sobre dataclass frozen | `FrozenInstanceError` | sí | plan igual antes/después |
| build_window_url | reutilización o mutación | ocho construcciones y snapshot | ocho URLs distintas | sí | A–H exactas |
| urlencode | colisión de URLs | comparación y decodificación | B≠C y D≠E | sí | strings y variables distintas |
| variables JSON | valores incorrectos | decodificación completa | valores exactos | sí | tabla A–H |
| SafeHttpClient | caché local | dos bodies distintos para mismo URL | ambos preservados | sí | sin atributo cache |
| urllib transport | reescritura | urlopen simulado | URL exacta | sí | `request.full_url` |
| respuesta anterior | reutilización | firma única por call | ocho firmas distintas | sí | body propio por ventana |
| mutación del plan | cambio entre llamadas | snapshot | sin cambios | sí | tuplas iguales |
| orden de llamadas | secuencia incorrecta | recorder | A–H | sí | ocho llamadas |
| reintentos | llamadas ocultas | HTTP 503 con max_retries=0 | una llamada | sí | contador 1 |
| firma | igualdad falsa por bytes | bytes iguales, claves distintas | firmas distintas | sí | SHA sobre claves |
| solapamientos | uso de bytes o firma | conjuntos sintéticos | intersección correcta | sí | claves privadas |
| unión | conteo incorrecto | patrón sintético | 70 únicos | sí | unión de claves |
| fase 2 | omisión accidental | prueba directa de regla | omisión deliberada | sí | unexpected_overlap decisivo |

## Clasificación

```text
B — No se encontró defecto local
```

Las ocho solicitudes se construyen y transmiten al transporte simulado con variables distintas y correctas. No se encontró caché local, reutilización de respuesta, mutación del plan, colisión de URL ni error en firmas, solapamientos o unión.

Esto aumenta la confianza en que el patrón observado se originó fuera de esos componentes locales, por ejemplo en comportamiento del backend, caché remota o materialización. No demuestra cuál mecanismo fue responsable y no debe describirse todavía como bug de VTEX.

```text
causa raíz demostrada = no
```

## CI de la auditoría

Primer run, con una prueba interpretando mal las etiquetas sanitizadas:

```text
workflow_run_id = 31056182114
job_id = 92474067834
resultado = 1 failed, 251 passed in 0.81s
producción modificada para corregirlo = no
```

Run corregido:

```text
workflow_run_id = 31056338276
job_id = 92474537725
conclusion = success
pruebas = 252 passed in 0.79s
errores = 0
warnings de pytest = 0
módulos Python compilados = 14
scripts Python compilados = 4
```

# Corrección del observador

## Fallo de referencia

```text
observer_run_id = 31048018717
observer_job_id = 92448254332
job = expose-controller-result
error = El resultado operacional contiene campos inesperados.
```

Workflow identificado desde el repositorio y el run:

```text
.github/workflows/precios-supermercados-sps-la-colonia-dispatch-recovery.yml
```

El observador descargó correctamente el artefacto del controlador, pero su allow-list antigua no contenía `mode` ni `workflow`.

## PR técnico #15

```text
PR = #15
rama = chore/la-colonia-observer-diagnostic-fields
título = Actualiza el observador del controlador de La Colonia
base = main
head técnico = 591b21e903caa005436da2c792cb3d6e46f5d046
merge SHA = d748b6f6645d227429198694379a8146f1e5c939
método = squash
auto-merge = no utilizado
```

Archivos modificados:

```text
.github/workflows/precios-supermercados-sps-la-colonia-dispatch-recovery.yml
precios-supermercados-sps/scripts/validar_resultado_controlador_la_colonia.js
precios-supermercados-sps/tests/test_la_colonia_dispatch_recovery.py
```

## Frontera de confianza

El observer mantiene:

```text
trigger = workflow_run del controlador
permissions = actions: read, contents: read
```

Hace checkout explícito de `main` con `persist-credentials: false` y ejecuta el validador confiable. No ejecuta código de la rama funcional, no publica comentarios y no envía dispatch.

## Validación cerrada

Modos permitidos:

```text
smoke
staged
diagnostic_overlap
```

Relaciones permitidas:

```text
smoke/staged
→ .github/workflows/precios-supermercados-sps-la-colonia-live.yml

diagnostic_overlap
→ .github/workflows/precios-supermercados-sps-la-colonia-diagnostic.yml
```

Se rechazan:

- modo desconocido;
- workflow desconocido;
- relación inválida;
- campo adicional;
- ruta arbitraria;
- valor no string;
- objeto o array;
- presencia de solo uno de `mode` o `workflow`;
- campo comercial adicional.

## Compatibilidad heredada

Los artefactos antiguos siguen siendo válidos solamente cuando `mode` y `workflow` están ambos ausentes. El resumen los marca como `legacy_artifact=true` y deja esos dos valores vacíos.

Un artefacto con solo uno de los dos campos se rechaza.

## Semántica de recuperación

Cuando:

```text
accepted = true
dispatch_sent = true
comment_published = false
```

el observer conserva el fallo controlado `RECOVERY_REQUIRED`, exige `request_id` y `live_run_id` válidos y no envía un segundo dispatch.

El resumen incluye únicamente identificadores sanitizados, `mode`, `workflow`, estado legacy y flags de recuperación. No publica URLs guardadas en el artefacto ni datos comerciales.

## Pruebas del observador

Se probaron:

- artefacto antiguo;
- staged;
- smoke;
- diagnóstico;
- ambos workflows válidos;
- modo desconocido;
- workflow desconocido;
- relación inválida;
- campo extra;
- tipos incorrectos;
- presencia parcial de campos;
- comentario publicado;
- comentario bloqueado;
- recuperación con live_run_id;
- ausencia de segundo dispatch;
- resumen sanitizado;
- rechazo de campos comerciales;
- trigger y permisos sin ampliación.

CI del PR técnico:

```text
workflow_run_id = 31056552333
job_id = 92475195624
conclusion = success
pruebas = 181 passed in 1.31s
errores = 0
warnings de pytest = 0
módulos Python compilados = 10
scripts Python compilados = 2
```

El único warning fue de infraestructura por acciones que declaran Node.js 20 y fueron ejecutadas con Node.js 24.

# Integración en PR #7

El nuevo `main` fue integrado mediante un commit de dos padres y sin force-push:

```text
padre funcional = 70366154bd60efca7012a4185e4c8bfdbe2f5194
padre main = d748b6f6645d227429198694379a8146f1e5c939
merge = 4b9dafc6762c29bc78ecd06ac705b351cddccbae
```

No hubo conflicto semántico. Se conservaron:

- todo el diagnóstico funcional;
- el archivo operacional;
- las pruebas de auditoría A–H;
- la política de fase 2;
- el runner normal.

Se incorporaron desde main exactamente los tres archivos del observador.

# Decisión y siguiente paso

```text
auditoría de requests = completada offline
defecto local = no encontrado
clasificación = B
observador = compatible con mode y workflow
PR técnico = fusionado
PR #7 = abierto y draft
archivo operacional = sin cambios
ejecuciones live de esta etapa = ninguna
autorización para otra ejecución live = inexistente
```

Siguiente trabajo recomendado:

1. mantener bloqueada cualquier ejecución live;
2. revisar el comportamiento remoto solo cuando exista una nueva autorización expresa y una hipótesis adicional concreta;
3. no cambiar todavía `OrderByNameASC`;
4. no agregar cache-busters ni cambiar `maxAge` sin evidencia;
5. no modificar la regla de fase 2 automáticamente;
6. conservar PR #7 abierto y en borrador hasta una decisión funcional separada.
