# Arquitectura — Precios de Supermercados SPS

Este documento describe únicamente la arquitectura necesaria para el **MVP actual**. El estado operativo concreto vive en [`PROJECT_STATE.md`](PROJECT_STATE.md).

## Objetivo

Cerrar La Colonia en San Pedro Sula y Tegucigalpa de punta a punta con el menor número de piezas posible:

```text
snapshots validados
-> SQLite compartido
-> importación nativa a Turso
-> consulta/visualización mínima en Dash + Plotly
```

La base se llama `precios-supermercados` y es única para el proyecto. No se crea una base por supermercado ni por ciudad.

No iniciar supermercado #2 antes de cerrar este flujo.

## Principios

1. La fuente manda; no se inventan datos.
2. El MVP usa primero capacidades nativas y operaciones one-shot.
3. No crear una abstracción sin consumidor actual.
4. No crear infraestructura recurrente para resolver una carga única.
5. No ampliar código legado si no participa en el camino mínimo.
6. El producto fuente se identifica independientemente de la ciudad.
7. Precio, disponibilidad y fecha pertenecen al estado comercial por ubicación.
8. Todo run terminal se registra.
9. Una observación idéntica no crea historia redundante.
10. Una observación nueva de La Colonia requiere autorización humana vigente para ese alcance.

## Flujo MVP

```text
full-catalog.json aprobado SPS
        ↓
validación exacta SHA-256 + metadata + 9,439 SKU
        ↓
generar_mvp_sqlite_la_colonia.py
        ↓
SQLite local: precios-supermercados.db
  ├─ supermarkets
  ├─ locations
  ├─ products
  ├─ price_history
  └─ scrape_runs
        ↓
PRAGMA integrity_check + foreign_key_check + reconciliación
        ↓
Upload SQLite File
        ↓
Turso: precios-supermercados
        ↓
Dash + Plotly mínimo
```

La primera importación no necesita conexión remota Turso, tokens ni workflow de escritura.

## Modelo físico mínimo

### `supermarkets`

Grain: una fila por supermercado.

La primera fila es `la_colonia`. Esta tabla evita repetir identidad/nombre de supermercado y permite que la misma base reciba futuros supermercados sin cambiar el modelo.

### `locations`

Grain: una fila por ciudad/contexto comercial del supermercado.

Para La Colonia:

```text
la_colonia_sps -> San Pedro Sula
la_colonia_tgu -> Tegucigalpa
```

La presencia de una ubicación no significa que ya existan precios para ella. El run/historial demuestra qué ciudad fue realmente observada.

### `products`

Grain: una fila por SKU/identidad fuente del supermercado.

Contiene únicamente atributos descriptivos actuales y la identidad fuente estable:

- `supermarket_id`;
- `source_key_type` + `source_key`;
- IDs fuente de producto/item;
- referencia/EAN;
- nombre;
- marca;
- presentación;
- categoría.

La clave única operativa es:

```text
supermarket_id + source_key_type + source_key
```

La ciudad no forma parte de la identidad del producto fuente.

### `price_history`

Grain: un periodo comercial por producto y ubicación.

Contiene:

- producto;
- supermercado y ubicación;
- precio efectivo;
- precio regular reportado cuando existe;
- promoción;
- disponibilidad;
- moneda;
- inicio/fin del periodo;
- run que originó el periodo.

`valid_to_utc IS NULL` representa el estado actual. No se materializa una tabla adicional de current.

### `scrape_runs`

Grain: una fila por ejecución terminal y ubicación.

Permite registrar una ejecución incluso cuando ningún precio cambie. En el futuro también puede registrar un run rechazado/fallido sin alterar historia comercial.

## Primera carga SPS

El snapshot aprobado produce exactamente:

```text
supermarkets = 1
locations = 2
products = 9439
price_history = 9439
scrape_runs = 1
```

Los 9,439 registros de `price_history` pertenecen a `la_colonia_sps`.

TGU queda con cero precios hasta completar su propio run. No se copian ni infieren precios SPS hacia TGU.

## Precio

```text
current_price          = precio efectivo observado
reported_regular_price = precio regular/tachado reportado por la tienda
previous_price         = current_price del periodo anterior aceptado
```

SQLite almacena los precios en centavos enteros (`*_price_minor`).

## Historial

Una ejecución posterior debe:

- registrar el run siempre;
- actualizar atributos descriptivos de `products` si cambiaron;
- comparar el estado comercial por `product_id + location_id`;
- mantener el periodo abierto si el estado no cambió;
- cerrar y abrir periodo sólo ante cambio relevante.

Ese actualizador se implementa cuando exista una segunda ejecución real que lo necesite.

## Ubicación

SPS y TGU usan la misma estructura física. Cada snapshot/run debe demostrar su propia ciudad antes de persistir precios.

La existencia de un binding técnico histórico no concede autorización para nuevas consultas live.

## Disponibilidad

El snapshot SPS actual demuestra:

```text
in_stock = 7081
unknown  = 2358
```

`unknown` permanece `unknown`. No se inventa cantidad, seller ni agotado.

## Backend

### Activo para el MVP

```text
SQLite -> Turso native upload
```

### No activos

```text
BigQuery      = legado/futuro
Google Sheets = legado
```

No construir adapters, migraciones o workflows de primera carga para esos backends.

## Visualización

La primera UI Dash + Plotly sólo necesita:

- búsqueda por nombre;
- selector/filtro de ciudad;
- filtros simples útiles;
- precio actual;
- precio regular reportado;
- promoción;
- disponibilidad.

No construir dashboards generales ni analítica avanzada antes de que esa pantalla funcione.

## Ejecución diaria

La Colonia se deja preparada para ejecución diaria después de validar al menos una segunda ejecución real y comprobar el comportamiento del histórico. La activación recurrente requiere autorización humana explícita para ese tráfico periódico.

## Código histórico

El repositorio contiene piezas de arquitecturas anteriores. Se consideran **deuda/historial**, no requisitos implícitos.

Regla: no tocarlas salvo que bloqueen el MVP. La limpieza se realiza después de entregar el camino funcional mínimo.

## Seguridad

Mantener únicamente controles proporcionales:

- no secrets en Git;
- no cookies/tokens/credenciales en logs o chat;
- no nuevas solicitudes live sin autorización;
- validación exacta del artifact aprobado;
- integridad y foreign keys SQLite antes de importar.

No añadir una capa de seguridad propia sin un riesgo real que no pueda resolverse de forma más simple.
