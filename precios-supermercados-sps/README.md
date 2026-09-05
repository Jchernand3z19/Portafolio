# Precios de Supermercados de San Pedro Sula

Proyecto de **web scraping, automatización y datos** para recolectar, normalizar, validar, historizar y comparar precios de supermercados con alcance inicial en San Pedro Sula y cobertura adicional ya verificada en Tegucigalpa.

## Presentación pública en el portafolio

El proyecto se presenta como el **proyecto principal** del portafolio profesional y comunica de forma explícita que los datos parten de sitios web públicos.

La tarjeta principal utiliza el estándar compartido definido en [`../docs/PROJECT_CARD_STANDARD.md`](../docs/PROJECT_CARD_STANDARD.md), por lo que conserva la identidad visual del proyecto sin crear un sistema distinto de estructura, tags o acciones frente a los demás proyectos publicados.

La versión pública muestra:

- flujo `Sitios web → Web Scraping → Validación → Histórico → Análisis`;
- una extracción real comprobable con enlace a la fuente, la evidencia y el código;
- cifras de escala verificadas;
- una tabla de cobertura con **todos los supermercados que ya tienen datos productivos aceptados**;
- evidencia analítica intra-cadena reproducible cuando la identidad del artículo está demostrada;
- la política fail-closed que impide publicar comparaciones cross-source basadas sólo en marca y presentación.

Cifras públicas verificadas al **4 de septiembre de 2026**:

- 6 supermercados / cadenas productivas integradas.
- 11 ubicaciones monitoreadas.
- 56,769 productos registrados.
- 108,315 periodos históricos de precio.
- Cobertura en San Pedro Sula y Tegucigalpa.

Cadenas con datos productivos aceptados:

| Supermercado | Ubicaciones |
| --- | --- |
| La Colonia | SPS, Tegucigalpa |
| Supermercados Colonial | SPS |
| Walmart | SPS, TGU FFAA, TGU El Sauce |
| PriceSmart | SPS 6603, Florencia 6602 |
| Comisariato Los Andes | SPS |
| Paiz | TGU Multiplaza, TGU Próceres |

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

La cobertura de scraping y la cobertura de comparación se tratan como conceptos distintos. Tener precio para un producto en dos supermercados **no autoriza** a compararlos automáticamente.

La muestra histórica de 10 filas entre Comisariato Los Andes y Supermercados Colonial fue retirada de la publicación porque su regla anterior —misma marca + misma presentación— no demuestra identidad comercial. El caso `Passion Jaguar` frente a `Passion Especial` queda como regresión explícita: compartir marca y presentación no basta para calcular ni mostrar un “mejor precio”.

Una fila cross-source sólo puede publicarse cuando supera el gate conservador que exige identidad fuerte y coherencia comercial. La metodología completa está en [`docs/COMPARATOR-METHODOLOGY.md`](docs/COMPARATOR-METHODOLOGY.md) y el contrato de publicación en [`docs/PUBLICATION-DATA-DICTIONARY.md`](docs/PUBLICATION-DATA-DICTIONARY.md).

Mientras no exista una fila autorizada por ese gate, [`portfolio/sample-data.json`](portfolio/sample-data.json) publica un estado vacío y explícito en lugar de una comparación dudosa.

La procedencia completa y los límites de interpretación se documentan en [`docs/portfolio-showcase.md`](docs/portfolio-showcase.md).

## Fuentes de verdad

- **Estado operativo mutable, autorizaciones, blockers y último CI:** [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md)
- **Presentación pública y evidencia de cifras del portafolio:** [`docs/portfolio-showcase.md`](docs/portfolio-showcase.md)
- **Metodología del comparador:** [`docs/COMPARATOR-METHODOLOGY.md`](docs/COMPARATOR-METHODOLOGY.md)
- **Contrato del dataset analítico/publicable:** [`docs/PUBLICATION-DATA-DICTIONARY.md`](docs/PUBLICATION-DATA-DICTIONARY.md)
- **Guía de implementación en Power BI:** [`docs/BI-IMPLEMENTATION-GUIDE.md`](docs/BI-IMPLEMENTATION-GUIDE.md)
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
11. Marca + presentación nunca bastan para autorizar una comparación cross-source de precio.
12. Si la identidad o la equivalencia comercial es ambigua, la comparación queda fuera de ahorro, mejor precio y canasta común.

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
homologación descriptiva
  ↓
safe_comparator                   # gate fail-closed
  ↓
price_analytics
  ↓
publication_dataset               # SERVE
  ↓
Power BI / portafolio
```

La cobertura productiva completa de seis cadenas no implica que todos los artículos sean comparables entre cadenas. La capa analítica publica únicamente la intersección cuya identidad y precio están demostrados para el alcance solicitado.

## Identidad

```text
source_product_id = identidad dentro de la fuente
product_id        = identidad potencialmente comparable entre fuentes
offer_id          = supermercado + ubicación comercial + producto fuente
```

Precio, promoción, disponibilidad y fecha no forman parte de IDs estables.

Un GTIN-8/12/13/14 sólo se considera identidad cross-source fuerte si supera check digit y se normaliza de forma canónica. Sin identidad fuerte, el producto puede permanecer bajo `prod_pending_*` y `pending_product_mapping`; semejanza textual no basta para unir productos de supermercados distintos.

Incluso con un GTIN común, una contradicción de marca, tipo, presentación o variante comercial puede bloquear el uso automático del grupo en comparaciones de precio.

## Precio e histórico

Se distinguen:

```text
current_price
reported_regular_price
historical_previous_price
```

`reported_regular_price` es una referencia declarada por la tienda, no evidencia de ahorro real. La reducción real compara el `current_price` actual contra el `current_price` del periodo aceptado inmediatamente anterior. Sin baseline aceptado no se inventa ahorro.

`fact_offer_history` representa periodos comerciales, no snapshots diarios duplicados. Si el estado no cambia, se confirma el periodo existente.

## Analítica y publicación

`price_analytics` sólo recibe grupos autorizados por `safe_comparator`. Para una canasta común exige el mismo producto comparable y un precio actual utilizable en cada supermercado/ubicación del alcance. No imputa precios ni sustituye faltantes por productos parecidos.

El denominador base se publica de forma explícita como:

```text
products_comparable_and_priced_in_every_supermarket_in_scope
```

El exportador reproducible [`scripts/exportar_modelo_analitico.py`](scripts/exportar_modelo_analitico.py) genera JSON/CSV para BI o portafolio desde estado ya persistido, sin hacer scraping y sin serializar credenciales.

## Power BI

Power BI consume el contrato derivado; no vuelve a hacer matching. Los activos versionables viven en [`powerbi/`](powerbi/) y la guía en [`docs/BI-IMPLEMENTATION-GUIDE.md`](docs/BI-IMPLEMENTATION-GUIDE.md).

Un `.pbix` binario no es la fuente de verdad del cálculo: las reglas críticas permanecen en Python, documentación y tests para que el dashboard sea reproducible y auditable.

## Almacenamiento físico activo

Turso / SQLite mantiene el estado productivo integrado bajo un modelo común. El detalle operativo, la huella de esquema vigente y las verificaciones de cada integración se consultan en `PROJECT_STATE.md` y en los reportes de evidencia versionados.

## Seguridad y tráfico live

La autonomía de desarrollo cubre trabajo offline, GitHub, tests, documentación y preparación fail-closed. El tráfico live y las escrituras productivas se ejecutan únicamente bajo una autorización humana explícita y vigente para su alcance.

Los workflows que usan secretos o autoridad de escritura ejecutan código confiable de `main`; un head de PR no recibe esas credenciales. Los detalles vigentes se consultan exclusivamente en [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md).

## Pruebas

Desde la raíz del monorepositorio:

```bash
python -m pip check
python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts
pytest precios-supermercados-sps/tests
```

La suite Python ejecuta también la suite Node canónica declarada en `edge/cloudflare/package.json` y la auditoría fail-closed de workflows. El último conteo observado se registra únicamente en `PROJECT_STATE.md`.