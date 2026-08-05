# La Colonia — recorrido y diagnóstico de ventanas

## Estado verificado

El trabajo funcional permanece en el PR `#7`, rama `feature/la-colonia-full-crawl-validation`.

- PR abierto, en borrador y no fusionado.
- `main` contiene el PR técnico `#14` en `12bff9918815fe2dc6768f45c54e47281948de66`.
- Baseline de 200 aceptado.
- Validation de 200 aceptada.
- Baseline de 500 rechazado dos veces en la ventana `380–399`.
- Se ejecutó una única vez el diagnóstico autorizado `la-colonia-window-diagnostic-380-399-001`.
- La ejecución diagnóstica terminó con `exit_code=2`, éxito técnico y outcome `unexpected_overlap`.
- No se ejecutó una segunda solicitud diagnóstica.
- No se ejecutó la tercera repetición de 500.
- No se ejecutó validation de 500.
- No se ejecutó `full`.
- No se modificó el runner normal.
- No existe persistencia, historial, ejecución diaria, Google Sheets, BigQuery ni Power BI.

## Evidencia histórica

Los dos recorridos normales de 500 coincidieron en las páginas `1–19`. En ambos, la página `20` produjo:

```text
from = 380
to = 399
orderBy = OrderByNameASC
productos esperados = 20
productos entregados por GraphQL = 19
productos observados por el runner = 19
SKU entregados = 19
SKU extraídos = 19
recordsFiltered = 9291
bytes = 20957
firma = c86ae16a7b54543c8c7e68422b70fb7dbe5eb06a27395f0f76b1c65f0e3ef5ca
```

Runs históricos:

```text
primer baseline live_run_id = 31035091894
segundo baseline live_run_id = 31037207732
```

No se demostró un error del parser, del runner ni del cálculo de `from/to`. Tampoco se demostró un producto fantasma, eliminado, oculto, un empate de nombres, un filtrado posterior ni un bug interno exacto de VTEX.

## Arquitectura separada

### Capa A — dominio

```text
src/precios_supermercados/scrapers/la_colonia_window_diagnostic.py
```

Construye ventanas, observa productos raw antes del parsing comercial, mantiene identidades únicamente en memoria, calcula firmas completas, solapamientos, unión y duplicados, y serializa solo métricas agregadas sanitizadas.

### Capa B — runtime y CLI

```text
src/precios_supermercados/scrapers/la_colonia_window_diagnostic_runtime.py
scripts/diagnosticar_ventanas_la_colonia.py
```

El runtime:

- acepta únicamente `frontier_380_399_v1`;
- ejecuta concurrencia `1`;
- aplica pausa fija de `1.5` segundos;
- limita el plan a 12 solicitudes y usa `max_retries=0`;
- registra una ventana parcial como `quality:partial_window` sin detener el diagnóstico;
- detiene errores HTTP, estructura inválida, total cambiante, duración o sanitización;
- escribe solo `diagnostic-summary.json` y `diagnostic-summary.md`;
- limita los artefactos a 64 KiB;
- no modifica el runner normal.

Una página parcial continúa siendo inaceptable en el recorrido normal.

### Capa C — infraestructura confiable

La infraestructura confiable fue fusionada mediante:

```text
PR técnico = #14
rama = chore/la-colonia-diagnostic-trusted-dispatch
head técnico = 76be29d7ffbdcf40a6091d31d006979b1ea1635e
merge SHA = 12bff9918815fe2dc6768f45c54e47281948de66
método = squash
```

El controlador continúa bajo `pull_request_target`, hace checkout explícito de `main` y nunca ejecuta código del PR dentro del contexto privilegiado.

## Esquema discriminado y selección confiable

El modo `diagnostic_overlap` exige exactamente:

```text
request_id
supermarket
mode
diagnostic_plan
delay_seconds
allow_full
```

Contrato autorizado y ejecutado:

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

Se rechazan ventanas, `from`, `to`, `windows`, `orderBy`, URLs, queries, `selectedFacets`, `max_requests`, parámetros normales mezclados, campos adicionales, campos faltantes y cualquier workflow suministrado por el comando.

La allow-list contiene exactamente:

```text
.github/workflows/precios-supermercados-sps-la-colonia-live.yml
.github/workflows/precios-supermercados-sps-la-colonia-diagnostic.yml
```

La selección se deriva únicamente del modo validado:

```text
smoke o staged       → workflow normal
diagnostic_overlap   → workflow diagnóstico
```

## Solicitud operacional única

Archivo:

```text
precios-supermercados-sps/.automation/la-colonia-live-command.json
```

Blob anterior:

```text
37e527c191141dc321c7b347b9526db7bb70c4e7
```

Commit operacional único:

```text
4860e7f01de26dbecfd2ca9cc9e0ed919b795f48
Solicita diagnóstico controlado de la frontera 380–399
```

Blob actual:

```text
92146efe01b99ff0cea99fc51967e90807d5b5da
```

Contenido actual, que debe conservarse hasta una limpieza futura autorizada:

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

No se creó otro commit para provocar el mismo diagnóstico.

## Controlador

```text
workflow = La Colonia - Despachador seguro por archivo
controller_run_id = 31048001628
controller_job_id = 92448195616
conclusion = success
head_sha = 4860e7f01de26dbecfd2ca9cc9e0ed919b795f48
ref = feature/la-colonia-full-crawl-validation
mode = diagnostic_overlap
workflow seleccionado = .github/workflows/precios-supermercados-sps-la-colonia-diagnostic.yml
dispatch_sent = true
live_run_id = 31048012566
```

Inputs normalizados:

```json
{
  "request_id": "la-colonia-window-diagnostic-380-399-001",
  "diagnostic_plan": "frontier_380_399_v1",
  "delay_seconds": "1.5"
}
```

Artefacto del controlador:

```text
artifact_id = 8947226926
artifact_name = la-colonia-file-dispatch-31048001628
artifact_digest = sha256:ee3ca0e7834c33317b627e522a3a9fcfde9c40a12d58be83b415f0bd6e3aa822
artifact_zip_size = 650 bytes
archivo = dispatcher-result.json
```

El controlador realizó un solo POST de `workflow_dispatch`.

GitHub bloqueó el comentario automático:

```text
GraphQL = HTTP no expuesto
REST = HTTP 403
comment_published = false
comment_method = null
```

El HTTP 403 pertenece a GitHub y no al sitio de La Colonia. El registro sanitizado fue publicado mediante el conector.

## Observador

```text
workflow = La Colonia - Recuperación observable del controlador
observer_run_id = 31048018717
observer_job_id = 92448254332
conclusion = failure
source controller run = 31048001628
```

El observador descargó y validó el digest del artefacto del controlador, pero falló de forma controlada con:

```text
El resultado operacional contiene campos inesperados.
```

La causa es que su allow-list no incluye todavía los campos sanitizados `mode` y `workflow` incorporados por el PR técnico. Este defecto no afectó el dispatch ni el diagnóstico. No se corrigió ni se repitió durante esta autorización.

## Workflow diagnóstico ejecutado

```text
workflow = La Colonia - Diagnóstico manual de ventanas
diagnostic_run_id = 31048012566
diagnostic_job_id = 92448236762
branch = feature/la-colonia-full-crawl-validation
commit = 4860e7f01de26dbecfd2ca9cc9e0ed919b795f48
workflow_conclusion = success
exit_code = 2
run_number = No expuesto
run_attempt = No expuesto
```

`exit_code=2` significa diagnóstico completado con anomalía y éxito técnico.

## Artefacto diagnóstico

```text
artifact_id = 8947237874
artifact_name = la-colonia-window-diagnostic-31048012566
artifact_digest = sha256:9815dd8a88779bf651c0cb9d3d1f1e52ca35d386212f87cc806c9c67edaf0db7
artifact_zip_size = 2238 bytes
created_at = 2026-08-05T21:18:11Z
```

Archivos revisados:

```text
diagnostic-summary.json = 6049 bytes
diagnostic-summary.md = 1870 bytes
total extraído = 7919 bytes
```

El total está por debajo de 64 KiB.

La revisión no encontró productos, nombres, marcas, precios, URLs, payloads, identificadores individuales ni hashes individuales. `SKU` aparece únicamente como nombre de una métrica agregada.

## Métricas globales

```text
schema_version = 1.0.0
request_id = la-colonia-window-diagnostic-380-399-001
diagnostic_plan = frontier_380_399_v1
started_at = 2026-08-05T21:17:54.200243+00:00
finished_at = 2026-08-05T21:18:10.489304+00:00
duration_seconds = 16.289049
requests_planned = 8
requests_attempted = 8
requests_completed = 8
delay_seconds_applied = 10.5
completed = true
anomalies_detected = true
phase_two_started = false
expected_unique_positions = 70
products_unique_in_union = 70
union_delta = 0
repeated_occurrences = 100
duplicates_within_windows = 0
total_initial = 9291
total_final = 9291
total_change_absolute = 0
total_change_ratio = 0.0
quality_events = [unexpected_overlap, diagnostic:unexpected_overlap]
diagnostic_outcome = unexpected_overlap
stop_reason = vacío
exit_code = 2
```

No están expuestos como campos del artefacto:

```text
http_403
http_429
persistent_http_429
http_5xx
retries
structural_events
security_events
sanitization_errors
```

No hubo `stop_reason` HTTP, estructural, de duración ni de sanitización. La configuración usa `max_retries=0`.

## Pausa y duración

Con ocho solicitudes completadas y pausa únicamente entre solicitudes:

```text
(8 - 1) × 1.5 = 10.5 segundos
```

El artefacto expuso exactamente `delay_seconds_applied=10.5`.

La diferencia frente a la duración total es:

```text
16.289049 - 10.5 = 5.789049 segundos
```

Corresponde al tiempo de solicitudes, procesamiento y serialización, no a pausas adicionales.

## Resultado por ventana

Todas las ventanas pertenecen a la fase 1 y usan `OrderByNameASC`.

| Ventana | From | To | Esperados | Productos | SKU agregados | Total | Bytes | Firma | Eventos |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| A | 360 | 379 | 20 | 20 | 20 | 9291 | 24848 | `2f17d8de521eff4051d6d98e0d3691a23c0c15c615dd87d4b325936414304ef5` | ninguno |
| B | 370 | 389 | 20 | 20 | 20 | 9291 | 21976 | `794a159fc3ba36033d24f151a9fcf6290458e8ec38b746da25322f52bc8eadbf` | ninguno |
| C | 380 | 399 | 20 | 20 | 20 | 9291 | 21976 | `794a159fc3ba36033d24f151a9fcf6290458e8ec38b746da25322f52bc8eadbf` | ninguno |
| D | 390 | 409 | 20 | 20 | 20 | 9291 | 18921 | `bfba342c7f91d58f8efeccac97efd6c49091bc37fe25bca5f2ddca58bed739fc` | ninguno |
| E | 400 | 419 | 20 | 20 | 20 | 9291 | 18921 | `bfba342c7f91d58f8efeccac97efd6c49091bc37fe25bca5f2ddca58bed739fc` | ninguno |
| F | 380 | 389 | 10 | 10 | 10 | 9291 | 10580 | `e9ce932619e78cb93a7abf9f8a1fac115e2e9817650f0f4d4dd50950c0033eac` | ninguno |
| G | 390 | 399 | 10 | 10 | 10 | 9291 | 11460 | `c5dd3759fcc64ac78d1341f7763fa194affe6a73c8a24378187ca87439aef2d0` | ninguno |
| H | 350 | 399 | 50 | 50 | 50 | 9291 | 57781 | `28b76e4750fa627d98df8e8b9370334ed60981795895da306ddeebc59bdc3494` | ninguno |

No hubo `quality:partial_window` en esta ejecución.

## Solapamientos

| Izquierda | Derecha | Esperado | Observado | Delta | Decisión |
|---|---|---:|---:|---:|---|
| A | B | 10 | 0 | -10 | unexpected_overlap |
| A | H | 20 | 20 | 0 | esperado |
| B | C | 10 | 20 | +10 | unexpected_overlap |
| B | F | 10 | 10 | 0 | esperado |
| B | G | 0 | 10 | +10 | unexpected_overlap |
| B | H | 20 | 20 | 0 | esperado |
| C | D | 10 | 0 | -10 | unexpected_overlap |
| C | F | 10 | 10 | 0 | esperado |
| C | G | 10 | 10 | 0 | esperado |
| C | H | 20 | 20 | 0 | esperado |
| D | E | 10 | 20 | +10 | unexpected_overlap |
| D | G | 10 | 0 | -10 | unexpected_overlap |
| D | H | 10 | 0 | -10 | unexpected_overlap |
| F | H | 10 | 10 | 0 | esperado |
| G | H | 10 | 10 | 0 | esperado |

El par F–G no fue expuesto por el artefacto.

## Unión y repetición

```text
posiciones únicas esperadas = 70
productos únicos en la unión = 70
union_delta = 0
repeated_occurrences = 100
duplicates_within_windows = 0
```

La unión no quedó por debajo de lo esperado. La anomalía se encuentra en la distribución entre ventanas y sus solapamientos, no en el total único de la unión.

## Comparación con los dos baselines

### Primer baseline

```text
live_run_id = 31035091894
products_returned = 19
response_bytes = 20957
signature = c86ae16a7b54543c8c7e68422b70fb7dbe5eb06a27395f0f76b1c65f0e3ef5ca
recordsFiltered = 9291
```

### Segundo baseline

```text
live_run_id = 31037207732
products_returned = 19
response_bytes = 20957
signature = c86ae16a7b54543c8c7e68422b70fb7dbe5eb06a27395f0f76b1c65f0e3ef5ca
recordsFiltered = 9291
```

### Ventana C del diagnóstico

```text
products_returned = 20
response_bytes = 21976
signature = 794a159fc3ba36033d24f151a9fcf6290458e8ec38b746da25322f52bc8eadbf
recordsFiltered = 9291
```

Comparación:

- el conteo no coincide: `20` frente a `19`;
- los bytes no coinciden: `21976` frente a `20957`;
- la firma no coincide;
- `recordsFiltered=9291` sí coincide;
- la página parcial histórica no se reprodujo en esta ejecución;
- el diagnóstico aportó evidencia nueva de solapamientos inesperados.

## Interpretación

### Observaciones

- B y C fueron ventanas completas con la misma cantidad de bytes y la misma firma completa.
- D y E fueron ventanas completas con la misma cantidad de bytes y la misma firma completa.
- A–B y C–D observaron `0` elementos donde se esperaban `10`.
- B–C y D–E observaron `20` donde se esperaban `10`.
- B–G observó `10` donde se esperaba `0`.
- F, G y H fueron completas.
- El total permaneció estable en `9291`.
- La unión única alcanzó las `70` posiciones esperadas.

### Patrón

El patrón observado es una distribución entre ventanas incompatible con los solapamientos posicionales esperados bajo `OrderByNameASC`.

### Evidencia compatible

Aumenta la evidencia compatible con:

- materialización o fronteras no estables bajo `OrderByNameASC`;
- movimiento o repetición entre consultas de rangos adyacentes;
- interpretación de rangos que no se comporta como una secuencia posicional estable.

Disminuye la confianza en:

- una posición faltante fija en `380–399`;
- una explicación exclusivamente dependiente del tamaño de ventana;
- `union_below_expected`;
- `catalog_changed`.

### Ordenamiento

La fase 2 no inició porque la fase 1 produjo la clasificación determinista `unexpected_overlap`. No existe evidencia comparativa entre `OrderByNameASC` y `OrderByReleaseDateDESC` en esta ejecución. No puede declararse `order_dependent`.

### Causa raíz

```text
causa raíz demostrada = no
```

No se identificó ni publicó ningún producto individual. No se atribuye la anomalía a un mecanismo interno exacto de VTEX.

## Siguiente trabajo técnico offline

Antes de proponer otra ejecución live:

1. Auditar offline la construcción final de las solicitudes GraphQL del runtime diagnóstico.
2. Añadir pruebas con transporte simulado que capturen las variables HTTP reales de A–H.
3. Verificar que cada solicitud transmite exactamente su `from`, `to` y `orderBy` distinto.
4. Añadir pruebas que demuestren que las firmas B=C y D=E no pueden originarse en reutilización accidental de variables, caché local o mutación de objetos del cliente.
5. Revisar offline el cálculo de solapamientos y `repeated_occurrences` contra conjuntos sintéticos conocidos.
6. Corregir por separado la allow-list del observador para aceptar `mode` y `workflow`, con pruebas, sin mezclarlo con una nueva ejecución.
7. No modificar automáticamente el runner normal ni cambiar `OrderByNameASC`.

No se implementó ninguna corrección durante esta autorización.

## Restricciones vigentes

- No ejecutar un segundo diagnóstico.
- No crear `la-colonia-window-diagnostic-380-399-002`.
- No ejecutar `la-colonia-baseline-products-500-003`.
- No ejecutar `la-colonia-validation-products-500-001`.
- No ejecutar `full`.
- No fusionar PR `#7`.
- Mantener PR `#7` en borrador y sin auto-merge.
- No modificar el archivo operacional nuevamente durante esta etapa.
- No aceptar páginas parciales en el runner normal.
- No publicar datos comerciales o identidades individuales.
- No agregar persistencia, historial, ejecución diaria, Google Sheets, BigQuery ni Power BI.
- Otra ejecución live requiere una autorización expresa nueva.
