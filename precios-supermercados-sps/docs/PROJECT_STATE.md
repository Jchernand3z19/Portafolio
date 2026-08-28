# Estado actual — Precios de Supermercados SPS

Este archivo describe únicamente el **estado operativo vigente**. GitHub `main`, PRs y CI siguen siendo la fuente de verdad técnica.

## Objetivo activo

Cerrar el **MVP mínimo de La Colonia en San Pedro Sula y Tegucigalpa** antes de iniciar otro supermercado.

```text
mvp_scope = la_colonia_sps_tgu
storage_first_load = sqlite_file
storage_destination = turso_native_upload
database_name = precios-supermercados
visualization = dash_plotly_minimal
```

La base es única para el proyecto completo. No se crea una base por supermercado ni por ciudad.

## Snapshot aprobado SPS disponible

El catálogo completo SPS ya fue obtenido y no debe descargarse otra vez para la primera carga.

```text
run_id = 32922877781
artifact_id = 9590684834
preserved_artifact_id = 9655225996
artifact_zip_sha256 = 0427e88be27df89fd9fcb50ed600ef5c6aef64177bfba92b4af3d2e25756a892
full_catalog_json_sha256 = 2780eeffa5ef62f2d1c8c2c8365e88da1ca0006622d2f7b1c3529f834c9b5e50
location_id = la_colonia_sps
sps_region_fingerprint = d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
catalog_products_reported = 9437
unique_products_extracted = 9437
skus_extracted = 9439
skus_with_price = 9439
availability_in_stock = 7081
availability_unknown = 2358
```

La diferencia `9439 SKU` vs `9437 source product_id` es válida: dos productos poseen dos SKU.

Tegucigalpa ya forma parte del alcance del MVP, pero **todavía no se atribuyen precios a TGU hasta completar y validar su propio run**.

## Normalización existente

La normalización previa se conserva, pero no es requisito para complicar la persistencia inicial.

```text
normalized_offers = 9439
presentation_normalized = 8436
presentation_pending = 1003
gtin_mapping_ready = 8965
product_mapping_pending = 474
```

No inventar los 1,003 pendientes de presentación ni los 474 mappings pendientes.

## Persistencia MVP

La primera carga usa el camino más corto:

```text
snapshot aprobado SPS
-> verificar SHA-256 y metadata
-> generar SQLite compartido
-> comprobar integridad/FKs/conteos
-> Upload SQLite File en Turso
```

No se necesita para esta primera carga:

- driver/adapter remoto Turso;
- workflow de escritura Turso;
- secrets Turso en GitHub;
- BigQuery;
- Google Sheets;
- nuevas capas de autoridad/seguridad.

El SQLite mínimo tiene cinco tablas:

```text
supermarkets
locations
products
price_history
scrape_runs
```

Granos:

- `supermarkets`: una fila por supermercado.
- `locations`: una fila por ciudad/contexto comercial del supermercado.
- `products`: una fila por SKU/identidad fuente del supermercado.
- `price_history`: un periodo comercial por producto y ubicación.
- `scrape_runs`: una fila por ejecución terminal.

Para el snapshot SPS inicial se esperan exactamente:

```text
supermarkets = 1
locations = 2            # SPS + TGU conocida, aunque TGU aún no tenga precios
products = 9439
price_history = 9439
scrape_runs = 1
open_prices = 9439
priced_rows = 9439
availability_in_stock = 7081
availability_unknown = 2358
tgu_price_rows = 0
```

## Precio

```text
current_price          = precio efectivo observado
reported_regular_price = precio regular/tachado declarado por la tienda
previous_price         = precio efectivo del periodo aceptado anterior
```

La base SQLite almacena precios en centavos enteros para evitar errores de coma flotante.

## Historial

`price_history.valid_to_utc IS NULL` representa el estado actual.

Una ejecución futura debe:

1. registrar siempre su fila en `scrape_runs`;
2. actualizar los atributos descriptivos de `products` cuando cambien;
3. comparar precio/promoción/disponibilidad contra el periodo abierto del producto en esa ciudad;
4. no crear historia nueva si el estado comercial no cambió;
5. cerrar el periodo previo y abrir uno nuevo si cambió un atributo comercial relevante.

Ese actualizador se implementa cuando exista la segunda ejecución real que lo necesite.

## Turso

El usuario ya tiene una cuenta Turso Free. La base se llamará:

```text
precios-supermercados
```

La primera importación se hará con `Upload SQLite File` después de validar el archivo local. No se requieren tokens para esa importación.

## Ciudades de La Colonia

```text
la_colonia_sps = San Pedro Sula
la_colonia_tgu = Tegucigalpa
```

Ambas ciudades viven en la misma tabla `locations` y sus precios viven en la misma `price_history`, diferenciados por `location_id`.

No crear tablas duplicadas por ciudad.

## BigQuery y Google Sheets

```text
bigquery = paused_legacy
bigquery_billing = not_enabled
google_sheets = legacy_inactive
```

El código previo puede permanecer mientras no bloquee el MVP, pero no se amplía ni se usa como arquitectura activa.

## Visualización

Después de importar el SQLite en Turso, la siguiente pieza es una UI mínima Dash + Plotly que permita:

- buscar producto por nombre;
- seleccionar/filtrar ciudad;
- filtrar por categoría/marca/disponibilidad cuando sea útil;
- mostrar precio actual;
- mostrar precio regular reportado si existe;
- mostrar promoción;
- mostrar disponibilidad.

El historial gráfico se activa cuando exista más de una observación aceptada.

## Ejecución diaria

La Colonia no se considera cerrada hasta probar al menos una segunda ejecución real de SPS/TGU y comprobar el histórico. Después se deja preparado el flujo diario.

Activar tráfico recurrente contra La Colonia requiere autorización humana explícita vigente para esa recurrencia; una ejecución read-only puntual no se convierte automáticamente en autorización diaria.

## Seguridad y live

La evidencia histórica no se interpreta como autorización abierta. Una autorización consumida no se reutiliza para generar tráfico nuevo.

La primera carga SQLite reutiliza exclusivamente el artifact SPS ya obtenido y no realiza nuevas solicitudes contra La Colonia.

## Deuda técnica

El repositorio contiene trabajo histórico más complejo de BigQuery, Google Sheets, Cloudflare, provenance y otras capas. **La existencia de ese código no lo convierte en requisito del MVP**.

No hacer una limpieza masiva ahora salvo que algo bloquee el camino mínimo. Primero cerrar el MVP funcional; después se podrá eliminar deuda sin mezclarla con la entrega.
