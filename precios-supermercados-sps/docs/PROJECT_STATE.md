# PROJECT_STATE — Precios Supermercados SPS

Estado canónico resumido. Para diseño y contratos detallados, ver `docs/arquitectura.md`. PRs, comentarios, logs y ramas históricas son evidencia, no autoridad operativa.

## MAIN

- Corte: 2026-08-22 (America/Tegucigalpa).
- `main` observado al iniciar este corte documental: `efdd37ade3ab55ea0aa48403e96adf9a2e9aa929`.
- GATE-17: `PASS_PRODUCTIVE_EVIDENCE`.
- `main` protegida.

## LAST VALIDATION

- Suite más reciente observada antes de este corte: `1265/1265 PASS` + `compileall PASS` en PR #123.
- Los cambios posteriores de marcador no introducen lógica de producto; su CI se valida antes de merge.
- Tráfico nuevo a La Colonia durante este trabajo: `0`.

## DONE

- Contratos protegidos `RawProduct`, `NormalizedOffer`, `ValidatedOffer`.
- Identificadores deterministas y `state_hash`.
- Separación entre readiness técnica, aceptación de catálogo y autoridad productiva.

## DONE_OFFLINE

- Extractor VTEX de La Colonia y normalización/validación sobre fixtures.
- Facets, particiones, coverage, reconciliación, completitud y detección adversarial de gaps/truncamiento/repeticiones.
- Structural discovery autenticado.
- Plan, transporte y finalización autenticados de catálogo.
- Clientes Python de gateway/receipts/provenance y verificadores Cloudflare.
- Worker productivo, Durable Object, OIDC, replay/fencing, receipts Ed25519 y tracing implementados y probados offline.
- Current/history backend-neutral, idempotencia, cronología, snapshots y pricing histórico.
- Auditoría fail-closed de workflows y acciones externas fijadas por SHA.

## DONE_PRODUCTIVE

- GATE-17 / protección de `main`: enforcement real demostrado.
- Infraestructura de sonda Cloudflare no-La-Colonia desplegada y ejecutada físicamente al menos una vez.
- Run físico controlado de referencia: `32551882793`; el job de sonda física completó correctamente.
- Evidencia firmada del intento 1 verificada fuera del Worker en el run verifier-only `32552932554`: firma Ed25519, bytes e identidad del artefacto válidos.
- El trigger diagnóstico por `push` protegido de `main` quedó demostrado mediante commit status `precios-sps/observability-shape-trigger` sobre el merge de PR #124.

Lo anterior no concede autoridad sobre La Colonia ni aceptación comercial de catálogo.

## PARTIAL

- Workers Observability de la sonda: transporte, consultas, parsers y verificadores existen; la reconciliación productiva completa sigue abierta por la forma real de la telemetría observada.
- La última verificación productiva conocida llegó hasta evidencia criptográfica válida y falló en reconciliación Observability con `probe_trace_http_status_mismatch`.
- Diagnóstico sanitizado de forma de telemetría: mecanismo de trigger productivo ya demostrado; la captura/reconciliación final del shape sigue en curso.
- Trusted collector productivo de La Colonia: preparado offline, sin autoridad productiva demostrada contra la fuente.

## BLOCKED

- `SPS_TECHNICAL_CONTEXT = UNCONFIRMED` — requiere observación live mínima autorizada de La Colonia.
- Aceptación exacta de catálogo — requiere autoridad productiva y validación live autorizada.
- Collector productivo de La Colonia — no puede declararse autoritativo con evidencia de la sonda controlada.

## READY_TO_IMPLEMENT

- Corregir y cerrar la reconciliación productiva de Workers Observability usando únicamente la evidencia física existente y lecturas sanitizadas permitidas.
- Sincronizar documentación obsoleta con este estado real.
- Después de cerrar la frontera de autoridad, diseñar persistencia durable que consuma una decisión autoritativa tipada; no un booleano caller-controlled.

## LIVE

```text
READY_FOR_LIVE = NO
ACTIVE_AUTHORIZATION_IDS = []
NETWORK_TO_LA_COLONIA = DENY_BY_DEFAULT
```

- `SPS-context-and-root-facets-001`: consumida; no reutilizar.
- `SPS-context-and-root-facets-002`: no autorizada.
- Ningún comentario, archivo, PR, workflow, fixture o artefacto equivale a autorización live.

## SPS

```text
SPS_TECHNICAL_CONTEXT = UNCONFIRMED
```

Las observaciones permanecen con ubicación no confirmada mientras no exista evidencia live autorizada.

## INFRASTRUCTURE

- GitHub: código, CI, gobernanza y evidencia versionada.
- Cloudflare: Workers + Durable Objects + GitHub OIDC + Ed25519 + Workers Observability.
- Wrangler fijado: `4.125.0`.
- Sonda controlada no-La-Colonia: desplegada y ejecutada físicamente; evidencia criptográfica verificada.
- Ruta productiva de La Colonia: implementada offline, sin autoridad productiva demostrada contra la fuente.

## PERSISTENCE

- Modelo lógico definido: configuración, productos, mappings, scrape runs, current, history y quality events.
- Current/history existe como lógica backend-neutral.
- Backend durable productivo: `MISSING / BLOCKED_DEPENDENCIES`.
- Google Sheets y BigQuery son opciones históricas/evolutivas, no infraestructura productiva activa del proyecto.

## AUTOMATION

- CI y diagnósticos técnicos: operativos con controles fail-closed.
- Workflows capaces de tráfico live a La Colonia: globalmente bloqueados.
- Scraping diario productivo: `MISSING / BLOCKED_DEPENDENCIES`.
- No existe persistencia diaria autoritativa.

## ANALYTICS

- Power BI continúa como destino analítico previsto.
- Pipeline productivo hacia Power BI: `MISSING / BLOCKED_DEPENDENCIES`.
- No alimentar analytics desde datos sin aceptación autoritativa persistida.

## NEXT

1. Cerrar el diagnóstico/reconciliación de Workers Observability usando el artefacto existente `32551882793`, sin nueva sonda física y sin contactar La Colonia.
2. Mantener `production_authority=false` y `catalog_accepted=false` mientras esa frontera siga abierta.
3. Con autoridad productiva técnicamente cerrada, implementar persistencia durable y luego automatización diaria.
4. Sólo con nueva autorización humana explícita: confirmar SPS y ejecutar validación live mínima/exacta de La Colonia.
5. Después: analytics y segundo supermercado.

## Invariantes actuales

```text
PRODUCTION_AUTHORITY = FALSE
CATALOG_ACCEPTED = FALSE
READY_FOR_LIVE = NO
SPS_TECHNICAL_CONTEXT = UNCONFIRMED
ACTIVE_AUTHORIZATION_IDS = []
```
