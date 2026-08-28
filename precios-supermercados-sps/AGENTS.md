# Instrucciones para agentes — Precios de Supermercados SPS

## Fuente de verdad

- Repositorio: `Jchernand3z19/Portafolio`.
- Proyecto: `precios-supermercados-sps/`.
- GitHub `main`, PRs y CI son la fuente de verdad técnica.
- `docs/PROJECT_STATE.md` describe el estado operativo vigente.
- `docs/arquitectura.md` sólo describe arquitectura que ya tiene uso real.

Antes de modificar: inspecciona `main`, PRs abiertos, CI y busca si la solución ya existe.

---

# REGLA MAESTRA: MVP MÍNIMO ANTES QUE ARQUITECTURA

El objetivo inmediato no es construir una plataforma general. El objetivo es tener **La Colonia San Pedro Sula funcionando de punta a punta con el mínimo código necesario**.

Hasta cerrar ese MVP:

- no iniciar supermercado #2;
- no generalizar para múltiples supermercados;
- no construir infraestructura para necesidades futuras;
- no automatizar una operación que todavía puede resolverse de forma simple/manual;
- no crear una capa propia cuando el proveedor ya ofrece la operación necesaria;
- no convertir una operación one-shot en un subsistema;
- no medir progreso por cantidad de archivos, tests, PRs, servicios o capas.

**Código que no acerca directamente el MVP a datos utilizables no es progreso.**

---

## Definición exacta del MVP de La Colonia

El MVP queda cerrado cuando exista esto, y no más:

1. El snapshot aprobado de La Colonia SPS se valida sin consultar nuevamente la fuente.
2. Los 9,439 SKU se convierten a una base SQLite válida.
3. La base puede subirse mediante la importación nativa de Turso (`Upload SQLite File`).
4. El almacenamiento mínimo permite:
   - identificar producto fuente;
   - consultar precio efectivo observado;
   - conservar precio regular reportado cuando exista;
   - conservar promoción y disponibilidad;
   - conservar el momento/run de observación;
   - añadir un nuevo periodo sólo cuando cambie el estado comercial relevante.
5. Existe una visualización mínima usable para buscar/filtrar productos y ver su precio actual.
6. CI queda verde y el estado real queda documentado.

No hace falta para cerrar este MVP:

- API propia de escritura remota a Turso;
- adapter genérico Turso;
- workflow de primera carga remota;
- tokens Turso en GitHub para la primera importación;
- sistema de migraciones genérico;
- microservicios;
- colas;
- cachés;
- MDM completo;
- fuzzy matching entre supermercados;
- PKI, keyrings, trust layers o nuevos sistemas criptográficos;
- scheduler de scraping diario;
- comparación entre supermercados;
- infraestructura BigQuery;
- nueva infraestructura Cloudflare;
- inventario exacto que el snapshot no demuestre.

Si alguna de esas piezas llega a ser necesaria después, se implementa cuando exista el consumidor real.

---

## Gate obligatorio de simplicidad

Antes de crear **cualquier** archivo de producción, módulo, clase, adapter, workflow, tabla, dependencia, servicio o documento técnico nuevo, responde internamente:

1. ¿Cuál es el blocker actual exacto?
2. ¿Puede resolverse usando una función/capacidad que ya existe?
3. ¿Puede resolverse con una operación nativa del proveedor?
4. ¿Puede resolverse manualmente si es una operación one-shot?
5. ¿Cuál es el cambio de código más pequeño que lo resuelve?
6. ¿Qué consumidor actual necesita la nueva pieza?
7. ¿Qué fallo real y observado evita la complejidad adicional?

Si una respuesta no es concreta, **no se crea la pieza**.

### Orden obligatorio de preferencia

Usa siempre este orden:

```text
capacidad nativa existente
> operación manual one-shot
> función/módulo existente
> cambio específico pequeño
> abstracción nueva
> servicio/infraestructura nueva
```

No saltar directamente a los últimos niveles.

### Presupuesto de complejidad

Para resolver un solo blocker del MVP:

- si la solución propone más de **3 archivos de producción nuevos**, rediseña primero;
- si propone más de **500 líneas netas nuevas**, rediseña primero;
- si requiere un workflow nuevo para una tarea one-shot, rediseña primero;
- si requiere una dependencia externa para algo que `sqlite3`/stdlib o código existente puede hacer, rediseña primero;
- si crea una abstracción con un solo consumidor actual, elimínala y usa la implementación específica;
- si el PR crece porque aparecen problemas no relacionados, sepáralos; no conviertas el PR en una migración general.

Estos números son un **hard stop de revisión**, no una meta que deba llenarse. El resultado correcto normalmente debe ser mucho menor.

No preguntes al usuario por cada rediseño técnico: encuentra primero la alternativa mínima por evidencia del repositorio. Sólo detente si la alternativa mínima requiere una decisión humana real.

---

## Regla especial para operaciones one-shot

Una operación que se hará una vez **no justifica** infraestructura recurrente.

Ejemplo actual:

```text
snapshot aprobado
-> generar SQLite
-> validar conteos/integridad
-> Upload SQLite File en Turso
```

Ese flujo tiene prioridad sobre:

```text
adapter remoto
-> driver HTTP
-> secrets
-> workflow
-> CLI remoto
-> rehidratación remota
-> reconciliación remota
```

La segunda ruta sólo se considera cuando exista una segunda ejecución real que necesite escribir automáticamente en Turso.

---

## Código existente y deuda de sobreingeniería

La existencia de código complejo en el repositorio **no lo convierte en requisito del MVP**.

- No extender código legado sólo porque ya existe.
- No crear compatibilidad con una capa que no tenga consumidor actual.
- No mantener una arquitectura futura en documentos como si fuera necesaria hoy.
- Si una pieza antigua no participa en el camino mínimo, déjala inactiva; su limpieza puede hacerse después del MVP si no bloquea.
- Si una pieza nueva del PR actual no es necesaria para el MVP, elimínala antes de fusionar.

### Estado de backends para este MVP

- **SQLite**: formato de preparación/importación inicial.
- **Turso**: destino durable mediante importación nativa del archivo SQLite.
- **BigQuery**: trabajo legado/futuro; no activar ni ampliar durante el MVP.
- **Google Sheets**: legado; no activar ni ampliar durante el MVP.

No construir un adapter Turso remoto para la primera carga.

---

## Modelo mínimo de persistencia

Para La Colonia con una sola fuente, empieza con el mínimo que el producto consume realmente.

Preferencia actual:

```text
products
  identidad y atributos fuente/normalizados necesarios para mostrar el producto

offer_history
  estado comercial observado por producto/ubicación
  el registro abierto representa el estado actual
  un cambio real cierra el periodo anterior y abre otro

scrape_runs
  una fila por ejecución terminal
```

No crear una tabla adicional si una consulta simple sobre estas tres resuelve el consumidor actual.

`current` puede derivarse del periodo abierto; no materializar una segunda tabla sólo por conveniencia antes de medir una necesidad real.

---

## Contratos y datos protegidos

No inventar ni completar valores para cerrar métricas.

Hechos actuales del snapshot aprobado:

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

Los 1,003 pendientes de presentación permanecen pendientes. Los 474 mappings pendientes permanecen pendientes. Los 2,358 `availability=unknown` permanecen `unknown`.

Reglas de precio:

```text
current_price          = precio efectivo observado
reported_regular_price = precio regular/tachado reportado por la tienda
previous_price         = current_price del periodo histórico aceptado anterior
```

`reported_regular_price` nunca sustituye a `previous_price`.

Identidades estables:

```text
source_product_id = identidad dentro de la fuente
product_id        = identidad comparable cuando existe evidencia suficiente
offer_id          = supermercado + ubicación + producto fuente
```

Precio, promoción, disponibilidad y fecha no forman parte de IDs estables.

---

## Tráfico live

Autonomía técnica no significa autorización live.

`ACTIVE_AUTHORIZATION_IDS = []` se interpreta como **ninguna autorización vigente**.

- No reutilizar autorizaciones consumidas.
- No realizar nuevas solicitudes contra La Colonia sin autorización humana explícita vigente.
- Evidencia ya obtenida puede reutilizarse offline.
- El snapshot aprobado puede procesarse/persistirse sin generar tráfico nuevo.
- No evadir CAPTCHA, login, 403, 429 ni controles anti-bot.

---

## Seguridad proporcional

Mantener controles básicos reales:

- no publicar tokens, cookies, Authorization headers, JWT, claves privadas ni credenciales;
- no guardar secrets en Git;
- mínimo privilegio en GitHub Actions cuando un workflow sea realmente necesario;
- acciones externas pinneadas a SHA completo.

No introducir sistemas de seguridad propios cuando no exista una amenaza o requisito real que los justifique.

---

## Git y desarrollo

Flujo por defecto:

1. auditar `main` y PRs abiertos;
2. identificar **un blocker**;
3. buscar solución existente/nativa;
4. implementar el cambio mínimo;
5. probar sólo lo pertinente y luego suite completa antes del merge;
6. revisar tamaño y diff adversarialmente;
7. eliminar piezas no necesarias;
8. fusionar sólo con CI verde.

No usar force push, reset destructivo ni rebase destructivo.

### Regla para documentación

Actualizar documentación sólo cuando cambia un estado real o una decisión vigente. No escribir diseño futuro como si ya fuera requisito.

---

## Visualización

Después de tener SQLite/Turso con datos válidos, la siguiente prioridad es una UI mínima en **Dash + Plotly**:

- búsqueda por nombre;
- filtros básicos útiles;
- precio actual;
- precio regular reportado si existe;
- promoción;
- disponibilidad;
- historial cuando exista más de una observación aceptada.

No construir un sistema de BI general antes de que esa pantalla mínima funcione.

---

# Criterio de éxito

Cuando una decisión enfrente:

> “arquitectura más completa” vs “camino más corto y correcto al MVP”

elige el segundo.

**El proyecto no necesita demostrar que puede soportar el futuro. Necesita primero funcionar para La Colonia SPS.**
