# La Colonia — auditoría offline del facet discovery

## Estado final de la etapa

```text
main inicial = 52152f2f5f13c9320f9cc32b22e3e2eacb2cf9a6
main final = 61b901973f869853cfd1060de1509ce9668ec782
PR funcional = #7 — abierto, draft y no fusionado
head funcional inicial = 0ec69d4d5290afe855bd03249aa8e11d584f840a
intento live = inconcluso
otra ejecución live = no autorizada
```

El intento `la-colonia-facet-discovery-001` continúa clasificado como:

```text
discovery_completed = false
discovery_outcome = inconclusive
stop_reason = controller_and_facet_run_not_observable
```

No se obtuvo `controller_run_id`, confirmación de dispatch, run de facets o
artefactos. No se presume que existieran solicitudes HTTP y no se inventan total
raíz, sampling, niveles, hojas o presupuesto.

## Archivo operacional intacto

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
blob inicial = 7b40b1dc9e12e4ded347c753b863b3fd3f8b8186
blob final = 7b40b1dc9e12e4ded347c753b863b3fd3f8b8186
```

La auditoría offline no modificó, restauró, eliminó ni volvió a confirmar este
archivo mediante otro commit.

## Regresión de pruebas corregida

La CI del commit operacional fue:

```text
workflow_run_id = 31123802072
job_id = 92690011372
compile = success
pytest = 427 passed, 1 failed in 1.64s
```

Falló `test_operational_contract_is_unchanged_when_present_on_functional_branch`
porque fijaba el request diagnóstico `frontier_380_399_v1` como único contenido
permitido. Esa prueba confundía una solicitud histórica con una propiedad
permanente.

La nueva prueba:

1. lee el archivo como UTF-8;
2. exige un objeto JSON;
3. comprueba el esquema exacto correspondiente al `mode`;
4. usa la interfaz pública `evaluate_file_request()`;
5. emplea contexto autorizado con `command_file_changed=true`;
6. exige aceptación del contrato vigente;
7. deriva el workflow desde código confiable;
8. valida los inputs normalizados;
9. rechaza workflow, URL, query, `selectedFacets`, headers y campos arbitrarios;
10. exige `allow_full=false`.

Se mantienen fixtures independientes para smoke, staged, diagnostic_overlap y
facet_discovery, además de rechazos de modo, campos, pausa, request ID y permisos
inválidos.

## Transición diagnostic a facet

La comparación del commit funcional anterior con `1a515913...` mostró un solo
archivo modificado:

```text
precios-supermercados-sps/.automation/la-colonia-live-command.json
```

Las pruebas sintéticas demuestran offline:

- ambos contratos históricos son válidos;
- `command_file_changed=false` rechaza sin dispatch;
- `command_file_changed=true` permite la evaluación;
- un evento reemplazado se rechaza silenciosamente;
- el request ID vigente se normaliza correctamente;
- el workflow facet procede de la allow-list confiable;
- la marca idempotente impide un segundo procesamiento;
- la ausencia de comentario no demuestra que existiera o no un run;
- las pruebas no usan internet.

## Auditoría del evento y del filtro paths

El workflow de `main` declara:

```yaml
on:
  pull_request_target:
    types: [synchronize]
    paths:
      - precios-supermercados-sps/.automation/la-colonia-live-command.json
```

La documentación oficial de GitHub confirma que `pull_request_target` admite
`synchronize` y filtros `paths`, y que el filtro de un Pull Request se evalúa
sobre los archivos de su diff. El commit operacional cambió exactamente la ruta
filtrada. No existe evidencia suficiente para retirar `paths`.

La causa histórica exacta permanece en el nivel:

```text
E — evidencia insuficiente para distinguir:
A = evento no creado
B = evento filtrado
C = workflow iniciado y fallido antes de evidencia
D = evidencia creada pero no recuperable
```

Sin `controller_run_id` no se clasifica C o D ni se atribuye el intento al
parser, dispatcher o adaptador.

## Clasificación global

```text
B — existe un defecto demostrable en main
```

El defecto independiente demostrado fue:

- `dispatcher-result.json` se creaba después de operaciones susceptibles de
  excepción;
- el checkpoint del dispatch se persistía después del comentario;
- el observador ignoraba conclusiones distintas de `success`;
- rechazos con `mode:null` y `workflow:null` eran incompatibles con el esquema
  del observador.

## PR técnico #17

```text
PR = #17 — Corrige la observabilidad del facet discovery de La Colonia
rama = fix/la-colonia-facet-discovery-observability
base = main
head = 4632be0e1aee23a1e2bd5a9bb81f28f0ae1ccbf8
estado = abierto, draft, no fusionado
auto-merge = deshabilitado
archivos modificados = 9
casos técnicos nuevos = 27
```

La corrección técnica:

- escribe un resultado sanitizado antes de invocar el controlador;
- valida evento, acción, PR #7, fork y SHA;
- delega en el controlador confiable existente;
- registra inmediatamente un dispatch facet válido sobre `ref=main`;
- conserva un único dispatch;
- registra comentarios GraphQL o REST exitosos sin publicarlos por sí misma;
- conserva evidencia cuando ambos comentarios son bloqueados;
- normaliza rechazos al esquema legacy del observador;
- convierte la ausencia del artefacto en error visible;
- observa todos los runs `completed`, incluidos fallos;
- mantiene checkout de `main`, permisos, allow-list y observador de solo lectura;
- no cambia `paths`, scraper, runner normal, adaptador o runtime.

La validación sintética local de los escenarios críticos pasó. GitHub no creó un
run asociado al head técnico mediante las herramientas disponibles:

```text
workflow_run_id = No expuesto
job_id = No expuesto
suite completa = Pendiente de verificación
fusión técnica = no realizada
integración de main en PR #7 = no realizada
```

El PR técnico no se fusionará sin checks completamente verdes.

## Incidencia administrativa en main

Durante la operación con el conector se crearon por error dos archivos
temporales y se eliminaron inmediatamente:

```text
e741f725546f17e3f931a1ce962fd3fe850c5102 — agrega noop
ea8508e941f1ba1f8d2c421980fded970c5d8080 — elimina noop
16d229a36ba8c9b0107f44abb65cab2ff63e506f — agrega marcador temporal
61b901973f869853cfd1060de1509ce9668ec782 — elimina marcador temporal
```

La comparación `52152f2...61b9019` devuelve `files=[]`: el árbol final de
`main` es idéntico al inicial, aunque el historial contiene esos cuatro commits
administrativos. Ninguno tocó el archivo operacional o ejecutó código live.

## Documentación oficial consultada

- Events that trigger workflows: `pull_request_target`, `synchronize` y `paths`.
- Workflow syntax for GitHub Actions: filtros de rutas y ramas.
- About pull request comparisons: diff de tres puntos para Pull Requests.
- GITHUB_TOKEN: supresión o aprobación de eventos generados por automatización.
- Secure use of `pull_request_target`: ejecutar solo código de la rama confiable.
- Workflow artifacts: persistencia y retención configurable.

## Restricciones confirmadas

No se ejecutó:

- un segundo facet discovery;
- `la-colonia-facet-discovery-002`;
- otro diagnóstico;
- baseline500-003;
- validation500;
- full;
- recorrido particionado.

```text
productos descargados = 0
facets reales consultadas = 0
persistencia = no
historial = no
ejecución diaria = no
Google Sheets = no
BigQuery = no
Power BI = no
PR #7 = abierto, draft y no fusionado
autorización live = consumida
otra ejecución live = NO AUTORIZADA
```

El siguiente paso es obtener una CI automática verificable para PR #17. Solo
con todos los checks verdes podrá fusionarse e integrarse `main` mediante merge
normal en PR #7.
