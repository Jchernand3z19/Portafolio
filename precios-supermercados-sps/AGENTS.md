# Instrucciones para agentes — Precios de Supermercados SPS

## Alcance y fuentes de verdad

- Proyecto: **Precios de Supermercados de San Pedro Sula**.
- Monorepositorio: `Portafolio`.
- Árbol principal: `precios-supermercados-sps/`.
- Workflows relacionados: `.github/workflows/`.

Antes de modificar, inspecciona `main`, PRs abiertos, CI y código. [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md) es la fuente canónica del estado operativo mutable y [`docs/arquitectura.md`](docs/arquitectura.md) describe la arquitectura estable. Runs, PRs, ramas y artifacts son evidencia/historia; no conceden autoridad comercial.

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

`dim_products` y `map_source_products` son contratos lógicos para identidad canónica cross-source. No deben materializarse físicamente sólo por previsión: se activan cuando exista una segunda fuente o un consumidor real que requiera equivalencias. `dim_products` no debe adquirir columnas específicas de supermercado, ubicación, precio o run; `map_source_products` conserva la relación fuente -> producto y la cola de revisión cuando esa capacidad se active.

## Autonomía técnica y tráfico live

La instrucción de autonomía del usuario autoriza continuar el desarrollo técnico del proyecto sin pedir aprobación para trabajo local/GitHub/offline: auditoría, diseño, código, tests, documentación, PRs, CI, merge y preparación de mecanismos fail-closed.

**Esa autonomía no se convierte por inferencia en una autorización permanente de tráfico live.** Antes de una observación nueva contra un supermercado verifica la autorización humana vigente y su alcance concreto.

Reglas:

- una autorización histórica consumida/cerrada no se reutiliza;
- no inventes Authorization IDs ni amplíes un marker a una fase distinta;
- binding, facet discovery, smoke de catálogo y full crawl son observaciones distintas salvo que la instrucción humana las cubra expresamente;
- la evidencia live ya obtenida puede reutilizarse offline sin repetir tráfico;
- si el alcance live requerido no está autorizado, continúa todo lo posible offline y detente únicamente en esa frontera real.

Cuando exista autorización explícita para tráfico público read-only, conserva `concurrency=1` cuando aplique, pacing razonable, presupuesto/deadline acotados y stop ante 403 persistente, 429, CAPTCHA, login obligatorio, datos personales obligatorios o riesgo de carga excesiva. No evadas controles anti-bot ni aumentes carga para forzar un resultado.

Una autorización read-only nunca cubre automáticamente:

- credenciales, secretos, cuentas o permisos que el agente no posee;
- billing, compras o gasto nuevo;
- login obligatorio con una cuenta del usuario;
- modificar datos o configuración en sistemas externos ajenos a GitHub del proyecto;
- checkout, pedidos, reservas, formularios que creen estado del lado servidor o cualquier transacción;
- despliegues productivos nuevos que creen coste o cambien infraestructura externa fuera de la ruta expresamente autorizada;
- decisiones manuales reales de mapping de producto cuando no puedan resolverse determinísticamente;
- trabajo puramente manual dentro de Power BI.

Los runs read-only no conceden por sí solos `production_authority`, `catalog_accepted` ni autoridad para persistir estado comercial. Esas fronteras siguen gobernadas por evidencia y contratos del producto.

## Ubicación

No etiquetes un precio como SPS por inferencia.

`la_colonia_online` es un **contexto fuente raw**, no una ubicación comercial. Debe permanecer `location_status=unknown`, sin `location_confidence`. Nunca lo conviertas bajo el mismo ID en SPS/TGU/tienda.

Una ubicación comercial requiere:

1. granularidad conocida;
2. binding técnico verificable cuando la fuente permite selección;
3. evidencia coherente con la oferta;
4. `extraction_enabled=true` sólo después de cerrar las fronteras anteriores.

`la_colonia_sps` ya posee binding técnico de ciudad confirmado por evidencia persistida, pero `extraction_enabled` sigue `false` hasta cerrar la aceptación del catálogo.

La radiografía puede proponer una transición. Si evidencia granularidad `store`, no colapses múltiples tiendas bajo una sola ciudad.

## Cloudflare

La ruta edge está en `edge/cloudflare/`. No flexibilices por conveniencia:

- hosts/path/métodos allowlisted;
- identidad repo/ref/workflow/environment/audience;
- destino físico, page size, order o traversal IDs;
- separación de private key y verificador;
- presupuesto/pacing/single-flight/replay/fencing;
- requisitos de tracing/Observability.

La sonda controlada ya produjo evidencia física contra origen propio. No la repitas sin una hipótesis nueva justificada y, cuando implique tráfico externo nuevo, sin la autorización live que corresponda.

El verifier actual de Observability usa discovery de traces y detalle `view: events`; el estado productivo de esa reconciliación se determina por una ejecución real, no por diagnósticos históricos ni por rebajar el contrato.

## Persistencia

La primera persistencia es Google Sheets; BigQuery queda para una fase posterior.

El modelo lógico conserva capacidades de identidad cross-source, pero el backend físico actual materializa únicamente seis tablas con grain/lifecycle/consumidor ya justificado:

```text
cfg_supermarkets
cfg_locations
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

`dim_products` y `map_source_products` permanecen diferidas hasta que exista necesidad cross-source real. No se crean, escriben ni leen como tabs activos de Google Sheets durante la fase de una sola fuente. La identidad fuente y `product_id` siguen dentro de current/history, por lo que la futura activación puede reconstruirse sin inventar observaciones.

También reutiliza `InMemoryTabularStore`/`TabularBatch`, rehidratación/restauración, guard de autoridad, binding durable de replay, plan Sheets, transporte cerrado, adapter read-modify-write, bootstrap, loader read-only y batch comercial.

Reglas críticas:

- no crear tablas por supermercado;
- antes de crear/materializar una tabla, justificar grain, key, lifecycle y consumidor; concepto futuro no basta;
- todo run final se registra;
- current/history sólo mutan con decisión aceptada y autoridad real;
- hashes/fingerprints prueban igualdad, no autoridad;
- runs rechazados/fallidos no alteran current/history;
- ausencia no implica baja;
- restaurar estado no autoriza un run nuevo;
- el loader de Sheets sigue read-only;
- no conectar persistencia productiva a un `catalog_accepted` caller-controlled.

El workbook físico puede tener tabs legados o diferidos. El adapter sólo gestiona el contrato físico activo y debe preservar tabs ajenos; una limpieza/migración real se hace explícitamente, con preflight y read-back, nunca ocultándola dentro de una escritura comercial.

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
- entrypoints live quedan fail-closed cuando no existe autorización vigente para ese alcance;
- entrypoints con secretos, mutación externa, costes o autoridad comercial siguen fail-closed hasta cerrar su frontera correspondiente.

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
