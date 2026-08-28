# Estado actual — Precios de Supermercados SPS

Este archivo describe el estado operativo vigente. GitHub `main`, PRs, Actions y
artifacts son la fuente de verdad técnica.

## Objetivo activo

Cerrar el MVP funcional de una sola cadena:

```text
La Colonia
├── San Pedro Sula
└── Tegucigalpa

database_name = precios-supermercados
storage = Turso
history = cambios comerciales
daily = pendiente de evidencia SPS + TGU y autorización
dashboard = fuera del MVP actual
ACTIVE_AUTHORIZATION_IDS = []
```

No iniciar otro supermercado ni construir visualización antes de cerrar este bloque.

## SPS — última evidencia válida

Ejecución read-only completa:

```text
workflow_run_id = 33143530292
artifact_id = 9675011477
observed_at_utc = 2026-08-28T05:09:23Z
location_id = la_colonia_sps
city = San Pedro Sula

catalog_products_reported = 9469
unique_products_extracted = 9469
skus_extracted = 9471
skus_with_price = 9471

availability_in_stock = 7093
availability_out_of_stock = 2378
availability_unknown = 0

catalog_complete = true
validation_passed = true
result = success
```

Dos productos fuente poseen dos SKU; por eso `9471 SKU` y `9469 product_id` son
consistentes.

El JSON del artifact usado para reconstrucción offline tiene:

```text
sha256 = 9c1b3015da39cd283d97bd66d694e5719700c58b5063d797934235c4ff7a6581
```

El snapshot antiguo de 9,439 SKU ya no es la referencia operativa válida.

## TGU — evidencia existente y fallo real

Ya existió una ejecución combinada SPS + TGU:

```text
workflow_run_id = 33141576809
artifact_id = 9674386788
sps_exit = 0
tgu_exit = 3
tgu_reason = product_search_graphql_errors
```

Antes del fallo TGU había confirmado la selección de ubicación de esa misma
ejecución y había avanzado parcialmente:

```text
catalog_products_reported = 9493
pages_completed = 158
product_requests_completed = 159
skus_extracted = 7428
skus_with_price = 7428
```

Esos 7,428 SKU son parciales y **no son estado aceptado de TGU**.

El artifact de fallo heredó etiquetas SPS porque el wrapper anterior sólo
reescribía ciudad/ubicación después de un éxito. No usar esas etiquetas como
evidencia de que los datos parciales pertenecían a SPS.

## Corrección TGU offline

El runner TGU mantiene el mismo scraper probado y aplica únicamente dos cambios
específicos al fallo observado:

1. `product_search_graphql_errors` puede reintentarse hasta dos veces adicionales;
2. durante toda la ejecución, incluidos fallos, la metadata usa
   `la_colonia_tgu` / `Tegucigalpa`.

Cualquier otro error sigue siendo fail-closed. Si el error GraphQL persiste tras
los reintentos, el run se detiene.

Esta corrección necesita una nueva autorización live puntual para demostrar un
catálogo TGU completo. No existe autorización activa.

## Persistencia MVP

El modelo sigue usando cinco tablas:

```text
supermarkets
locations
products
price_history
scrape_runs
```

Una sola fila de supermercado:

```text
la_colonia
```

Dos ubicaciones:

```text
la_colonia_sps = San Pedro Sula
la_colonia_tgu = Tegucigalpa
```

No existen tablas ni bases separadas por ciudad.

## Updater histórico

`actualizar_mvp_sqlite_la_colonia.py` implementa el camino mínimo:

```text
snapshot completo aceptado
-> registrar scrape_run
-> upsert de products
-> comparar estado comercial por producto + ubicación
-> mismo estado: no nueva historia
-> cambio: cerrar periodo + abrir periodo
-> producto nuevo: periodo inicial
```

Estado comparado:

```text
current_price
reported_regular_price
is_promotion
availability
```

También cubre:

- replay exacto idempotente;
- aislamiento SPS/TGU;
- rechazo previo de snapshot incompleto;
- transacción con rollback;
- `PRAGMA foreign_key_check`;
- validación de integridad y periodos actuales duplicados.

Los tests offline cubren explícitamente los seis casos mínimos del MVP:
mismo estado, cambio de precio, cambio de disponibilidad, producto nuevo, replay
exacto y run inválido/incompleto.

## Reconstrucción limpia SPS verificada offline

Aplicando el artifact SPS `9675011477` a una base nueva con el updater:

```text
supermarkets = 1
locations = 2
products = 9471
price_history = 9471
scrape_runs = 1
open_price_history = 9471

la_colonia_sps:
  in_stock = 7093
  out_of_stock = 2378
  unknown = 0

la_colonia_tgu:
  price_history = 0

PRAGMA integrity_check = ok
foreign_key_check = empty
```

Esto demuestra que el SPS vigente puede producir la mitad SPS de la futura base
limpia sin reutilizar la carga vieja.

## Turso

Base única:

```text
precios-supermercados
```

La carga actualmente visible en Turso corresponde a la primera prueba vieja,
aproximadamente:

```text
products = 9439
availability_in_stock = 7081
availability_unknown = 2358
```

Esa carga está autorizada como descartable y no debe corregirse masivamente.

Camino vigente:

```text
carga vieja
-> descartar cuando TGU sea válido
-> construir SQLite limpio con SPS válido + TGU válido
-> validar
-> reemplazar carga Turso
-> verificar Turso
```

No reemplazar Turso antes de tener un catálogo TGU completo aceptado.

## Precio

```text
current_price          = precio efectivo observado
reported_regular_price = precio regular/tachado declarado por la fuente
previous_price         = precio efectivo del periodo histórico aceptado anterior
```

Los precios físicos del SQLite se almacenan en centavos enteros.

## Normalización

Presentaciones, mappings y otros campos pendientes no bloquean el MVP.

No inventar valores. Conservar el valor fuente y usar `NULL`/pending cuando no
pueda demostrarse una normalización.

## Ejecución diaria

No hay recurrencia live autorizada.

Orden pendiente:

```text
1. validar TGU live con autorización nueva
2. construir y verificar base limpia SPS + TGU
3. reemplazar/verificar Turso
4. ejecutar segunda/tercera observación real
5. comprobar histórico/idempotencia en operación real
6. preparar flujo diario mínimo
7. activar recurrencia sólo con autorización humana explícita
```

Un fallo de una ciudad no permite mezclar datos parciales ni declarar exitoso el
run global.

## Seguridad y live

```text
ACTIVE_AUTHORIZATION_IDS = []
```

Autorizaciones anteriores están consumidas y no se reutilizan.

Artifacts existentes sí pueden analizarse offline.

## Fuera del alcance actual

No trabajar ahora en:

- Dashboard/Dash/Plotly;
- supermercado #2;
- BigQuery;
- Google Sheets;
- Cloudflare;
- APIs públicas;
- microservicios;
- comparación entre supermercados;
- inventario exacto;
- normalización perfecta.

La deuda histórica que no bloquea puede permanecer hasta después del MVP.
