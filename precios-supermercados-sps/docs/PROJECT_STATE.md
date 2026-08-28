# Estado actual — Precios de Supermercados SPS

GitHub `main`, Pull Requests, Actions, artifacts y Turso son la fuente de verdad técnica.

## Objetivo activo

Cerrar el MVP funcional de una sola cadena:

```text
La Colonia
├── San Pedro Sula
└── Tegucigalpa

database_name = precios-supermercados
storage = Turso
history = cambios comerciales por ubicación
dashboard = fuera del MVP actual
```

No iniciar otro supermercado ni construir visualización antes de cerrar este bloque.

## Persistencia MVP

El modelo usa exactamente cinco tablas:

```text
supermarkets
locations
products
price_history
scrape_runs
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

Reglas vigentes:

```text
mismo estado -> registrar scrape_run, no abrir historia nueva
estado cambió -> cerrar periodo actual y abrir periodo nuevo
producto nuevo -> insertar producto y abrir periodo inicial
replay exacto -> no duplicar
snapshot inválido/incompleto -> no mutar estado aceptado
```

`actualizar_mvp_sqlite_la_colonia.py` prueba estas reglas offline y
`actualizar_mvp_turso_la_colonia.py` las aplica directamente en Turso mediante el
protocolo HTTP de Turso, sin subir de nuevo el archivo SQLite y sin agregar otra
dependencia.

## Base limpia inicial SPS + TGU

La base se reconstruyó desde los dos primeros snapshots completos aceptados:

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
```

Snapshot inicial SPS:

```text
workflow_run_id = 33143530292
artifact_id = 9675011477
location_id = la_colonia_sps
catalog_products_reported = 9469
skus_extracted = 9471
in_stock = 7093
out_of_stock = 2378
sps_region_fingerprint = d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
json_sha256 = 9c1b3015da39cd283d97bd66d694e5719700c58b5063d797934235c4ff7a6581
```

Snapshot inicial TGU:

```text
workflow_run_id = 33150113253
artifact_id = 9677584556
location_id = la_colonia_tgu
catalog_products_reported = 9493
skus_extracted = 9495
in_stock = 7584
out_of_stock = 1911
json_sha256 = 97c688290b5b1d00580c908d20164fa41f0282cb2f133e95e73030ac16bc0595
```

La unión inicial contiene 9,509 identidades SKU únicas. SPS y TGU comparten la
identidad del producto y conservan estado comercial independiente por ubicación.

## Turso — base limpia y persistencia directa comprobadas

Base única:

```text
precios-supermercados
```

La carga vieja de prueba fue eliminada el `2026-08-28`, la base fue recreada desde
el SQLite limpio y `TURSO_AUTH_TOKEN` fue renovado en GitHub.

La persistencia directa GitHub -> Turso quedó implementada en `main` mediante el PR
#340. Mantiene las cinco tablas y usa transacción fail-closed para cada snapshot.

## Segunda observación real — aceptada

Ejecución conjunta:

```text
workflow_run_id = 33197121042
artifact_id = 9697218431
artifact_digest = sha256:d6d5196dc7f52b6fa00da691c516d41fd5e4e456276ca5c898140caad2ad049e
```

SPS:

```text
scrape_run_id = 33197121042-sps
catalog_products_reported = 9469
skus_extracted = 9471
json_sha256 = 2aca3c7b4ee89ed77c750654be1c3d2c5ae6f98b7e8ff020a1de0886706cb55a
history_opened = 793
history_closed = 793
```

TGU:

```text
scrape_run_id = 33197121042-tgu
catalog_products_reported = 9493
skus_extracted = 9495
json_sha256 = b3c4c9390a3a5da8467a041d0c4cfcb7df4ed1cf8255aef8e94304a380ebaa36
history_opened = 555
history_closed = 555
```

Estado de Turso después de aceptar ambos snapshots:

```text
products = 9509
price_history = 20314
scrape_runs = 4
open_price_history = 18966
duplicate_open_periods = 0
```

Un timeout HTTP del cliente ocurrió después de que Turso había confirmado el commit
de SPS. El estado se reconcilió por `scrape_run_id` + SHA antes de continuar; no se
repitió una escritura incierta.

## Tercera observación real — aceptada e idempotente

Ejecución conjunta:

```text
workflow_run_id = 33202545775
artifact_id = 9698730415
artifact_digest = sha256:fcb11c5a5aea8ac17568eb881839d02ac7563b3f1da85fc446b4a131c50720ab
```

SPS:

```text
scrape_run_id = 33202545775-sps
catalog_products_reported = 9469
skus_extracted = 9471
json_sha256 = 1cfa1bd6500928f0f5c5259cd09b23601c1260f0f22d748990f17b9d7fb353d8
history_opened = 0
history_closed = 0
```

TGU:

```text
scrape_run_id = 33202545775-tgu
catalog_products_reported = 9493
skus_extracted = 9495
json_sha256 = edff6d902ab63f9b9119f10869abee5d718d1822d72448980efc9397e1343d3d
history_opened = 0
history_closed = 0
```

La verificación posterior desde GitHub Actions (`33203720746`) confirmó ambos runs
y el estado final:

```text
products = 9509
price_history = 20314
scrape_runs = 6
open_price_history = 18966
duplicate_open_periods = 0

la_colonia_sps:
  in_stock = 7093
  out_of_stock = 2378

la_colonia_tgu:
  in_stock = 7790
  out_of_stock = 1705
```

La tercera observación demuestra la idempotencia real requerida: los dos
`scrape_runs` se registraron, pero `price_history` no aumentó porque el estado
comercial era igual al aceptado en la segunda observación.

## Flujo MVP

PR #343 contiene el flujo mínimo permanente de actualización:

```text
workflow_dispatch autorizado o schedule diario autorizado
-> SPS completo read-only
-> TGU completo read-only
-> validar ambos snapshots
-> persistir SPS en Turso
-> persistir TGU en Turso
-> reconciliar cada commit por run_id + SHA
-> verificar 9509 productos, 18966 estados abiertos y cero duplicados
-> publicar artifact de evidencia
```

No agrega servicios, tablas ni un segundo mecanismo de scraping. Los timeouts
ambiguos de escritura se resuelven únicamente con una comprobación read-only
acotada del commit; no se reintenta una escritura de estado desconocido.

## Ejecución diaria autorizada

El usuario autorizó explícitamente el `2026-08-28T19:53:13Z` el paso de ejecución
diaria recurrente para terminar el MVP de La Colonia, manteniendo el alcance sin
sobreingeniería.

```text
scope = La Colonia SPS + TGU
mode = full catalog read-only + validación + persistencia Turso
cadence = daily
cron_utc = 17 11 * * *
local_time = 05:17 America/Tegucigalpa
status = authorized until revoked
```

El workflow conserva `workflow_dispatch` para operación manual autorizada y usa el
mismo job para el `schedule`; no existe un pipeline paralelo.

## Precio

```text
current_price          = precio efectivo observado
reported_regular_price = precio regular/tachado declarado por la fuente
previous_price         = current_price del periodo histórico aceptado anterior
```

Los precios persistidos se almacenan en centavos enteros.

## Seguridad y live

La autorización temporal de 24 horas usada para las observaciones #2 y #3 sigue
siendo evidencia histórica y no se interpreta como autorización abierta.

La autorización recurrente anterior cubre únicamente el schedule diario de La
Colonia SPS + TGU. Cualquier tráfico live fuera de ese alcance requiere autorización
humana explícita vigente. Los artifacts existentes pueden analizarse, verificarse y
persistirse sin volver a consultar el sitio cuando su identidad y SHA están
comprobados.

## Pendiente para cierre

```text
1. pasar CI y fusionar PR #343
2. verificar main
3. retirar rama/workflows temporales de validación de 24h
4. dejar activo el schedule diario autorizado
5. comprobar el primer ciclo diario programado
```

No es necesario agregar otra arquitectura para cerrar La Colonia.

## Fuera del alcance actual

No trabajar ahora en:

- dashboard;
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
