# Arquitectura — Retail Price Intelligence / Precios de Supermercados SPS

Este documento describe la arquitectura estable. Cifras, últimos runs e incidentes vigentes viven en [`PROJECT_STATE.md`](PROJECT_STATE.md).

## Vista general

```text
sitios públicos por fuente/ubicación
        ↓
extractores especializados
        ↓
snapshots source-faithful + evidencia
        ↓
validación de ubicación + completitud
        ↓
persistencia comercial común
        ↓
Turso / histórico compacto
        ↓
homologación derivada
        ↓
safe comparator + freshness
        ↓
Python analytics
        ↓
┌────────────────────────┬──────────────────────────┬───────────────────────────┐
│ Business Mart v1       │ Consumer Mart v2         │ Consumer Catalog v3       │
│ privado / B2B          │ público / comparación    │ público / navegación      │
└───────────┬────────────┴─────────────┬────────────┴─────────────┬─────────────┘
            ↓                          ↓                          ↓
         Power BI              escenarios B2C          Compra Inteligente
```

La base comercial es única. No existe una tabla o histórico independiente por supermercado que pueda divergir del estado compartido.

## Cobertura productiva

La arquitectura integra seis cadenas:

- La Colonia;
- Supermercados Colonial;
- Walmart;
- PriceSmart;
- Comisariato Los Andes;
- Paiz.

Cada extractor conserva las particularidades de su fuente, pero todos cruzan la misma frontera de validación/persistencia.

## Principios

1. La fuente manda; no se inventan datos.
2. Identidad fuente, ubicación y estado comercial son conceptos distintos.
3. Un snapshot incompleto o sin ubicación demostrada no se persiste.
4. Runs rechazados no sustituyen el último estado válido.
5. Una observación idéntica no crea un periodo histórico redundante.
6. Los precios persistidos usan minor units.
7. Homologar no significa autorizar comparación.
8. Marca + presentación nunca bastan para unir productos cross-retailer.
9. `current_price` es el precio efectivo observado; `reported_regular_price` es sólo referencia.
10. Power BI y la web consumen datos derivados; no ejecutan scraping ni matching.
11. Comparaciones stale/ambiguas/incompletas fallan cerrado.
12. Workflows con secretos ejecutan sólo código confiable de `main`.

# 1. Ingesta por fuente

Cada extractor read-only debe:

- respetar budgets, delays, deadlines y reintentos acotados;
- producir identidad fuente estable;
- conservar evidencia/raw cuando el contrato lo exige;
- demostrar el contexto comercial de la captura;
- declarar completitud;
- no escribir directamente a la base productiva.

Los extractores operativos viven en `scripts/` y reutilizan contratos/normalizadores en `src/precios_supermercados/`.

# 2. Snapshot validado

El snapshot es la frontera entre adquisición y persistencia. Según la fuente debe permitir verificar:

- `supermarket_id`;
- `location_id`;
- `catalog_complete`;
- `location_verified_same_run`;
- conteos fuente vs extraídos;
- identidad estable de producto/SKU;
- precio, disponibilidad y promoción cuando existan;
- procedencia/digest de ejecución.

La persistencia vuelve a validar el snapshot. Tener un archivo en disco no le concede autoridad.

# 3. Persistencia comercial

## `supermarkets`

Una fila por cadena.

## `locations`

Una fila por contexto comercial persistible. La ciudad es atributo de la ubicación, no identidad de producto.

## `products`

Una identidad fuente estable dentro de cada supermercado, con descriptores disponibles: nombre, marca, presentación, categoría, GTIN/EAN y llaves fuente.

## `price_history`

Un periodo comercial por producto + ubicación. Conserva:

- `current_price_minor`;
- `reported_regular_price_minor`;
- promoción;
- disponibilidad;
- moneda;
- inicio/fin del periodo;
- run de procedencia.

`valid_to_utc IS NULL` representa el estado actual. No existe una segunda tabla current que pueda contradecir el histórico.

## `scrape_runs`

Una ejecución persistida por ubicación con estado, conteos y digest del snapshot.

# 4. Actualización recurrente

El workflow productivo común es:

```text
.github/workflows/precios-supermercados-sps-la-colonia-mvp-update.yml
```

El nombre conserva historia del proyecto, pero hoy procesa las seis cadenas.

```text
capturar fuentes
→ validar todos los snapshots
→ si todos pasan, persistir
→ verificar run_id + digest + estado actual
→ verificar FKs / integridad / duplicados
→ publicar evidencia
```

La compuerta es global y fail-closed: una fuente inválida evita persistencia parcial del ciclo.

# 5. Homologación derivada

`product_homologation_profiles` normaliza GTIN, nombre, marca, taxonomía, presentación y conflictos sin cambiar la verdad comercial fuente.

El workflow de homologación corre después de una actualización productiva exitosa. Un refresh sin cambios puede ser un no-op verificable.

# 6. Comparabilidad y freshness

`safe_comparator.py` es la frontera que autoriza comparaciones cross-source.

Estados principales:

- `comparable`;
- `review_required`;
- `not_comparable`.

Una identidad fuerte puede habilitar comparación sólo si no existen contradicciones comerciales. El caso de regresión `Passion Jaguar != Passion Especial` permanece bloqueado aunque otros descriptores coincidan.

Freshness se evalúa antes de ranking/PCI. Una fuente stale/unavailable puede conservar su último dato visible con aviso, pero no producir una recomendación competitiva nueva.

# 7. Analytics autoritativa en Python

La lógica crítica vive antes de las interfaces:

- precio actual/anterior y movimientos;
- histórico y ventanas suficientes;
- promoción declarada vs reducción histórica;
- ranking, PCI, spread y cobertura;
- canasta común y escenarios de compra;
- freshness y estados fail-closed.

No se imputa precio cero ni se usa precio regular como historia observada.

# 8. Serving RPI vigente

## Business Mart v1

`rpi-business-mart/v1` es el contrato B2B privado. Incluye dimensiones y facts de comparación actual, histórico de precios, promociones, canasta, cobertura y freshness.

Se genera con `scripts/exportar_rpi_marts.py` y alimenta los activos reproducibles de `powerbi/rpi/`.

## Consumer Mart v2

`rpi-consumer-mart/v2` es el contrato público analítico reducido. Contiene sólo identidades/ofertas autorizadas para comparación, historia resumida y escenarios B2C.

## Consumer Catalog v3

`rpi-consumer-catalog/v3` es el contrato público de navegación de gran volumen. Separa visibilidad de comparabilidad y usa:

```text
manifest + facets + demand-loaded indexes + bounded partitions
```

Las particiones tienen máximo 250 filas y sus hashes/tamaños son verificables. El alcance público actual es cinco contextos SPS: La Colonia, Colonial, Walmart, PriceSmart y Comisariato Los Andes.

El navegador no consulta Turso ni hace matching.

# 9. Publicación

Cadena vigente:

```text
accepted commercial state
→ homologation refresh
→ exportación RPI read-only
→ validación de schema/scope/hash/secretos
→ artifact seguro
→ sync atómico a portfolio-data
```

Se publican Consumer Mart v2, Consumer Catalog v3 y la muestra del portafolio. Business Mart permanece privado.

`precios-sps-publication/v1` y `precios-sps-static-bi-dataset/v1` se conservan como contratos legados/compatibilidad; no son la frontera RPI principal.

# 10. Power BI

Power BI consume el Business Mart y no debe:

- resolver identidad;
- inferir ubicación;
- decidir aceptación de runs;
- recalcular matching;
- consultar Turso o sitios fuente;
- redefinir PCI, freshness o historia crítica.

Activos reproducibles: [`../powerbi/rpi/`](../powerbi/rpi/).
Guía: [`BI-IMPLEMENTATION-GUIDE.md`](BI-IMPLEMENTATION-GUIDE.md).

# 11. Compra Inteligente

La web B2C consume únicamente archivos estáticos publicados y ofrece navegación, comparación segura, selección manual, cantidades, lista persistida, refresh explícito, escenarios de canasta, historial resumido y exportación CSV/PDF.

Totales:

```text
unit_price = current_price
line_total = unit_price * quantity
```

No se infieren impuestos, delivery, service fees o membership fees.

# 12. Backends

Productivo:

```text
Turso
```

Reproducibilidad/local:

```text
SQLite
```

Google Sheets y BigQuery pueden existir en componentes históricos/experimentales, pero no son la ruta productiva principal vigente.

# 13. Seguridad

Controles estructurales:

- secretos fuera de Git;
- Actions externas pinneadas por SHA;
- permisos mínimos;
- checkout inmutable en workflows privilegiados;
- PR head sin secretos/autoridad productiva;
- budgets live explícitos;
- snapshot validation fail-closed;
- FKs/integridad/duplicados verificados;
- publicación pública sanitizada y atómica.

# Fuente de verdad operativa

Este documento evita fijar cifras que cambian con cada ciclo. Consultar [`PROJECT_STATE.md`](PROJECT_STATE.md) para el último estado y `reports/` para evidencia histórica.
