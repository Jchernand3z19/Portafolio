# Decisiones técnicas

## DT-001 — Monorepositorio

El proyecto vive en `precios-supermercados-sps/`. Los workflows viven en `.github/workflows/`.

## DT-002 — Contratos Python conservadores y dependencias explícitas

Los contratos de dominio usan `dataclass`, `StrEnum`, `Decimal`, `datetime` y validaciones propias. Las dependencias externas del proyecto se declaran en `requirements.txt`; actualmente incluyen `pytest`, `playwright` y `PyYAML`. No se presenta la biblioteca estándar como única dependencia del proyecto completo.

## DT-003 — Nomenclatura única

Los nombres oficiales son `current_price`, `reported_regular_price`, `scrape_run_id`, `availability` y `run_status`. No se mantienen alias paralelos.

## DT-004 — Tres etapas explícitas

- `RawProduct`: fidelidad de la fuente.
- `NormalizedOffer`: formato común, incluso con interpretación parcial.
- `ValidatedOffer`: hash, estado de revisión y eventos de calidad.

## DT-005 — Observaciones parciales legítimas

Marca, categoría, subcategoría y componentes de presentación pueden quedar nulos. El contrato conserva el producto con `pending_fields`, `review_status = needs_review` y eventos `pending_normalization`. No se inventan datos.

## DT-006 — Regla de precio por disponibilidad

`in_stock` requiere `current_price > 0`. `out_of_stock`, `not_listed` y `unknown` permiten `current_price = null`.

## DT-007 — Identidad independiente del precio

Precio, promoción, disponibilidad y fecha no participan en `source_product_id`, `product_id` ni `offer_id`.

## DT-008 — Sensibilidad de llaves fuente

ID interno, SKU, barcode e ID de API conservan mayúsculas y minúsculas y solo eliminan espacios externos. La normalización específica de un supermercado deberá documentarse en su adaptador y pruebas.

## DT-009 — URL conservadora

La URL estable elimina fragmentos y solo parámetros inequívocos de tracking: `utm_*`, `gclid`, `fbclid`, `msclkid`, `mc_cid`, `mc_eid`. `ref` y cualquier parámetro potencialmente funcional se conservan.

## DT-010 — Componentes obligatorios no vacíos

`supermarket_id`, `location_id`, `source_product_id` y `source_key` se validan antes de crear identificadores.

## DT-011 — Producto fuente y normalizado

`source_product_id` identifica el registro del supermercado. `product_id` agrupa productos comparables. El mapeo puede permanecer `pending` sin eliminar la observación.

## DT-012 — Oferta por ubicación

`offer_id` combina supermercado, ubicación y producto fuente.

## DT-013 — Promoción declarada versus reducción real

`is_promotion` conserva la condición observada. `reported_regular_price` no demuestra ahorro. La reducción real se calculará contra el último `current_price` histórico aceptado. No existe `promotion_text`.

## DT-014 — Ubicación auditable

`location_status` puede ser `confirmed`, `inferred` o `unknown`. Confirmed/inferred requieren `location_evidence` y `location_confidence` entre 0 y 1.

## DT-015 — Hash con nulos deterministas

`state_hash` incluye precios, promoción, disponibilidad y atributos normalizados relevantes, incluso cuando sean nulos. Cambios cosméticos no alteran el hash.

## DT-016 — Estados de ejecución

`run_status` usa `running`, `success`, `warning`, `rejected`, `failed`, `abandoned`. Una ejecución incompleta se marca `rejected`; no actualiza precios, disponibilidad ni periodos.

## DT-017 — Métricas de completitud

Cada ejecución registra cobertura de páginas, productos, ofertas y precios, comparación con la última ejecución aceptada, rechazos y eventos estructurales. Los umbrales viven en `cfg_supermarkets`.

## DT-018 — Historial trazable

Cada periodo registra `change_type`, `changed_fields`, ejecución de apertura/cierre, precios originales, versiones, ubicación y auditoría. Un reintento no duplica historial.

## DT-019 — Trazabilidad GitHub

`fact_scrape_runs` conserva workflow, run ID, intento, commit SHA y ref ejecutada.

## DT-020 — Google Sheets es contrato histórico, no backend elegido

El modelo documenta ocho tabs compatibles con una primera etapa en Google Sheets, pero no conecta Google Sheets ni solicita credenciales. Esa documentación no obliga a escoger Sheets, BigQuery, SQLite o PostgreSQL como backend productivo antes de cerrar la frontera de aceptación autoritativa.

## DT-021 — Sitio público fuera de alcance

No se modifica Mundial 2026, `js/main.js`, el registro de proyectos ni la página pública.

## DT-022 — Frontera comercial fail-closed y backend-neutral

`commercial_state.py` implementa la transición current/history sin almacenamiento externo. Sólo un run `success` o `warning` con catálogo aceptado puede mutar estado. `running`, `rejected`, `failed`, `abandoned` o catálogo no aceptado no mutan. La capa revalida `state_hash`, exige cronología `observed_at_utc <= validated_at_utc <= decided_at_utc`, hace replay idempotente y rechaza reutilización conflictiva de `scrape_run_id`.

Una oferta ausente de un payload posterior no se interpreta como eliminación, `not_listed` ni `out_of_stock`; esos estados requieren evidencia explícita. El booleano `catalog_accepted` de esta capa no concede autoridad live: en producción debe provenir de un collector autoritativo con provenance independiente.

## DT-023 — CI también valida `main`

La suite offline corre en pull requests, manualmente y en pushes a `main` que afecten `precios-supermercados-sps/**` o `.github/workflows/**`. Esto reduce el riesgo de falso verde mientras GATE-17 siga abierto y `main` no tenga protección productiva. La auditoría de workflows prueba que esta cobertura no desaparezca silenciosamente.

## DT-024 — Replay terminal liga evidencia persistible

`running` es un estado transitorio y no consume la identidad terminal de `scrape_run_id`. El mismo run puede evolucionar de `running` a su decisión final. En cambio, una decisión terminal aplicada o descartada comercialmente queda ligada de forma idempotente a su decisión, `state_hash`, timestamps, identidad de oferta y evidencia persistible/auditable (`source_url`, versiones, trazabilidad fuente explícita, ubicación, review/pending y eventos de calidad).

Reutilizar un `scrape_run_id` terminal con evidencia distinta falla cerrado. `raw_values` no participa en ese fingerprint porque es un contenedor crudo arbitrario y no forma parte de la identidad persistible definida por esta frontera. Esto no altera `state_hash`: los cambios comerciales siguen determinados exclusivamente por los campos canónicos del estado.

## DT-025 — No fijar el HEAD mutable dentro de la fuente canónica

Los SHAs históricos usados como evidencia de auditoría pueden documentarse. El HEAD “actual” de `main` se consulta en GitHub y no se intenta mantener autorreferencialmente dentro de README/arquitectura, porque cualquier merge que actualice esos archivos produciría inmediatamente un nuevo HEAD y volvería obsoleto el valor escrito.
