# Estado actual — Precios de Supermercados SPS

Este documento es la **fuente canónica del estado operativo mutable**. [`arquitectura.md`](arquitectura.md) describe la arquitectura estable; PRs, runs, ramas y artifacts son evidencia histórica y no conceden autoridad.

## Corte

Estado verificado al **2026-08-22 (America/Tegucigalpa)**.

```text
base técnica del corte = 2c3c0f956a05de10c2e0ed415d2f227ca889aff5 (merge de PR #161)
últimos hitos técnicos integrados = #157, #158, #159, #160, #161
última suite completa observada = 1481/1481 PASS (merge-ref final de PR #161, run 32607400298)
compileall = PASS
GATE-17 = PASS_PRODUCTIVE_EVIDENCE
ACTIVE_AUTHORIZATION_IDS = []
LIVE_REQUESTS_CURRENT_RUN = 0
READY_FOR_LIVE = NO
SPS_TECHNICAL_CONTEXT = UNCONFIRMED
production_authority = false
catalog_accepted = false
```

## Semántica de estado

| Estado | Significado |
|---|---|
| `DONE` | Contrato/lógica integrada y estable. |
| `DONE_OFFLINE` | Implementado y probado sin afirmar efecto productivo externo. |
| `DONE_PRODUCTIVE` | Evidencia física/productiva observada para esa capacidad concreta. |
| `PARTIAL_PRODUCTIVE` | Parte de la cadena se demostró físicamente, pero la frontera completa sigue abierta. |
| `BLOCKED_LIVE` | Requiere una observación real de la fuente. |
| `BLOCKED_HUMAN_DECISION` | Requiere autorización humana explícita. |
| `BLOCKED_EXTERNAL` | Requiere ejecución/configuración de un servicio externo. |
| `BLOCKED_DEPENDENCIES` | Depende de cerrar una frontera anterior. |

## Fase 0

| Área | Estado | Hecho verificable / bloqueo |
|---|---|---|
| 0A — suite completa | `DONE` | Suite Python + Node canónica; Node usa `edge/cloudflare/package.json` como única lista de verdad. |
| 0B — hardening físico de catálogo | `DONE` | PR #158 recuperó rechazo temprano de reutilización de `physical_evidence_id` / `fetch_span_id`. |
| 0C — ramas históricas | `DONE` | PR #160 auditó 158 ramas: 102 `MERGED_OR_SUBSUMED`, 55 `CLOSED_SUPERSEDED`, 0 `UNIQUE_UNMERGED`; la única `OPEN_CURRENT` era el propio PR de auditoría. |
| 0E — Raw → Normalized → Validated | `DONE` | PR #159 conectó la transformación real sin persistencia ni autoridad. |
| 0F — semántica de ubicación | `DONE_OFFLINE` | PR #161 fija `la_colonia_online` como contexto fuente raw `UNKNOWN`; no puede promoverirse bajo ese mismo ID a SPS/TGU/tienda. |
| 0G — identidad/dimensión de producto | `DONE_OFFLINE` | PR #161 valida GTIN, conserva `pending_product_mapping` y añade `dim_products` + `map_source_products`. |
| 0H — documentación canónica | `IN_PROGRESS` | PR documental actual sincroniza README, arquitectura, modelo, decisiones, AGENTS y este estado. |
| 0I — workbook físico base | `DONE_PRODUCTIVE` para existencia/configuración inicial | Workbook físico creado/releído con seis tabs del contrato anterior; cero filas `fact_*`. |
| 0J — GitHub Actions → Google Sheets | `PARTIAL_PRODUCTIVE / BLOCKED_EXTERNAL` | Workflow seguro existe; falta ejecutar `check -> apply-config -> check` sobre `main` para migrar/verificar las ocho tabs actuales. |
| 0K — verifier Cloudflare/Observability | `PARTIAL_PRODUCTIVE / BLOCKED_EXTERNAL` | Sonda física y verificación Ed25519 existen; falta ejecutar con éxito el verifier actual `traces -> events` contra esa evidencia existente. |
| 0L — CI/protección | `DONE_PRODUCTIVE` para GATE-17; auditoría continua | Ruleset de `main` demostró enforcement; workflows SPS siguen bajo auditoría fail-closed. |

## Contratos y producto

`RawProduct`, `NormalizedOffer` y `ValidatedOffer` permanecen contratos protegidos.

La identidad se separa en:

```text
source_product_id = identidad dentro de la fuente
product_id        = identidad comparable entre fuentes
offer_id          = supermercado + ubicación comercial + producto fuente
```

Un GTIN válido se normaliza a GTIN-14 y puede producir `prod_gtin_*`. Barcode ausente/inválido conserva `prod_pending_*` + `pending_product_mapping`.

Presentaciones multipack no se colapsan: `2 x 500 ml` conserva 2 unidades, 500 ml por unidad y 1000 ml total.

## La Colonia — ubicación y live

Contexto raw actual:

```text
location_id = la_colonia_online
location_status = unknown
location_confidence = null
```

Ese ID representa el catálogo público en línea observado; no es una ubicación comercial.

Estado de la ubicación candidata `la_colonia_sps`:

```text
city = San Pedro Sula
in_scope = true
granularity = unknown
technical_binding_confirmed = false
source_location_key = null
extraction_enabled = false
```

La UI conocida expone SPS y Tegucigalpa, pero eso no demuestra si precio/inventario cambia por ciudad o por tienda. La radiografía preparada continúa bloqueada y requiere una **nueva autorización humana explícita y limitada** antes de cualquier request a La Colonia.

Una autorización de radiografía no cubre smoke, facets, GraphQL replay, crawl, persistencia ni ejecución diaria.

## Cloudflare

Evidencia física existente:

```text
physical probe source run = 32551882793
verifier-only run         = 32552932554
```

La sonda demostró OIDC, Worker/Durable Object, fetch al origen controlado, bytes esperados y receipt Ed25519; el verifier-only revalidó firma/bytes/identidad.

El código actual ya consulta Workers Observability con discovery de traces y detalle `view: events`, exigiendo custom span único y child fetch reconciliado. La antigua conclusión de que la API pública necesariamente impedía esa reconciliación queda como diagnóstico histórico, no como estado canónico.

**0K sigue abierto** hasta observar un PASS real del verifier actual sobre la evidencia existente. No hace falta repetir una request a La Colonia para esa prueba.

## Persistencia

Contrato lógico actual de ocho tablas:

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

`dim_products` contiene atributos normalizados/canónicos por `product_id`. `map_source_products` conserva identidad fuente, mapping y la cola de revisión.

El workbook físico fue materializado antes de integrar esas dos tablas nuevas. Por tanto:

- existencia física del workbook: demostrada;
- configuración física original de seis tabs: demostrada;
- esquema lógico actual de ocho tabs: integrado y probado offline;
- migración física a ocho tabs por GitHub Actions: **pendiente**;
- persistencia comercial de ofertas: **bloqueada** por ubicación y autoridad.

La ruta prevista para 0J es:

```text
main + workflow manual de storage
-> mode=check
-> autenticación service account
-> lectura del workbook
-> mode=apply-config
-> materialización atómica de las ocho tabs/config
-> mode=check
-> read-back consistente
```

No se deben introducir ofertas para demostrar 0J.

Configuración externa esperada, sin publicar valores:

```text
Environment: precios-sps-storage
Variable: PRECIOS_SPS_GOOGLE_SPREADSHEET_ID
Secret: PRECIOS_SPS_GOOGLE_SERVICE_ACCOUNT_JSON
```

## Regla comercial del precio

```text
current_price           = precio observado que paga el cliente
reported_regular_price  = referencia declarada por la tienda
previous_accepted_price = current_price del periodo aceptado inmediatamente anterior
```

Ahorro real:

```text
max(previous_accepted_price - current_price, 0)
```

`reported_regular_price` e `is_promotion` no sustituyen el histórico propio.

## Próximas acciones sin tráfico a La Colonia

1. fusionar el sync documental 0H;
2. ejecutar y cerrar 0J con `check -> apply-config -> check` desde GitHub Actions sobre `main`;
3. ejecutar y cerrar 0K usando la evidencia física existente de la sonda;
4. reauditar 0L tras cualquier cambio de workflow/configuración.

Sólo después de cerrar Fase 0 corresponde pedir una nueva autorización humana para una radiografía mínima de ubicación.

## Tráfico live

Los PR #157–#161 y el trabajo documental posterior se realizaron sin nuevas requests a La Colonia.

Esto no significa que nunca existieron pruebas live históricas; sólo describe el bloque actual de trabajo y la allow-list vigente vacía.
