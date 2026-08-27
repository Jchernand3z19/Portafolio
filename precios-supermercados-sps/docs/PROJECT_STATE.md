# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. La arquitectura estable vive en [`arquitectura.md`](arquitectura.md), el modelo físico en [`modelo-datos.md`](modelo-datos.md) y las decisiones técnicas en [`decisiones-tecnicas.md`](decisiones-tecnicas.md).

GitHub sigue siendo la fuente de verdad para `main`, SHA, PRs y CI. Este archivo no duplica esos valores transitorios para no quedar obsoleto al fusionar el mismo cambio que lo actualiza.

## Corte actual

Estado verificado al **2026-08-27 UTC**:

```text
SPS_TECHNICAL_CONTEXT = CONFIRMED
location_id = la_colonia_sps
granularity = city
technical_binding_confirmed = true
full_catalog_validation_passed = true
full_crawl = true
catalog_products_reported = 9437
unique_products_extracted = 9437
skus_extracted = 9439
skus_with_price = 9439
products_normalized = 9439 / 9439
presentation_normalized = 8436
presentation_pending = 1003
gtin_mapping_ready = 8965
product_mapping_pending = 474
history_change_integration = verified_offline
tabular_rehydrate_restore_cycle = verified_offline
persistent_backend_selected = turso
turso_sqlite_contract = verified_offline
turso_adapter = verified_offline
turso_bootstrap = verified_offline
turso_transactions_rollback = verified_offline
turso_replay = verified_offline
turso_read_back_rehydrate = verified_offline
initial_snapshot_loader = verified_offline
initial_snapshot_turso_plan = verified_offline
initial_snapshot_9439_sqlite_integration = verified_with_synthetic_full_shape
initial_snapshot_exact_sqlite_preflight = prepared_for_first_load
first_durable_turso_load = false
bigquery_productive_path = retired_fail_closed
bigquery_implementation = legacy_preserved
google_sheets_selected = false
google_sheets_productive_path = retired_fail_closed
google_sheets_writes = false
initial_snapshot_approved = true
initial_snapshot_run_id = 32922877781
initial_snapshot_artifact_id = 9590684834
initial_snapshot_preserved_artifact_id = 9655225996
commercial_persistence = pending_turso_credentials_and_first_load
extraction_enabled = false
ACTIVE_AUTHORIZATION_IDS = []
```

`ACTIVE_AUTHORIZATION_IDS = []` significa que no existe autorización live vigente. La evidencia histórica **no se interpreta como autorización abierta**. Cualquier nuevo tráfico contra La Colonia requiere autorización humana explícita vigente; una autorización anterior consumida no se reutiliza.

`extraction_enabled=false` controla tráfico futuro. No invalida por sí mismo un artifact histórico que ya fue obtenido, validado y aprobado para una carga concreta.

## One-shot full catalog — consumido

La autorización humana para obtener una vez el catálogo completo read-only de La Colonia San Pedro Sula terminó correctamente en el intento #15.

```text
authorization_mode = one_time_full_catalog_after_staged_validation
authorized_at_utc = 2026-08-25T21:13:44Z
termination_condition = first_successful_downloadable_full_sps_catalog
termination_condition_met = true
attempt_sequence = 15
active = false
```

Fingerprint técnico SPS preservado:

```text
sps_region_fingerprint = d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
```

No se persisten cookies, `regionId` raw, sesión, headers ni URLs sensibles.

## Catálogo completo — snapshot inicial aprobado

Evidencia del intento #15:

```text
run_id = 32922877781
artifact_id = 9590684834
artifact_name = la-colonia-sps-data-32922877781
artifact_digest = sha256:0427e88be27df89fd9fcb50ed600ef5c6aef64177bfba92b4af3d2e25756a892
full_catalog_json_sha256 = 2780eeffa5ef62f2d1c8c2c8365e88da1ca0006622d2f7b1c3529f834c9b5e50
source_commit = 589b694fdc75fd97d47fcc5259062fb026cf7ee4
result = success
catalog_complete = true
validation_passed = true
catalog_product_coverage = 1.0
location_verified_same_run = true
catalog_products_reported = 9437
unique_products_extracted = 9437
skus_extracted = 9439
skus_with_price = 9439
skus_without_price = 0
partitions_detected = 62
partitions_completed = 62
product_requests_completed = 252
```

La diferencia 9,439 SKU vs 9,437 `productId` es válida: 9,435 productos tienen un SKU y 2 productos tienen dos SKU. Las 9,439 identidades fuente son únicas.

El snapshot exacto fue aprobado como primera carga mediante decisión versionada. El loader valida el SHA-256 de `full-catalog.json` **antes** de interpretar filas y luego revalida metadata, ubicación y conteos. No acepta otro archivo por similitud de datos.

Una copia byte-equivalente del artifact original quedó preservada como artifact `9655225996`; su ZIP conserva el mismo SHA-256. La primera carga Turso usa esa evidencia existente y no vuelve a consultar La Colonia.

La aprobación no autoriza nuevas consultas a La Colonia, no sirve para otro snapshot y no crea una infraestructura general de autoridad.

## Productos y normalización

```text
sku_input = 9439
source_keys_unique = 9439
normalized_offers = 9439
presentation_normalized = 8436
presentation_pending = 1003
gtin_mapping_ready = 8965
product_mapping_pending = 474
source_values_preserved = true
versioned_overrides = true
normalization_before_state_hash = true
```

Las 1,003 presentaciones pendientes no se inventan: permanecen con campos normalizados incompletos y `needs_review`. Los 474 SKU sin GTIN válido conservan `prod_pending_*` y mapping pendiente. Esto no impide conservar sus precios y disponibilidad con identidad fuente estable.

La fuente original permanece separada de valores normalizados. Overrides manuales se ligan a `source_product_id + source_signature`; si cambia la evidencia fuente el override anterior no se reutiliza silenciosamente.

## Historial comercial — verificado offline

El motor backend-neutral y el adapter Turso verifican:

- primera observación crea `offers_current` y un periodo inicial;
- observación idéntica posterior actualiza/confirmar current sin crear un periodo histórico redundante;
- cada ejecución terminal crea su registro en `scrape_runs`;
- cambio real de estado comercial cierra el periodo anterior y abre uno nuevo;
- replay exacto es idempotente;
- el mismo `scrape_run_id` con fingerprint divergente falla cerrado;
- rehidratación permite continuar en un proceso nuevo;
- fallo parcial dentro de la transacción revierte todas las mutaciones del run;
- run rechazado registra ledger/evidencia permitida pero no muta estado comercial.

`extraction_enabled` no es permiso de persistencia. El snapshot histórico aprobado puede persistirse manteniendo ese switch en `false`; todos los demás gates de ubicación y evidencia siguen vigentes.

## Turso / SQLite — backend operativo activo

El contrato físico activo vive en `turso_contract.py` y la persistencia en `turso_persistence.py`.

Tablas:

```text
supermarkets
locations
products
source_products
offers_current
offer_history
scrape_runs
quality_events
normalization_overrides
```

Características ya implementadas y cubiertas offline:

```text
STRICT tables
foreign_keys = ON
schema_version = 1
constraints e índices críticos
transacción por run
rollback completo
current/history
read-back
rehydrate
exact replay
replay conflictivo fail-closed
precios en minor units/centavos
runs rechazados sin mutación comercial
quality events
SQLite :memory: como motor real de pruebas
```

La ruta completa de 9,439 filas se prueba sobre SQLite real con un snapshot sintético de forma completa y determinista. Además existe una prueba de integración que exige el archivo aprobado exacto mediante `PRECIOS_SPS_APPROVED_SNAPSHOT_JSON`; el workflow de primera carga la ejecuta sobre el artifact preservado **antes** de intentar la conexión remota.

La primera carga durable todavía no se ha ejecutado. La frontera pendiente es crear/configurar la base Turso y proporcionar al workflow, mediante GitHub Actions Secrets, las credenciales esperadas por el driver:

```text
TURSO_DATABASE_URL
TURSO_AUTH_TOKEN
```

Ninguno de esos valores debe guardarse en Git, documentación o chat.

## BigQuery — implementación preservada, ruta productiva retirada

El trabajo BigQuery previo no se destruye: contrato, adapter, fake client, bootstrap GCP y pruebas legadas permanecen como implementación histórica/futura.

Sin embargo:

```text
ACTIVE_STORAGE_BACKEND = turso
bigquery_productive_path = retired_fail_closed
first_durable_bigquery_load = false
```

El workflow `.github/workflows/precios-supermercados-sps-bigquery-first-load.yml` está hard fail-closed y ya no solicita OIDC ni configuración GCP. Reactivarlo requeriría una decisión explícita futura y un nuevo cambio versionado.

## Google Sheets — retirado

Google Sheets no forma parte del camino objetivo.

- planner/adapter/bootstrap se conservan sólo como evidencia/compatibilidad histórica;
- el workflow `.github/workflows/precios-supermercados-sps-google-sheets-storage.yml` conserva auditoría histórica pero su preflight emite siempre `allowed=false`;
- no se añadirá funcionalidad nueva ni se solicitarán credenciales nuevas para Sheets.

## Precio

```text
current_price          = precio efectivo observado
reported_regular_price = precio regular/tachado declarado por la tienda
previous_price         = current_price del periodo histórico aceptado anterior
```

`reported_regular_price` nunca sustituye a `previous_price`. El ahorro real compara el `current_price` actual contra el del periodo histórico aceptado inmediatamente anterior. Si no existe baseline, no se inventa ahorro.

## Disponibilidad e inventario

El artifact #15 conserva:

```text
availability_in_stock = 7081
availability_unknown = 2358
```

Los 2,358 `unknown` permanecen `unknown`. El snapshot no preservó evidencia suficiente para `available_quantity_observed`, `availability_evidence` y `seller_id`; esos campos quedan `NULL` y `quantity_is_exact=false`.

Completar inventario de primera clase probablemente requerirá una observación live futura. Cuando se llegue a esa frontera se deberá pedir autorización humana nueva indicando alcance, número aproximado de peticiones y evidencia buscada.

## Workflow de primera carga Turso

`.github/workflows/precios-supermercados-sps-turso-first-load.yml` está preparado como `workflow_dispatch` manual y sólo permite el run desde `main` del repositorio canónico con confirmación booleana explícita.

El flujo previsto es:

```text
artifact preservado exacto
-> verificar SHA-256 del ZIP
-> verificar file set
-> verificar SHA-256 del JSON
-> instalar dependencias fijadas
-> integración exacta 9439 SKU sobre SQLite real
-> validar presencia de secrets Turso sin imprimirlos
-> CLI cargar_snapshot_inicial_turso.py --apply
-> bootstrap + transacción Turso
-> read-back + rehydrate + reconciliación
```

No contiene crawler, no llama a La Colonia y no está programado diariamente.

## Visualización

Dash + Plotly permanece como destino futuro, pero **no es prioridad todavía**. Antes deben existir persistencia Turso real, inventario suficientemente sustentado, ejecución diaria estable y varias ejecuciones consecutivas verificadas.

## Frontera del producto

```text
SOURCE                                  [DONE]
SPS CONTEXT                             [DONE]
FULL CATALOG                            [DONE]
COMPLETENESS / TECHNICAL ACCEPTANCE     [DONE]
PRODUCT NORMALIZATION                   [DONE WITH REVIEW QUEUE]
CURRENT / HISTORY SEMANTICS             [DONE OFFLINE]
REHYDRATE / REPLAY                      [DONE OFFLINE]
TURSO / SQLITE CONTRACT                 [DONE OFFLINE]
TURSO TRANSACTION / ROLLBACK            [DONE OFFLINE]
TURSO CURRENT/HISTORY/REHYDRATE         [DONE OFFLINE]
INITIAL SNAPSHOT APPROVAL               [DONE OFFLINE]
INITIAL SNAPSHOT -> TURSO PLAN          [DONE OFFLINE]
FULL 9439 SQLITE SYNTHETIC INTEGRATION  [DONE OFFLINE]
EXACT ARTIFACT SQLITE PREFLIGHT         [PREPARED — RUNS BEFORE FIRST LOAD]
BIGQUERY PRODUCTIVE PATH                [RETIRED]
GOOGLE SHEETS PRODUCTIVE PATH           [RETIRED]
FIRST DURABLE TURSO LOAD                [NEXT — HUMAN CREDENTIAL BOUNDARY]
INVENTORY EVIDENCE / HISTORY            [PENDING]
DAILY AUTOMATION                        [PENDING]
CONSECUTIVE RUN VALIDATION              [PENDING]
DASH + PLOTLY                           [PENDING AFTER LA COLONIA E2E]
TEGUCIGALPA                             [PENDING]
SUPERMARKET #2                          [PENDING]
```

## Próximo paso exacto — frontera humana Turso

No crear cuentas, bases o secretos externos por inferencia.

Cuando CI y revisión del cambio Turso estén cerrados, el siguiente paso productivo es:

1. crear/seleccionar una base Turso;
2. generar un token de acceso para esa base;
3. guardar `TURSO_DATABASE_URL` y `TURSO_AUTH_TOKEN` directamente como GitHub Actions Secrets del repositorio;
4. ejecutar manualmente el workflow de primera carga desde `main` con `apply_initial_snapshot=true`;
5. verificar el read-back/reconciliación antes de conectar futuras ejecuciones.

La primera carga no necesita ni autoriza una nueva consulta a La Colonia.
