# Instrucciones para agentes — Precios de Supermercados SPS

## Alcance y fuentes de verdad

- Proyecto: **Precios de Supermercados de San Pedro Sula**.
- Monorepositorio: `Portafolio`.
- Árbol principal: `precios-supermercados-sps/`.
- Workflows relacionados: `.github/workflows/`.

Antes de modificar, inspecciona `main`, PRs abiertos, CI y código. [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md) es la fuente canónica del estado operativo mutable y [`docs/arquitectura.md`](docs/arquitectura.md) describe la arquitectura estable. Runs, PRs, ramas y artifacts son evidencia/historia; no conceden autoridad comercial.

Si `PROJECT_STATE.md` contradice evidencia más nueva en `main`, corrige primero el documento mediante PR; no reviertas código nuevo por seguir un corte viejo.

## MVP primero — control contra sobrearquitectura

El objetivo es cerrar La Colonia San Pedro Sula end-to-end antes de comenzar otro supermercado. Progreso significa datos utilizables y confiables más cerca de existir, no cantidad de PRs, tests o capas.

Antes de crear una clase, adapter, verifier, workflow, tabla o documento nuevo, comprueba que resuelve un blocker actual, que no existe ya una pieza reutilizable y que la nueva frontera es realmente necesaria. Prefiere una implementación específica y clara para La Colonia cuando una plataforma genérica no tenga consumidor actual.

La simplificación no permite evadir controles del sitio, exceder presupuesto de tráfico, inventar ubicación SPS, exponer secretos/datos personales ni convertir evidencia técnica en autoridad comercial.

## Contratos protegidos

`RawProduct`, `NormalizedOffer` y `ValidatedOffer` son contratos protegidos. No se modifican sin necesidad demostrada, compatibilidad y pruebas.

Reglas comerciales protegidas:

- `current_price` es el precio efectivo observado;
- `reported_regular_price` es sólo el precio regular/tachado declarado por la tienda cuando existe evidencia separada;
- `previous_price` es derivado del histórico y nunca es alias de `reported_regular_price`;
- el ahorro real compara el `current_price` actual contra el `current_price` aceptado inmediatamente anterior;
- sin baseline confiable no se inventa ahorro;
- `is_promotion` conserva la señal promocional observada.

## Identidad de producto

Distingue siempre:

```text
source_product_id = identidad dentro de la fuente
product_id        = identidad comparable entre fuentes
offer_id          = supermercado + ubicación comercial + producto fuente
```

- precio, promoción, disponibilidad y fecha no forman parte de IDs estables;
- `source_product_id` y `offer_id` se recalculan en fronteras críticas;
- GTIN sólo crea identidad cross-supermercado si supera check digit y se normaliza a GTIN-14;
- si no existe identidad fuerte, conserva `prod_pending_*` + mapping pendiente;
- no elimines una observación porque el mapping esté pendiente;
- no colapses multipacks: conserva unidades, contenido por unidad y total sólo cuando el alcance esté demostrado.

Durante la primera fuente, `productos` puede conservar la identidad fuente y el `product_id` asociado. `product_mapping` formaliza la equivalencia fuente -> producto canónico y cobra especial importancia al incorporar un segundo supermercado. La identidad del producto no depende de ciudad; la ciudad pertenece a la observación de precio/inventario mediante `location_id`.

## Autonomía técnica y tráfico live

La autonomía del usuario permite continuar desarrollo local/GitHub/offline: auditoría, diseño, código, tests, documentación, PRs, CI y merge.

**No crea autorización permanente de tráfico live.** Antes de cualquier observación nueva contra un supermercado verifica autorización humana vigente y su alcance.

Reglas:

- una autorización histórica consumida no se reutiliza;
- no inventes Authorization IDs ni amplíes un marker;
- evidencia live ya obtenida puede reutilizarse offline;
- si falta autorización live, continúa todo lo posible offline y detente sólo en esa frontera real;
- con autorización read-only, conserva concurrencia/pacing/presupuesto acotados y detente ante 403 persistente, 429, CAPTCHA, login obligatorio o riesgo de carga excesiva;
- no evadas controles anti-bot.

Una autorización read-only nunca cubre automáticamente credenciales, billing, login de usuario, mutación externa, compras, despliegues con coste, decisiones manuales de mapping sin evidencia o escrituras productivas no autorizadas.

Los runs read-only no conceden por sí solos `production_authority`, `catalog_accepted` ni autoridad de persistencia.

## Ubicación

No etiquetes un precio como SPS por inferencia.

`la_colonia_online` es un **contexto fuente raw**, no una ubicación comercial. Debe permanecer `location_status=unknown`, sin `location_confidence`. Nunca lo conviertas bajo el mismo ID en SPS/TGU/tienda.

Una ubicación comercial requiere granularidad conocida, binding técnico verificable cuando la fuente permite selección y evidencia coherente. `la_colonia_sps` posee binding técnico de ciudad confirmado. `extraction_enabled` permanece separado de esa evidencia.

Fingerprint SPS protegido:

```text
d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
```

## Catálogo y normalización actuales

El catálogo completo aceptado técnicamente del intento #15 contiene 9,439 SKU y 9,437 productos. La normalización de presentación del snapshot está cerrada en 9,439/9,439 con cero pendientes.

Conserva siempre valor fuente y valor normalizado por separado. Overrides revisados deben estar ligados a identidad/firma fuente y fallar cerrado si esa firma cambia.

## Inventario

`availability=unknown` no se interpreta como agotado por inferencia. Antes de confiar en inventario histórico se debe conservar como dato de primera clase, como mínimo:

```text
available_quantity_observed
availability
availability_evidence
seller_id
```

Verifica que la cantidad corresponda al seller seleccionado. Describe la cantidad como observada/reportada por la fuente, no como inventario físico o venta exacta salvo evidencia adicional.

## Persistencia — BigQuery seleccionado

**BigQuery es el backend persistente seleccionado. Google Sheets queda fuera del camino objetivo.**

La lógica de dominio, current/history, replay, rehidratación y validación permanece backend-neutral. El código legado de Google Sheets puede coexistir temporalmente durante la migración, pero no debe recibir nueva funcionalidad, no debe ejecutarse para persistir el catálogo y sus entrypoints deben quedar neutralizados antes de la primera persistencia real BigQuery.

Tablas objetivo mínimas:

```text
supermarkets
locations
productos
precios_historicos
inventario_historico
scrape_runs
quality_events
normalization_overrides
product_mapping
```

Reglas críticas:

- no crear tablas por supermercado;
- `locations` relaciona `location_id` con supermercado y ciudad;
- `productos` no duplica ciudad;
- `precios_historicos` e `inventario_historico` llevan `supermarket_id`, `location_id` e identidad de producto;
- usar nombres explícitos `current_price` y `reported_regular_price`; no una columna ambigua `price/precio`;
- todo run final debe poder registrarse;
- runs rechazados/fallidos no alteran estado comercial aceptado;
- ausencia de producto no implica baja ni agotado;
- hashes/fingerprints prueban igualdad, no autoridad;
- restaurar estado no autoriza un run nuevo;
- una tabla nueva necesita grain, key, lifecycle y consumidor actuales.

Para BigQuery, prioriza tablas de observaciones históricas aptas para análisis temporal. Precio e inventario pueden registrar una observación por run exitoso; los cambios/estado actual se derivan con SQL/views, mientras el motor comercial backend-neutral conserva validación e idempotencia.

Antes de cualquier escritura cloud real, detente en la frontera de proyecto/dataset/credenciales/billing si no están ya disponibles y autorizados.

## Visualización — Dash + Plotly

La aplicación objetivo es **Python Dash + Plotly**. Power BI ya no es el destino del producto. No añadas funcionalidad nueva a `power_bi_projection.py`; puede permanecer temporalmente como código legado hasta que sea seguro retirarlo.

La aplicación debe consumir únicamente datos persistidos/validados y permitir progresivamente búsqueda, precio actual/anterior, variaciones, historial, filtros, disponibilidad, calidad y comparación entre supermercados cuando exista una segunda fuente.

## Cloudflare

La ruta edge existente vive en `edge/cloudflare/`. No flexibilices allowlists, identidad OIDC, presupuesto/pacing, single-flight/replay/fencing, claves o Observability por conveniencia. No repitas una sonda física sin hipótesis nueva y autorización live cuando corresponda.

## GitHub Actions

Antes de modificar workflows, lee `.github/workflows/AGENTS.md`.

- acciones externas fijadas a SHA completo;
- mínimo privilegio;
- checkout inmutable cuando aplica;
- `persist-credentials: false`;
- workflows SPS nuevos entran en `test_workflow_security_audit.py`;
- no debilites el auditor para hacer pasar una configuración;
- entrypoints live quedan fail-closed sin autorización vigente;
- entrypoints con secretos, mutación externa, costes o autoridad comercial siguen fail-closed hasta cerrar su frontera.

## Seguridad de datos

Nunca publiques cookies, Authorization headers, tokens, JWT, session IDs, orderForm IDs, direcciones, coordenadas, datos personales, private keys, spreadsheet IDs ni credenciales. Para valores opacos usa fingerprints sanitizados.

## Desarrollo y Git

1. verifica `main`, PRs concurrentes y `PROJECT_STATE.md`;
2. comprende tests/políticas del área;
3. crea rama técnica;
4. implementa el cambio mínimo;
5. ejecuta suite completa;
6. abre PR;
7. revisa diff, CI, seguridad, comentarios y threads;
8. fusiona sólo con expected head SHA.

No uses force push, reset destructivo ni rebase destructivo.

## Pruebas

```bash
python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts
pytest precios-supermercados-sps/tests
```

No declares conteos de tests que no hayas observado en un run real.
