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

### Gate obligatorio de simplicidad

Antes de introducir **cualquier** módulo, abstracción, servicio, dependencia, protocolo, capa de confianza o mecanismo criptográfico nuevo, responde internamente estas cuatro preguntas:

1. ¿Cuál es el blocker **actual** que impide avanzar el producto?
2. ¿Cuál es el cambio más pequeño que lo resuelve con código existente?
3. ¿Qué consumidor **actual** necesita la nueva abstracción? Dos consumidores hipotéticos futuros no cuentan.
4. ¿Qué fallo real y demostrado evita la complejidad adicional?

Si no hay respuestas concretas, **no se crea la nueva capa**.

Reglas adicionales para el MVP:

- una abstracción genérica necesita al menos dos consumidores actuales; con uno solo, implementa la solución específica;
- no introducir criptografía, keyrings, attestation frameworks, identity planes, trust services ni PKI salvo que una plataforma externa lo exija, exista una amenaza demostrada que no pueda resolverse más simple o el usuario lo pida explícitamente;
- no crear un servicio, workflow o tabla para representar un estado que puede vivir como una decisión/configuración versionada;
- no convertir un control operativo simple en un subsistema de seguridad independiente;
- si una solución propuesta añade más módulos/capas que el problema que resuelve, vuelve a comparar contra la alternativa mínima antes de implementarla;
- para el snapshot inicial ya obtenido de La Colonia, una aprobación versionada y auditable del artifact conocido es suficiente; no requiere una infraestructura criptográfica propia;
- `extraction_enabled` controla **tráfico futuro**, no invalida automáticamente evidencia histórica ya obtenida y verificada.

La simplificación no permite evadir controles del sitio, exceder presupuesto de tráfico, inventar ubicación SPS, exponer secretos/datos personales ni aceptar evidencia que falle validaciones técnicas existentes.

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

Durante la primera fuente, `source_products` conserva la identidad fuente y el `product_id` asociado. La separación `products` / `source_products` formaliza la equivalencia fuente -> producto canónico y cobra especial importancia al incorporar un segundo supermercado. La identidad del producto no depende de ciudad; la ciudad pertenece a la oferta mediante `location_id`.

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

Un run read-only no concede por sí solo aceptación comercial; un snapshot histórico puede aceptarse únicamente mediante una decisión versionada que lo identifique de forma exacta y después de que sus validaciones técnicas ya hayan pasado.

## Ubicación

No etiquetes un precio como SPS por inferencia.

`la_colonia_online` es un **contexto fuente raw**, no una ubicación comercial. Debe permanecer `location_status=unknown`, sin `location_confidence`. Nunca lo conviertas bajo el mismo ID en SPS/TGU/tienda.

Una ubicación comercial requiere granularidad conocida, binding técnico verificable cuando la fuente permite selección y evidencia coherente. `la_colonia_sps` posee binding técnico de ciudad confirmado. `extraction_enabled` permanece separado de esa evidencia.

Fingerprint SPS protegido:

```text
d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
```

## Catálogo y normalización actuales

El catálogo completo aceptado técnicamente del intento #15 contiene 9,439 SKU y 9,437 productos. El pipeline produce 9,439 ofertas normalizadas, pero **no** todas tienen la presentación estructurada resuelta: 8,436 quedaron normalizadas y 1,003 permanecen `needs_review`. En identidad canónica, 8,965 SKU están listos por GTIN válido y 474 mantienen mapping pendiente. No conviertas pendientes en valores normalizados ni inventes equivalencias para cerrar conteos.

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

## Persistencia — Turso / SQLite seleccionado

**Turso es el backend persistente operativo seleccionado.** SQLite `:memory:` usa el mismo contrato físico para pruebas offline. BigQuery queda como implementación legada/futura preservada, pero no como ruta productiva activa; Google Sheets permanece retirado/fail-closed.

La lógica de dominio, current/history, replay, rehidratación y validación permanece backend-neutral. No dupliques esa lógica dentro del adapter Turso.

Tablas operativas mínimas:

```text
supermarkets
locations
products
source_products
offers_current
offer_history
scrape_runs
quality_events
normalization_overrides
```

Reglas críticas:

- no crear tablas por supermercado;
- `locations` relaciona `location_id` con supermercado y ciudad;
- `products` representa identidad canónica y `source_products` la identidad dentro de la fuente;
- `offers_current` conserva el último estado aceptado por oferta;
- `offer_history` abre un periodo inicial y sólo agrega/cierra periodos ante cambios comerciales reales; una confirmación idéntica posterior no crea historia redundante;
- cada ejecución terminal se registra en `scrape_runs`, aunque no haya cambios comerciales;
- precio se conserva con semántica `current_price` / `reported_regular_price` y además en minor units enteras para consultas monetarias físicas seguras;
- `unknown` permanece `unknown`; `seller_id`, cantidad y evidencia quedan `NULL`/no exactos mientras el snapshot no los demuestre;
- runs rechazados/fallidos no alteran estado comercial aceptado;
- ausencia de producto no implica baja ni agotado;
- replay exacto es idempotente y el mismo `scrape_run_id` con fingerprint divergente falla cerrado;
- restaurar/rehidratar estado no autoriza un run nuevo;
- una tabla nueva necesita grain, key, lifecycle y consumidor actuales.

La primera carga de La Colonia usa exclusivamente el snapshot aprobado por SHA-256 exacto; nunca dispara scraping live. Antes de una escritura Turso real, valida el snapshot completo contra SQLite y reconcilia read-back. Las credenciales productivas se leen sólo desde `TURSO_DATABASE_URL` y `TURSO_AUTH_TOKEN`; nunca se guardan en el repositorio ni se pegan en documentación.

El workflow legado de primera carga BigQuery debe permanecer fail-closed mientras Turso sea el backend activo. No habilites escrituras BigQuery por inferencia ni por disponibilidad futura de billing.

## Visualización — Dash + Plotly

La aplicación objetivo es **Python Dash + Plotly**. Power BI ya no es el destino del producto. No añadas funcionalidad nueva a `power_bi_projection.py`; puede permanecer temporalmente como código legado hasta que sea seguro retirarlo.

La visualización no es prioridad hasta cerrar La Colonia end-to-end: persistencia durable, inventario suficientemente sustentado, ejecución diaria estable y varias ejecuciones consecutivas verificadas. La aplicación deberá consumir únicamente datos persistidos/validados.

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
- entrypoints con secretos, mutación externa o costes siguen fail-closed hasta cerrar su frontera.

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
