# La Colonia — facet discovery y estado de la prueba controlada

## Infraestructura confiable

```text
main = 52152f2f5f13c9320f9cc32b22e3e2eacb2cf9a6
PR técnico = #16 — fusionado
PR funcional = #7 — abierto, draft y no fusionado
```

El controlador y el workflow de facets ejecutan código confiable de `main`. El
archivo operacional se trata únicamente como datos. El modo `facet_discovery`
solo puede seleccionar el workflow fijo de facets y el adaptador solo reconoce
las operaciones lógicas `root_total` y `category_tree`.

## Solicitud autorizada

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

La solicitud fue escrita una sola vez en:

```text
precios-supermercados-sps/.automation/la-colonia-live-command.json
```

Registro:

```text
commit operacional = 1a515913a514d3b246c3445eddfff8fcb0d951b4
blob anterior = 92146efe01b99ff0cea99fc51967e90807d5b5da
blob actual = 7b40b1dc9e12e4ded347c753b863b3fd3f8b8186
```

El archivo no se restauró ni se modificó por segunda vez.

## Resultado observable

La ejecución queda clasificada como `inconclusive`.

No se obtuvo evidencia observable de:

- comentario o marca idempotente para el request ID;
- identificador del controlador;
- confirmación de dispatch;
- identificador del workflow de facets;
- artefactos JSON o Markdown;
- métricas agregadas del sitio.

Por tanto, no se presume que las dos solicitudes HTTP hayan ocurrido y no se
publican valores inventados.

```text
requests_planned = 2 por contrato
requests_attempted = no expuesto
requests_completed = no expuesto
root_total = no expuesto
total de control = no expuesto
sampling = no expuesto
niveles = no expuesto
conteos por nivel = no expuesto
hojas positivas = no expuesto
hojas cero = no expuesto
presupuesto = no expuesto
discovery_completed = false
discovery_outcome = inconclusive
stop_reason = controller_and_facet_run_not_observable
```

No se descargaron productos ni se publicaron categorías, valores, rutas,
productos, SKU, EAN, marcas, precios, promociones o identificadores.

## CI del commit operacional

```text
workflow_run_id = 31123802072
job_id = 92690011372
conclusion = failure
compilación = success
pytest = 1 failed, 427 passed in 1.64s
```

Falló únicamente:

```text
test_operational_contract_is_unchanged_when_present_on_functional_branch
```

La prueba esperaba de forma fija el contrato diagnóstico anterior y rechazó el
nuevo contrato autorizado de facets. La autorización no permitía corregir código
ni repetir el live, por lo que la etapa se detuvo.

## Restricciones y decisión

No se ejecutó manualmente ningún workflow. No hubo segundo commit operacional,
segundo facet discovery, segundo diagnóstico, baseline500-003, validation500,
full ni recorrido particionado.

```text
resultado = inconclusive
repetición automática = no
otra ejecución live = no autorizada
PR #7 = abierto, draft y no fusionado
```

Siguiente trabajo offline:

1. corregir la prueba que fija el contrato diagnóstico anterior;
2. revisar por qué el controlador no dejó evidencia recuperable;
3. añadir regresiones de observabilidad e idempotencia;
4. ejecutar toda la suite offline;
5. solicitar autorización nueva antes de cualquier segundo intento.
