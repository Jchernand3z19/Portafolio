# Precios de Supermercados de San Pedro Sula

Proyecto para recolectar, normalizar, validar y conservar cambios relevantes de precios y disponibilidad de supermercados, con alcance inicial en San Pedro Sula.

## Estado actual

**La ingeniería offline de La Colonia está avanzada; el acceso live sigue cerrado y no existe aceptación productiva del catálogo.**

Estado verificado al **2026-08-21 (America/Tegucigalpa)**:

- `main` está protegida; GATE-17 permanece `PASS_PRODUCTIVE_EVIDENCE`.
- La revisión integrada más reciente de este corte es PR #83.
- Suite integrada: **1209/1209 pruebas aprobadas** + `compileall`.
- No existen autorizaciones live activas.
- `SPS-context-and-root-facets-001` está consumida; `002` no está autorizada.
- SPS technical context continúa `UNCONFIRMED`.
- Los entrypoints live hacia La Colonia permanecen globalmente bloqueados.
- **Requests live a La Colonia durante estas fases: 0.**
- Cloudflare Workers/Durable Objects/OIDC/Ed25519/Workers Observability están implementados y probados **offline**, pero no desplegados.
- Structural discovery, transporte de catálogo, reconciliación de observability y manifest de run están conectados offline.
- La readiness técnica del catálogo ya se distingue de autoridad productiva: puede comprobarse completitud técnica sin producir `catalog_accepted=true` ni `production_authority=true`.
- `trusted_collector_provenance_unavailable` permanece en la aceptación canónica hasta evidencia productiva real.
- `commercial_state.py` y `commercial_pricing.py` implementan current/history y reducción real offline; no existe backend productivo conectado.
- PR #84 prepara una sonda Cloudflare aislada contra un origen controlado no-La-Colonia y obtuvo **1212/1212** en CI, pero mientras no esté integrado no se cuenta como parte de `main`.

La fuente canónica del estado es [`docs/arquitectura.md`](docs/arquitectura.md). La evidencia de GATE-17 está en [`docs/gate-17-verification.md`](docs/gate-17-verification.md).

## Contratos protegidos

- `RawProduct`: observación fiel a la fuente.
- `NormalizedOffer`: formato común sin inventar datos faltantes.
- `ValidatedOffer`: oferta validada con `state_hash`, revisión y evidencia de calidad.

No se modifican estos contratos sin necesidad demostrada y una tarea explícita que lo requiera.

Una oferta `in_stock` exige `current_price > 0`. `out_of_stock`, `not_listed` y `unknown` pueden conservar precio nulo.

## Regla comercial del histórico

`reported_regular_price` es un dato informado por el supermercado; **no demuestra ahorro real**.

La reducción real se calcula contra el `current_price` del periodo histórico **aceptado inmediatamente anterior**. `reported_regular_price` e `is_promotion` no forman parte de esa fórmula. Si no existe baseline confiable, no se inventa una reducción.

Runs `rejected`, `failed`, `abandoned` o no autoritativos no alteran current/history.

## La Colonia

Identidad VTEX:

```text
Producto: productId -> productReference -> linkText
SKU:      itemId
```

Deduplicar no demuestra completitud. La validación offline comprueba árbol/facets, membership, totals, ventanas, gaps, truncamiento, repetición, reconciliación independiente, unión producto/SKU y conflictos de owner.

## Cadena Cloudflare offline

La ruta de ingeniería actual es:

```text
GitHub Actions
-> GitHub OIDC
-> Cloudflare Worker
-> Durable Object
-> request físico permitido
-> receipt Ed25519 + hash de respuesta
-> verificación criptográfica Python
-> Workers Observability
-> manifest estructural / catálogo
-> readiness técnica
```

Ya existen offline:

- política OIDC cerrada a repo/ref/workflow/environment/run;
- JWKS de GitHub con origen fijo;
- allowlist exacto del endpoint GraphQL de La Colonia en el Worker productivo;
- presupuesto, pacing, single-flight, replay y fencing en Durable Object;
- firmas Ed25519 y release ligada a `CF_VERSION_METADATA`;
- observability por request;
- discovery estructural autenticado;
- plan de catálogo derivado internamente, no elegido por caller;
- collector de páginas que reconstruye las URLs canónicas;
- finalizador que reconcilia cada página con observability y crea un manifest de run;
- evaluación de readiness que **nunca** convierte evidencia offline en autoridad productiva.

Nada de esto equivale a un despliegue real. No hay Worker remoto, Durable Object remoto, clave privada real en Cloudflare ni spans productivos verificados.

## Sonda controlada antes de La Colonia

PR #84 prepara una prueba física separada contra un origen propio `workers.dev`. La sonda usa Worker, Durable Object, OIDC audience/environment, llaves y dominio de firma **distintos** de la ruta productiva de La Colonia.

La finalidad es comprobar Cloudflare físicamente sin tocar La Colonia. La sonda no concede autoridad de catálogo.

## Persistencia

La lógica comercial actual es backend-neutral y offline. El modelo lógico contempla:

- `cfg_supermarkets`;
- `cfg_locations`;
- `dim_products`;
- `map_source_products`;
- `fact_scrape_runs`;
- `fact_offers_current`;
- `fact_offer_history`;
- `fact_quality_events`.

No existe almacenamiento productivo seleccionado/conectado. Google Sheets y BigQuery permanecen como opciones históricas/evolutivas, no como infraestructura activa.

Un backend productivo no debe recibir un booleano `catalog_accepted` controlable por caller; debe consumir una decisión autoritativa verificable cuando esa frontera exista.

## Pruebas

Desde la raíz del monorepositorio:

```bash
python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts
pytest precios-supermercados-sps/tests
```

La CI también ejecuta la suite Node de `edge/cloudflare` y auditoría fail-closed de workflows.

## Bloqueos actuales

Antes de scraping comercial productivo todavía faltan, en este orden:

1. integrar y luego desplegar/probar la sonda Cloudflare contra un origen controlado no-La-Colonia;
2. demostrar físicamente OIDC, Durable Object, firma, release y observability en Cloudflare;
3. establecer una frontera de autoridad productiva del collector;
4. obtener autorización humana nueva para cualquier request a La Colonia;
5. confirmar SPS mediante una observación live mínima autorizada;
6. ejecutar validación exacta del catálogo bajo presupuesto cerrado;
7. sólo entonces conectar persistencia, automatización diaria y Power BI.

El segundo supermercado espera a que esta plataforma común quede estable.