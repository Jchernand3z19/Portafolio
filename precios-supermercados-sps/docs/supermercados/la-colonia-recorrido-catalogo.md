# La Colonia — recorrido y diagnóstico de ventanas

## Estado verificado

El trabajo funcional permanece en el PR `#7`, rama `feature/la-colonia-full-crawl-validation`.

- PR abierto, en borrador y no fusionado.
- Baseline de 200 aceptado.
- Validation de 200 aceptada.
- Baseline de 500 rechazado dos veces en la ventana `380–399`.
- Tercera repetición de 500 no ejecutada.
- Validation de 500 no ejecutada.
- `full` no ejecutado.
- Diagnóstico de ventanas no ejecutado.
- Sin persistencia, historial, ejecución diaria, Google Sheets, BigQuery ni Power BI.
- Archivo operacional sin cambios.

## Evidencia del problema

Los dos recorridos de 500 coincidieron en las páginas `1–19`. En ambos, la página `20` produjo:

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

No está demostrado un error del parser, del runner ni del cálculo de `from/to`. La hipótesis más fuerte sigue siendo un desajuste determinista entre el total o índice reportado por VTEX y la lista materializada para esa frontera. La causa interna exacta no está demostrada.

## Arquitectura separada

### Capa A — dominio

```text
src/precios_supermercados/scrapers/la_colonia_window_diagnostic.py
```

Construye ventanas, observa productos raw, mantiene identidades únicamente en memoria, calcula firmas, solapamientos, unión y duplicados, y serializa solo métricas agregadas sanitizadas.

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

La página parcial del recorrido normal continúa siendo rechazada.

### Capa C — infraestructura confiable

La infraestructura confiable fue implementada y fusionada mediante:

```text
PR técnico: #14
Título: Habilita el despacho confiable del diagnóstico de ventanas de La Colonia
Rama: chore/la-colonia-diagnostic-trusted-dispatch
Head técnico: 76be29d7ffbdcf40a6091d31d006979b1ea1635e
Método: squash
Merge SHA: 12bff9918815fe2dc6768f45c54e47281948de66
Fecha de fusión: 2026-08-05T20:39:23Z
```

El controlador continúa bajo `pull_request_target`, hace checkout explícito de `main` y nunca ejecuta código del PR dentro del contexto privilegiado.

## Esquema discriminado

### Recorridos normales

`smoke` y `staged` conservan exactamente los campos y reglas anteriores:

```text
request_id
supermarket
mode
page_size
max_pages
max_products
delay_seconds
profile
thresholds
allow_full
```

### Diagnóstico

El modo `diagnostic_overlap` exige exactamente:

```text
request_id
supermarket
mode
diagnostic_plan
delay_seconds
allow_full
```

Contrato permitido:

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

## Selección confiable de workflow

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

El controlador mapea la ruta confiable al nombre de archivo permitido, valida la correspondencia entre modo y workflow y despacha sobre la rama head verificada. El archivo operacional no puede indicar la ruta del workflow.

## Workflow diagnóstico

```text
.github/workflows/precios-supermercados-sps-la-colonia-diagnostic.yml
```

Controles:

- único trigger: `workflow_dispatch`;
- inputs: `request_id`, `diagnostic_plan`, `delay_seconds`;
- único plan: `frontier_380_399_v1`;
- única pausa: `1.5`;
- permisos `contents: read`;
- concurrencia única;
- timeout de 15 minutos;
- códigos `0` y `2` como éxito técnico;
- códigos `3`, `4` y `5` como fallo;
- sin `schedule`, `push`, `pull_request`, `pull_request_target` ni `issue_comment`.

El workflow está disponible en `main`, pero no fue ejecutado.

## Plan cerrado `frontier_380_399_v1`

Fase 1, `OrderByNameASC`:

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

Fase 2 opcional, `OrderByReleaseDateDESC`:

```text
C = 380–399
F = 380–389
G = 390–399
H = 350–399
```

La fase 2 no puede activarse desde el archivo operacional. El runtime decide continuar únicamente si la fase 1 termina técnicamente, el total permanece estable y el resultado sigue siendo ambiguo.

## Códigos de salida

```text
0 = completado sin anomalía
2 = completado con anomalía, sin fallo técnico
3 = catálogo cambiante
4 = HTTP, estructura o duración
5 = sanitización, seguridad o artefacto
```

El informe utiliza `completed`, `diagnostic_outcome`, `anomalies_detected` y `stop_reason`; no reutiliza la semántica `accepted` del runner normal.

## Sanitización

El artefacto puede publicar firmas completas de ventana y métricas agregadas. No puede publicar:

```text
productId
productReference
productName
linkText
itemId
SKU
EAN
nombres
marcas
precios
URLs
payloads
identidades individuales
hashes individuales
```

## Integración de main en PR #7

La rama funcional se actualizó mediante un merge commit real de dos padres:

```text
Head anterior de PR #7: 9e481ceda6670aae009e56edbd195c3a27e24f81
Main integrado: 12bff9918815fe2dc6768f45c54e47281948de66
Merge commit funcional: f04f79bd35837ed638312bcf143edda701075785
```

Se conservó el dominio, runtime, CLI, pruebas funcionales y documentación de PR #7. La única resolución específica fue actualizar una prueba antigua que esperaba que el dispatcher todavía rechazara `diagnostic_overlap`; ahora comprueba la aceptación del contrato exacto y la selección del workflow confiable.

CI posterior al merge:

```text
workflow run = 31045490588
job = 92439859239
compilación src y scripts = éxito
pruebas = 238 passed in 0.69s
errores = 0
warnings de pytest = 0
```

La compilación incluyó 14 módulos de `src` y cuatro scripts:

```text
diagnosticar_ventanas_la_colonia.py
probar_la_colonia.py
procesar_solicitud_archivo_la_colonia.py
publicar_resultado_la_colonia.py
```

El único warning fue de infraestructura: GitHub forzó a Node.js 24 acciones que todavía declaran Node.js 20.

## Archivo operacional

Permanece exactamente:

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

Blob SHA verificado:

```text
37e527c191141dc321c7b347b9526db7bb70c4e7
```

## Bloqueos vigentes

- Diagnóstico live: no ejecutado y pendiente de autorización expresa.
- Tercera repetición normal de 500: bloqueada.
- Validation de 500: bloqueada.
- `full`: bloqueado y no ejecutado.
- PR #7: debe permanecer abierto, en borrador, sin fusionar y sin auto-merge.
- Archivo operacional: no debe modificarse antes de una autorización live separada.

## Próxima solicitud conceptual

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
NO AUTORIZADA TODAVÍA
```
