# Precios de Supermercados de San Pedro Sula

Proyecto de **web scraping, automatización y datos** para recolectar, normalizar, validar, historizar y comparar precios de supermercados con alcance inicial en San Pedro Sula y cobertura adicional ya verificada en Tegucigalpa.

## Presentación pública en el portafolio

El proyecto se presenta como el **proyecto principal** del portafolio profesional y comunica de forma explícita que los datos parten de sitios web públicos.

La versión pública muestra:

- flujo `Sitios web → Web Scraping → Validación → Histórico → Análisis`;
- una extracción real comprobable con enlace a la fuente, la evidencia y el código;
- cifras de escala verificadas;
- una comparación de 10 productos representativos de consumo básico entre dos supermercados;
- marca y presentación/cantidad para evitar comparaciones engañosas.

Cifras públicas verificadas al **4 de septiembre de 2026**:

- 5 fuentes integradas.
- 9 ubicaciones monitoreadas.
- 47,470 productos registrados en el estado integrado utilizado como base de la presentación.
- 90,876 periodos históricos de precio en ese mismo corte.
- Cobertura en San Pedro Sula y Tegucigalpa.

### Extracción web comprobable

La evidencia pública principal usa una captura aceptada de **Comisariato Los Andes**:

- fuente: <https://comisariatolosandes.com/>;
- captura: `2026-09-04T01:44:35.172709Z`;
- 6,646 productos con precio;
- 120 promociones;
- artifact de GitHub Actions `9920279680`;
- snapshot SHA-256 `a1fe77e3c3132c96c01f7cd792084d47ae25fbb09e3eb69fb67b230d5f09f9fc`.

Metadatos públicos: [`portfolio/scraping-proof.json`](portfolio/scraping-proof.json).

Evidencia versionada: [`reports/comisariato-los-andes/2026-09-04-full/`](reports/comisariato-los-andes/2026-09-04-full/).

### Comparación pública

La tabla visible usa 10 productos cotidianos con esta estructura:

```text
Producto
Marca
Presentación / cantidad
Ciudad
Precio Comisariato Los Andes
Precio Supermercados Colonial
Mejor precio
```

La regla para incluir una fila es **misma marca + misma presentación/cantidad**. La selección sirve para demostrar la comparación y **no se presenta como la canasta básica oficial de Honduras**.

Los Andes usa el snapshot aceptado indicado arriba. Los valores de Colonial fueron comprobados el 4 de septiembre de 2026 contra su catálogo web público oficial. La muestra versionada está en [`portfolio/sample-data.json`](portfolio/sample-data.json).

La procedencia completa y los límites de interpretación se documentan en [`docs/portfolio-showcase.md`](docs/portfolio-showcase.md).

## Fuentes de verdad

- **Estado operativo mutable, autorizaciones, blockers y último CI:** [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md)
- **Presentación pública y evidencia de cifras del portafolio:** [`docs/portfolio-showcase.md`](docs/portfolio-showcase.md)
- **Arquitectura estable:** [`docs/arquitectura.md`](docs/arquitectura.md)
- **Modelo de datos:** [`docs/modelo-datos.md`](docs/modelo-datos.md)
- **Decisiones técnicas:** [`docs/decisiones-tecnicas.md`](docs/decisiones-tecnicas.md)

El README no replica SHAs de ejecución, authorization IDs ni flags operativos mutables. Esos valores se consultan en `PROJECT_STATE.md` y en la evidencia real de GitHub. Los metadatos estrictamente necesarios para demostrar la extracción pública sí se versionan porque forman parte de la presentación del proyecto.

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

La visualización completa de comparación todavía es una capa posterior. La presentación actual muestra una comparación pública curada de 10 productos, no un dashboard cross-source productivo terminado.

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
