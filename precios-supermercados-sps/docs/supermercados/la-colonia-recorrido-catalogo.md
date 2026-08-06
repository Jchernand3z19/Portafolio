# La Colonia — recorrido completo, facet discovery y frontera confiable

## Estado verificado

```text
main inicial = d748b6f6645d227429198694379a8146f1e5c939
main con infraestructura confiable = 52152f2f5f13c9320f9cc32b22e3e2eacb2cf9a6
PR técnico = #16 — fusionado
PR funcional = #7 — abierto, borrador y no fusionado
merge de main en PR #7 = 2b313d229e7064784ef7a24f30a57ec7e69e2c8f
```

Esta etapa no ejecutó `facet_discovery`, no consultó facets reales y no realizó tráfico a La Colonia. Tampoco ejecutó un segundo diagnóstico, `baseline500-003`, `validation500` ni `full`.

## PR técnico confiable

El Pull Request técnico:

```text
#16 — Habilita el descubrimiento confiable de facets de La Colonia
rama = chore/la-colonia-facet-discovery-trusted-dispatch
base inicial = d748b6f6645d227429198694379a8146f1e5c939
head técnico = 3ce3313b7d51fa03c22ceecfdd4c60c9dfaf8008
merge SHA = 52152f2f5f13c9320f9cc32b22e3e2eacb2cf9a6
método = merge commit
```

Fue fusionado únicamente después de una CI completa verde:

```text
workflow_run_id = 31070502873
job_id = 92517278017
251 passed in 1.56s
errores = 0
omisiones = 0
warnings de pytest = 0
módulos Python compilados = 15
scripts Python compilados = 3
```

## Arquitectura de confianza

El controlador privilegiado conserva `pull_request_target`, pero ejecuta solamente código ya fusionado en `main`.

Flujo:

1. El controlador hace checkout explícito de `main`.
2. El archivo operacional del PR se recupera por API y se trata solo como datos no confiables.
3. El dispatcher Python de `main` valida el esquema discriminado exacto.
4. La selección de workflow se deriva exclusivamente del modo validado.
5. `facet_discovery` se despacha sobre `ref=main`.
6. El workflow de facets hace otro checkout explícito de `main`.
7. Adaptador, queries, runtime, límites, sanitización y artefactos proceden exclusivamente de `main`.

La rama funcional no puede controlar:

- host;
- endpoint;
- URL;
- query;
- `operationName`;
- variables;
- `selectedFacets`;
- headers;
- timeout;
- límites;
- workflow.

## Esquemas cerrados del dispatcher

### Smoke y staged

Campos exactos:

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

### Diagnostic overlap

Campos exactos:

```text
request_id
supermarket
mode
diagnostic_plan
delay_seconds
allow_full
```

### Facet discovery

Campos exactos:

```text
request_id
supermarket
mode
discovery_plan
delay_seconds
allow_full
```

Contrato autorizado para infraestructura, pero no para ejecución:

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
AUTORIZACIÓN LIVE = NO AUTORIZADA TODAVÍA
```

El contrato no fue escrito en el archivo operacional.

## Selección confiable de workflows

```text
smoke / staged
→ .github/workflows/precios-supermercados-sps-la-colonia-live.yml

diagnostic_overlap
→ .github/workflows/precios-supermercados-sps-la-colonia-diagnostic.yml

facet_discovery
→ .github/workflows/precios-supermercados-sps-la-colonia-facet-discovery.yml
```

La allow-list efectiva contiene exactamente esos tres workflows. La ruta nunca procede del archivo operacional.

Inputs normalizados de facet discovery:

```json
{
  "request_id": "la-colonia-facet-discovery-001",
  "discovery_plan": "catalog_categories_v1",
  "delay_seconds": "1.5"
}
```

## Workflow de facet discovery

El workflow nuevo usa únicamente:

```yaml
on:
  workflow_dispatch:
```

Características:

```text
permissions = contents: read
checkout = main
concurrency = 1
timeout del job = 10 minutos
max_retries = 0
máximo de solicitudes = 2
pausa = 1.5 segundos
```

No contiene `schedule`, `push`, `pull_request`, `pull_request_target`, `issue_comment` ni `workflow_run`. No tiene permisos `actions: write`, `issues: write` ni `pull-requests: write`.

## Adaptador confiable

Valores fijados por código:

```text
host = www.lacolonia.com
endpoint = https://www.lacolonia.com/_v/segment/graphql/v1
HTTPS = obligatorio
timeout HTTP = 20 segundos
user agent = fijo
cookies = no
tokens VTEX = no
APIs administrativas = no
```

Operaciones permitidas:

```text
FacetDiscoveryRootTotal
FacetDiscoveryCategoryTree
```

Variables fijas:

```json
{
  "query": "",
  "fullText": "",
  "selectedFacets": [],
  "from": 0,
  "to": 0
}
```

La primera operación solicita únicamente `recordsFiltered`. La segunda solicita el total de control, `sampling`, facets de categoría, relaciones `children` y `quantity`. Ninguna operación solicita productos, SKU, precios o marcas.

## Runtime y reglas de rechazo

El runtime exige:

- total raíz numérico y positivo;
- total de control igual al total raíz;
- `sampling=false`;
- `category-1` presente;
- niveles consecutivos hasta `category-8`;
- `children` explícito;
- cantidades numéricas y no negativas;
- hijo no superior al padre;
- al menos una hoja positiva;
- máximo 250 hojas positivas;
- presupuesto calculable;
- máximo 500 solicitudes futuras.

Detiene y rechaza:

```text
sampling=true
total cambiante
estructura inválida
árbol incompleto
cantidad inválida
más de 250 hojas
más de dos solicitudes
fallo de sanitización
artefacto mayor de 64 KiB
```

Un presupuesto superior a 500 produce `over_budget`: es un resultado técnico completo, pero no autoriza el recorrido.

## Presupuesto

```text
primary_requests = Σ ceil(quantity_partition / 50)
probe_requests = Σ max(pages_partition - 1, 0)
recovery_reserve = 4 × min(particiones_positivas, 5)
reconciliation_requests = páginas de las dos particiones mayores
estimated_total_requests = suma de los cuatro componentes
```

```text
estimated_total_requests <= 500 → within_budget
estimated_total_requests > 500  → over_budget
```

No existe presupuesto real de La Colonia porque no se consultaron sus facets.

## Códigos de salida

```text
0 = discovery completado y dentro del presupuesto
2 = discovery completado, pero sobre presupuesto
3 = sampling_detected
4 = total cambiante o árbol incompleto
5 = transporte, estructura o cantidad inválida
6 = sanitización o seguridad
```

Solo `0` y `2` representan éxito técnico del workflow. No existe repetición automática para los demás códigos.

## Sanitización

Artefactos permitidos:

```text
facet-discovery-summary.json
facet-discovery-summary.md
```

Cada archivo y el conjunto deben permanecer por debajo de 64 KiB.

Campos públicos permitidos:

```text
schema_version
request_id
discovery_plan
started_at
finished_at
requests_planned
requests_attempted
requests_completed
delay_seconds_applied
root_total
sampling_detected
facet_levels_detected
facet_values_count
leaf_partitions_count
positive_leaf_partitions
zero_quantity_partitions
estimated_primary_requests
estimated_probe_requests
estimated_recovery_reserve
estimated_reconciliation_requests
estimated_total_requests
request_limit
within_request_limit
discovery_completed
discovery_outcome
stop_reason
quality_events
```

Datos prohibidos:

- nombres o valores de categorías;
- rutas de facets;
- `selectedFacets`;
- URLs y queries;
- payloads;
- productos;
- `productId` o `productReference`;
- SKU, `itemId` o EAN;
- marcas y precios;
- identificadores individuales.

## Observador y recuperación

El observador reconoce la relación cerrada:

```text
facet_discovery
→ .github/workflows/precios-supermercados-sps-la-colonia-facet-discovery.yml
```

Rechaza modos, workflows, tipos o relaciones desconocidas. Conserva compatibilidad con artefactos legacy y mantiene `RECOVERY_REQUIRED` cuando el dispatch fue enviado pero el comentario no pudo publicarse. El observador no inicia ni repite workflows.

## Integración en PR #7

El nuevo `main` se integró mediante un merge commit real de dos padres:

```text
padre funcional = e89373d9762b2ac090247937eeffa765afbe9f53
padre main = 52152f2f5f13c9320f9cc32b22e3e2eacb2cf9a6
merge funcional = 2b313d229e7064784ef7a24f30a57ec7e69e2c8f
force-push = no
```

Los módulos compartidos usan los mismos blobs fusionados en `main`; no existen dos runtimes divergentes. La prueba funcional completa de facet discovery permanece en PR #7 y se ejecuta junto con las pruebas técnicas.

CI combinada antes de esta actualización documental:

```text
workflow_run_id = 31070620092
job_id = 92517615722
428 passed in 2.13s
errores = 0
omisiones = 0
warnings de pytest = 0
módulos Python compilados = 19
scripts Python compilados = 5
```

## Archivo operacional

Permanece exactamente:

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

## Decisión y siguiente paso

```text
infraestructura confiable = disponible en main
workflow facet discovery = disponible, no ejecutado
facets reales = no consultadas
PR #7 = abierto, borrador, no fusionado
próxima solicitud = NO AUTORIZADA TODAVÍA
```

La próxima acción posible requiere una autorización separada y expresa para escribir el contrato `la-colonia-facet-discovery-001` en el archivo operacional. Esta documentación no concede esa autorización.
