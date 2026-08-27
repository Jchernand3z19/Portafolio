# Arquitectura — Precios de Supermercados SPS

Este documento describe la **arquitectura estable**. El estado operativo mutable, autorizaciones y evidencia concreta viven en [`PROJECT_STATE.md`](PROJECT_STATE.md).

No uses PRs históricos, ramas o este documento para inferir autorización live.

## 1. Objetivo

Construir una plataforma que recolecte precios e inventario observado de supermercados, normalice la información a un contrato común, valide identidad/calidad/completitud, conserve historia consultable y sirva una aplicación web **Python Dash + Plotly**.

Alcance inicial: **San Pedro Sula, un supermercado a la vez**. La Colonia debe quedar end-to-end antes de iniciar supermercado #2.

Principios:

1. la fuente manda; no se inventan atributos, disponibilidad ni ubicación;
2. contexto fuente y ubicación comercial son conceptos distintos;
3. corrección técnica no equivale a autoridad productiva;
4. toda ambigüedad crítica falla cerrada;
5. identidad estable no depende de precio, disponibilidad ni fecha;
6. todo run terminal se registra;
7. un mismo esquema sirve a todos los supermercados;
8. lógica comercial independiente del backend;
9. BigQuery es el único backend persistente activo;
10. Dash + Plotly es la capa de consumo seleccionada;
11. una tabla nueva requiere grain, key, lifecycle y consumidor reales;
12. persistir evidencia histórica y habilitar tráfico futuro son permisos distintos.

## 2. Flujo principal

```text
Fuente
  ↓
Extractor específico
  ↓
RawProduct
  ↓
Normalización específica + reglas/overrides
  ↓
NormalizedOffer
  ↓
Validación + identidad + state_hash
  ↓
ValidatedOffer
  ↓
Completitud técnica + provenance verificada
  ↓
Atestación de autoridad comercial + política específica de fuente
  ↓
Verified commercial authority + crev1_* bound evidence
  ↓
Motor backend-neutral de current/history + replay
  ↓
BigQueryWritePlan
  ↓
Storage port
  ↓
BigQueryAdapter
  ├─ FakeBigQueryClient          [offline]
  └─ GoogleCloudBigQueryClient   [cloud]
  ↓
BigQuery
  ↓
Views de estado actual / variaciones
  ↓
Python Dash + Plotly
```

El dominio no importa el SDK de Google. El fake prueba contrato, bootstrap, primera carga simulada, replay, conflictos, rollback y read-back sin red. El cliente Google Cloud sólo implementa el port.

## 3. Contratos protegidos

### `RawProduct`
Observación fiel a la fuente. Conserva únicamente lo que el extractor pudo demostrar.

### `NormalizedOffer`
Forma común entre supermercados. Normalizar no significa completar información inexistente.

### `ValidatedOffer`
Oferta normalizada que pasó validaciones y contiene `state_hash`, estado de revisión y quality events.

### `VerifiedLaColoniaCommercialAuthority`
Capability productiva específica de fuente. Sólo existe después de verificar una atestación Ed25519 y reconciliarla con readiness técnica y provenance exactas. No acepta `catalog_accepted` como booleano libre.

Estos contratos sólo cambian cuando exista una necesidad demostrada, compatibilidad y pruebas.

## 4. Identidad

```text
source_product_id = identidad estable dentro de la fuente
product_id        = identidad comparable entre fuentes
offer_id          = supermercado + ubicación comercial + producto fuente
```

Precio, promoción, disponibilidad y fecha nunca forman parte de los IDs estables.

GTIN-8/12/13/14 sólo puede producir identidad cross-source cuando supera check digit y se normaliza a GTIN-14. Sin identidad fuerte se conserva `prod_pending_*`; la observación no se descarta.

La ciudad pertenece a `locations` y a la observación mediante `location_id`; no se duplica dentro de `productos`.

## 5. Producto y presentación

Se conservan por separado valores fuente y normalizados. La presentación estructurada usa sólo atributos demostrables. Overrides revisados deben ligarse a `source_product_id + source_signature` para no reutilizar una corrección cuando cambie la evidencia fuente.

## 6. Ubicación

Se distinguen:

- **source location context**: contexto raw del payload;
- **commercial location**: ciudad/tienda demostrada a la que puede atribuirse una observación.

Para La Colonia:

```text
la_colonia_online = contexto fuente raw; no es ciudad ni tienda
la_colonia_sps    = ubicación comercial SPS con binding técnico confirmado
la_colonia_tgu    = ubicación conocida fuera del alcance inicial
```

La existencia del binding técnico no activa por sí sola extracción productiva ni concede autorización live.

`extraction_enabled` es un gate de **contacto futuro con la fuente**. No invalida automáticamente una evidencia histórica ya obtenida. El preparador comercial genérico continúa exigiendo ese flag; una capability privada y auditada permite serializar un snapshot con extracción apagada sólo después de una autoridad comercial tipada. Esa serialización nunca modifica el catálogo original ni persiste `extraction_enabled=true`.

## 7. Precio

```text
current_price          = precio efectivo observado
reported_regular_price = precio regular/tachado declarado por la tienda
previous_price         = derivado de una observación histórica aceptada anterior
```

`reported_regular_price` nunca sustituye a `previous_price`. El ahorro real compara observaciones aceptadas de `current_price`.

## 8. Inventario observado

La proyección física admite:

```text
available_quantity_observed
availability
availability_evidence
seller_id
quantity_is_exact
observed_at_utc
scrape_run_id
```

El snapshot disponible no demuestra cantidad/seller/evidencia completos. Por tanto esos valores permanecen `NULL` cuando falta respaldo y `unknown` permanece `unknown`. No se infiere `out_of_stock`.

## 9. Current/history backend-neutral vs historia BigQuery

Son dos representaciones deliberadamente distintas:

```text
motor Python current/history = periodos y transición comercial
BigQuery                     = observaciones analíticas por run aceptado
```

Un run con precio idéntico confirma el periodo Python sin abrir uno nuevo, pero agrega una observación BigQuery. Un cambio real abre/cierra periodos Python y agrega su observación BigQuery. Los tests reconcilian ambas capas.

## 10. Autoridad comercial

Provenance física, completitud técnica y aceptación comercial son tres estados diferentes.

```text
verified provenance
        +
technical readiness
        +
signed commercial authority attestation
        ↓
source-specific authority policy
        ↓
VerifiedLaColoniaCommercialAuthority
```

La atestación comercial usa una raíz Ed25519 separada del receipt del collector porque responde a una pregunta distinta: el receipt demuestra **qué request/response ocurrió**; la autoridad comercial decide **si esa evidencia puede promoverse a estado comercial**.

`CommercialAuthorityClaims` liga como mínimo supermercado, ubicación, run, autorización fuente, status final, instante de decisión y los digests de discovery, plan autenticado y manifest. La verificación criptográfica por sí sola mantiene `production_authority=false` y `catalog_accepted=false`.

La política de La Colonia promueve únicamente cuando:

- `technical_catalog_complete=true`;
- la readiness está explícitamente lista para recibir evidencia autoritativa;
- readiness y provenance comparten el manifest exacto;
- la firma pertenece al keyring comercial confiable;
- todos los IDs/digests coinciden exactamente;
- la decisión no antecede la evidencia física.

Después de la promoción, `derive_bound_run_evidence_id` produce `crev1_*` sobre autoridad + decisión + ofertas + métricas + quality events. BigQuery vuelve a exigir ese binding para cualquier run que intente mutar estado comercial.

Los tests de auditoría restringen tanto el derivador `crev1_*` como la capability privada de snapshot a la política verificada de La Colonia. Scripts y workflows no pueden saltarse esa frontera.

## 11. BigQuery — contrato físico cerrado

El contrato ejecutable vive en `src/precios_supermercados/bigquery_contract.py` y su proyección en `bigquery_persistence.py`.

Tablas:

```text
supermarkets
locations
productos
precios_historicos
inventario_historico
scrape_runs
quality_events
normalization_overrides
product_mapping
```

Grain, logical key, null semantics, partición y clustering exactos están documentados en [`modelo-datos.md`](modelo-datos.md) y validados por tests.

Particiones iniciales:

```text
precios_historicos     DATE(observed_at_utc)
inventario_historico   DATE(observed_at_utc)
scrape_runs            DATE(started_at_utc)
quality_events         DATE(observed_at_utc)
```

Precio/inventario clusterizan por `supermarket_id`, `location_id`, `source_product_id`. BigQuery conserva una observación por run comercial aceptado aunque el valor no cambie.

### Atomicidad e idempotencia

`BigQueryAdapter` verifica el `run_fingerprint` antes de escribir. El mismo run/fingerprint es no-op; reutilizar el mismo `scrape_run_id` con plan diferente falla cerrado.

El cliente Google Cloud materializa primero staging efímero y luego ejecuta todas las mutaciones destino en una única transacción BigQuery. Conflictos en hechos inmutables producen un error dentro de una sentencia `SELECT`, de modo que la transacción se revierte. Dimensiones/mapping se resuelven mediante `MERGE`.

El adapter **no crea proyectos ni datasets**. Esa acción está fuera del dominio y marca la frontera cloud/humana de la primera carga durable.

## 12. Google Sheets legado

Google Sheets queda **retirado como backend productivo**.

- `storage_contract.py` declara únicamente BigQuery como backend activo;
- planner/adapter/bootstrap de Sheets permanecen sólo como evidencia/compatibilidad y están ligados a constantes `LEGACY_SHEETS_*`;
- el workflow histórico conserva su estructura de auditoría pero preflight emite siempre `allowed=false`;
- el job que porta credenciales permanece condicionado a `allowed == 'true'`, por lo que no puede ejecutar;
- no se añade funcionalidad nueva ni se solicitan nuevas credenciales de Sheets.

## 13. Product mapping

`product_mapping` conserva la relación `source product -> canonical product`. GTIN válido puede resolverla automáticamente; sin identidad fuerte se conserva estado `pending`/singleton. Su valor cross-source crecerá con supermercado #2, pero la tabla ya tiene consumidor y lifecycle claros.

## 14. Normalization overrides

Git/versionado sigue siendo la fuente confiable de reglas durante el MVP. BigQuery materializa sólo excepciones explícitas y auditables; no se crea una fila por producto. `source_signature` evita reutilización silenciosa después de un cambio fuente.

## 15. Runs y quality events

Todo run terminal se registra aunque no cambie precio/inventario. Runs rechazados/fallidos no contaminan productos, precios, inventario ni mapping comerciales. Hashes/fingerprints demuestran igualdad, no autoridad.

## 16. Cloudflare / provenance

La ruta edge existente conserva allowlists, OIDC, presupuesto/pacing, single-flight, replay/fencing, receipts y Observability. Su existencia no concede autoridad comercial ni autorización live.

La evidencia live ya obtenida se reutiliza offline. Una observación nueva de La Colonia requiere autorización humana vigente.

## 17. Automatización diaria

Sólo se habilita después de demostrar binding, completitud, normalización/validación, primera persistencia BigQuery durable recuperable, inventario suficiente y manejo de runs rechazados sin contaminación.

Los fallos no borran el último estado confiable.

## 18. Dash + Plotly

Dash consumirá views de BigQuery; no redefinirá reglas de negocio. Las primeras views previstas son `vw_precios_actuales`, `vw_inventario_actual` y `vw_ofertas_actuales`, con derivaciones de precio anterior, cambio y ahorro real.

Power BI queda legado; no se añade funcionalidad nueva a esa ruta.

## 19. GitHub y CI

Todo cambio sigue:

```text
audit main/PRs
-> rama
-> cambio mínimo
-> suite completa
-> PR
-> diff + CI + reviews/threads
-> merge con expected head SHA
```

Los workflows mantienen mínimo privilegio, pins SHA completos y entrypoints live fail-closed.

## 20. Orden actual

```text
CATÁLOGO LA COLONIA                    [DONE]
NORMALIZACIÓN PRODUCTOS                [DONE]
CURRENT/HISTORY + REPLAY OFFLINE       [DONE]
COMMERCIAL AUTHORITY CONTRACT          [DONE OFFLINE]
AUTHORITY → BIGQUERY FAKE              [DONE OFFLINE]
BIGQUERY CONTRACT                      [DONE OFFLINE]
BIGQUERY ADAPTER / FAKE / BOOTSTRAP    [DONE OFFLINE]
REPLAY / PARTIAL FAILURE / READ-BACK   [DONE OFFLINE]
GOOGLE SHEETS PRODUCTIVE PATH          [RETIRED]
PRODUCTION AUTHORITY ATTESTATION       [HUMAN TRUST BOUNDARY]
FIRST DURABLE LOAD                     [CLOUD/HUMAN BOUNDARY]
INVENTORY FIRST-CLASS                  [PENDING]
DAILY AUTOMATION                       [PENDING]
DASH + PLOTLY                          [PENDING]
TEGUCIGALPA                            [PENDING]
SUPERMARKET #2                         [PENDING]
```
