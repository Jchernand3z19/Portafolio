# La Colonia — recorrido completo, diagnóstico y contrato de cobertura

## Estado de la fase

El trabajo funcional permanece en el PR `#7`, rama
`feature/la-colonia-full-crawl-validation`.

```text
PR #7 = abierto
borrador = sí
fusionado = no
auto-merge = deshabilitado
main = d748b6f6645d227429198694379a8146f1e5c939
head inicial de esta etapa = bc2ee7b5aed1344be08d3375f2ef34f346ab9df9
```

Esta etapa fue exclusivamente offline:

- no se ejecutó ningún workflow live;
- no se modificó el archivo operacional;
- no se ejecutó un segundo diagnóstico;
- no se ejecutó `la-colonia-baseline-products-500-003`;
- no se ejecutó `la-colonia-validation-products-500-001`;
- no se ejecutó `full`;
- no se modificó el runner normal;
- no se cambió `OrderByNameASC`;
- no se añadieron cache-busters;
- no se cambió `maxAge`.

## Problema funcional

Dos recorridos normales devolvieron 19 productos para el rango `380–399`, con
`recordsFiltered=9291`, misma firma y mismos bytes. El diagnóstico posterior
devolvió páginas completas, pero mostró bloques desplazados o repetidos:

```text
B = 370–389
C = 380–399
B = C como conjunto completo de 20 productos

D = 390–409
E = 400–419
D = E como conjunto completo de 20 productos
```

Solapamientos observados:

```text
A ∩ B = 0; esperado = 10
B ∩ C = 20; esperado = 10
C ∩ D = 0; esperado = 10
D ∩ E = 20; esperado = 10
```

La unión diagnóstica tuvo 70 productos únicos para 70 posiciones solicitadas,
pero las identidades no se materializaron de forma estable en los rangos.

La auditoría local descartó construcción errónea de URLs, variables `from/to`,
reutilización de respuestas, caché local, mutación del plan, reintentos ocultos
y errores en firmas, solapamientos o unión. La clasificación sigue siendo:

```text
B — No se encontró defecto local
causa raíz remota demostrada = no
```

No se declara un bug interno exacto de VTEX.

## Por qué deduplicar no demuestra completitud

La deduplicación responde a esta pregunta:

> ¿Cuántas identidades distintas fueron recibidas?

No responde a esta otra:

> ¿Fueron recibidas todas las identidades que debían existir?

Si una página remota repite productos de una página anterior y omite otros, la
deduplicación evita guardar dos veces los repetidos, pero no recupera los
omitidos. Incluso `products_unique == recordsFiltered` es insuficiente cuando
existen bloques repetidos, sondas con solapamientos incompatibles, membresía de
partición inválida o posiciones lógicas sin evidencia.

## Comportamiento del runner normal actual

`LaColoniaCatalogRunner`:

1. inicia en `page=1`;
2. construye la URL con `page`, `page_size` y `OrderByNameASC`;
3. deriva `from=(page-1)×page_size` y `to=from+page_size-1`;
4. valida que la primera página empiece en cero;
5. exige ancho constante, sin huecos ni solapamientos entre rangos normales;
6. lee `recordsFiltered` y fija el número de páginas planificadas;
7. rechaza páginas parciales o con más productos de los esperados;
8. calcula una firma ordenada de identidades de producto;
9. rechaza una firma de página completa ya vista;
10. cuenta productos duplicados entre páginas;
11. deduplica SKU antes de acumularlos;
12. finaliza como aceptado cuando completó todas las páginas planificadas y no
    existen errores o eventos estructurales obligatorios.

Controles existentes que se conservan:

- páginas parciales rechazadas;
- página completa idéntica rechazada;
- continuidad de los rangos enviados;
- `orderBy` estable;
- métricas separadas de productos y SKU;
- deduplicación de SKU;
- total inicial y final registrados.

Limitación principal:

La continuidad de `from/to` prueba que el cliente pidió rangos consecutivos; no
prueba que el backend materializó identidades consecutivas y estables dentro de
esos rangos. El total cambiante es una advertencia en baseline, y los duplicados
entre páginas no son por sí solos una condición obligatoria de rechazo.

## Contrato explícito de completitud

### Magnitudes distintas

| Magnitud | Definición |
|---|---|
| `products_received` | Ocurrencias recibidas, incluyendo repetidas. |
| `products_unique` | Identidades estables distintas después de deduplicar. |
| posiciones solicitadas | Unión matemática de los rangos `from/to`. |
| páginas completas | Respuestas con exactamente la cantidad esperada. |
| bloques repetidos | Mismo conjunto completo devuelto para rangos diferentes. |
| solapamiento esperado | Intersección matemática de dos rangos. |
| solapamiento observado | Intersección de identidades privadas recibidas. |
| `products_reported` | `recordsFiltered` de la partición o catálogo raíz. |
| cobertura demostrada | Todas las invariantes se cumplen. |
| cobertura no demostrada | Falta una invariante aunque el conteo coincida. |

### Invariantes por página

- rango válido y dentro del límite local;
- cantidad recibida igual a la esperada;
- ninguna identidad duplicada dentro de la página;
- identidad de producto estable disponible;
- todos los productos pertenecen a la partición solicitada;
- total reportado compatible con la partición descubierta.

### Invariantes por recorrido de una partición

- total estable durante el recorrido;
- todas las posiciones `0..recordsFiltered-1` tienen evidencia;
- todas las páginas base están completas;
- ningún conjunto completo se repite para rangos diferentes;
- todo solapamiento observado coincide exactamente con el esperado;
- ningún duplicado silencioso en rangos que debían ser disjuntos;
- cantidad de identidades únicas igual al total de la partición;
- si se usa otro `orderBy`, ambos recorridos completos producen el mismo conjunto;
- el presupuesto de solicitudes no se excede.

### Invariantes globales

- respuesta de facets sin muestreo;
- todas las categorías hoja descubiertas fueron intentadas;
- todas las particiones fueron completadas;
- la unión global deduplicada coincide con `recordsFiltered` raíz;
- los productos presentes en varias categorías se cuentan una sola vez;
- no quedan productos sin categoría o sin partición demostrada;
- no hubo cambio del total raíz durante la operación;
- no se excedió el límite global de solicitudes.

### Regla de aceptación

```text
accepted = coverage_demonstrated = true
```

solo cuando todas las invariantes de página, partición y catálogo se cumplen.

La igualdad aislada:

```text
products_unique == recordsFiltered
```

no permite aceptar si existen `repeated_page_sets`, `unexpected_overlaps`,
`missing_coverage_events`, totals cambiantes o particiones no demostradas.

## Investigación oficial de VTEX

Fuentes primarias consultadas:

- Search GraphQL, extensión oficial `vtex.search-graphql`;
- Intelligent Search API v1;
- guía oficial para listar facets;
- documentación oficial de arquitectura del catálogo;
- documentación oficial para agregar o editar productos.

### Hechos documentados

- `productSearch` acepta `selectedFacets`, `orderBy`, `from` y `to`.
- `from` es el inicio de paginación y su valor por defecto es `0`.
- `to` es el final de paginación y su valor por defecto es `9`.
- `recordsFiltered` en `ProductSearch` es el número total de productos.
- `OrderByNameASC`, `OrderByNameDESC`, `OrderByPriceASC`,
  `OrderByPriceDESC` y `OrderByReleaseDateDESC` están documentados, junto con
  otros órdenes no habilitados por el proyecto.
- `selectedFacets` reemplaza parámetros antiguos como `map` y `category`.
- `category-1` representa departamento, `category-2` categoría,
  `category-3` subcategoría y niveles posteriores continúan la jerarquía.
- la API de facets devuelve `key`, `value`, `quantity` y puede devolver hijos.
- un valor de facet se devuelve cuando al menos un producto de la búsqueda tiene
  ese valor.
- la respuesta de facets expone `sampling`.
- la agregación GraphQL de facets puede usar solo los primeros 30 000 productos
  cuando la búsqueda es muy grande.
- un producto disponible debe estar asociado con una categoría y al menos un SKU.
- VTEX recomienda asociar el producto con el nivel de categoría más específico.
- desde julio de 2026, VTEX recomienda Intelligent Search API v1 para nuevas
  integraciones headless y desaconseja Search GraphQL para nuevas integraciones.
- la API v1 incorpora `Cache-Control`; VTEX indica leer ese encabezado y no fijar
  duraciones de caché en el cliente.

### Hechos observados

- dos páginas históricas parciales en `380–399`;
- bloques completos B=C y D=E;
- solapamientos 0 o 20 donde se esperaban 10;
- total estable en 9291 durante el diagnóstico;
- construcción local de requests correcta.

### Inferencias

- el origen del patrón está fuera de los componentes locales auditados;
- particiones menores reducen el alcance de una frontera inestable;
- sondas solapadas permiten detectar desplazamientos que una paginación disjunta
  no detectaría;
- una segunda ordenación sirve para reconciliar conjuntos, no para asumir que la
  primera quedó corregida.

### Hipótesis

- el comportamiento puede depender de backend, caché remota, CDN o
  materialización de resultados;
- una categoría hoja podría tener fronteras más estables que la búsqueda raíz;
- Intelligent Search API v1 podría ofrecer una integración futura más apropiada,
  pero no existe evidencia de La Colonia en esta etapa.

### Datos no disponibles

No se encontró en la documentación oficial consultada:

- garantía de orden estable ante productos con el mismo nombre;
- garantía de desempate determinista para `OrderByNameASC`;
- garantía de que páginas consecutivas nunca repiten u omiten productos;
- límite máximo oficial de `from/to` para el campo GraphQL actual;
- garantía de completitud de una búsqueda grande mediante una sola ordenación.

La ausencia de estas garantías no demuestra un defecto de VTEX.

## Estrategias evaluadas

| Estrategia | Cómo funciona | Resuelve | No resuelve | Prueba de completitud | Solicitudes estimadas con total 9291 | Duplicados | Omisiones | Complejidad | Compatibilidad | Recomendación |
|---|---|---|---|---|---:|---|---|---|---|---|
| A — secuencial actual | Rangos disjuntos con `OrderByNameASC`. | Páginas parciales y repeticiones exactas dentro del mismo run. | Desplazamientos sin firma idéntica y omisiones compensadas. | Insuficiente. | 465 con tamaño 20; 186 con 50. | Medio | Alto | Baja | Sí | No aceptar como prueba completa. |
| B — reducir tamaño | Páginas menores y más controles. | Localiza mejor una frontera. | No elimina inestabilidad; eleva carga. | Solo con sondas adicionales. | 930 con tamaño 10; 1859 con 5. | Medio | Medio/alto | Media | Sí | Solo recuperación local. |
| C — dos `orderBy` | Recorre dos veces y une. | Descubre diferencias entre órdenes. | Ambos órdenes pueden omitir; unión grande no prueba posiciones. | Requiere ambos recorridos completos y conjuntos reconciliados. | 930 con tamaño 20; 372 con 50. | Alto | Medio | Media | Sí | Solo reconciliación selectiva. |
| D — categorías/facets | Divide por filtros de categoría. | Reduce tamaño y aísla anomalías. | Categorías solapadas o discovery incompleto. | Cada partición completa + unión raíz. | `1 + Σceil(nᵢ/p)`. | Alto entre categorías | Bajo/medio | Media | Sí | Recomendable como base. |
| E — cada categoría + dedupe | Recorre categorías y deduplica identidad. | Productos en varias categorías. | Dedupe no recupera omitidos. | Exige totales, posiciones y unión raíz. | `Σceil(nᵢ/p)`. | Controlable | Medio sin contrato | Media | Sí | Parte del híbrido. |
| F — hojas recursivas | Usa el nivel más específico disponible. | Minimiza particiones grandes. | Facets muestreadas o árbol incompleto. | `sampling=false`, todas las hojas y unión raíz. | Depende del árbol; mayor por redondeos. | Controlable | Bajo si discovery completo | Alta | Sí | Recomendable. |
| G — recuperación de frontera | Reconsulta solo límites anómalos con ventanas pequeñas. | Localiza bloque repetido/desplazado. | No garantiza el resto del catálogo. | Reconciliación con páginas vecinas. | Base + 2–6 por anomalía. | Bajo | Medio | Media | Sí | Recomendable y acotada. |
| H — híbrida | Hojas + sondas + recuperación + reconciliación selectiva. | Detección, recuperación y prueba agregada. | No supera una fuente incapaz de materializar cobertura. | Contrato completo de partición y raíz. | Debe calcularse antes; límite de diseño 500. | Bajo después de dedupe | Bajo si acepta | Alta | Sí | Seleccionada. |
| I — no recorrible | Rechaza cuando falta evidencia. | Evita publicar un catálogo falso. | No recupera productos. | `accepted=false` explícito. | Se detiene al agotar evidencia/presupuesto. | N/A | No oculta el riesgo | Baja | Sí | Obligatoria como salida segura. |

Las cantidades son estimaciones matemáticas, no ejecuciones. La partición puede
incrementar la suma por redondeos y por productos presentes en más de una
categoría.

## Estrategia recomendada

```text
C — estrategia híbrida
```

### Algoritmo propuesto

#### Fase 0 — preflight

1. Obtener en una futura ejecución autorizada el total raíz y facets de categoría.
2. Rechazar si `sampling=true`.
3. Extraer únicamente categorías hoja con cantidad positiva.
4. Deduplicar `(facet_key, facet_value)` durante el discovery.
5. Calcular antes del tráfico el presupuesto:

```text
primary = Σ ceil(partition_total / page_size)
frontier_probes = Σ max(primary_pages_in_partition - 1, 0)
recovery_reserve = particiones × ventanas_acotadas
secondary_order = solo particiones anómalas
```

6. Rechazar antes de iniciar si el máximo planificado supera el límite.

#### Fase 1 — recorrido primario por partición

- mantener `OrderByNameASC`;
- usar una solicitud lógica a la vez;
- usar hasta 50 productos por página para limitar carga;
- exigir total igual a la cantidad descubierta para la partición;
- comprobar páginas completas e identidades únicas;
- validar que cada producto pertenece a la partición;
- registrar firmas de secuencia y conjunto solo en memoria;
- rechazar conjuntos completos repetidos para rangos diferentes.

#### Fase 2 — sondas de frontera

Entre dos páginas base consecutivas, consultar una ventana pequeña que cruce la
frontera. La intersección con cada vecino debe coincidir exactamente con la
intersección matemática esperada.

Una sonda no se acepta como nueva cobertura; solo aporta evidencia de continuidad.

#### Fase 3 — recuperación local

Si una frontera falla:

- detener el avance de esa partición;
- dividir únicamente la frontera en ventanas menores predeterminadas;
- no aceptar ventanas arbitrarias suministradas externamente;
- mantener un máximo fijo de solicitudes de recuperación;
- reconciliar la unión recuperada con ambos vecinos;
- rechazar la partición si persiste la anomalía o se agota el presupuesto.

#### Fase 4 — reconciliación por orden

Un segundo `orderBy` no se ejecuta para todo el catálogo por defecto. Se reserva
para una partición anómala o una muestra de validación.

Para aceptarlo:

- ambos recorridos deben demostrar cobertura independientemente;
- sus conjuntos de identidades deben ser iguales;
- diferencias de posición son admisibles entre órdenes;
- diferencias de conjunto son rechazo.

#### Fase 5 — unión global

- unir identidades de producto de todas las particiones;
- contar ocurrencias duplicadas entre categorías;
- no materializar dos veces el mismo producto;
- exigir que la unión única coincida con el total raíz;
- exigir cero productos residuales sin categoría o partición;
- aceptar solo si todas las particiones fueron demostradas.

## Identidad y deduplicación

### Identidad de producto para cobertura

Orden recomendado:

1. `productId`;
2. `productReference`;
3. `linkText` estable.

Una identidad basada únicamente en nombre no debe demostrar cobertura porque los
nombres no son necesariamente únicos. La ausencia de identidad estable es un
evento de rechazo.

### Identidad de SKU para materialización

Se conserva la jerarquía existente de `source_key_type` y `source_key`.

La deduplicación ocurre después de probar cobertura de producto. No debe
convertir una partición incompleta en aceptada.

## Categorías y productos compartidos

Un producto puede aparecer en más de una partición navegable. La estrategia:

- cuenta la ocurrencia en cada partición para validar esa partición;
- deduplica globalmente por identidad de producto;
- registra `duplicate_occurrences`;
- no rechaza solo por aparecer en dos categorías si ambas membresías son válidas;
- exige que la unión global final coincida con el total raíz.

## Productos sin categoría

La documentación indica que un producto disponible debe pertenecer a una
categoría. Aun así, la implementación debe detectar un residual:

```text
root_total - global_partition_union
```

Un residual no se etiqueta automáticamente como “producto sin categoría”; también
puede significar facets incompletas o productos omitidos. Cualquiera de esas
interpretaciones impide demostrar cobertura.

## Catálogo cambiante

La estrategia toma snapshots de:

- total raíz inicial/final;
- cantidad descubierta por partición;
- total de cada página y sonda.

Cualquier cambio invalida la demostración actual. No se mezclan resultados de
dos estados distintos del catálogo. La ejecución se detiene y queda rechazada.

## Límite responsable de solicitudes

El modelo offline usa un límite de diseño de 500 solicitudes, no activado live.

Con 9291 productos:

```text
mínimo teórico a page_size=50 = ceil(9291 / 50) = 186
```

Un recorrido raíz con una sonda por frontera sería aproximadamente 371
solicitudes. La partición cambia el valor por redondeos y membresía múltiple. La
reconciliación completa con un segundo orden puede superar el presupuesto.

Por eso el plan se calcula después de descubrir facets y antes de iniciar. Si
`requests_planned > request_limit`, el catálogo se declara no recorrible bajo ese
plan, sin degradar controles.

## Modelo sanitizado de cobertura

El resumen expone únicamente:

```text
partitions_discovered
partitions_attempted
partitions_completed
pages_expected
pages_attempted
pages_completed
products_reported
products_received
products_unique
duplicate_occurrences
repeated_page_sets
unexpected_overlaps
missing_coverage_events
total_changes
uncategorized_products
request_limit
coverage_demonstrated
coverage_reason
accepted
```

No publica:

- productos;
- SKU;
- nombres;
- marcas;
- precios;
- URLs;
- categorías;
- valores de facets;
- identificadores individuales;
- hashes individuales.

## Implementación offline realizada

Se añadieron módulos independientes del runner normal:

```text
src/precios_supermercados/scrapers/la_colonia_catalog_coverage.py
src/precios_supermercados/scrapers/la_colonia_catalog_partitions.py
```

`la_colonia_catalog_coverage.py`:

- modela páginas, particiones y cobertura global;
- detecta páginas parciales;
- detecta duplicados internos y entre rangos;
- detecta conjuntos completos repetidos;
- compara solapamientos esperados/observados;
- exige posiciones lógicas cubiertas;
- exige total estable;
- reconcilia varios `orderBy`;
- verifica la unión global;
- produce resumen sanitizado.

`la_colonia_catalog_partitions.py`:

- extrae categorías hoja desde fixtures de facets;
- ignora hojas con cantidad cero;
- rechaza quantities incompatibles;
- rechaza facets muestreadas;
- limita el número de particiones;
- calcula solicitudes primarias, reserva de recuperación y reconciliación;
- no realiza solicitudes.

El runner normal no importa estos módulos y no fue modificado.

## Pruebas sintéticas

Archivos:

```text
tests/test_la_colonia_catalog_coverage.py
tests/test_la_colonia_catalog_partitions.py
```

Casos cubiertos:

1. recorrido secuencial estable;
2. página parcial;
3. bloque B=C;
4. bloque D=E;
5. rangos diferentes con misma firma;
6. duplicados dentro de página;
7. duplicados entre páginas;
8. productos omitidos con páginas completas;
9. total estable con cobertura falsa;
10. total cambiante;
11. categoría hoja completa;
12. producto en dos categorías;
13. residual sin categoría;
14. partición parcial;
15. partición repetida;
16. unión completa entre categorías;
17. unión incompleta;
18. reconciliación exitosa entre dos órdenes;
19. reconciliación fallida;
20. límite máximo de solicitudes;
21. resumen sanitizado;
22. runner normal sigue rechazando páginas parciales;
23. membresía de partición inválida;
24. partición descubierta no recorrida;
25. tipo explícito del reporte global;
26. discovery de categorías hoja;
27. facets muestreadas;
28. hojas duplicadas y quantities incompatibles;
29. límite de particiones;
30. presupuesto con recuperación y reconciliación;
31. presupuesto excedido antes de tráfico.

CI de implementación previa a documentación:

```text
workflow_run_id = 31059485312
job_id = 92484074117
conclusion = success
308 passed in 3.73s
compile src = success
compile scripts = success
```

El único warning fue de infraestructura: acciones que declaran Node.js 20 fueron
ejecutadas con Node.js 24.

## Condiciones de aceptación futuras

Una futura validación podrá aceptar únicamente cuando:

- facets no muestreadas;
- particiones dentro del límite;
- presupuesto dentro del límite;
- todas las páginas base completas;
- todas las sondas de frontera reconciliadas;
- cero bloques repetidos;
- cero solapamientos inesperados;
- cero totals cambiantes;
- cada partición con únicos igual a su total;
- todos los órdenes usados reconciliados;
- unión global igual al total raíz;
- cero residual sin partición;
- resumen sanitizado válido.

## Condiciones de rechazo futuras

- página parcial o vacía;
- más productos de los esperados;
- identidad de producto inestable o ausente;
- duplicado dentro de página;
- bloque completo repetido en otro rango;
- solapamiento inesperado;
- posición lógica sin evidencia;
- total cambiante;
- facet muestreada;
- categoría hoja no recorrida;
- membresía inválida;
- unión por debajo o por encima del total raíz;
- reconciliación de órdenes fallida;
- límite de solicitudes excedido;
- sanitización fallida.

## Viabilidad

```text
viabilidad técnica del diseño offline = demostrada
viabilidad live en La Colonia = pendiente
completitud del catálogo actual = no demostrada
```

La estrategia puede detectar y rechazar los patrones conocidos, y define cómo
recuperar una frontera de forma acotada. Todavía no existe evidencia de que las
facets públicas de La Colonia sean completas y no muestreadas, ni de que las
particiones hoja materialicen páginas estables.

## Decisión sobre PR #7

```text
Decisión principal = 2 — dividir la activación del recorrido híbrido en otra fase
Estado inmediato = bloqueado hasta nueva evidencia live autorizada
```

PR #7 debe permanecer abierto y en borrador como investigación, diagnóstico y
diseño offline. No debe marcarse listo ni fusionarse. La integración del nuevo
recorrido en `LaColoniaCatalogRunner` debe ocurrir en una fase separada después
de validar facets, presupuesto y al menos una partición controlada.

## Evidencia live necesaria más adelante

Sin proponer ni autorizar una ejecución ahora, una futura fase necesitaría:

1. total raíz y facets con `sampling=false`;
2. conteo de categorías hoja y presupuesto calculado;
3. una partición pequeña completa;
4. una partición con más de una página y sonda de frontera;
5. evidencia de membresía de todos los productos de la partición;
6. unión de particiones comparada con total raíz;
7. reconciliación selectiva si aparece una anomalía;
8. cero publicación de datos comerciales.

## Archivo operacional

Debe permanecer exactamente:

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

## Restricciones vigentes

- no ejecutar otro diagnóstico;
- no crear `la-colonia-window-diagnostic-380-399-002`;
- no ejecutar `la-colonia-baseline-products-500-003`;
- no ejecutar `la-colonia-validation-products-500-001`;
- no ejecutar `full`;
- no modificar el archivo operacional;
- no cambiar automáticamente `OrderByNameASC`;
- no agregar cache-busters;
- no cambiar `maxAge` sin evidencia;
- no admitir ventanas arbitrarias;
- no aceptar páginas repetidas;
- no asumir que deduplicar recupera omitidos;
- no fusionar PR #7;
- mantener PR #7 en borrador y sin auto-merge;
- no agregar persistencia, historial, ejecución diaria, Google Sheets, BigQuery
  ni Power BI;
- toda nueva ejecución live requiere autorización expresa separada.
