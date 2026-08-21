# Precios de Supermercados de San Pedro Sula

Fundación técnica para recolectar, normalizar, validar y conservar cambios relevantes de precios y disponibilidad de supermercados con alcance inicial en San Pedro Sula.

## Estado

**Ingeniería offline de La Colonia integrada; live globalmente bloqueado.**

Estado verificado al 2026-08-20:

- Las revisiones de CI, frontera comercial, identidad, evidencia auditable y pricing histórico están integradas en `main`.
- El HEAD mutable de `main` se verifica directamente en GitHub y no se fija como “SHA actual” dentro de este archivo, porque el propio merge de documentación cambiaría ese SHA.
- `main` conserva los entrypoints live con guard global fail-closed.
- No existen autorizaciones live activas.
- `SPS-context-and-root-facets-001` está consumida; `002` no está autorizada.
- SPS technical context continúa `UNCONFIRMED`.
- No se declara catálogo live completo.
- GATE-17 continúa `FAIL_PRODUCTIVE_EVIDENCE`: la rama `main` no está protegida.
- El collector autoritativo con provenance física independiente sigue pendiente; la aceptación canónica del catálogo permanece fail-closed.
- `live_safety.py` es un modelo offline, no un enforcement productivo de red.
- `commercial_state.py` implementa una frontera comercial offline atómica e idempotente: runs no aceptados no mutan estado y las ausencias no se convierten en bajas implícitas.
- La frontera recalcula `source_product_id` y `offer_id` deterministas, preserva la relación estable con la llave fuente y rechaza deriva de moneda para una oferta existente.
- `current` conserva la evidencia del último run aceptado incluso cuando el `state_hash` no cambia; el histórico mantiene la evidencia de apertura del periodo.
- La evidencia `raw_values` se guarda y se expone mediante snapshots defensivos para impedir mutaciones posteriores del current/history.
- `changed_fields` usa la misma canonicalización textual que `state_hash`, por lo que diferencias cosméticas no crean cambios falsos.
- El replay terminal liga decisión, estado y evidencia persistible/auditable; `running` es transitorio y no consume anticipadamente el `scrape_run_id` terminal.
- `commercial_pricing.py` deriva reducciones reales exclusivamente contra el `current_price` del periodo aceptado inmediatamente anterior; `reported_regular_price` nunca demuestra ahorro real.
- La capa de pricing revalida identidad determinista, `state_hash`, cronología, contigüidad y metadatos de apertura/cierre antes de calcular.
- La última suite completa verificada contiene **850/850 pruebas aprobadas**, además de `compileall`, en GitHub Actions con Python 3.12.14.
- No existe todavía un backend productivo conectado para current/history.

La fuente canónica única del estado y los gates es [`docs/arquitectura.md`](docs/arquitectura.md). Los documentos bajo `docs/supermercados/` conservan evidencia e historia y no conceden autoridad operativa.

## Contratos protegidos

- `RawProduct`: observación fiel a la fuente.
- `NormalizedOffer`: formato común que permite campos normalizados pendientes sin inventar datos.
- `ValidatedOffer`: hash, revisión y eventos de calidad antes de persistir.

Una oferta `in_stock` exige `current_price > 0`. Los estados `out_of_stock`, `not_listed` y `unknown` pueden conservar precio nulo. Marca, categoría, subcategoría y presentación pueden quedar pendientes con `review_status = needs_review`.

## Regla comercial del histórico

`reported_regular_price` es un dato informado por el supermercado y no demuestra ahorro real. La reducción real se calcula contra el `current_price` del periodo histórico aceptado inmediatamente anterior. Una ejecución `rejected`, `failed` o `abandoned` nunca actualiza estado comercial ni abre falsos periodos históricos.

La frontera offline actual además exige:

- `success` o `warning` más `catalog_accepted = true` para permitir mutación comercial;
- `source_product_id` y `offer_id` recalculados desde sus componentes deterministas;
- una identidad lógica de oferta no puede fragmentarse entre IDs distintos ni moverse entre ubicaciones;
- la relación `supermarket_id + source_product_id -> source_key` permanece estable;
- la moneda de una oferta existente permanece estable;
- `state_hash` recalculado y válido antes de aplicar;
- cronología cerrada `observed_at_utc <= validated_at_utc <= decided_at_utc`;
- un `scrape_run_id` terminal no puede reutilizarse con otra decisión, timestamps ni evidencia persistible/auditable;
- `running` no consume la identidad terminal y puede evolucionar a una decisión final del mismo run;
- el mismo hash confirma el periodo abierto sin duplicar historial y refresca la evidencia de `current` al último run aceptado;
- `raw_values` queda aislado mediante snapshots defensivos al entrar y salir de la frontera comercial;
- `changed_fields` compara textos con la canonicalización usada por `state_hash`;
- un cambio cierra exactamente un periodo y abre exactamente uno nuevo;
- una oferta ausente de un payload posterior no se interpreta como `not_listed`, `out_of_stock` ni eliminación.

Para derivar ahorro real, `commercial_pricing.py` exige que current/history reconcilien: mismo `offer_id`, IDs fuente deterministas, un único periodo abierto al final, periodos contiguos, evidencia temporal válida y coherencia entre el run que cierra un periodo y el que abre el siguiente. Si la evidencia no reconcilia, falla cerrado y no produce una reducción.

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
│   ├── commercial_state.py
│   ├── commercial_pricing.py
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
    ├── test_commercial_state*.py
    ├── test_commercial_pricing*.py
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

Hitos de validación verificados:

- baseline integrado mediante PR #7: **770/770**;
- PR #19 — frontera comercial, cronología y hardening de CI: **796/796**;
- PR #20 — coherencia de evidencia `current` y canonicalización de `changed_fields`: **798/798**;
- PR #22 — replay ligado a evidencia persistible y transición `running -> terminal`: **801/801**;
- PR #23 — continuidad de identidad de oferta: **810/810**;
- PR #24 — IDs deterministas revalidados en la frontera: **808/808**;
- PR #25 — snapshots defensivos de evidencia: **812/812**;
- PR #26 — reducción real contra histórico aceptado: **844/844**;
- PR #27 — reconciliación fail-closed de evidencia de pricing: **850/850**, además de `compileall`, en GitHub Actions con Python 3.12.14.

Las variaciones de conteo entre revisiones corresponden a adición/reemplazo de regresiones, no a relajación de gates. La CI canónica se ejecuta en pull requests, manualmente y en pushes a `main` que afecten el proyecto o sus workflows.

## Bloqueos productivos actuales

- autorización humana nueva antes de cualquier tráfico live;
- GATE-17: protección/ruleset productivo de `main`;
- trusted collector con provenance independiente y no controlable por caller;
- enforcement físico productivo de egress/claim/fencing;
- confirmación técnica SPS mediante evidencia live autorizada;
- aceptación canónica antes de conectar un backend comercial productivo.

Google Sheets, BigQuery, scraping diario y Power BI no deben activarse para datos comerciales hasta cerrar esas dependencias. La lógica de transición current/history y las derivaciones de pricing pueden probarse y evolucionar offline sin tráfico live ni infraestructura externa.
