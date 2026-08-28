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
daily = pendiente de observaciones consecutivas + flujo diario + autorización recurrente
dashboard = fuera del MVP actual
ACTIVE_AUTHORIZATION_IDS = []
```

No iniciar otro supermercado ni construir visualización antes de cerrar este bloque.

## SPS — última evidencia válida

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

sps_region_fingerprint = d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
json_sha256 = 9c1b3015da39cd283d97bd66d694e5719700c58b5063d797934235c4ff7a6581
```

Dos productos fuente poseen dos SKU; por eso `9471 SKU` y `9469 product_id` son
consistentes. El snapshot antiguo de 9,439 SKU ya no es referencia operativa.

## TGU — última evidencia válida

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
catalog_product_coverage = 1.0

catalog_complete = true
validation_passed = true
result = success

json_sha256 = 97c688290b5b1d00580c908d20164fa41f0282cb2f133e95e73030ac16bc0595
```

Dos productos fuente poseen dos SKU. El fallo anterior
`product_search_graphql_errors` queda sólo como evidencia histórica; la ejecución
parcial `33141576809` no forma parte del estado aceptado.

El runner TGU reutiliza el scraper operativo de SPS y añade sólo el retry acotado
del fallo GraphQL observado. Cualquier otro fallo sigue siendo fail-closed.

## Persistencia MVP

El modelo usa exactamente cinco tablas:

```text
supermarkets
locations
products
price_history
scrape_runs
```

Una sola cadena:

```text
la_colonia
```

Dos ubicaciones:

```text
la_colonia_sps = San Pedro Sula
la_colonia_tgu = Tegucigalpa
```

Identidad de producto:

```text
supermarket_id + source_key_type + source_key
```

Estado comercial histórico por producto + ubicación:

```text
current_price
reported_regular_price
is_promotion
availability
```

Reglas:

```text
mismo estado -> registrar run, no abrir historia nueva
estado cambió -> cerrar periodo actual y abrir periodo nuevo
producto nuevo -> insertar producto y abrir periodo inicial
replay exacto -> no duplicar
snapshot inválido/incompleto -> no mutar estado aceptado
```

`actualizar_mvp_sqlite_la_colonia.py` implementa y prueba estas reglas offline.

## Base limpia SPS + TGU

La base limpia se reconstruyó desde los dos artifacts aceptados:

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

La unión produce 9,509 identidades SKU únicas; SPS y TGU no se modelan como
catálogos de productos independientes.

## Turso — reemplazo limpio completado y reconciliado

Base única:

```text
precios-supermercados
```

La carga vieja de prueba fue eliminada el `2026-08-28` y la base fue recreada desde
el SQLite limpio anterior. Después se renovó `TURSO_AUTH_TOKEN` en GitHub.

La reconciliación de solo lectura desde GitHub Actions fue exitosa:

```text
verification_workflow_run_id = 33184874691
verification_job_id = 98896132583
result = success

tables =
  locations
  price_history
  products
  scrape_runs
  supermarkets

supermarkets = 1
locations = 2
products = 9509
price_history = 18966
scrape_runs = 2
open_price_history = 18966
duplicate_open_periods = 0

la_colonia_sps:
  in_stock = 7093
  out_of_stock = 2378

la_colonia_tgu:
  in_stock = 7584
  out_of_stock = 1911
```

Los dos `scrape_runs` remotos coinciden con los artifacts y SHA aceptados de SPS y
TGU. Por tanto, reemplazar/reconciliar la carga inicial de Turso ya no es pendiente.

## Persistencia directa GitHub -> Turso

El siguiente cambio técnico es usar los mismos snapshots completos aceptados para
actualizar Turso directamente, sin volver a subir un archivo SQLite completo.

Requisitos del camino mínimo:

```text
snapshot válido
-> validar esquema/ubicación/run
-> registrar scrape_run
-> upsert products
-> comparar estado por ubicación
-> cerrar/abrir historia sólo cuando corresponda
-> commit atómico
```

No agregar tablas, base por ciudad ni dependencia externa si el protocolo HTTP de
Turso y la librería estándar son suficientes.

## Precio

```text
current_price          = precio efectivo observado
reported_regular_price = precio regular/tachado declarado por la fuente
previous_price         = current_price del periodo histórico aceptado anterior
```

Los precios persistidos se almacenan en centavos enteros.

## Ejecución diaria

No hay recurrencia live autorizada.

Orden pendiente:

```text
1. terminar y validar persistencia directa GitHub -> Turso
2. ejecutar segunda observación real SPS + TGU con autorización puntual nueva
3. aplicarla a Turso y comprobar histórico/idempotencia real
4. ejecutar tercera observación real con nueva autorización puntual
5. preparar el workflow diario mínimo con los mismos scrapers y persistencia
6. activar recurrencia sólo con autorización humana explícita
7. validar el primer ciclo diario y cerrar La Colonia MVP
```

Un fallo de una ciudad no permite persistir su snapshot parcial ni declararlo como
ejecución aceptada.

## Seguridad y live

```text
ACTIVE_AUTHORIZATION_IDS = []
```

Todas las autorizaciones live anteriores están consumidas. Cualquier marker,
workflow o evidencia histórica no se interpreta como autorización abierta. Un
nuevo tráfico live requiere autorización humana explícita vigente para su alcance;
la recurrencia diaria requiere una autorización recurrente separada.

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

La deuda histórica que no bloquee el MVP puede permanecer hasta después del cierre
de La Colonia.
