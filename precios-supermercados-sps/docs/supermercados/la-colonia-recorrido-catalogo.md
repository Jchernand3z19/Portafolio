# La Colonia — recorrido y modo diagnóstico de ventanas

## Estado de la fase

La fase vive en el PR `#7`, rama `feature/la-colonia-full-crawl-validation`.

- PR abierto, en borrador y no fusionado.
- Baseline de 200 aceptado.
- Validation de 200 aceptada.
- Baseline de 500 rechazado dos veces.
- La ventana `380–399` devolvió 19 de 20 productos de forma reproducible.
- No se autorizó una tercera repetición normal.
- Validation de 500 continúa bloqueada.
- `full` no se ejecutó.
- No existe persistencia, historial, ejecución diaria, Google Sheets, BigQuery ni Power BI.
- El archivo operacional no se modificó.

## Diagnóstico previo

Los dos runs de 500 coincidieron en las páginas `1–19`. La página `20` volvió a producir:

```text
from = 380
to = 399
productos esperados = 20
productos entregados por GraphQL = 19
productos observados por el runner = 19
SKU entregados = 19
SKU extraídos = 19
recordsFiltered = 9291
bytes = 20957
firma = c86ae16a7b54543c8c7e68422b70fb7dbe5eb06a27395f0f76b1c65f0e3ef5ca
```

No está demostrado un error del parser, del runner ni del cálculo de `from/to`. La hipótesis más fuerte continúa siendo un desajuste determinista entre el total/índice reportado por VTEX y la lista materializada para esa frontera. La causa interna exacta no está demostrada.

## Arquitectura separada

### Capa A — dominio

Archivo:

```text
src/precios_supermercados/scrapers/la_colonia_window_diagnostic.py
```

Responsabilidades:

- representar ventanas inclusivas;
- construir consultas exactas;
- observar productos antes del parsing comercial;
- mantener identidades únicamente en memoria;
- calcular firmas completas de ventana;
- calcular solapamientos, unión y duplicados;
- serializar únicamente métricas agregadas;
- bloquear identificadores, hashes individuales y datos comerciales.

No conoce GitHub Actions ni el controlador.

### Capa B — runtime y CLI

Archivos:

```text
src/precios_supermercados/scrapers/la_colonia_window_diagnostic_runtime.py
scripts/diagnosticar_ventanas_la_colonia.py
```

Responsabilidades:

- aceptar únicamente el plan `frontier_380_399_v1`;
- ejecutar ventanas en orden y con concurrencia `1`;
- usar pausa fija de `1.5` segundos;
- limitar el plan a 12 solicitudes lógicas y usar `max_retries=0`;
- detenerse ante errores HTTP, estructura inválida, total cambiante o duración excedida;
- permitir que una ventana parcial se registre como `quality:partial_window`;
- escribir únicamente `diagnostic-summary.json` y `diagnostic-summary.md`;
- devolver códigos de salida explícitos.

El runtime no modifica el runner normal. La página parcial del recorrido normal continúa siendo rechazada.

### Capa C — infraestructura confiable

El controlador actual se ejecuta mediante `pull_request_target`, hace checkout de `main` y valida el archivo de comando con código confiable.

Archivos relevantes en `main`:

```text
.github/workflows/precios-supermercados-sps-la-colonia-command.yml
precios-supermercados-sps/src/precios_supermercados/automation/la_colonia_file_dispatcher.py
precios-supermercados-sps/scripts/procesar_solicitud_archivo_la_colonia.py
precios-supermercados-sps/tests/test_la_colonia_file_dispatcher.py
precios-supermercados-sps/tests/test_la_colonia_dispatch_runtime.py
precios-supermercados-sps/tests/test_la_colonia_dispatch_recovery.py
```

El dispatcher confiable actual:

- exige un esquema fijo de diez campos;
- solo acepta `smoke` y `staged`;
- prohíbe `full`;
- fija el workflow normal;
- rechaza campos desconocidos.

Por tanto, **el diagnóstico seguro no puede habilitarse sin cambiar `main`**. Agregar soporte únicamente en el PR #7 no convierte ese código en confiable para `pull_request_target`.

## Contrato propuesto

Se seleccionó un esquema discriminado por `mode`, porque elimina campos irrelevantes y evita combinaciones inválidas.

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

El comando no puede recibir:

```text
from
to
lista de ventanas
orderBy
max_requests
URL
query
selectedFacets
```

Todos esos valores salen de allow-lists de código.

## Plan cerrado `frontier_380_399_v1`

### Fase 1 obligatoria

`OrderByNameASC`:

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

Total: 8 solicitudes.

### Fase 2 opcional

`OrderByReleaseDateDESC`:

```text
C = 380–399
F = 380–389
G = 390–399
H = 350–399
```

La fase 2 no es activable desde el archivo de comando. El runtime solo continúa cuando la fase 1 terminó sin fallo técnico, el total permaneció estable y el resultado sigue siendo ambiguo según reglas deterministas.

Máximo total: 12 solicitudes. Concurrencia: 1. Pausa: 1.5 segundos.

## Detención

El diagnóstico se detiene ante:

- HTTP 403 o CAPTCHA;
- HTTP 429;
- HTTP 5xx;
- error GraphQL o estructura inválida;
- cambio de `recordsFiltered`;
- más de 12 ventanas;
- duración máxima de 300 segundos;
- fallo de sanitización;
- artefacto superior a 64 KiB.

El cliente diagnóstico usa `max_retries=0`. Así, el límite de 12 coincide también con el máximo de solicitudes HTTP y no queda oculto por reintentos.

Una ventana con 19 productos no detiene el diagnóstico por sí sola. Se registra como:

```text
quality:partial_window
```

## Códigos de salida

```text
0 = diagnóstico completado sin anomalía
2 = diagnóstico completado con anomalía, sin fallo técnico
3 = diagnóstico inconcluso porque cambió el catálogo
4 = detención por HTTP, estructura o duración
5 = fallo de sanitización, seguridad o artefacto
```

El workflow considera `0` y `2` como éxito técnico. Los códigos `3`, `4` y `5` fallan el job. No se reutiliza `accepted=true/false` del runner normal; el informe usa:

```text
completed
diagnostic_outcome
anomalies_detected
stop_reason
```

## Interpretación determinista

Resultados posibles:

- `window_size_dependent`: C es parcial, F y G están completas, su unión contiene 20 identidades y H está completa.
- `localized_missing_position`: exactamente una de F o G es parcial.
- `unexpected_overlap`: algún solapamiento observado difiere del esperado.
- `union_below_expected`: la unión única queda por debajo de las posiciones esperadas.
- `order_dependent`: la condición parcial o el conteo cambia entre NameASC y ReleaseDateDESC para C, F, G o H.
- `catalog_changed`: `recordsFiltered` cambia durante la secuencia.
- `inconclusive`: hay anomalía, pero las reglas anteriores no distinguen una explicación.
- `no_anomaly_observed`: todas las ventanas completan el patrón esperado.

El runtime no declara una causa raíz de VTEX.

## Artefactos sanitizados

Campos de ventana permitidos:

```text
window
from
to
order_by
products_expected
products_returned
skus_returned
records_filtered
response_bytes
signature
quality_events
```

Campos prohibidos:

```text
productId
productReference
productName
linkText
itemId
SKU
EAN
nombre
marca
precio
URL
payload
identidades individuales
hashes individuales
```

La firma completa de una ventana sí se publica porque representa el conjunto ordenado completo y no una identidad individual.

## Workflow seleccionado

Se seleccionó un workflow separado:

```text
.github/workflows/precios-supermercados-sps-la-colonia-diagnostic.yml
```

Razones:

- permisos e inputs mínimos;
- artefacto y códigos de salida propios;
- ninguna mezcla con `smoke`, `staged`, `validation` o `full`;
- menor riesgo para el recorrido normal;
- revisión estática sencilla;
- único trigger: `workflow_dispatch`.

El workflow preparado no contiene `schedule`, `push`, `pull_request` ni `issue_comment`. No se ejecutó.

## PR técnico

```text
PR TÉCNICO REQUERIDO — PENDIENTE DE AUTORIZACIÓN
```

Es indispensable porque el controlador de `pull_request_target` usa código de `main`, y el PR #7 no puede convertir su propio dispatcher en código confiable antes de fusionarse. Además, el PR #7 continúa bloqueado por la validación incompleta del catálogo.

Rama sugerida:

```text
chore/la-colonia-diagnostic-trusted-dispatch
```

Título sugerido:

```text
Habilita el despacho confiable del diagnóstico de ventanas de La Colonia
```

Alcance mínimo del PR técnico:

1. `la_colonia_file_dispatcher.py`:
   - esquema discriminado por `mode`;
   - allow-list `diagnostic_overlap` + `frontier_380_399_v1`;
   - `delay_seconds=1.5` y `allow_full=false` obligatorios;
   - selección explícita del workflow diagnóstico;
   - rechazo de ventanas, órdenes y URLs arbitrarias.
2. Workflow controlador:
   - allow-list de los dos paths de workflow;
   - dispatch únicamente al workflow indicado por la decisión confiable;
   - nunca ejecutar código del PR dentro de `pull_request_target`.
3. Workflow diagnóstico:
   - incorporar la definición preparada y revisada;
   - `workflow_dispatch` únicamente.
4. Tests confiables:
   - esquema normal sin regresión;
   - esquema diagnóstico aceptado solo con valores exactos;
   - campos arbitrarios rechazados;
   - idempotencia;
   - workflow correcto;
   - `full` prohibido.

`procesar_solicitud_archivo_la_colonia.py` no requiere cambio funcional si `DispatchDecision.as_dict()` continúa entregando el workflow seleccionado. Debe incluirse en las pruebas de regresión.

Orden correcto:

1. completar y revisar offline la parte de dominio/runtime en PR #7;
2. autorizar y fusionar el PR técnico a `main`;
3. rebasar o actualizar PR #7 con `main`;
4. revisar nuevamente contrato, workflow y CI;
5. solicitar autorización expresa para una ejecución diagnóstica;
6. actualizar el archivo operacional solo después de esa autorización.

## Pruebas offline

Estado previo:

```text
171 passed
```

Se agregaron pruebas de runtime, seguridad, artefactos, workflow y frontera de confianza. La CI ejecuta exactamente:

```bash
python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts
pytest precios-supermercados-sps/tests
```

Resultado verificado:

```text
workflow run = 31043403471
job = 92432972945
compilación de src y scripts = éxito
pruebas = 196 passed in 0.64s
errores = 0
warnings de pytest = 0
warning de infraestructura = acciones Node.js 20 forzadas a Node.js 24
```

## Bloqueos vigentes

- Ninguna ejecución live autorizada.
- Archivo operacional sin cambios.
- Tercera repetición normal de 500 bloqueada.
- Validation de 500 bloqueada.
- `full` bloqueado y no ejecutado.
- PR #7 debe permanecer abierto, en borrador y sin auto-merge.
