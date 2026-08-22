# Modelo común de datos y almacenamiento

Este documento define el **modelo lógico estable**. El estado de implementación/productividad de Google Sheets, autorizaciones y último CI vive en [`PROJECT_STATE.md`](PROJECT_STATE.md).

La fase inicial del producto utiliza **Google Sheets como almacenamiento temporal estructurado**. BigQuery se incorpora después, cuando el proceso esté estable. La lógica comercial permanece backend-neutral para que esa migración no cambie las reglas de negocio.

## 1. Nomenclatura oficial

| Concepto | Nombre oficial |
|---|---|
| Precio actual | `current_price` |
| Precio regular informado | `reported_regular_price` |
| ID de ejecución | `scrape_run_id` |
| Disponibilidad | `availability` |
| Estado de ejecución | `run_status` |
| Fecha de observación | `observed_at_utc` |
| Estado de ubicación | `location_status` |
| Evidencia de ubicación | `location_evidence` |
| Confianza de ubicación | `location_confidence` |
| Versión del extractor | `extractor_version` |
| Versión del esquema | `schema_version` |

No se mantienen aliases paralelos como contrato oficial.

## 2. Capas de dominio

```text
RawProduct
-> NormalizedOffer
-> ValidatedOffer
-> decisión comercial
-> CurrentCommercialOffer / OfferHistoryPeriod
-> registros tabulares
```

### `RawProduct`

Observación fiel a la fuente. Puede contener campos faltantes si la fuente no los demuestra.

### `NormalizedOffer`

Representación común entre supermercados. La normalización no inventa marca, presentación, ubicación, precio ni promoción.

### `ValidatedOffer`

Incluye identidad derivada, `state_hash`, estado de revisión, timestamps y eventos de calidad suficientes para la frontera comercial.

## 3. Identidad

La identidad comercial separa:

- supermercado;
- ubicación;
- producto fuente;
- producto normalizado/comparable.

Reglas:

- precio/fecha/promoción/disponibilidad no forman parte de IDs estables;
- IDs derivados se recalculan en fronteras críticas y al rehidratar;
- una llave fuente no puede migrar silenciosamente a otra identidad;
- `offer_id` está ligado a supermercado + ubicación + producto fuente;
- `product_id` puede cambiar sólo por una corrección explícita del mapeo normalizado.

## 4. Ubicación

Las ofertas conservan:

```text
supermarket_id
location_id
location_status
location_evidence
location_confidence
```

La configuración de ubicación además distingue:

- ciudad visible;
- alcance;
- granularidad (`city`, `store`, `unknown`, etc.);
- binding técnico;
- `source_location_key`;
- `extraction_enabled`.

No se persisten ofertas comerciales de una ubicación que no esté habilitada por el catálogo de ubicaciones. Para una fuente con selector, el binding técnico debe estar confirmado antes de tratar el precio como perteneciente a SPS/tienda.

## 5. Estado comercial

`state_hash` representa el estado comercial relevante de una oferta y permite decidir si se mantiene el periodo abierto o existe un cambio.

Incluye, según el contrato vigente, campos como:

- `current_price`;
- `reported_regular_price`;
- promoción;
- disponibilidad;
- atributos normalizados relevantes.

Cambios cosméticos no deben crear un nuevo periodo.

## 6. Histórico

Por cada identidad de oferta existe como máximo un periodo abierto.

### Sin cambio

```text
nuevo state_hash == current.state_hash
-> current se confirma/actualiza con la nueva observación permitida
-> no se abre un segundo periodo
```

### Con cambio

```text
nuevo state_hash != current.state_hash
-> cerrar periodo anterior
-> abrir exactamente un nuevo periodo
-> actualizar current
```

El histórico registra run de apertura/cierre, timestamps y suficiente evidencia para auditar la transición.

## 7. Precio regular y reducción real

Separar siempre:

```text
current_price
reported_regular_price
previous_accepted_current_price
```

`reported_regular_price` es el precio de referencia declarado por la tienda. No demuestra ahorro real.

La reducción real se deriva de:

```text
max(previous_accepted_current_price - current_price, 0)
```

Si falta baseline aceptado o precio actual confiable, la reducción queda no derivable; no se inventa.

## 8. Estados de run

Estados terminales/operativos incluyen:

```text
running
success
warning
rejected
failed
abandoned
```

Sólo una decisión comercial aceptada puede mutar current/history.

- `running` es transitorio;
- `rejected`, `failed`, `abandoned` no mutan current/history;
- un run terminal idéntico puede reintentarse idempotentemente;
- reutilizar el mismo `scrape_run_id` con evidencia terminal divergente falla cerrado.

## 9. Tablas comunes

Todos los supermercados comparten las mismas tablas gestionadas:

```text
cfg_supermarkets
cfg_locations
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

No se crea una tabla por cadena de supermercado.

### `cfg_supermarkets`

Configuración/versionado operativo del supermercado.

### `cfg_locations`

Ubicaciones, alcance, granularidad, binding técnico y habilitación.

### `fact_offers_current`

Snapshot comercial actual por identidad de oferta.

### `fact_offer_history`

Periodos históricos abiertos/cerrados.

### `fact_scrape_runs`

Registro de toda ejecución terminal aunque no haya cambios comerciales.

### `fact_quality_events`

Eventos estructurales/de calidad ligados a run y secuencia determinista.

## 10. Rehidratación durable

Un runner nuevo debe poder reconstruir current/history a partir del backend.

La representación tabular conserva lo necesario para revalidar:

- identidad fuente/normalizada;
- `state_hash`;
- precios/promoción/disponibilidad;
- ubicación/evidencia;
- run de origen/apertura/cierre;
- versiones extractor/schema;
- review/pending/quality metadata;
- cronología y contigüidad.

La rehidratación recalcula IDs/hash y rechaza:

- gaps/overlaps;
- múltiples periodos abiertos;
- periodo cerrado sin run de cierre;
- current que no coincide con el periodo abierto;
- evidencia temporal incoherente.

`raw_values` voluminoso no forma parte del snapshot durable cuando no participa en identidad/hash/transición.

## 11. Atomicidad

La frontera comercial produce un `TabularBatch` completo antes de escribir.

`InMemoryTabularStore` actúa como referencia de semántica:

- preflight antes de commit;
- upsert de configuración/current/history;
- runs/calidad inmutables;
- replay idéntico permitido;
- divergencia rechazada;
- conflicto tardío revierte el batch completo.

El adapter real debe preservar esa semántica.

## 12. Google Sheets

Google Sheets es el backend temporal de la primera fase, no la lógica de negocio.

El adapter:

1. lee metadata y tablas gestionadas existentes;
2. reconstruye el store local;
3. valida header/ancho/tipos/PK/duplicados;
4. aplica el `TabularBatch` localmente;
5. materializa el snapshot final completo mediante un único plan de workbook.

Pestañas ajenas al proyecto se preservan.

El plan usa `spreadsheets.batchUpdate` y escribe strings como `stringValue` para evitar interpretación accidental como fórmulas.

## 13. Seguridad del transporte Sheets

El transporte productivo previsto:

- recibe un `spreadsheet_id` opaco, no URL arbitraria;
- usa endpoint fijo de Google Sheets v4;
- service account con scope mínimo de Sheets;
- no usa Google Drive para la operación normal;
- no sigue redirects;
- timeouts acotados;
- errores sanitizados;
- nunca refleja private key/body de credenciales.

La configuración externa exacta y su estado se mantienen en `PROJECT_STATE.md`.

## 14. Dataset para Power BI

La persistencia debe permitir derivar como mínimo:

- producto;
- marca;
- presentación;
- categoría/subcategoría cuando exista;
- supermercado;
- ubicación comercial;
- precio actual;
- precio histórico previo;
- precio regular/referencia declarado;
- promoción;
- disponibilidad;
- fecha de observación;
- periodos/cambios;
- reducción real.

Power BI consume datos aceptados/persistidos. No decide identidad, ubicación, completitud ni autoridad.

## 15. Evolución a BigQuery

Cuando el flujo esté estable, BigQuery puede sustituir/acompañar Google Sheets como backend durable/analítico.

La migración debe conservar:

- IDs;
- semántica current/history;
- reglas de replay;
- run log completo;
- quality events;
- timestamps UTC;
- evidencia de ubicación;
- autoridad de catálogo upstream.

No se cambian reglas comerciales sólo por cambiar el backend.
