# Instrucciones para agentes — Precios de Supermercados SPS

## Fuente de verdad

- Repositorio: `Jchernand3z19/Portafolio`.
- Proyecto: `precios-supermercados-sps/`.
- GitHub `main`, PRs y CI mandan sobre recuerdos o prompts antiguos.
- `docs/PROJECT_STATE.md` describe el estado operativo vigente.
- `docs/arquitectura.md` sólo debe describir arquitectura que el MVP usa realmente.

Antes de modificar: inspecciona `main`, PRs abiertos, CI y busca si la solución ya existe.

# REGLA MAESTRA — MVP MÍNIMO ANTES QUE ARQUITECTURA

El objetivo inmediato es **La Colonia funcionando de punta a punta en San Pedro Sula y Tegucigalpa con el mínimo código necesario**.

Hasta cerrar ese MVP:

- no iniciar supermercado #2;
- no construir infraestructura para necesidades futuras;
- no automatizar una operación que todavía puede resolverse manualmente;
- no crear una capa propia cuando el proveedor ya ofrece la operación necesaria;
- no convertir una operación one-shot en un subsistema;
- no medir progreso por cantidad de archivos, tests, PRs, servicios o capas.

La base sí debe ser reutilizable para futuros supermercados y ciudades porque ese es un requisito actual del producto, pero **no se implementa ningún supermercado adicional todavía**.

**Código que no acerca directamente el MVP a datos utilizables no es progreso.**

## MVP exacto de La Colonia

El MVP queda cerrado cuando exista esto:

1. El snapshot aprobado de SPS se valida sin consultarlo nuevamente.
2. Los datos se convierten a un SQLite válido con el modelo mínimo compartido.
3. Ese archivo se importa usando `Upload SQLite File` de Turso en una base llamada `precios-supermercados`.
4. La misma base distingue supermercado, ciudad, producto, precio/historial y run.
5. SPS y TGU pueden persistirse sin crear bases o tablas nuevas por ciudad.
6. Una UI mínima Dash + Plotly permite buscar/filtrar productos y ver el precio actual por ciudad.
7. Antes de activar recurrencia, al menos una segunda ejecución real valida la actualización/histórico.
8. El scraper queda preparado para ejecución diaria; activar tráfico recurrente exige autorización humana explícita vigente.
9. CI queda verde y la documentación refleja exactamente ese estado.

No hace falta para la primera importación:

- API o adapter remoto Turso;
- workflow de escritura Turso;
- tokens Turso;
- migraciones genéricas;
- BigQuery o Google Sheets activos;
- microservicios, colas o cachés;
- MDM o fuzzy matching;
- nueva infraestructura Cloudflare;
- nuevas capas criptográficas/PKI/trust;
- comparación entre supermercados;
- inventario exacto que la fuente no demuestre.

## Gate obligatorio de simplicidad

Antes de crear cualquier archivo de producción, módulo, clase, adapter, workflow, tabla, dependencia o servicio, responde internamente:

1. ¿Cuál es el blocker actual exacto?
2. ¿Existe ya una función/capacidad que lo resuelva?
3. ¿El proveedor ofrece una operación nativa?
4. ¿Es one-shot y puede hacerse manualmente?
5. ¿Cuál es el cambio de código más pequeño?
6. ¿Qué consumidor actual necesita la nueva pieza?
7. ¿Qué fallo real observado evita la complejidad extra?

Si una respuesta no es concreta, **no se crea la pieza**.

Orden obligatorio:

```text
capacidad nativa existente
> operación manual one-shot
> función/módulo existente
> cambio específico pequeño
> abstracción nueva
> servicio/infraestructura nueva
```

### Presupuesto de complejidad

Para un solo blocker del MVP:

- más de **3 archivos de producción nuevos** -> rediseñar;
- más de **500 líneas netas nuevas** -> rediseñar;
- workflow nuevo para una tarea one-shot -> rediseñar;
- dependencia externa cuando `sqlite3`/stdlib o código existente basta -> rediseñar;
- abstracción con un solo consumidor actual -> eliminarla y usar solución específica;
- problemas no relacionados -> separarlos, no ampliar el PR.

Es un hard stop de revisión, no una meta. El resultado correcto normalmente debe ser mucho menor.

No interrumpas al usuario por el rediseño técnico: busca primero la alternativa mínima. Detente sólo ante una frontera humana real.

## Regla especial para la primera carga

El camino vigente es:

```text
snapshot aprobado
-> generar SQLite
-> validar integridad/conteos
-> Upload SQLite File en Turso
```

No reemplazarlo por:

```text
adapter remoto -> driver HTTP -> secrets -> workflow -> CLI remoto
```

La escritura automática remota se evalúa cuando exista una **segunda ejecución real** que necesite actualizar Turso.

## Persistencia mínima

La base única del proyecto se llama conceptualmente `precios-supermercados` y usa cinco tablas:

```text
supermarkets
  identidad del supermercado

locations
  ciudades/contextos comerciales del supermercado

products
  una fila por SKU/identidad fuente; atributos descriptivos actuales

price_history
  precio, precio regular reportado, promoción, disponibilidad y vigencia por ciudad

scrape_runs
  una fila por ejecución terminal
```

No crear una base por supermercado ni una base por ciudad.

No crear `offers_current`: el estado actual es `price_history.valid_to_utc IS NULL`.
No crear mapping, inventory, quality-events u otra tabla física sin un consumidor real.

Una ejecución futura deberá registrar su run y sólo abrir un nuevo periodo cuando cambie el estado comercial relevante. Ese actualizador se implementa cuando exista la segunda ejecución real que lo necesite.

## Datos protegidos

Snapshot aprobado SPS:

```text
catalog_products_reported = 9437
unique_products_extracted = 9437
skus_extracted = 9439
skus_with_price = 9439
presentation_normalized = 8436
presentation_pending = 1003
gtin_mapping_ready = 8965
product_mapping_pending = 474
availability_in_stock = 7081
availability_unknown = 2358
```

No inventar los 1,003 pendientes de presentación, los 474 mappings pendientes ni convertir `unknown` en agotado.

Precio:

```text
current_price          = precio efectivo observado
reported_regular_price = precio regular/tachado reportado por la tienda
previous_price         = current_price del periodo histórico aceptado anterior
```

`reported_regular_price` nunca sustituye a `previous_price`.

Identidad fuente operativa:

```text
supermarket_id + source_key_type + source_key
```

La ciudad pertenece al estado comercial/histórico, no a la identidad del producto fuente. Precio, promoción, disponibilidad y fecha tampoco forman parte de esa identidad.

## Código histórico / deuda

La existencia de código complejo no lo convierte en requisito del MVP.

- BigQuery: legado/futuro; no activar ni ampliar.
- Google Sheets: legado; no activar ni ampliar.
- Cloudflare/provenance: no ampliar salvo que un futuro tráfico live autorizado lo necesite.
- Código antiguo que no bloquee el MVP puede quedarse inactivo hasta después de la entrega.
- Una pieza nueva innecesaria debe eliminarse antes del merge.

No hacer una limpieza masiva antes del MVP salvo que algo bloquee el camino mínimo.

## Tráfico live

Los markers/IDs versionados del repositorio no conceden por sí solos una autorización live nueva.

- no reutilizar autorizaciones consumidas;
- no realizar solicitudes nuevas contra La Colonia sin autorización humana explícita vigente para ese alcance;
- evidencia ya obtenida sí puede reutilizarse offline;
- la primera carga del snapshot aprobado no genera tráfico nuevo;
- no evadir CAPTCHA, login, 403, 429 ni controles anti-bot.

## Seguridad proporcional

- no secrets, tokens, cookies, JWT ni claves privadas en Git, logs o chat;
- mínimo privilegio si un workflow llega a ser realmente necesario;
- acciones externas pinneadas a SHA completo;
- no construir un sistema de seguridad propio sin un riesgo/requisito real que no pueda resolverse más simple.

## Desarrollo

1. auditar `main` y PRs;
2. identificar un blocker;
3. buscar solución existente/nativa;
4. implementar el cambio mínimo;
5. probar lo pertinente y luego la suite completa antes del merge;
6. revisar tamaño/diff adversarialmente;
7. eliminar piezas no necesarias;
8. fusionar sólo con CI verde.

No usar force push, reset destructivo ni rebase destructivo.

Actualizar documentación sólo cuando cambie un estado real. No documentar diseño futuro como requisito vigente.

## Visualización

Después de importar el SQLite en Turso, construir sólo la UI mínima:

- búsqueda por nombre;
- selector/filtro de ciudad;
- filtros simples útiles;
- precio actual;
- precio regular reportado si existe;
- promoción;
- disponibilidad;
- historial cuando exista más de una observación aceptada.

**Cuando compitan “arquitectura más completa” y “camino más corto y correcto al MVP”, elegir el segundo.**
