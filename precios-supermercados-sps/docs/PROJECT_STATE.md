# Estado actual — Precios de Supermercados SPS

Este archivo describe únicamente el **estado operativo vigente**. GitHub `main`, PRs y CI siguen siendo la fuente de verdad técnica.

## Objetivo activo

Cerrar el **MVP mínimo de La Colonia San Pedro Sula** antes de ampliar arquitectura o iniciar otro supermercado.

```text
mvp_scope = la_colonia_sps_only
storage_first_load = sqlite_file
storage_destination = turso_native_upload
visualization = dash_plotly_minimal
new_live_traffic_authorized = false
ACTIVE_AUTHORIZATION_IDS = []
```

## Snapshot aprobado disponible

El catálogo completo ya fue obtenido y no debe descargarse otra vez para la primera carga.

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

La diferencia `9439 SKU` vs `9437 product_id` es válida: dos productos poseen dos SKU.

## Normalización existente

La normalización previa se conserva, pero no es requisito para complicar la primera persistencia.

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
snapshot aprobado
-> verificar SHA-256 y metadata
-> generar SQLite
-> comprobar integridad/conteos
-> Upload SQLite File en Turso
```

No se necesita para esta primera carga:

- driver/adapter remoto Turso;
- workflow de escritura Turso;
- secrets Turso en GitHub;
- BigQuery;
- Google Sheets;
- nuevas capas de autoridad/seguridad;
- nueva extracción live.

El SQLite mínimo tiene sólo dos tablas:

```text
scrape_runs
  registra el run terminal

offer_history
  conserva identidad fuente + atributos mostrables + estado comercial
  valid_to_utc NULL = estado actual
```

Para el primer snapshot se esperan exactamente:

```text
scrape_runs = 1
offer_history = 9439
open_offers = 9439
priced_offers = 9439
availability_unknown = 2358
```

## Precio

```text
current_price          = precio efectivo observado
reported_regular_price = precio regular/tachado declarado por la tienda
previous_price         = precio efectivo del periodo aceptado anterior
```

La base SQLite almacena precios en centavos enteros para evitar errores de coma flotante.

## Historial

En el MVP, el registro abierto de `offer_history` representa el estado actual. Una ejecución futura debe:

1. registrar siempre su fila en `scrape_runs`;
2. comparar contra el periodo abierto de cada identidad fuente;
3. no crear historia nueva si el estado comercial no cambió;
4. cerrar el periodo previo y abrir uno nuevo si cambió precio/promoción/disponibilidad u otro atributo que realmente forme parte del estado aceptado.

Ese actualizador **no se implementa hasta tener una segunda ejecución real que lo necesite**.

## Turso

El usuario ya tiene una cuenta Turso Free. La base Turso todavía no debe crearse vacía.

Primero se genera y valida el SQLite local; después el usuario lo sube mediante `Upload SQLite File`.

No generar tokens para la primera importación.

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
- filtrar por categoría/marca/disponibilidad cuando sea útil;
- mostrar precio actual;
- mostrar precio regular reportado si existe;
- mostrar promoción;
- mostrar disponibilidad.

El historial gráfico se activa cuando exista más de una observación aceptada.

## Seguridad y live

`ACTIVE_AUTHORIZATION_IDS = []` significa que no existe autorización live vigente.

La evidencia histórica no se interpreta como autorización abierta. Una autorización consumida no se reutiliza para generar tráfico nuevo.

La primera carga reutiliza exclusivamente el artifact ya obtenido. No realiza nuevas solicitudes contra La Colonia.

## Deuda técnica

El repositorio contiene trabajo histórico más complejo de BigQuery, Google Sheets, Cloudflare, provenance y otras capas. **La existencia de ese código no lo convierte en requisito del MVP**.

No hacer una limpieza masiva ahora salvo que algo bloquee el camino mínimo. Primero cerrar el MVP funcional; después se podrá eliminar deuda sin mezclarla con la entrega.
