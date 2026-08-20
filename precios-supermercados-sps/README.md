# Precios de Supermercados de San Pedro Sula

Fundación técnica para recolectar, normalizar, validar y conservar cambios relevantes de precios y disponibilidad de supermercados con alcance inicial en San Pedro Sula.

## Estado

**Ingeniería offline de La Colonia integrada en `main`; live globalmente bloqueado.**

Estado verificado al 2026-08-20:

- PR #17 y PR #7 están merged.
- `main` conserva los entrypoints live con guard global fail-closed.
- No existen autorizaciones live activas.
- `SPS-context-and-root-facets-001` está consumida; `002` no está autorizada.
- SPS technical context continúa `UNCONFIRMED`.
- No se declara catálogo live completo.
- GATE-17 continúa `FAIL_PRODUCTIVE_EVIDENCE`: la rama `main` no está protegida.
- El collector autoritativo con provenance física independiente sigue pendiente; la aceptación canónica del catálogo permanece fail-closed.
- `live_safety.py` es un modelo offline, no un enforcement productivo de red.
- Persistencia e histórico están especificados como contrato, pero no existe todavía un backend productivo conectado.

La fuente canónica única del estado y los gates es [`docs/arquitectura.md`](docs/arquitectura.md). Los documentos bajo `docs/supermercados/` conservan evidencia e historia y no conceden autoridad operativa.

## Contratos protegidos

- `RawProduct`: observación fiel a la fuente.
- `NormalizedOffer`: formato común que permite campos normalizados pendientes sin inventar datos.
- `ValidatedOffer`: hash, revisión y eventos de calidad antes de persistir.

Una oferta `in_stock` exige `current_price > 0`. Los estados `out_of_stock`, `not_listed` y `unknown` pueden conservar precio nulo. Marca, categoría, subcategoría y presentación pueden quedar pendientes con `review_status = needs_review`.

## Regla comercial del histórico

`reported_regular_price` es un dato informado por el supermercado y no demuestra ahorro real. La reducción real se calcula contra el último `current_price` de una ejecución históricamente aceptada. Una ejecución `rejected`, `failed` o `abandoned` nunca actualiza estado comercial ni abre falsos periodos históricos.

## Identidad VTEX de La Colonia

Producto:

`productId -> productReference -> linkText`

SKU:

`itemId`

Deduplicar no demuestra completitud. El evaluador exige evidencia estructural, cobertura total, estabilidad de totales, reconciliación independiente y unión consistente; aun así la aceptación permanece cerrada mientras falte provenance confiable del collector.

## Estructura principal

```text
precios-supermercados-sps/
├── .automation/
├── config/supermercados/la-colonia.yaml
├── docs/
│   ├── arquitectura.md
│   ├── decisiones-tecnicas.md
│   ├── modelo-datos.md
│   └── supermercados/
├── reports/discovery/
├── scripts/
│   ├── probar_la_colonia.py
│   ├── diagnosticar_ventanas_la_colonia.py
│   ├── descubrir_facets_la_colonia.py
│   └── control/publicación del dispatcher
├── src/precios_supermercados/
│   ├── models.py
│   ├── identifiers.py
│   ├── live_safety.py
│   ├── automation/
│   ├── diagnostics/
│   └── scrapers/
│       ├── la_colonia.py
│       ├── la_colonia_graphql.py
│       ├── la_colonia_runner.py
│       ├── la_colonia_catalog_partitions.py
│       ├── la_colonia_catalog_coverage.py
│       ├── la_colonia_facet_discovery*.py
│       └── la_colonia_window_diagnostic*.py
└── tests/
    ├── fixtures/
    ├── pruebas de contratos e identidad
    ├── pruebas de crawler/completitud/reconciliación
    ├── pruebas de SPS/diagnósticos
    ├── pruebas de live safety
    └── auditoría de workflows
```

Los workflows del proyecto viven en `.github/workflows/`.

## Pruebas

Desde la raíz del monorepositorio:

```bash
python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts
pytest precios-supermercados-sps/tests
```

Última validación histórica verificada previa a esta actualización: **770/770 pruebas aprobadas** en GitHub Actions sobre el head que fue integrado mediante PR #7. La CI canónica se ejecuta en pull requests, manualmente y en pushes a `main` que afecten el proyecto o sus workflows.

## Bloqueos productivos actuales

- autorización humana nueva antes de cualquier tráfico live;
- GATE-17: protección/ruleset productivo de `main`;
- trusted collector con provenance independiente y no controlable por caller;
- enforcement físico productivo de egress/claim/fencing;
- confirmación técnica SPS mediante evidencia live autorizada;
- aceptación canónica antes de cualquier persistencia comercial.

Google Sheets, BigQuery, scraping diario y Power BI no deben activarse para datos comerciales hasta cerrar esas dependencias. El desarrollo offline de interfaces de persistencia, histórico e idempotencia sí puede continuar sin tráfico live.
