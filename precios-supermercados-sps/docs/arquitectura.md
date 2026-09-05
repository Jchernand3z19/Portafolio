# Arquitectura — Precios de Supermercados SPS

Este documento describe la arquitectura estable del producto. El estado operativo mutable —últimos runs, cifras, autorizaciones y blockers— vive en [`PROJECT_STATE.md`](PROJECT_STATE.md).

## Objetivo

Operar una plataforma de precios de supermercados con un contrato común para múltiples fuentes, histórico por ubicación, homologación conservadora y una capa analítica/publicable que nunca tenga que rehacer scraping ni inventar equivalencias.

```text
sitios públicos
      ↓
extractores por fuente
      ↓
snapshots source-faithful
      ↓
validación + ubicación + completitud
      ↓
persistencia comercial común
      ↓
Turso / SQLite
      ↓
homologación descriptiva
      ↓
safe_comparator (fail-closed)
      ↓
price_analytics
      ↓
publication_dataset
      ↓
Power BI / portafolio / consumidores
```

La base productiva es única para el proyecto. No existe una base ni una tabla de histórico independiente por supermercado.

## Cobertura productiva

La arquitectura soporta seis cadenas productivas integradas:

- La Colonia;
- Supermercados Colonial;
- Walmart;
- PriceSmart;
- Comisariato Los Andes;
- Paiz.

Cada extractor conserva particularidades de su sitio, pero entrega un snapshot compatible con la misma frontera de persistencia comercial.

## Principios

1. La fuente manda; no se inventan datos.
2. Identidad fuente, ubicación comercial y estado de precio son conceptos distintos.
3. Un snapshot no se persiste si no demuestra completitud y ubicación bajo su contrato.
4. Runs fallidos/rechazados no sustituyen el último estado comercial confiable.
5. Todo run terminal aceptado queda trazable mediante `scrape_runs`.
6. Una observación comercial idéntica no crea un periodo histórico redundante.
7. Los precios se almacenan como enteros de unidad menor (`*_price_minor`).
8. La homologación descriptiva no equivale a autorización para comparar precios.
9. Marca + presentación nunca bastan para unir dos productos de supermercados distintos.
10. Power BI y el portafolio consumen datos derivados; no ejecutan matching ni scraping.
11. Workflows con secretos ejecutan exclusivamente código confiable de `main`.
12. El tráfico live y las escrituras productivas requieren una autorización humana vigente para su alcance.

## Capa 1 — Ingesta por fuente

Cada supermercado tiene un extractor adaptado a su contrato público. Esa especialización queda confinada a la ingesta.

Responsabilidades:

- obtener datos read-only;
- respetar budgets, delays, deadlines y reintentos acotados;
- conservar evidencia/raw cuando el contrato lo requiere;
- producir identidad fuente estable;
- demostrar la ubicación/contexto comercial de la captura;
- declarar completitud del catálogo;
- no escribir directamente a la base productiva.

Los extractores operativos viven en `scripts/` y reutilizan normalizadores/contratos de `src/precios_supermercados/`.

## Capa 2 — Snapshot validado

El snapshot es la frontera entre scraping y persistencia.

Un snapshot aceptable debe permitir verificar, según la fuente:

- `supermarket_id`;
- `location_id`;
- `catalog_complete`;
- `location_verified_same_run`;
- conteos declarados vs extraídos;
- identidad fuente de productos/SKU;
- precio/disponibilidad/promoción cuando existan;
- procedencia de la ejecución.

La persistencia vuelve a validar el snapshot. Un archivo presente en disco no es autoridad por sí mismo.

## Capa 3 — Persistencia comercial común

### `supermarkets`

Grain: una fila por cadena.

### `locations`

Grain: una fila por contexto comercial persistible.

La ciudad es un atributo de la ubicación; no forma parte de la identidad del producto fuente.

### `products`

Grain: una identidad fuente estable dentro de un supermercado.

Incluye, cuando la fuente los provee:

- nombre;
- marca;
- presentación;
- categoría;
- EAN/GTIN reportado;
- IDs/keys fuente.

La unicidad operativa se basa en el contrato de identidad de cada fuente, no en nombre + marca.

### `price_history`

Grain: un periodo comercial por producto + ubicación.

Incluye:

- `current_price_minor`;
- `reported_regular_price_minor` cuando existe;
- promoción;
- disponibilidad;
- moneda;
- inicio/fin del periodo;
- run que originó la observación.

`valid_to_utc IS NULL` representa el estado actual. No se materializa otra tabla “current” que pueda divergir del histórico.

### `scrape_runs`

Grain: una ejecución persistida por ubicación.

Conserva, entre otros campos, identidad del run, estado, conteos y digest del snapshot. Permite verificar que el commit lógico corresponde exactamente al archivo aceptado.

## Semántica de precio

Se distinguen explícitamente:

```text
current_price
reported_regular_price
historical_previous_price
```

`reported_regular_price` es una referencia declarada por la tienda. No demuestra ahorro real.

La reducción histórica real usa el `current_price` del periodo aceptado inmediatamente anterior. Si no hay baseline aceptado, la reducción no se inventa.

## Actualización diaria

Workflow confiable:

`.github/workflows/precios-supermercados-sps-la-colonia-mvp-update.yml`

Aunque conserva un nombre histórico, es el workflow productivo común de las seis cadenas.

Secuencia conceptual:

```text
capturar cadenas de forma acotada
        ↓
validar todos los snapshots
        ↓
persistir estado comercial
        ↓
verificar run_id + digest + current state
        ↓
foreign_key_check + integridad + duplicados
        ↓
publicar evidencia
```

El workflow corre secuencialmente y usa `concurrency` sin cancelación en progreso para no interrumpir una transacción operativa por una segunda ejecución.

El schedule productivo vive en el YAML del workflow y se considera fuente de verdad para la hora recurrente.

## Operador confiable de ejecución manual

`.github/workflows/precios-supermercados-sps-production-operator.yml` permite convertir una solicitud controlada ya fusionada en `main` en un `workflow_dispatch` del workflow productivo.

Propiedades:

- observa sólo un archivo de solicitud fijo en `main`;
- no recibe secretos de Turso;
- valida esquema, operación y ventana de autorización;
- no ejecuta head de PR;
- sólo puede despachar un workflow productivo fijo sobre `main`.

Esto separa la autoridad de iniciar una ejecución de las credenciales usadas durante la persistencia.

## Homologación descriptiva

Después de una actualización productiva exitosa, el workflow:

`.github/workflows/precios-supermercados-sps-homologation-refresh.yml`

recalcula `product_homologation_profiles` a partir de `products` ya persistidos.

La homologación normaliza:

- GTIN;
- nombre;
- marca;
- taxonomía;
- presentación estructurada;
- tokens descriptivos;
- conflictos y estado de revisión.

Esta tabla es derivada. La verdad comercial original permanece en `products` y `price_history`.

## Gate de comparación fail-closed

`src/precios_supermercados/safe_comparator.py` es la única frontera que autoriza comparaciones directas cross-source.

Estados:

- `comparable`;
- `review_required`;
- `not_comparable`.

Para ser `comparable`, dos registros deben tener identidad fuerte compartida y no presentar contradicciones de marca, tipo, presentación o descriptores comerciales.

Un GTIN compartido no obliga a comparar si el resto de la evidencia contradice la identidad comercial.

Caso de regresión obligatorio:

```text
Passion Jaguar != Passion Especial
```

aunque marca y presentación coincidan.

Metodología: [`COMPARATOR-METHODOLOGY.md`](COMPARATOR-METHODOLOGY.md).

## Capa analítica

### `price_analytics.py`

Calcula sobre grupos `comparable`:

- precio actual por fuente/ubicación;
- mejor precio;
- máximo comparable;
- ahorro absoluto y porcentual;
- canasta común;
- subcanastas con cantidades explícitas.

No imputa precios. Un producto agotado explícitamente o sin precio en alguna ubicación sale del denominador común.

Una canasta de cero productos no tiene supermercado ganador.

### `buyer_profile_analytics.py`

Aplica cantidades de un perfil únicamente al universo ya comparable. Si el perfil pide un producto fuera del universo común, falla cerrado.

### `price_change_analytics.py`

Compara ejecuciones sólo cuando el alcance es idéntico. Un delta de total de canasta se calcula sólo si ambos runs comparten exactamente el mismo universo no vacío.

### `price_history_analytics.py`

Resume series de una identidad canónica + supermercado + ubicación sin interpolar observaciones inexistentes.

## Dataset de publicación

`publication_dataset.py` proyecta la analítica a un contrato estable y sin autoridad operativa:

`precios-sps-publication/v1`

Tablas lógicas:

- `scope`;
- `offers`;
- `products`;
- `common_basket`;
- `excluded_group_counts`.

El exportador `scripts/exportar_modelo_analitico.py` materializa JSON/CSV desde SQLite read-only o Turso confiable. No hace scraping y no serializa URL/token de base de datos.

Diccionario: [`PUBLICATION-DATA-DICTIONARY.md`](PUBLICATION-DATA-DICTIONARY.md).

## Power BI

Power BI es consumidor de la capa SERVE.

No debe:

- resolver identidad;
- inferir ubicación;
- decidir si un run fue aceptado;
- recalcular matching por nombre/marca/presentación;
- acceder a secretos de scraping/Turso.

Activos reproducibles: [`../powerbi/`](../powerbi/).
Guía: [`BI-IMPLEMENTATION-GUIDE.md`](BI-IMPLEMENTATION-GUIDE.md).

## Portafolio público

El portafolio presenta:

- cobertura productiva verificada;
- evidencia concreta de scraping;
- hallazgos analíticos respaldados;
- sólo comparaciones cross-source que superen el gate.

La antigua muestra basada en “misma marca + misma presentación” está retirada. `portfolio/sample-data.json` permanece explícitamente vacío hasta que existan filas publicadas por el contrato seguro.

## Backends

### Productivo

```text
Turso
```

### Reproducibilidad/local

```text
SQLite
```

Existen componentes históricos/experimentales para Google Sheets y BigQuery, pero no constituyen la ruta productiva principal actual.

## Seguridad

Controles estructurales:

- secrets fuera de Git;
- acciones externas pinneadas por SHA;
- permisos mínimos por workflow/job;
- checkout inmutable;
- PR head sin secretos ni autoridad productiva;
- budgets live explícitos;
- validación fail-closed de snapshots;
- integridad/FK/duplicados después de persistir;
- workflows derivados sólo después de upstream exitoso confiable.

La auditoría ejecutable de workflows vive en `tests/test_workflow_security_audit.py` y su módulo base.

## Fuente de verdad operativa

Este documento evita fijar cifras/run IDs que cambian diariamente. Consultar [`PROJECT_STATE.md`](PROJECT_STATE.md) para el último estado verificado y los reportes versionados en `reports/` para evidencia histórica.