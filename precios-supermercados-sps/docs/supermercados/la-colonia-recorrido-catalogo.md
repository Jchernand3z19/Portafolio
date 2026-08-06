# La Colonia — recorrido completo, cobertura y facet discovery

## Estado de la fase

El trabajo funcional permanece en el Pull Request `#7`, rama
`feature/la-colonia-full-crawl-validation`.

```text
main = d748b6f6645d227429198694379a8146f1e5c939
PR #7 = abierto
borrador = sí
fusionado = no
auto-merge = deshabilitado
head inicial de facet discovery = f613c7bc832161c8743d8c227223085663755fc4
```

Esta etapa es exclusivamente offline:

- no se consultaron facets reales de La Colonia;
- no se realizó ninguna solicitud HTTP a La Colonia;
- no se ejecutó ningún workflow live;
- no se modificó el archivo operacional;
- no se ejecutó un segundo diagnóstico;
- no se ejecutó `la-colonia-baseline-products-500-003`;
- no se ejecutó `la-colonia-validation-products-500-001`;
- no se ejecutó `full`;
- no se modificó `LaColoniaCatalogRunner`;
- no se añadió persistencia, historial ni ejecución diaria.

## Problema funcional heredado

La paginación raíz presentó páginas parciales, bloques completos repetidos y
solapamientos incompatibles con los rangos solicitados. El diagnóstico observó,
entre otros casos:

```text
B = 370–389
C = 380–399
B y C devolvieron el mismo conjunto completo

D = 390–409
E = 400–419
D y E devolvieron el mismo conjunto completo
```

La auditoría local descartó errores de construcción de `from/to`, reutilización
de URLs, variables o respuestas, caché local, mutación del plan y errores en
firmas, intersecciones o unión. La clasificación continúa siendo:

```text
B — No se encontró defecto local
causa raíz remota demostrada = no
```

Deduplicar evita almacenar dos veces una identidad, pero no recupera las
identidades omitidas por un bloque remoto repetido.

## Estrategia híbrida vigente

La estrategia funcional seleccionada continúa siendo:

1. descubrir categorías o facets hoja;
2. rechazar facets muestreadas;
3. calcular cantidades por partición solo en memoria;
4. calcular el presupuesto antes del recorrido;
5. recorrer cada partición;
6. usar sondas de frontera;
7. recuperar únicamente fronteras anómalas;
8. reconciliar de forma selectiva;
9. deduplicar globalmente;
10. exigir que la unión coincida con el total raíz;
11. rechazar cuando no pueda demostrarse cobertura.

Los módulos de cobertura y particiones permanecen separados del runner normal.

# Facet discovery

## Objetivo

`facet_discovery` es un modo conceptual cerrado cuya única función futura será
obtener métricas agregadas suficientes para decidir si el recorrido particionado
puede planificarse responsablemente.

No descarga ni publica productos. Solo necesita conocer:

- `recordsFiltered` raíz;
- estado de `sampling`;
- niveles `category-n` expuestos;
- cantidad agregada de valores por nivel;
- relaciones padre-hijo;
- cantidad de hojas positivas y hojas de cantidad cero;
- cantidades privadas por hoja;
- presupuesto estimado;
- resultado de viabilidad dentro de 500 solicitudes.

## Contrato propuesto

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
AUTORIZACIÓN LIVE = NO AUTORIZADO TODAVÍA
```

El parser exige exactamente esos seis campos y valores. No acepta:

- URL;
- query;
- `selectedFacets` arbitrarias;
- niveles suministrados por el comando;
- `from`;
- `to`;
- `orderBy`;
- `page_size`;
- `max_pages`;
- `max_products`;
- `max_requests`;
- `profile`;
- `thresholds`;
- `full`;
- `workflow`;
- cualquier otro campo adicional.

El request ID queda cerrado como `la-colonia-facet-discovery-001` para la futura
prueba mínima. El archivo operacional no fue actualizado con este contrato.

## Plan cerrado `catalog_categories_v1`

El plan contiene exactamente dos solicitudes lógicas predeterminadas:

| Secuencia | Nombre lógico | Resultado requerido |
|---:|---|---|
| 1 | `root_total` | `recordsFiltered` raíz. |
| 2 | `category_tree` | Total de control, `sampling` y árbol de categorías. |

El runtime offline no contiene URL ni query arbitraria. Exige que un transporte
inyectado resuelva únicamente esos dos nombres lógicos. Un adaptador confiable
futuro deberá traducirlos a consultas públicas fijas y revisadas.

El plan fija en código:

```text
page_size para presupuesto = 50
request_limit = 500
concurrency = 1
delay_seconds = 1.5
max_retries = 0
solicitudes de discovery = 2
nivel máximo permitido = category-8
máximo de particiones positivas = 250
```

No se hardcodea ningún nombre real de categoría.

## Sampling

La regla es estricta:

```text
sampling = true
→ discovery_outcome = sampling_detected
→ discovery_completed = false
→ within_request_limit = false
→ presupuesto = 0
→ recorrido particionado no autorizado
```

Una muestra no se usa para construir un árbol definitivo ni para inferir que las
categorías no observadas no existen.

## Identificación de hojas

Una hoja representa la partición más específica expuesta por la respuesta.

Reglas:

1. una raíz debe comenzar en `category-1`;
2. cada hijo debe avanzar exactamente un nivel;
3. se permiten niveles hasta `category-8`;
4. cada nodo debe declarar `children`;
5. `children=[]` identifica explícitamente una hoja;
6. la ausencia de `children` se trata como árbol incompleto, no como hoja;
7. una hoja positiva se transforma en una partición privada;
8. una hoja con cantidad cero se cuenta, pero no genera requests de recorrido;
9. las rutas y valores se conservan únicamente en memoria;
10. el artefacto publica solo conteos agregados.

El nodo padre y sus hijos no se convierten simultáneamente en particiones. Solo
se conserva la ruta más específica disponible.

## Validación de cantidades

Se rechaza:

- cantidad negativa;
- cantidad no numérica;
- hijo con cantidad mayor que su padre;
- la misma ruta repetida con cantidades incompatibles;
- total raíz negativo o inválido;
- cambio de total entre las dos respuestas.

La suma de hojas positivas se compara con el total raíz:

```text
suma de hojas < total raíz
→ incomplete_facet_tree
```

```text
suma de hojas > total raíz
→ posible pertenencia múltiple entre particiones
→ el discovery puede completarse
→ se registra leaf_quantities_exceed_root_total
```

Una suma superior no demuestra por sí sola cuáles productos están compartidos.
La deduplicación y el residual global se validarán durante el recorrido futuro.

## Árbol incompleto

El resultado es `incomplete_facet_tree` cuando ocurre cualquiera de estos casos:

- no se devuelve una facet de categoría;
- existe un salto entre niveles;
- falta `children` en un nodo;
- las hojas positivas no cubren el total raíz;
- se supera el límite de 250 hojas positivas;
- la jerarquía no puede distinguir hoja de corte.

No se activa un recorrido con un árbol incompleto.

# Presupuesto

## Componentes

El estimador existente fue ampliado sin cambiar sus defaults históricos. El modo
cerrado activa cuatro componentes:

### Solicitudes primarias

```text
primary_requests = Σ ceil(quantity_partition / 50)
```

### Sondas de frontera

Se reserva una sonda por cada frontera interna:

```text
probe_requests = Σ max(pages_partition - 1, 0)
```

### Reserva de recuperación

Se reservan cuatro solicitudes para un máximo de cinco particiones anómalas:

```text
recovery_reserve = 4 × min(particiones_positivas, 5)
```

Si las anomalías exceden la reserva, el futuro recorrido deberá detenerse en vez
de ampliar el límite dinámicamente.

### Reconciliación

Se reserva un segundo recorrido completo para las dos particiones con mayor
cantidad de páginas:

```text
reconciliation_requests = páginas de las dos particiones mayores
```

La reconciliación continúa siendo selectiva; no se presupone un segundo recorrido
de todo el catálogo.

### Total

```text
estimated_total_requests =
    primary_requests
  + probe_requests
  + recovery_reserve
  + reconciliation_requests
```

Clasificación:

```text
estimated_total_requests <= 500 → within_budget
estimated_total_requests > 500  → over_budget
```

`over_budget` completa el discovery, pero prohíbe iniciar el recorrido.

## Presupuestos de fixtures

Los valores siguientes proceden únicamente de fixtures sintéticos:

| Páginas sintéticas por partición | Resultado |
|---|---:|
| `[10, 8, 1]` | Menor que 500. |
| `[82, 81, 1]` | Exactamente 500. |
| `[82, 81, 2]` | Mayor que 500. |

No se calculó el presupuesto real de La Colonia porque no se consultaron sus
facets.

# Runtime offline

Se añadieron:

```text
precios-supermercados-sps/src/precios_supermercados/scrapers/
  la_colonia_facet_discovery.py
  la_colonia_facet_discovery_runtime.py
```

Y se amplió:

```text
precios-supermercados-sps/src/precios_supermercados/scrapers/
  la_colonia_catalog_partitions.py
```

El runtime:

- acepta únicamente `catalog_categories_v1`;
- exige un transporte inyectado;
- no posee transporte HTTP predeterminado;
- no importa `SafeHttpClient`;
- no construye URL;
- no conoce GitHub Actions;
- mantiene concurrencia uno;
- exige `max_retries=0`;
- intenta como máximo dos solicitudes lógicas;
- aplica una pausa de 1.5 segundos entre ellas;
- detiene `sampling=true`;
- detiene cambio de total;
- detiene estructura inválida;
- detiene cantidades inválidas;
- produce JSON y Markdown sanitizados;
- no modifica `LaColoniaCatalogRunner`.

Resultados posibles:

```text
within_budget
over_budget
sampling_detected
incomplete_facet_tree
invalid_quantities
no_positive_partitions
inconclusive
```

Solo `within_budget` produce `accepted=true` como propiedad interna del resultado.
`accepted` no se publica en el artefacto porque no forma parte del contrato
sanitizado autorizado.

# Sanitización

## Campos permitidos

El artefacto futuro puede contener únicamente:

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

## Datos prohibidos

No se serializan:

- nombres de categorías;
- valores de categories/facets;
- rutas privadas de partición;
- URLs;
- consultas completas;
- payloads;
- productos;
- SKU;
- marcas;
- precios;
- EAN;
- identificadores individuales.

El JSON y el Markdown están limitados a 64 KiB.

# Pruebas offline

Se añadió:

```text
precios-supermercados-sps/tests/test_la_colonia_facet_discovery.py
```

La CI recolectó 49 casos nuevos. Cubren:

- contrato válido;
- plan desconocido;
- catorce campos arbitrarios rechazados;
- total raíz válido;
- `sampling=false`;
- `sampling=true`;
- `category-1`;
- `category-2`;
- `category-3`;
- `category-4` adicional;
- selección de la hoja más específica;
- árbol incompleto por ausencia de `children`;
- particiones de cantidad cero;
- cantidades negativas;
- cantidades no numéricas;
- cantidades incompatibles en una ruta duplicada;
- cambio del total;
- presupuesto inferior a 500;
- presupuesto exactamente 500;
- presupuesto superior a 500;
- clasificación runtime `over_budget`;
- máximo de solicitudes;
- concurrencia uno;
- `max_retries=0`;
- contrato cerrado del artefacto;
- ausencia de nombres y valores privados en JSON y Markdown;
- ausencia de productos y SKU;
- límite de 64 KiB;
- runner normal sin integración;
- cobertura offline existente sin regresión;
- prueba con sockets bloqueados;
- cantidades de hojas superiores al total por pertenencia múltiple;
- residual global;
- límite de particiones;
- `no_positive_partitions`;
- clasificación de cantidades inválidas;
- clasificación de árbol incompleto;
- compatibilidad de los defaults históricos del presupuesto;
- activación explícita de sondas y reservas cerradas.

CI de implementación antes de actualizar esta documentación:

```text
workflow_run_id = 31063182758
job_id = 92495258556
conclusion = success
358 passed in 1.43s
errores = 0
warnings de pytest = 0
```

# Frontera confiable

## Decisión

```text
PR TÉCNICO REQUERIDO — PENDIENTE DE AUTORIZACIÓN
```

Razones verificadas en `main`:

1. el dispatcher solo reconoce comandos normales y `diagnostic_overlap`;
2. `facet_discovery` sería interpretado con el contrato normal y rechazado;
3. la allow-list de workflows contiene únicamente el workflow live normal y el
   workflow diagnóstico;
4. no existe un workflow manual separado para facet discovery;
5. el observador solo relaciona `smoke`, `staged` y `diagnostic_overlap` con esos
   dos workflows.

La futura frontera confiable requeriría, en otro PR técnico:

- ampliar el dispatcher con un tercer contrato cerrado;
- añadir una constante y allow-list para el workflow de facets;
- añadir un workflow manual separado y de mínimo privilegio;
- añadir un script/adaptador que traduzca los dos requests lógicos a consultas
  públicas fijas;
- añadir publicación de artefacto sanitizado;
- ampliar el observador con la relación cerrada
  `facet_discovery → workflow de facets`;
- añadir pruebas de seguridad, allow-list, legado y recuperación.

Ese PR técnico no fue creado en esta etapa.

# Futura prueba mínima

```text
ESTADO = NO AUTORIZADA TODAVÍA
request_id = la-colonia-facet-discovery-001
plan = catalog_categories_v1
máximo de solicitudes = 2
concurrencia = 1
max_retries = 0
pausa = 1.5 segundos
```

Criterios de detención:

- `sampling=true`;
- total raíz cambiante;
- estructura de facets inválida;
- cantidad negativa, no numérica o incompatible;
- salto de nivel;
- nodo sin `children`;
- ausencia de hojas positivas;
- residual entre hojas y total raíz;
- más de 250 hojas positivas;
- artefacto mayor de 64 KiB;
- fallo de sanitización;
- más de dos solicitudes lógicas.

Datos sanitizados esperados:

- total raíz;
- sampling;
- niveles detectados;
- conteos por nivel;
- hojas positivas y cero;
- cuatro componentes de presupuesto;
- total estimado;
- clasificación dentro/fuera de 500;
- outcome y stop reason.

Riesgos:

- la API pública podría no devolver un árbol completo en una sola respuesta;
- `sampling=true` impediría la planificación;
- las cantidades podrían representar pertenencia múltiple;
- el total podría cambiar entre las dos solicitudes;
- el presupuesto podría exceder 500;
- el adaptador futuro podría requerir revisión ante una estructura pública
  diferente de la normalizada en fixtures.

Resultado esperado:

```text
within_budget u over_budget
```

solo cuando `sampling=false`, el árbol es completo y las cantidades son válidas.

# Archivo operacional

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

# Decisión sobre PR #7

PR #7 debe permanecer:

```text
open = true
draft = true
merged = false
auto_merge = disabled
```

La implementación offline puede mantenerse en el PR como diseño y contrato. No
se debe integrar el modo al runner normal ni activar tráfico hasta que exista una
autorización separada para el PR técnico y, posteriormente, para la prueba mínima.

# Restricciones vigentes

- no ejecutar facets reales;
- no ejecutar otro diagnóstico;
- no baseline500-003;
- no validation500;
- no full;
- no modificar el archivo operacional;
- no fusionar PR #7;
- mantener draft;
- no habilitar auto-merge;
- no aceptar `sampling=true`;
- no aceptar árbol incompleto;
- no exceder 500 solicitudes;
- no publicar nombres ni valores de categorías;
- no publicar productos, SKU, marcas, precios o identificadores;
- no integrar al runner normal;
- no crear todavía el PR técnico;
- no persistencia;
- no historial;
- no ejecución diaria;
- no Google Sheets;
- no BigQuery;
- no Power BI.
