# Precios de Supermercados de San Pedro Sula

Proyecto para recolectar, normalizar, validar, historizar y comparar precios de supermercados con alcance inicial en San Pedro Sula.

## Fuentes de verdad

- **Estado operativo mutable, autorizaciones y blockers:** [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md)
- **Arquitectura estable:** [`docs/arquitectura.md`](docs/arquitectura.md)
- **Modelo de datos:** [`docs/modelo-datos.md`](docs/modelo-datos.md)
- **Decisiones técnicas:** [`docs/decisiones-tecnicas.md`](docs/decisiones-tecnicas.md)

GitHub es la fuente de verdad para `main`, PRs, CI, runs y artifacts. Este README no replica SHAs ni autorizaciones transitorias.

## Principios

1. La fuente manda: no se inventan precios, atributos, disponibilidad ni ubicación.
2. `la_colonia_online` es contexto raw; una oferta sólo se etiqueta como SPS cuando existe binding técnico verificable.
3. Completitud, hash o fingerprint no equivalen por sí solos a autorización live.
4. Runs fallidos/rechazados no modifican el último estado comercial confiable.
5. El histórico abre un periodo nuevo sólo cuando cambia un estado comercial relevante.
6. Todo run terminal se registra, aunque el estado comercial no cambie.
7. La lógica de negocio permanece independiente del backend.
8. No se crea una tabla por supermercado.
9. Durante el MVP se prefiere el cambio mínimo con consumidor actual.
10. La Colonia debe quedar end-to-end antes de comenzar supermercado #2.

## Flujo de datos vigente

```text
SOURCE
  ↓
RawProduct
  ↓
NormalizedOffer
  ↓
ValidatedOffer
  ↓
completitud + aprobación versionada
  ↓
current/history backend-neutral
  ↓
TursoWritePlan
  ↓
TursoAdapter
  ├─ SQLite :memory:     # pruebas offline con SQL real
  └─ Turso               # persistencia durable
  ↓
queries validadas
  ↓
Dash + Plotly            # después de cerrar La Colonia end-to-end
```

Turso es el backend persistente operativo. BigQuery queda preservado como implementación legada/futura y su primera carga productiva está retirada/fail-closed. Google Sheets permanece retirado/fail-closed.

## Identidad

```text
source_product_id = identidad dentro de la fuente
product_id        = identidad potencialmente comparable entre fuentes
offer_id          = supermercado + ubicación comercial + producto fuente
```

Precio, promoción, disponibilidad y fecha no forman parte de IDs estables.

Un GTIN-8/12/13/14 sólo se considera identidad cross-source fuerte si supera check digit y se normaliza de forma canónica. Sin identidad fuerte se conserva `prod_pending_*` y mapping pendiente; semejanza textual no basta para unir productos de supermercados distintos.

## Precio e histórico

Se distinguen:

```text
current_price
reported_regular_price
previous_price
```

`reported_regular_price` es una referencia declarada por la tienda, no evidencia de ahorro real. `previous_price` se deriva del `current_price` del periodo aceptado inmediatamente anterior. Sin baseline aceptado no se inventa ahorro.

Turso materializa:

```text
offers_current = último estado aceptado
offer_history  = periodos de cambios reales
scrape_runs    = cada ejecución terminal
```

Una confirmación idéntica posterior no crea un periodo histórico redundante.

## Almacenamiento físico activo

El contrato Turso/SQLite usa:

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

El snapshot inicial aprobado de La Colonia se valida por SHA-256 exacto antes de interpretarlo. La primera carga durable se prepara desde el artifact preservado existente; no requiere ni autoriza una nueva consulta al supermercado.

## Seguridad y tráfico live

La autonomía de desarrollo cubre trabajo offline, GitHub, tests, documentación y preparación fail-closed. No crea autorización permanente para tráfico contra supermercados.

Cualquier nueva observación live exige autorización humana explícita y vigente para su alcance concreto. Autorizaciones históricas consumidas no se reutilizan.

Las credenciales Turso se inyectan sólo mediante GitHub Actions Secrets con los nombres definidos por el runtime. Nunca se guardan en el repositorio ni se solicitan por chat.

## Pruebas

Desde la raíz del monorepositorio:

```bash
python -m pip check
python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts
pytest precios-supermercados-sps/tests
```

La suite cubre dominio, persistencia, SQL SQLite real y auditoría fail-closed de workflows. Los conteos concretos se obtienen de los runs reales de CI, no se fijan en este README.
