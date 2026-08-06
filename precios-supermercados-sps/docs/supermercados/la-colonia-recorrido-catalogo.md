# La Colonia — auditoría offline del facet discovery

## Estado

```text
main inicial de la auditoría = 52152f2f5f13c9320f9cc32b22e3e2eacb2cf9a6
PR funcional = #7 — abierto, draft y no fusionado
intento live = inconcluso
otra ejecución live = no autorizada
```

La solicitud `la-colonia-facet-discovery-001` se escribió una sola vez en el
archivo operacional. No se obtuvo `controller_run_id`, confirmación de dispatch,
run de facets o artefactos sanitizados. No se presume que existieran solicitudes
HTTP y no se inventan total raíz, sampling, niveles, hojas o presupuesto.

```text
discovery_completed = false
discovery_outcome = inconclusive
stop_reason = controller_and_facet_run_not_observable
```

## Archivo operacional

Permanece exactamente:

```json
{
  "request_id": "la-colonia-facet-discovery-001",
  "supermarket": "la_colonia",
  "mode": "facet_discovery",
  "discovery_plan": "catalog_categories_v1",
  "delay_seconds": 1.5,
  "allow_full": false
}
```

```text
commit operacional = 1a515913a514d3b246c3445eddfff8fcb0d951b4
blob = 7b40b1dc9e12e4ded347c753b863b3fd3f8b8186
```

La auditoría offline no modificó, restauró ni eliminó el archivo.

## Regresión de pruebas

La CI del commit operacional fue:

```text
workflow_run_id = 31123802072
job_id = 92690011372
compile = success
pytest = 427 passed, 1 failed in 1.64s
```

Falló `test_operational_contract_is_unchanged_when_present_on_functional_branch`
porque comparaba el archivo real exclusivamente con el request diagnóstico
`frontier_380_399_v1`. Esa aserción confundía una solicitud histórica con una
propiedad permanente.

La prueba fue sustituida por una validación semántica que:

1. lee UTF-8 y exige un objeto JSON;
2. comprueba el esquema exacto según `mode`;
3. usa `evaluate_file_request()` con contexto autorizado y
   `command_file_changed=true`;
4. exige aceptación del contrato vigente;
5. deriva el workflow desde código confiable;
6. valida inputs normalizados;
7. prohíbe workflow, URL, query, `selectedFacets`, headers y otros campos
   arbitrarios;
8. exige `allow_full=false`.

También se añadieron fixtures independientes para smoke, staged,
diagnostic_overlap y facet_discovery, junto con rechazos de modo, campos,
pausa, request ID y permisos inválidos.

## Transición operacional

La comparación del commit anterior con el commit operacional mostró un solo
commit y un solo archivo modificado:

```text
precios-supermercados-sps/.automation/la-colonia-live-command.json
```

Las pruebas sintéticas demuestran offline:

- diagnostic_overlap y facet_discovery siguen siendo contratos cerrados válidos;
- `command_file_changed=false` rechaza sin dispatch ni comentario;
- `command_file_changed=true` permite la evaluación;
- un commit reemplazado se rechaza silenciosamente;
- la marca `la-colonia-file-dispatch:la-colonia-facet-discovery-001` impide un
  segundo procesamiento;
- la ausencia de comentario solo indica elegibilidad y no demuestra que un run
  haya existido;
- ninguna prueba usa internet.

## Auditoría del trigger

El workflow de `main` declara:

```yaml
on:
  pull_request_target:
    types: [synchronize]
    paths:
      - precios-supermercados-sps/.automation/la-colonia-live-command.json
```

GitHub documenta que `pull_request_target` admite `synchronize` y filtros
`paths`; los filtros de un Pull Request se evalúan sobre los archivos de su diff.
El commit `1a515913...` realmente cambió la ruta filtrada. Por ello no existe una
prueba que justifique retirar `paths`.

La causa histórica exacta continúa sin poder distinguirse entre:

```text
A = evento no creado
B = evento filtrado antes de iniciar
C = workflow iniciado y fallido antes de evidencia
D = evidencia creada pero no recuperable por el conector
E = evidencia insuficiente para distinguir
```

Para el intento histórico se conserva `E`: no existe run ID para clasificar C o
D ni evidencia para atribuir el problema al parser, dispatcher o adaptador.

## Defecto demostrado en main

La auditoría del código sí encontró un defecto independiente y demostrable:

- `dispatcher-result.json` se creaba después de operaciones que podían lanzar
  una excepción;
- el checkpoint de dispatch se persistía después del intento de comentario;
- el observador solo procesaba runs del controlador con conclusión `success`.

Así, un run que hubiera iniciado podía terminar sin artefacto o con un artefacto
de fallo no observado. La clasificación global de la auditoría es:

```text
B — existe un defecto demostrable en main
```

## PR técnico

```text
PR = #17 — Corrige la observabilidad del facet discovery de La Colonia
rama = fix/la-colonia-facet-discovery-observability
base = main
estado = abierto; listo para revisión; no fusionado; auto-merge deshabilitado
```

La corrección técnica:

- crea un artefacto sanitizado antes de invocar el controlador;
- pre-valida evento, acción, PR #7, fork y SHA;
- delega en el controlador confiable existente;
- registra inmediatamente un dispatch facet válido sobre `ref=main`;
- conserva un único dispatch;
- convierte la ausencia de artefacto en error visible;
- hace que el observador procese todos los runs `completed`;
- mantiene checkout de `main`, permisos mínimos, allow-list y observador de solo
  lectura;
- no cambia el filtro `paths`, el scraper, el runner normal, adaptador o runtime.

La validación sintética local de fallos pre y post dispatch pasó. La CI de GitHub
del PR técnico continúa pendiente de aparecer; no se fusionará sin checks verdes.

## Documentación oficial consultada

- Events that trigger workflows — `pull_request_target`, `synchronize` y `paths`.
- Workflow syntax for GitHub Actions — filtros de ramas y rutas.
- GITHUB_TOKEN — supresión y aprobación de eventos generados por automatización.
- Securely using pull_request_target — checkout exclusivo de código confiable.
- Workflow artifacts — persistencia y retención de artefactos.

## Restricciones confirmadas

No se ejecutó:

- un segundo facet discovery;
- `la-colonia-facet-discovery-002`;
- otro diagnóstico;
- baseline500-003;
- validation500;
- full;
- recorrido particionado.

No se descargaron productos ni se consultaron facets reales. No se añadió
persistencia, historial, ejecución diaria, Google Sheets, BigQuery o Power BI.
PR #7 permanece abierto, draft y sin fusionar. La autorización live anterior
está consumida y otra ejecución no está autorizada.
