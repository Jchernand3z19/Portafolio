# Decisiones técnicas iniciales

## DT-001 — Monorepositorio

El proyecto vive en `precios-supermercados-sps/` dentro de `Portafolio`. Solo el workflow queda en `.github/workflows/` por requisito de GitHub.

## DT-002 — Contratos con biblioteca estándar

Se usan `dataclass`, `Enum`, `Decimal`, `datetime` y validaciones propias. Esto reduce dependencias antes de conocer las necesidades reales del primer extractor.

## DT-003 — Dependencias mínimas

La única dependencia externa es `pytest`, utilizada por las pruebas. No se agregan librerías de scraping, Google Sheets, Power BI, BigQuery ni servidor web.

## DT-004 — Tres etapas explícitas

- `RawProduct` protege la fidelidad de la fuente.
- `NormalizedOffer` entrega el formato común.
- `ValidatedOffer` agrega hash y eventos de calidad antes de persistir.

Esta separación evita que un scraper mezcle extracción, interpretación y escritura.

## DT-005 — Identidad independiente del precio

`source_product_id` depende del supermercado y de una llave fuente estable. `offer_id` agrega la ubicación. Precio, promoción, disponibilidad y fecha nunca forman parte de esas identidades.

Prioridad de llave:

1. ID interno del sitio.
2. SKU.
3. Código de barras.
4. ID de API.
5. URL estable sin rastreo.

## DT-006 — Producto normalizado y producto fuente no son equivalentes

`source_product_id` identifica el registro del supermercado. `product_id` agrupa el producto normalizado para comparación entre supermercados. El mapeo futuro queda en `map_source_products` y debe poder revisarse.

## DT-007 — Oferta por ubicación

`offer_id` combina supermercado, ubicación y producto fuente. Esto permite que el mismo artículo tenga precio o disponibilidad diferente por sucursal.

## DT-008 — Promoción declarada versus reducción real

`is_promotion` registra la condición observada o normalizada. `reported_regular_price` conserva el valor informado por el supermercado, pero no demuestra ahorro. La reducción real se calculará después contra el último `current_price` histórico comparable.

No se crea una columna `promotion_text`.

## DT-009 — Ausencia no equivale a agotado

Los estados permitidos son `in_stock`, `out_of_stock`, `not_listed` y `unknown`. Un producto desaparecido se clasifica como `not_listed` o `unknown` salvo evidencia explícita de agotamiento.

## DT-010 — Ubicación auditable

La ubicación puede ser `confirmed`, `inferred` o `unknown`. Los dos primeros estados requieren evidencia y una confianza entre 0 y 1.

## DT-011 — Hash de estado

El `state_hash` incluye precio actual, precio regular informado, promoción, disponibilidad, marca normalizada, unidades, contenido total y unidad de medida. Normaliza diferencias cosméticas y no incluye URLs.

## DT-012 — Persistencia idempotente

La capa futura de almacenamiento deberá impedir duplicados por reintentos y garantizar un único periodo actual por `offer_id`.

## DT-013 — Google Sheets es un contrato, no una integración

Esta fase documenta las tabs y relaciones, pero no solicita credenciales ni realiza llamadas a Google Sheets.

## DT-014 — Sitio público fuera de alcance

No se modifica `js/main.js`, el registro de proyectos ni la página pública hasta que exista contenido real para presentar.
