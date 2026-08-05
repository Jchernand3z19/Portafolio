# Decisiones técnicas iniciales

## DT-001 — Monorepositorio

El proyecto vive en `precios-supermercados-sps/`. Solo el workflow está en `.github/workflows/`.

## DT-002 — Contratos con biblioteca estándar

Se usan `dataclass`, `StrEnum`, `Decimal`, `datetime` y validaciones propias. La única dependencia externa continúa siendo `pytest`.

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

## DT-020 — Google Sheets es un contrato

Esta fase documenta las ocho tabs, pero no conecta Google Sheets ni solicita credenciales.

## DT-021 — Sitio público fuera de alcance

No se modifica Mundial 2026, `js/main.js`, el registro de proyectos ni la página pública.
