# Arquitectura — Precios de Supermercados SPS

Este documento describe la **arquitectura estable**. El estado operativo mutable, autorizaciones y evidencia concreta viven en [`PROJECT_STATE.md`](PROJECT_STATE.md).

No uses PRs históricos, ramas o este documento para inferir autorización live.

## 1. Objetivo

Construir una plataforma que recolecte precios e inventario observado de supermercados, normalice la información a un contrato común, valide identidad/calidad/completitud, conserve historia consultable y posteriormente sirva una aplicación web **Python Dash + Plotly**.

Alcance inicial: **San Pedro Sula, un supermercado a la vez**. La Colonia debe quedar end-to-end antes de iniciar supermercado #2.

Principios:

1. la fuente manda; no se inventan atributos, disponibilidad ni ubicación;
2. contexto fuente y ubicación comercial son conceptos distintos;
3. completitud técnica no equivale por sí sola a aprobación de un snapshot;
4. toda ambigüedad crítica falla cerrada;
5. identidad estable no depende de precio, disponibilidad ni fecha;
6. todo run terminal se registra;
7. un mismo esquema sirve a todos los supermercados;
8. lógica comercial independiente del backend;
9. Turso es el backend persistente operativo y SQLite `:memory:` ejecuta el mismo contrato en pruebas offline;
10. BigQuery queda preservado como implementación legada/futura, no como ruta productiva activa;
11. Google Sheets permanece retirado/fail-closed;
12. Dash + Plotly se desarrolla sólo después de cerrar La Colonia end-to-end;
13. una tabla nueva requiere grain, key, lifecycle y consumidor reales;
14. durante el MVP se prefiere la solución mínima con consumidor actual sobre una plataforma genérica futura.

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
Completitud + aprobación versionada cuando corresponda
  ↓
Motor backend-neutral de current/history + replay
  ↓
TursoWritePlan
  ↓
TursoAdapter
  ├─ sqlite3 :memory:      [offline]
  └─ turso_serverless      [remoto]
  ↓
Turso / SQLite
  ↓
queries de estado actual / historial
  ↓
Python Dash + Plotly       [después de La Colonia E2E]
```

El dominio no depende del driver remoto. El mismo contrato físico se ejecuta sobre SQLite real para bootstrap, transacciones, replay, rollback, read-back y rehidratación antes de usar Turso remoto.

Para el primer snapshot de La Colonia, la aprobación es una decisión versionada y específica del artifact conocido; no constituye un subsistema general de autoridad ni habilita extracción futura.

## 3. Contratos protegidos

### `RawProduct`
Observación fiel a la fuente. Conserva únicamente lo que el extractor pudo demostrar.

### `NormalizedOffer`
Forma común entre supermercados. Normalizar no significa completar información inexistente.

### `ValidatedOffer`
Oferta normalizada que pasó validaciones y contiene `state_hash`, estado de revisión y quality events.

Estos contratos sólo cambian cuando exista una necesidad demostrada, compatibilidad y pruebas.

## 4. Identidad

```text
source_product_id = identidad estable dentro de la fuente
product_id        = identidad comparable entre fuentes
offer_id          = supermercado + ubicación comercial + producto fuente
```

Precio, promoción, disponibilidad y fecha nunca forman parte de los IDs estables.

GTIN-8/12/13/14 sólo puede producir identidad cross-source cuando supera check digit y se normaliza a GTIN-14. Sin identidad fuerte se conserva `prod_pending_*`; la observación no se descarta.

La ciudad pertenece a `locations` y a la oferta mediante `location_id`; no se duplica dentro de `products` ni `source_products`.

## 5. Producto y presentación

Se conservan por separado valores fuente y normalizados. La presentación estructurada usa sólo atributos demostrables. Overrides revisados deben ligarse a `source_product_id + source_signature` para no reutilizar una corrección cuando cambie la evidencia fuente.

Los pendientes de presentación o mapping no bloquean la persistencia de la observación fuente; permanecen explícitos como `needs_review`/`pending`.

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

La existencia del binding técnico no activa por sí sola extracción ni concede autorización live. `extraction_enabled` controla tráfico futuro y no se reutiliza como gate para invalidar evidencia histórica ya obtenida.

## 7. Precio

```text
current_price          = precio efectivo observado
reported_regular_price = precio regular/tachado declarado por la tienda
previous_price         = current_price del periodo histórico aceptado anterior
```

`reported_regular_price` nunca sustituye a `previous_price`. El ahorro real compara periodos aceptados de `current_price`.

Turso conserva además `current_price_minor` y `reported_regular_price_minor` como enteros en centavos HNL. Es una representación física complementaria; no cambia la semántica de dominio.

## 8. Inventario observado

El contrato físico admite:

```text
available_quantity_observed
availability
availability_evidence
seller_id
quantity_is_exact
observed_at_utc
scrape_run_id
```

El snapshot disponible no demuestra cantidad/seller/evidencia completos. Por tanto esos valores permanecen `NULL`, `quantity_is_exact=false` y `unknown` permanece `unknown`. No se infiere `out_of_stock`.

## 9. Current/history backend-neutral y persistencia Turso

El motor Python define la transición comercial; Turso materializa ese resultado durable:

```text
motor Python current/history
        ↓
offers_current = último estado aceptado
offer_history  = periodos de cambios reales
scrape_runs    = una fila por ejecución terminal
```

Una ejecución idéntica posterior:

```text
crea scrape_runs
actualiza/confirma offers_current
NO crea un nuevo periodo histórico
```

Un cambio comercial real cierra el periodo abierto y crea uno nuevo. El mismo `scrape_run_id` y fingerprint es replay exacto/no-op; reutilizar el ID con un fingerprint diferente falla cerrado.

## 10. Turso / SQLite — contrato físico activo

El contrato ejecutable vive en `src/precios_supermercados/turso_contract.py`; la proyección y adapter en `turso_persistence.py`.

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

Propiedades físicas:

- tablas `STRICT`;
- foreign keys activadas;
- constraints y unique keys explícitas;
- índices para scope/current/history/runs;
- `_schema_version` y migraciones incrementales;
- transacción por plan/run;
- rollback completo ante fallo parcial;
- read-back + rehydrate;
- replay exacto y conflicto divergente fail-closed.

SQLite `:memory:` no es un fake: ejecuta el SQL real del contrato. El remoto usa el mismo port DB-API mediante `turso_serverless`.

### Primera carga

La primera carga sólo acepta el snapshot aprobado exacto:

```text
artifact preservado
-> SHA-256 ZIP
-> file set exacto
-> SHA-256 JSON
-> metadata/conteos
-> loader + normalización
-> commercial persistence
-> TursoWritePlan
-> SQLite real preflight 9439 SKU
-> conexión Turso
-> bootstrap + apply transaccional
-> read-back + rehydrate + reconciliación
```

El preflight no consulta La Colonia. La conexión remota usa exclusivamente `TURSO_DATABASE_URL` y `TURSO_AUTH_TOKEN` inyectados como GitHub Actions Secrets.

## 11. BigQuery legado/futuro

El contrato BigQuery, adapters, fake client, bootstrap GCP y pruebas se conservan porque representan trabajo útil y pueden servir en una etapa analítica futura.

No obstante:

- `storage_contract.py` declara Turso como backend activo;
- el workflow productivo de primera carga BigQuery está hard fail-closed;
- no se solicita OIDC GCP ni se ejecuta DML BigQuery desde la ruta normal;
- reactivar BigQuery requiere una decisión futura explícita y versionada.

La persistencia Turso no intenta imitar el modelo de observación completa por run de BigQuery: para el MVP evita snapshots históricos redundantes cuando el estado comercial no cambia.

## 12. Google Sheets legado

Google Sheets queda retirado como backend productivo.

- planner/adapter/bootstrap permanecen sólo como evidencia/compatibilidad;
- el workflow histórico conserva su estructura de auditoría pero su preflight emite siempre `allowed=false`;
- no se añade funcionalidad nueva ni se solicitan credenciales de Sheets.

## 13. Product mapping

`source_products.product_id` conserva la relación fuente -> producto canónico. GTIN válido puede resolverla automáticamente; sin identidad fuerte queda `mapping_status=pending` con identidad `prod_pending_*`.

No se hace fuzzy matching automático entre supermercados. La decisión cross-source sólo se ampliará cuando exista supermercado #2 y evidencia suficiente.

## 14. Normalization overrides

Git/versionado sigue siendo la fuente confiable de reglas durante el MVP. Turso materializa sólo excepciones explícitas/auditables cuando existan. `source_signature` evita reutilización silenciosa después de un cambio fuente.

## 15. Runs y quality events

Todo run terminal se registra aunque no cambie precio/inventario. Runs rechazados/fallidos no contaminan `offers_current` ni `offer_history`. Hashes/fingerprints demuestran igualdad y replay; no aprueban por sí solos un snapshot nuevo.

## 16. Cloudflare / provenance live

La ruta edge existente conserva allowlists, OIDC, presupuesto/pacing, single-flight, replay/fencing, receipts y Observability para tráfico live autorizado. No se amplía ni se convierte en requisito de la carga histórica inicial.

La evidencia live ya obtenida se reutiliza offline. Una observación nueva de La Colonia requiere autorización humana vigente.

## 17. Automatización diaria

Sólo se habilita después de demostrar:

1. primera persistencia Turso durable y recuperable;
2. read-back/reconciliación correcta;
3. conexión de futuras ejecuciones aceptadas a Turso;
4. inventario suficientemente sustentado;
5. runs rechazados sin contaminación;
6. varias ejecuciones consecutivas correctas.

Los fallos no borran el último estado confiable.

## 18. Dash + Plotly

Dash queda después del cierre técnico end-to-end de La Colonia. Consumirá datos persistidos/validados y no redefinirá reglas de negocio.

Power BI permanece legado; no se añade funcionalidad nueva a esa ruta.

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

Los workflows mantienen mínimo privilegio, pins SHA completos y entrypoints live fail-closed. La primera carga Turso es `workflow_dispatch` manual; no tiene `schedule`.

## 20. Orden actual

```text
CATÁLOGO LA COLONIA                    [DONE]
NORMALIZACIÓN PRODUCTOS                [DONE WITH REVIEW QUEUE]
CURRENT/HISTORY + REPLAY OFFLINE       [DONE]
TURSO / SQLITE CONTRACT                [DONE OFFLINE]
TRANSACTION / ROLLBACK / REHYDRATE     [DONE OFFLINE]
INITIAL SNAPSHOT APPROVAL              [DONE OFFLINE]
FULL 9439 SQLITE INTEGRATION            [DONE OFFLINE]
EXACT ARTIFACT PREFLIGHT               [PREPARED]
BIGQUERY PRODUCTIVE PATH               [RETIRED]
GOOGLE SHEETS PRODUCTIVE PATH          [RETIRED]
FIRST DURABLE TURSO LOAD               [NEXT HUMAN CREDENTIAL BOUNDARY]
INVENTORY FIRST-CLASS                  [PENDING]
DAILY AUTOMATION                       [PENDING]
CONSECUTIVE RUN VALIDATION             [PENDING]
DASH + PLOTLY                          [PENDING AFTER LA COLONIA E2E]
TEGUCIGALPA                            [PENDING]
SUPERMARKET #2                         [PENDING]
```