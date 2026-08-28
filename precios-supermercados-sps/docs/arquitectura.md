# Arquitectura — Precios de Supermercados SPS

Este documento describe únicamente la arquitectura necesaria para el **MVP actual**. El estado operativo concreto vive en [`PROJECT_STATE.md`](PROJECT_STATE.md).

## Objetivo

Cerrar La Colonia San Pedro Sula de punta a punta con el menor número de piezas posible:

```text
snapshot aprobado
-> SQLite mínimo
-> importación nativa a Turso
-> consulta/visualización mínima en Dash + Plotly
```

No diseñar para supermercado #2 antes de cerrar este flujo.

## Principios

1. La fuente manda; no se inventan datos.
2. El MVP usa primero capacidades nativas y operaciones one-shot.
3. No crear una abstracción sin consumidor actual.
4. No crear infraestructura recurrente para resolver una carga única.
5. No ampliar código legado si no participa en el camino mínimo.
6. Precio, disponibilidad y fecha no forman parte de la identidad fuente estable.
7. Todo run terminal se registra.
8. Una observación idéntica no crea historia redundante.
9. Una observación nueva de La Colonia requiere autorización humana vigente.

## Flujo MVP

```text
full-catalog.json aprobado
        ↓
validación exacta SHA-256 + metadata + 9,439 SKU
        ↓
generar_mvp_sqlite_la_colonia.py
        ↓
SQLite local
  ├─ scrape_runs
  └─ offer_history
        ↓
PRAGMA integrity_check + reconciliación de conteos
        ↓
Upload SQLite File
        ↓
Turso
        ↓
Dash + Plotly mínimo
```

No existe una conexión remota Turso en la primera carga. No se necesitan tokens ni un workflow de escritura para importar el archivo inicial.

## Modelo físico mínimo

### `scrape_runs`

Grain: una fila por ejecución terminal.

Guarda sólo la evidencia necesaria para saber qué snapshot produjo la observación persistida.

### `offer_history`

Grain: un periodo comercial por identidad fuente y ubicación.

Contiene:

- supermercado y ubicación;
- identidad fuente estable;
- IDs/descriptores fuente útiles para mostrar el producto;
- nombre, marca, presentación y categoría observados;
- precio efectivo;
- precio regular reportado cuando existe;
- promoción;
- disponibilidad;
- inicio/fin del periodo;
- run que originó el periodo.

`valid_to_utc IS NULL` representa el estado actual. No se materializa otra tabla de current durante el MVP porque una consulta simple resuelve ese consumidor.

## Precio

```text
current_price          = precio efectivo observado
reported_regular_price = precio regular/tachado reportado por la tienda
previous_price         = current_price del periodo anterior aceptado
```

SQLite almacena los precios en centavos enteros (`*_price_minor`).

## Historial

Primera carga:

```text
9439 SKU -> 9439 periodos abiertos
1 run    -> 1 fila en scrape_runs
```

Una ejecución futura sólo justifica construir el actualizador cuando exista esa segunda ejecución real. Su comportamiento requerido será:

- registrar el run siempre;
- mantener el periodo abierto si el estado no cambió;
- cerrar y abrir periodo sólo ante cambio relevante.

No construir esa automatización anticipadamente.

## Identidad

Para este MVP la identidad operativa puede apoyarse directamente en:

```text
supermarket_id + location_id + source_key_type + source_key
```

Los IDs canónicos/GTIN y mappings ya investigados pueden conservarse como trabajo disponible, pero no son requisito para mostrar y conservar correctamente el primer supermercado.

No hacer fuzzy matching ni MDM antes de supermercado #2.

## Ubicación

`la_colonia_sps` es la ubicación comercial confirmada del snapshot aprobado.

`la_colonia_online` es contexto fuente histórico y no debe reinterpretarse como ciudad.

La existencia del binding técnico no concede autorización para nuevas consultas live.

## Disponibilidad

El snapshot actual demuestra:

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

No construir adapters, migraciones o workflows para esos backends durante el MVP.

## Visualización

La primera UI Dash + Plotly sólo necesita:

- búsqueda por nombre;
- filtros simples si ayudan al uso;
- precio actual;
- precio regular reportado;
- promoción;
- disponibilidad.

No construir dashboards generales, analítica avanzada ni comparación entre supermercados antes de que esa pantalla funcione.

## Código histórico

El repositorio contiene piezas de arquitecturas anteriores. Se consideran **deuda/historial**, no requisitos implícitos.

Regla: no tocarlas salvo que bloqueen el MVP. La limpieza se realiza después de entregar el camino funcional mínimo.

## Seguridad

Mantener únicamente controles proporcionales:

- no secrets en Git;
- no cookies/tokens/credenciales en logs o chat;
- no nuevas solicitudes live sin autorización;
- validación exacta del artifact aprobado;
- integridad SQLite antes de importar.

No añadir una capa de seguridad propia sin un riesgo real que no pueda resolverse de forma más simple.
