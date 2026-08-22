# Instrucciones para agentes — Precios de Supermercados SPS

## Alcance

- Proyecto: **Precios de Supermercados de San Pedro Sula**.
- Monorepositorio: `Portafolio`.
- Árbol principal: `precios-supermercados-sps/`.
- Workflows relacionados: `.github/workflows/`.

## Fuentes de verdad

1. Inspecciona `main`, PRs abiertos, CI y código antes de modificar.
2. [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md) es la fuente canónica del **estado operativo mutable**.
3. [`docs/arquitectura.md`](docs/arquitectura.md) describe la **arquitectura estable**.
4. Runs, cuerpos de PR, comentarios, ramas y artifacts son evidencia/historia; no conceden autoridad.
5. No reconstruyas componentes ya integrados ni crees contratos paralelos sin necesidad demostrada.

Si un dato de `PROJECT_STATE.md` contradice evidencia más nueva en `main`, corrige primero el documento mediante PR; no uses el documento viejo para revertir código nuevo.

## Contratos protegidos

`RawProduct`, `NormalizedOffer` y `ValidatedOffer` son contratos protegidos. No se modifican sin tarea explícita, necesidad demostrada, compatibilidad y pruebas.

Regla comercial protegida:

- `reported_regular_price` es sólo dato declarado por la tienda;
- el ahorro real compara el `current_price` actual contra el `current_price` del periodo histórico aceptado inmediatamente anterior;
- sin baseline confiable no se inventa ahorro;
- Power BI consume esta semántica desde la proyección común; no debe redefinirla en DAX.

## Autoridad y tráfico live

La política por defecto es **deny**.

Al corte vigente:

```text
ACTIVE_AUTHORIZATION_IDS = []
READY_FOR_LIVE = NO
SPS_TECHNICAL_CONTEXT = UNCONFIRMED
production_authority = false
catalog_accepted = false
```

Siempre verifica `docs/PROJECT_STATE.md` y el código antes de asumir que esos valores cambiaron.

Reglas obligatorias:

- ningún agente inventa un authorization ID;
- cumplir un formato no significa estar autorizado;
- una autorización consumida no se reutiliza;
- una autorización humana debe ser explícita, vigente y limitada al objetivo descrito;
- una autorización para radiografía de ubicación no autoriza smoke, facets, GraphQL replay, crawl ni persistencia;
- no ejecutes accidentalmente `--live`;
- Reviewer, Tests y Documentación permanecen offline salvo instrucción distinta explícita.

Sin autorización explícita están prohibidos nuevos HTTP/VTEX/GraphQL/Playwright/crawler/diagnostics/facet discovery/smoke/full crawl hacia La Colonia.

Cuando una prueba live esté expresamente autorizada, conserva como mínimo:

- `concurrency = 1`;
- pacing cerrado;
- `max_retries = 0` salvo una decisión específica revisada;
- presupuesto/deadline acotados;
- stop ante `403` persistente, `429`, CAPTCHA, login obligatorio, dirección/GPS personal obligatorio o riesgo de carga excesiva.

## Ubicaciones

No etiquetes un precio como SPS por inferencia.

Una ubicación comercial requiere:

1. granularidad conocida (`city`, `store` u otra explícitamente modelada);
2. binding técnico verificable con la fuente cuando ésta permite seleccionar ubicación;
3. evidencia de ubicación coherente con la oferta;
4. `extraction_enabled=true` sólo después de las fronteras anteriores.

Para La Colonia SPS, mientras `granularity=unknown` o `technical_binding_confirmed=false`, la persistencia de ofertas debe fallar cerrada.

La radiografía preparada en PR #145–#148 sólo puede proponer una transición; nunca habilita extracción automáticamente. Si evidencia `store`, no colapses varias tiendas bajo una ubicación ciudad.

## Cloudflare

La ruta productiva/edge de La Colonia está en `edge/cloudflare/` y su política no se flexibiliza para facilitar pruebas.

Prohibido sin tarea explícita y revisión de seguridad:

- ampliar hosts/path/métodos allowlisted;
- convertir repo/ref/workflow/environment/audience en inputs del caller;
- permitir que caller elija destino físico, URL, page size, order o traversal IDs fuera del contrato canónico;
- compartir private keys Ed25519 con GitHub;
- aceptar una firma offline como `production_authority`;
- transformar un PASS parcial de sonda en autoridad de catálogo.

### Sonda controlada

La sonda no-La-Colonia ya produjo evidencia física de OIDC/DO/fetch/firma. Eso **no** autoriza La Colonia ni cierra por sí solo la reconciliación estricta de Workers Observability.

No repitas la sonda física sólo para volver a demostrar la misma evidencia. Repetirla requiere una razón explícita (cambio de infraestructura, nueva hipótesis o autorización correspondiente) y debe seguir `docs/cloudflare-controlled-probe-runbook.md`.

La private key de sonda/productiva nunca se publica, pega en chat, logs, artifacts ni GitHub.

## Persistencia

La primera persistencia prevista es Google Sheets; BigQuery queda para una fase posterior estable.

Fronteras ya existentes que deben reutilizarse:

- tablas comunes y serializers;
- `InMemoryTabularStore` / `TabularBatch` como referencia atómica;
- rehidratación durable current/history;
- restauración del motor entre runners con reserva de run IDs terminales;
- guard de persistencia que bloquea decisiones caller-controlled mutantes;
- binding durable `crev1_` para reconocer igualdad/replay sin conceder autoridad;
- plan `spreadsheets.batchUpdate`;
- transporte Sheets cerrado;
- adapter read-modify-write;
- bootstrap manual;
- loader read-only Google Sheets → snapshot → rehidratación → estado restaurado;
- batch comercial previo al adapter.

Reglas críticas:

- no crear una pestaña por supermercado si la tabla común ya resuelve la dimensión;
- cada run final debe registrarse aunque no haya cambios;
- current/history sólo mutan con decisión comercial aceptada y evidencia autoritativa real;
- un hash/fingerprint prueba igualdad de replay, **no autoridad**;
- replay idéntico no duplica; divergencia falla;
- runs rechazados/fallidos no alteran current/history;
- ausencia en un payload no implica baja;
- restaurar estado no autoriza una ejecución nueva;
- el loader de Sheets es read-only y no debe adquirir capacidades de escritura;
- no conectar persistencia productiva a un `catalog_accepted` caller-controlled.

## Power BI

`power_bi_projection.py` es la frontera semántica read-only para el futuro dataset.

- reutiliza la lógica comercial de ahorro real existente;
- separa `reported_regular_price` del baseline histórico aceptado;
- expone `price_direction`, disponibilidad, promoción, ubicación y `review_status`;
- preserva tipos numéricos/temporales hasta la frontera de consumo;
- no persiste, no scrapea y no concede autoridad;
- el dataset/refresh productivo sólo puede consumir datos aceptados y durables.

No implementes una segunda definición de ahorro real en DAX, scripts o workflows.

## GitHub Actions

Antes de modificar workflows, lee `.github/workflows/AGENTS.md`.

- acciones externas fijadas a SHA completo;
- mínimo privilegio;
- checkout inmutable cuando aplica;
- `persist-credentials: false`;
- todo workflow SPS nuevo debe incorporarse a `test_workflow_security_audit.py`;
- no debilites el auditor para hacer pasar una configuración nueva;
- workflows capaces de tocar La Colonia permanecen bloqueados hasta autorización explícita y cambio versionado correspondiente.

## Seguridad de datos

Nunca publiques cookies, `Authorization`, tokens, JWT, session IDs, orderForm IDs, direcciones, coordenadas, datos personales, private keys o credenciales.

Cuando una observación técnica necesite distinguir valores opacos, usa fingerprints sanitizados en vez de reflejar el valor fuente.

## Desarrollo y Git

Antes de modificar:

1. verifica `main` y SHA base;
2. revisa PRs/cambios concurrentes;
3. comprende tests/políticas del área;
4. crea rama técnica;
5. implementa el cambio mínimo;
6. ejecuta suite relevante/completa;
7. abre PR;
8. revisa diff, seguridad y threads;
9. fusiona con expected head SHA.

No uses force push, reset destructivo ni rebase destructivo.

## Pruebas

Código Python/lógica ejecutable:

```bash
python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts
pytest precios-supermercados-sps/tests
```

La suite cubre también componentes Node de Cloudflare y auditoría fail-closed de workflows.

No declares un conteo de tests si no fue observado en un run real. El conteo vigente se registra en `docs/PROJECT_STATE.md`.

## Roles multiagente

- **Principal:** integra decisiones y cambios autorizados.
- **Reviewer:** revisión adversarial offline.
- **Tests:** validación offline.
- **Live:** sólo durante una autorización humana explícita y limitada.
