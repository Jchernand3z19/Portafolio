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
daily = pendiente de reemplazo Turso + observaciones consecutivas + autorización recurrente
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

El fingerprint canónico del contexto SPS que permanece protegido por los tests es:

```text
d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
```

El JSON aceptado tiene:

```text
sha256 = 9c1b3015da39cd283d97bd66d694e5719700c58b5063d797934235c4ff7a6581
```

El snapshot antiguo de 9,439 SKU ya no es la referencia operativa válida.

## TGU — catálogo completo validado

La corrección mínima se validó con una ejecución read-only TGU propia:

```text
workflow_run_id = 33150113253
artifact_id = 9677584556
artifact_digest = sha256:6f4116dac8c64341ef5d4da0b5664979f8ef3a55bd45b20f449553758d958b82
observed_at_utc = 2026-08-28T07:14:45Z
location_id = la_colonia_tgu
city = Tegucigalpa

catalog_products_reported = 9493
unique_products_extracted = 9493
skus_extracted = 9495
skus_with_price = 9495

availability_in_stock = 7584
availability_out_of_stock = 1911
availability_unknown = 0

partitions_detected = 62
partitions_completed = 62
planned_product_requests = 217
product_requests_completed = 236
catalog_product_coverage = 1.0

catalog_complete = true
validation_passed = true
result = success
```

Dos productos fuente poseen dos SKU; por eso `9495 SKU` y `9493 product_id` son
consistentes.

El JSON aceptado tiene:

```text
sha256 = 97c688290b5b1d00580c908d20164fa41f0282cb2f133e95e73030ac16bc0595
```

El fallo anterior `product_search_graphql_errors` queda únicamente como evidencia
histórica. La ejecución `33141576809` llegó a 7,428 SKU parciales y **no** forma
parte del estado aceptado.

## Corrección TGU validada

El runner TGU mantiene el mismo scraper probado y sólo añade el comportamiento
necesario para el fallo observado:

1. `product_search_graphql_errors` puede reintentarse hasta dos veces adicionales;
2. durante toda la ejecución, incluidos fallos, la metadata usa
   `la_colonia_tgu` / `Tegucigalpa`.

Cualquier otro error sigue siendo fail-closed. La ejecución completa TGU demuestra
que no se necesitó un scraper distinto ni una arquitectura separada por ciudad.

## Persistencia MVP

El modelo sigue usando exactamente cinco tablas:

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

## Base limpia SPS + TGU verificada

Se reconstruyó desde cero con los dos artifacts aceptados y el updater vigente:

```text
workflow_run_id = 33151305834
artifact_id = 9677798005
artifact_digest = sha256:81494e24a162d0f0d83bb9151b63c8933a00ff7acaa27a471783698a6f06af86
sqlite_sha256 = 9da2a6665b1a8d466ed59bb58730c52bd0b55f6bb1c6793a668adaaeb504cf14

supermarkets = 1
locations = 2
products = 9509
price_history = 18966
scrape_runs = 2
open_price_history = 18966
duplicate_open_periods = 0

la_colonia_sps:
  current_rows = 9471
  in_stock = 7093
  out_of_stock = 2378
  unknown = 0

la_colonia_tgu:
  current_rows = 9495
  in_stock = 7584
  out_of_stock = 1911
  unknown = 0

shared_product_identities = 9457
sps_only_product_identities = 14
tgu_only_product_identities = 38

PRAGMA integrity_check = ok
foreign_key_check = empty
journal_mode = wal
page_size = 4096
auto_vacuum = 0
encoding = UTF-8
```

La unión produce `9509` productos porque SPS y TGU comparten 9,457 identidades de
SKU; no se suman catálogos completos como si fueran productos distintos.

El artifact contiene `precios-supermercados.sqlite`, `SHA256SUMS.txt` y
`manifest.json`, y está preparado para la importación inicial limpia a Turso.

## Turso

Base objetivo única:

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

El estado correcto para el siguiente paso ya existe como SQLite limpio y validado.
El camino vigente queda reducido a:

```text
carga vieja Turso
-> reemplazar por artifact 9677798005
-> reconciliar Turso contra la base limpia
-> ejecutar observaciones reales siguientes
```

No crear otro esquema ni otra base para resolver esta importación.

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
1. reemplazar/verificar Turso con la base limpia ya validada
2. ejecutar segunda/tercera observación real con autorizaciones puntuales nuevas
3. comprobar histórico/idempotencia en operación real
4. preparar flujo diario mínimo
5. activar recurrencia sólo con autorización humana explícita
```

Un fallo de una ciudad no permite mezclar datos parciales ni declarar exitoso el
run global.

## Seguridad y live

```text
ACTIVE_AUTHORIZATION_IDS = []
```

La autorización puntual usada para `33150113253` está consumida. Autorizaciones
anteriores también están consumidas y no se reutilizan. Cualquier marker, workflow
o evidencia histórica no se interpreta como autorización abierta; un nuevo tráfico
live requiere autorización humana explícita vigente para su alcance.

Artifacts existentes sí pueden analizarse y transformarse offline.

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
