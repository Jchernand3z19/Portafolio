# Precios de Supermercados de San Pedro Sula

Proyecto para recolectar, normalizar, validar, historizar y comparar precios de supermercados con alcance inicial en San Pedro Sula y cobertura adicional ya verificada en Tegucigalpa.

## Presentación pública en el portafolio

El proyecto se presenta como el **proyecto principal** del portafolio profesional.

La versión pública prioriza lenguaje entendible para una persona no técnica y muestra primero el valor del proyecto: qué hace, qué cobertura tiene, qué datos reales ya genera y qué preguntas permite responder.

Cifras públicas verificadas al **4 de septiembre de 2026**:

- 5 fuentes integradas.
- 9 ubicaciones monitoreadas.
- 47,470 productos registrados en el estado integrado utilizado como base de la presentación.
- 90,876 periodos históricos de precio en ese mismo corte.
- Cobertura en San Pedro Sula y Tegucigalpa.

La tabla visible en el portafolio ya no usa registros sintéticos ni identificadores `SKU-DEMO`. Utiliza una muestra real proveniente del snapshot aceptado del 4 de septiembre de 2026. Para que la presentación sea fácil de entender, muestra únicamente:

```text
Producto
Ciudad
Precio actual
Precio regular
Promoción
Disponibilidad
```

La procedencia exacta de esa muestra, sus hashes y el criterio de publicación se documentan en [`docs/portfolio-showcase.md`](docs/portfolio-showcase.md).

## Fuentes de verdad

- **Estado operativo mutable, autorizaciones, blockers y último CI:** [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md)
- **Presentación pública y evidencia de cifras del portafolio:** [`docs/portfolio-showcase.md`](docs/portfolio-showcase.md)
- **Arquitectura estable:** [`docs/arquitectura.md`](docs/arquitectura.md)
- **Modelo de datos:** [`docs/modelo-datos.md`](docs/modelo-datos.md)
- **Decisiones técnicas:** [`docs/decisiones-tecnicas.md`](docs/decisiones-tecnicas.md)

El README no replica SHAs de ejecución, authorization IDs ni flags operativos. Esos valores cambian con el tiempo y deben consultarse en `PROJECT_STATE.md` y en la evidencia real de GitHub. Las cifras públicas del portafolio sí quedan versionadas en `portfolio-showcase.md` porque forman parte de la presentación publicada y deben poder auditarse.

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
Turso / SQLite
  ↓
proyección semántica
  ↓
consumo analítico                 # SERVE
```

La visualización completa de comparación todavía es una capa posterior. La presentación actual del portafolio no la muestra como si ya estuviera terminada.

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

Turso / SQLite mantiene el estado productivo integrado bajo un modelo común. El detalle operativo, la huella de esquema vigente y las verificaciones de cada integración se consultan en `PROJECT_STATE.md` y en los reportes de evidencia versionados.

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
