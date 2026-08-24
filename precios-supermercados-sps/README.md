# Precios de Supermercados de San Pedro Sula

Proyecto para recolectar, normalizar, validar, historizar y comparar precios de supermercados con alcance inicial en San Pedro Sula.

## Fuentes de verdad

- **Estado operativo mutable, autorizaciones, blockers y último CI:** [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md)
- **Arquitectura estable:** [`docs/arquitectura.md`](docs/arquitectura.md)
- **Modelo de datos:** [`docs/modelo-datos.md`](docs/modelo-datos.md)
- **Decisiones técnicas:** [`docs/decisiones-tecnicas.md`](docs/decisiones-tecnicas.md)

El README no replica SHAs, runs, conteos de tests, authorization IDs ni flags operativos. Esos valores cambian con el tiempo y deben consultarse en `PROJECT_STATE.md` y en la evidencia real de GitHub.

## Principios

1. La fuente manda: no se inventan precios, atributos ni ubicación.
2. `la_colonia_online` es contexto raw; una oferta sólo puede etiquetarse como SPS mediante una frontera de binding verificable.
3. Corrección técnica, firma, hash o completitud no equivalen por sí solos a autoridad productiva.
4. Runs fallidos/rechazados no modifican el último estado comercial confiable.
5. El histórico abre un periodo nuevo sólo cuando cambia un estado comercial relevante.
6. Todo run terminal se registra, aunque no exista cambio de precio.
7. La lógica de negocio permanece independiente del backend.
8. Una entidad lógica no obliga a crear una tabla física antes de existir una necesidad real.
9. No se crea una tabla por supermercado.
10. Power BI consume datos curados; no decide limpieza, ubicación, identidad ni aceptación.

## Flujo de datos

```text
SOURCE
  ↓
INGEST
  ↓
RawProduct                         # RAW / source-faithful
  ↓
NormalizedOffer
  ↓
ValidatedOffer                    # CLEAN / validated
  ↓
completitud + provenance + ACCEPT/REJECT
  ↓
current/history                   # CURATED
  ↓
Google Sheets                     # backend temporal
  ↓
proyección semántica
  ↓
Power BI                          # SERVE
```

BigQuery queda como evolución posterior cuando el proceso completo sea estable. La migración podrá cambiar el modelo físico sin cambiar la semántica comercial.

## Identidad

```text
source_product_id = identidad dentro de la fuente
product_id        = identidad potencialmente comparable entre fuentes
offer_id          = supermercado + ubicación comercial + producto fuente
```

Precio, promoción, disponibilidad y fecha no forman parte de IDs estables.

Un GTIN-8/12/13/14 sólo se considera identidad cross-source fuerte si supera check digit y se normaliza de forma canónica. Sin identidad fuerte, el producto puede permanecer bajo `prod_pending_*` y `pending_product_mapping`; semejanza textual no basta para unir productos de supermercados distintos.

## Precio e histórico

Se distinguen:

```text
current_price
reported_regular_price
historical_previous_price
```

`reported_regular_price` es una referencia declarada por la tienda, no evidencia de ahorro real. La reducción real compara el `current_price` actual contra el `current_price` del periodo aceptado inmediatamente anterior. Sin baseline aceptado no se inventa ahorro.

`fact_offer_history` representa periodos comerciales, no snapshots diarios duplicados. Si el estado no cambia, se confirma el periodo existente.

## Almacenamiento físico activo

Google Sheets es el backend temporal y materializa únicamente seis tablas con grain/lifecycle ya justificados:

```text
cfg_supermarkets
cfg_locations
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

Los contratos lógicos:

```text
dim_products
map_source_products
```

permanecen diferidos hasta que exista una segunda fuente o un consumidor real que requiera identidad canónica cross-source. `source_product_id` y `product_id` continúan presentes en current/history, por lo que esa capacidad puede activarse y backfillearse posteriormente sin inventar observaciones.

## Seguridad y tráfico live

La autonomía de desarrollo cubre trabajo offline, GitHub, tests, documentación y preparación fail-closed. No crea una autorización permanente para tráfico contra supermercados.

Cualquier nueva observación live exige autorización humana explícita y vigente para su alcance concreto. Autorizaciones históricas consumidas no se reutilizan. Los detalles vigentes se consultan exclusivamente en [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md).

## Pruebas

Desde la raíz del monorepositorio:

```bash
python -m pip check
python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts
pytest precios-supermercados-sps/tests
```

La suite Python ejecuta también la suite Node canónica declarada en `edge/cloudflare/package.json` y la auditoría fail-closed de workflows. El último conteo observado se registra únicamente en `PROJECT_STATE.md`.
