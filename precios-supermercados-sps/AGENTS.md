# Instrucciones para agentes — Precios de Supermercados SPS

## Alcance del proyecto

- Proyecto: **Precios de Supermercados de San Pedro Sula**.
- Monorepositorio: `Portafolio`.
- Código y documentación del proyecto: `precios-supermercados-sps/`.
- Workflows relacionados: `.github/workflows/`.
- Estas instrucciones aplican a todo el árbol bajo `precios-supermercados-sps/`.

## Fuente de verdad

- Inspecciona el repositorio, Git y las pruebas antes de asumir el estado actual.
- No reconstruyas componentes existentes ni crees implementaciones, contratos o estructuras paralelas.
- Reutiliza los contratos y módulos existentes.
- Distingue explícitamente hechos verificados, contexto previo no verificado, inferencias e hipótesis.
- La documentación histórica no sustituye la verificación del código y Git actuales.

## Contratos protegidos

`RawProduct`, `NormalizedOffer` y `ValidatedOffer` son contratos protegidos. No los modifiques sin autorización humana explícita para hacerlo.

## Gobernanza de La Colonia

- PR funcional: **#7 — Valida el recorrido completo del catálogo de La Colonia**.
- Rama funcional: `feature/la-colonia-full-crawl-validation`.
- Mantén PR #7 abierto y en draft hasta autorización explícita. No lo fusiones ni habilites auto-merge.
- **PR #17 — observabilidad del facet discovery** debe permanecer congelado salvo una tarea explícita dedicada a él. Desde tareas de PR #7 no lo modifiques, integres ni fusiones.

## Autorizaciones y tráfico live

Estado vigente:

- `SPS-context-and-root-facets-001`: consumida; no reutilizar ni repetir.
- `SPS-context-and-root-facets-002`: no creada y no autorizada.
- `ACTIVE_AUTHORIZATION_IDS`: vacío; no hay autorizaciones live activas.
- `network-to-lacolonia`: prohibido por defecto.

Reglas obligatorias:

- Ningún agente puede inventar un authorization ID. Cumplir el formato no equivale a estar autorizado.
- Solo una instrucción humana explícita puede habilitar una autorización live vigente.
- Una autorización consumida no puede reutilizarse.
- Solo un agente o hilo puede asumir el rol Live para una prueba expresamente autorizada.
- Reviewer, Tests y Documentación permanecen offline.
- No ejecutes accidentalmente `--live` ni tráfico a La Colonia.

Cuando exista autorización live explícita, conserva como mínimo:

- `concurrency = 1`;
- `minimum delay = 1.5 s`;
- `max retries = 1`;
- el presupuesto específico y cerrado de la prueba.

Detén el intento ante `403` persistente, `429`, CAPTCHA, autenticación obligatoria, dirección personal obligatoria, GPS preciso obligatorio o riesgo de carga excesiva.

Sin autorización explícita están prohibidos: full crawl, recorrido completo por categorías, `baseline500-003`, `validation500`, facet discovery live, repetición de diagnósticos consumidos, persistencia comercial, historial, ejecución diaria, Google Sheets, BigQuery y Power BI.

## Archivo operacional protegido

`precios-supermercados-sps/.automation/la-colonia-live-command.json` no se modifica salvo tarea explícita. La existencia de una solicitud histórica en ese archivo no autoriza procesarla, repetirla ni sustituirla.

## Seguridad

Nunca publiques ni conserves sin sanitizar: cookies, `Authorization`, tokens, JWT, session IDs, orderForm IDs, direcciones, coordenadas, datos personales o credenciales.

## Desarrollo y Git

Antes de modificar archivos:

1. inspecciona `git status`;
2. confirma la rama y el HEAD;
3. confirma el estado del working tree;
4. comprende las pruebas existentes y el alcance autorizado.

No cambies de rama automáticamente. No hagas rebase, reset, merge, push ni operaciones sobre PRs sin autorización expresa. Coordina cualquier trabajo concurrente; agentes secundarios no deben modificar simultáneamente la misma rama principal.

## Pruebas

Aplica la validación proporcional al tipo de cambio y siempre sin red externa no autorizada.

### Cambios solo documentales

Cuando únicamente cambien `docs/`, `AGENTS.md`, `README` u otros archivos Markdown, y no cambien código, tests, fixtures, requirements, configuración ejecutable o workflows:

- revisa `git diff`;
- verifica que no existan cambios fuera de alcance;
- ejecuta pruebas solo si la documentación modifica o afirma comportamiento ejecutable que necesite comprobarse;
- no declares CI verde si no fue ejecutada.

### Cambios Python o lógica ejecutable

Ejecuta:

```bash
python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts
pytest precios-supermercados-sps/tests
```

### Cambios del diagnóstico Playwright

Además de la validación Python, ejecuta las pruebas específicas de Playwright/browser correspondientes. Estas pruebas deben usar contenido sintético, archivos locales o loopback e impedir tráfico externo, salvo autorización live explícita y vigente.

Si la máquina local no tiene Playwright o navegador:

- no lo instales automáticamente salvo autorización de la tarea;
- ejecuta las pruebas disponibles;
- registra exactamente las pruebas omitidas o bloqueadas y la causa;
- no declares la suite completa verde;
- distingue el resultado local del resultado de CI.

### Cambios de workflows

No ejecutes workflows live. Realiza la validación estática/offline apropiada y deja la ejecución remota a la CI normal autorizada.

## Roles multiagente

- **Principal:** integra decisiones y cambios autorizados.
- **Reviewer:** analiza y revisa; offline por defecto.
- **Tests:** ejecuta validaciones offline; no live.
- **Live:** solo existe para una tarea explícitamente autorizada y debe ser el único agente/hilo con tráfico live.

## Documentación y cierre

Actualiza la documentación cuando cambie una decisión técnica. No presentes documentación histórica como estado actual sin verificarla.

Al cerrar cada tarea relevante informa:

- estado inicial;
- archivos modificados;
- pruebas ejecutadas y resultado exacto;
- tráfico live realizado o `0`;
- estado de autorizaciones;
- estado de PR #7 y PR #17;
- siguiente paso propuesto;
- si el siguiente paso fue o no ejecutado.
