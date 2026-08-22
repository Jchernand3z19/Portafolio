# Precios de Supermercados de San Pedro Sula

Proyecto para recolectar, normalizar, validar y conservar cambios relevantes de precios y disponibilidad de supermercados, con alcance inicial en San Pedro Sula.

## Estado actual

**La ingeniería offline de La Colonia y de la frontera Cloudflare está avanzada; el acceso live a La Colonia sigue cerrado y no existe aceptación productiva del catálogo.**

Estado verificado al **2026-08-21 (America/Tegucigalpa)**:

- `main` está protegida; GATE-17 permanece `PASS_PRODUCTIVE_EVIDENCE`.
- La revisión offline más reciente integrada es PR #91.
- CI observada en PR #91: **1234/1234 pruebas aprobadas** + `compileall`.
- No existen autorizaciones live activas.
- `SPS-context-and-root-facets-001` está consumida; `002` no está autorizada.
- SPS technical context continúa `UNCONFIRMED`.
- Los entrypoints live hacia La Colonia permanecen globalmente bloqueados.
- **Requests live a La Colonia durante estas fases: 0.**
- Cloudflare Workers/Durable Objects/OIDC/Ed25519/Workers Observability están implementados y probados **offline**, pero no desplegados.
- Structural discovery, transporte de catálogo, reconciliación de observability y manifest de run están conectados offline.
- La readiness técnica del catálogo se distingue de autoridad productiva: puede comprobarse completitud técnica sin producir `catalog_accepted=true` ni `production_authority=true`.
- `trusted_collector_provenance_unavailable` permanece en la aceptación canónica hasta evidencia productiva real.
- `commercial_state.py` y `commercial_pricing.py` implementan current/history y reducción real offline; no existe backend productivo conectado.
- La sonda Cloudflare no-La-Colonia está integrada offline con origen controlado, OIDC, Durable Object, receipt Ed25519, verificación criptográfica independiente y reconciliación contra Workers Observability. **No ha sido desplegada ni ejecutada físicamente.**
- Wrangler está fijado a `4.125.0`; el runbook evita CLI mutable y el directorio edge ignora estado local/secrets temporales.
- En el barrido posterior a PR #91 no quedó una tarea de implementación offline conocida que pueda cerrar honestamente la frontera productiva sin acceso externo a Cloudflare.

La fuente canónica del estado es [`docs/arquitectura.md`](docs/arquitectura.md). El procedimiento de la primera prueba externa está en [`docs/cloudflare-controlled-probe-runbook.md`](docs/cloudflare-controlled-probe-runbook.md). La evidencia de GATE-17 está en [`docs/gate-17-verification.md`](docs/gate-17-verification.md).

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

Nada de esto equivale a un despliegue real. No hay Worker productivo remoto, Durable Object productivo remoto, clave privada productiva real en Cloudflare ni spans productivos verificados.

## Sonda controlada antes de La Colonia

La sonda integrada usa una cadena separada:

```text
workflow manual cloudflare-probe
-> OIDC de sonda
-> Worker precios-sps-controlled-probe
-> ProbeLedger
-> Worker precios-sps-controlled-origin (*.workers.dev)
-> challenge/body exactos
-> receipt probe-1 Ed25519
-> verifier GitHub sin OIDC
-> Workers Observability
-> custom span + único child fetch
-> PlatformReconciledControlledProbe
```

Separaciones obligatorias:

- origen, gateway y Durable Object distintos de producción;
- audience/environment/llaves/signing key/schema/dominio criptográfico distintos;
- caller sin input de origin URL;
- sólo HTTPS `*.workers.dev` y path exacto;
- La Colonia rechazada antes de cualquier fetch;
- el job con OIDC no hace checkout;
- el job que verifica código no tiene `id-token: write`;
- el verifier usa public key confiable fuera del Worker;
- el token de Workers Observability está separado del job OIDC;
- cualquier resultado mantiene `catalog_accepted=false` y `production_authority=false`.

La sonda está `DONE_OFFLINE / READY_FOR_EXTERNAL_DEPLOYMENT`; todavía **NO DESPLEGADA / NO EJECUTADA**.

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

Último resultado observado para PR #91:

```text
1234 passed
compileall PASS
```

## Bloqueos actuales

Antes de scraping comercial productivo todavía faltan, en este orden:

1. conectar/configurar una cuenta Cloudflare para la sonda;
2. desplegar `precios-sps-controlled-origin` y `precios-sps-controlled-probe` con llaves exclusivas de sonda;
3. configurar el Environment GitHub `cloudflare-probe` y ejecutar una sonda física;
4. demostrar físicamente OIDC, Durable Object, Version Metadata, Ed25519 y Workers Observability, manteniendo La Colonia en 0 requests;
5. preparar la frontera productiva real sin invocarla todavía contra La Colonia;
6. obtener autorización humana nueva para cualquier request a La Colonia;
7. confirmar SPS mediante una observación live mínima autorizada;
8. ejecutar validación exacta del catálogo bajo presupuesto cerrado;
9. sólo entonces conectar persistencia, automatización diaria y Power BI.

El segundo supermercado espera a que esta plataforma común quede estable.
