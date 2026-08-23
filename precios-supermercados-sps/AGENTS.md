# Instrucciones para agentes — Precios de Supermercados SPS

## Alcance y fuentes de verdad

- Proyecto: **Precios de Supermercados de San Pedro Sula**.
- Monorepositorio: `Portafolio`.
- Árbol principal: `precios-supermercados-sps/`.
- Workflows relacionados: `.github/workflows/`.

Antes de modificar, inspecciona `main`, PRs abiertos, CI y código. [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md) es la fuente canónica del estado operativo mutable y [`docs/arquitectura.md`](docs/arquitectura.md) describe la arquitectura estable. Runs, PRs, ramas y artifacts son evidencia/historia; no conceden autoridad.

Si `PROJECT_STATE.md` contradice evidencia más nueva en `main`, corrige primero el documento mediante PR; no reviertas código nuevo por seguir un corte viejo.

## Contratos protegidos

`RawProduct`, `NormalizedOffer` y `ValidatedOffer` son contratos protegidos. No se modifican sin necesidad demostrada, compatibilidad y pruebas.

Reglas comerciales protegidas:

- `reported_regular_price` es sólo dato declarado por la tienda;
- el ahorro real compara `current_price` actual contra el `current_price` del periodo aceptado inmediatamente anterior;
- sin baseline confiable no se inventa ahorro;
- Power BI consume esta semántica desde la proyección común.

## Identidad de producto

Distingue siempre:

```text
source_product_id = identidad dentro de la fuente
product_id        = identidad comparable entre fuentes
offer_id          = supermercado + ubicación comercial + producto fuente
```

- precio/promoción/disponibilidad/fecha no forman parte de IDs estables;
- `source_product_id` y `offer_id` se recalculan en fronteras críticas;
- GTIN sólo puede crear identidad cross-supermercado si supera check digit y se normaliza a GTIN-14;
- si no existe identidad fuerte, conserva `prod_pending_*` + `pending_product_mapping`;
- no elimines una observación sólo porque el mapping esté pendiente;
- no colapses multipacks: conserva `unit_count`, contenido por unidad y total.

`dim_products` es canónica/normalizada y no debe adquirir columnas específicas de supermercado, ubicación, precio o run. `map_source_products` conserva la relación fuente -> producto y la cola de revisión.

## Autoridad y tráfico live

La política por defecto es **deny**.

```text
ACTIVE_AUTHORIZATION_IDS = []
LIVE_REQUESTS_CURRENT_RUN = 0
READY_FOR_LIVE = NO
SPS_TECHNICAL_CONTEXT = UNCONFIRMED
production_authority = false
catalog_accepted = false
```

Siempre verifica `PROJECT_STATE.md` y el código antes de asumir que esos valores cambiaron.

Sin autorización humana explícita y vigente están prohibidos nuevos HTTP/VTEX/GraphQL/Playwright/crawler/diagnostics/facet discovery/smoke/full crawl hacia La Colonia.

- ningún agente inventa un authorization ID;
- una autorización consumida no se reutiliza;
- una autorización para radiografía no autoriza otras operaciones;
- no ejecutes accidentalmente `--live`;
- Reviewer, Tests y Documentación permanecen offline salvo autorización distinta explícita.

Cuando una prueba live esté expresamente autorizada, conserva `concurrency=1`, pacing cerrado, cero retries ocultos salvo decisión revisada, presupuesto/deadline acotados y stop ante 403 persistente, 429, CAPTCHA, login obligatorio, datos personales obligatorios o riesgo de carga excesiva.

## Ubicación

No etiquetes un precio como SPS por inferencia.

`la_colonia_online` es un **contexto fuente raw**, no una ubicación comercial. Debe permanecer `location_status=unknown`, sin `location_confidence`. Nunca lo conviertas bajo el mismo ID en SPS/TGU/tienda.

Una ubicación comercial requiere:

1. granularidad conocida;
2. binding técnico verificable cuando la fuente permite selección;
3. evidencia coherente con la oferta;
4. `extraction_enabled=true` sólo después de cerrar las fronteras anteriores.

Para `la_colonia_sps`, mientras `granularity=unknown` o `technical_binding_confirmed=false`, la persistencia comercial debe fallar cerrada.

La radiografía preparada sólo puede proponer una transición. Si evidencia granularidad `store`, no colapses múltiples tiendas bajo una sola ciudad.

## Cloudflare

La ruta edge está en `edge/cloudflare/`. No flexibilices por conveniencia:

- hosts/path/métodos allowlisted;
- identidad repo/ref/workflow/environment/audience;
- destino físico, page size, order o traversal IDs;
- separación de private key y verificador;
- presupuesto/pacing/single-flight/replay/fencing;
- requisitos de tracing/Observability.

La sonda controlada ya produjo evidencia física contra origen propio. No autoriza La Colonia ni autoridad de catálogo. No la repitas sin una hipótesis nueva justificada.

El verifier actual de Observability usa discovery de traces y detalle `view: events`; el estado productivo de esa reconciliación se determina por una ejecución real, no por diagnósticos históricos ni por rebajar el contrato.

## Persistencia

La primera persistencia es Google Sheets; BigQuery queda para una fase posterior.

Reutiliza las ocho tablas comunes y las fronteras existentes:

```text
cfg_supermarkets
cfg_locations
dim_products
map_source_products
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

También reutiliza `InMemoryTabularStore`/`TabularBatch`, rehidratación/restauración, guard de autoridad, binding durable de replay, plan Sheets, transporte cerrado, adapter read-modify-write, bootstrap, loader read-only y batch comercial.

Reglas críticas:

- no crear tablas por supermercado;
- todo run final se registra;
- current/history sólo mutan con decisión aceptada y autoridad real;
- hashes/fingerprints prueban igualdad, no autoridad;
- runs rechazados/fallidos no alteran current/history ni materializan dimensión/mapping comercial;
- ausencia no implica baja;
- restaurar estado no autoriza un run nuevo;
- el loader de Sheets sigue read-only;
- no conectar persistencia productiva a un `catalog_accepted` caller-controlled.

El workbook físico puede tener un esquema anterior al lógico. Las migraciones de tabs gestionadas deben hacerse por la ruta segura de storage y comprobarse por read-back; no se arreglan manualmente para saltar el preflight productivo.

## Power BI

`power_bi_projection.py` es la frontera semántica read-only. No dupliques la definición de ahorro real en DAX, scripts o workflows. Dataset/refresh productivo sólo consume datos aceptados y durables.

## GitHub Actions

Antes de modificar workflows, lee `.github/workflows/AGENTS.md`.

- acciones externas fijadas a SHA completo;
- mínimo privilegio;
- checkout inmutable cuando aplica;
- `persist-credentials: false`;
- todo workflow SPS nuevo entra en `test_workflow_security_audit.py`;
- no debilites el auditor para hacer pasar una configuración;
- entrypoints capaces de tocar La Colonia permanecen bloqueados sin autorización explícita.

## Seguridad de datos

Nunca publiques cookies, Authorization headers, tokens, JWT, session IDs, orderForm IDs, direcciones, coordenadas, datos personales, private keys, spreadsheet IDs ni credenciales. Para valores opacos usa fingerprints sanitizados.

## Desarrollo y Git

1. verifica `main` y PRs concurrentes;
2. comprende tests/políticas del área;
3. crea rama técnica;
4. implementa el cambio mínimo;
5. ejecuta suite completa;
6. abre PR;
7. revisa diff, seguridad y threads;
8. fusiona con expected head SHA.

No uses force push, reset destructivo ni rebase destructivo.

## Pruebas

```bash
python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts
pytest precios-supermercados-sps/tests
```

La suite ejecuta también la suite Node canónica declarada en `edge/cloudflare/package.json` y la auditoría fail-closed de workflows. No declares un conteo de tests si no fue observado en un run real.
