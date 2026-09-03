# Instrucciones para agentes — Precios de Supermercados SPS

## Fuente de verdad

- Repositorio: `Jchernand3z19/Portafolio`.
- Proyecto: `precios-supermercados-sps/`.
- GitHub `main`, PRs, Actions y artifacts mandan sobre recuerdos o prompts antiguos.
- `docs/PROJECT_STATE.md` describe el estado operativo vigente.
- Antes de modificar: auditar `main`, PRs abiertos, CI y buscar si la solución ya existe.

# Fase activa — catálogo completo PriceSmart listo para gate Turso

Maxi Despensa y Despensa Familiar permanecen **NO-GO TEMPORAL PARA PRICE
TRACKING WEB**. No reabrir esas cadenas sin una fuente digital pública nueva y
una instrucción explícita.

PriceSmart Honduras quedó completo para SPS club 6603 y Florencia club 6602. El
Sauce 6604 permanece excluido. `reports/pricesmart/2026-09-02-complete/` demuestra
26 raíces, 24 no vacías, 2,766 productos y 6,078 SKU únicos por club. El full
restante consumió 50 POST HTTP 200, cero retries; Alimentos se reutilizó sin
recrawl. Los dos clubes conservan contexto separado por 115 diferencias reales de
precio entre SKU cotizados en ambos.

El delta offline contra el estado productivo Alimentos es, por ubicación: 1,127
estados sin cambio y 4,951 ofertas SKU nuevas, agrupadas en 1,642 productos fuente
y 3,309 variantes adicionales. No hay cambios comerciales previos, cambios sólo
de metadata ni ausencias. La persistencia offline, replay, aislamiento, FK e
integridad pasaron sobre las cinco tablas.

La única frontera pendiente es la escritura productiva Turso. No ejecutarla sin
una autorización separada. No recrawlear, no consultar El Sauce, no crear
recurrencia y no interpretar ausencia como `out_of_stock`. Publicar, corregir CI,
fusionar y verificar `main` sí están autorizados para esta fase.

# Referencia — cierre inicial de La Colonia sin sobreingeniería

El objetivo de aquella fase fue una sola cadena:

```text
La Colonia
├── la_colonia_sps
└── la_colonia_tgu

persistencia = Turso / precios-supermercados
histórico = cambios comerciales
operación = ejecución diaria
```

Las restricciones de aquella fase fueron:

- no iniciar supermercado #2;
- no construir Dashboard/Dash/Plotly;
- no activar BigQuery ni Google Sheets;
- no construir Cloudflare, microservicios, APIs públicas ni arquitectura multi-cloud;
- no crear abstracciones para necesidades futuras;
- no limpiar deuda que no bloquee el MVP;
- no convertir una operación one-shot en un subsistema.

En la fase activa, mantener cerrado Maxi/DF y avanzar PriceSmart sólo dentro del
gate autorizado. Probe, full, Turso y recurrencia son permisos separados.
No modificar scrapers, parsers ni fixtures de La Colonia, Colonial o Walmart salvo
bug compartido demostrado que bloquee el trabajo; no refactorizar por estética.

## Definición del MVP

La Colonia queda cerrada cuando exista evidencia de:

1. SPS completo, con precios y disponibilidad básica correcta.
2. TGU con binding propio, catálogo completo, precios y disponibilidad demostrable.
3. Una única base `precios-supermercados` con SPS y TGU diferenciados por `location_id`.
4. Histórico que no duplica periodos si el estado no cambia y sí abre uno nuevo ante cambio real.
5. `scrape_runs` por ejecución aceptada, replay idempotente y run inválido sin corrupción.
6. La carga vieja de prueba en Turso descartada y sustituida por SPS + TGU válidos.
7. Al menos 2–3 ejecuciones reales consecutivas válidas.
8. Ejecución diaria preparada; activar recurrencia live requiere autorización humana explícita.
9. CI verde y `PROJECT_STATE.md` actualizado.

No forman parte de este MVP:

- Dashboard;
- otros supermercados;
- inventario exacto;
- normalización perfecta;
- BigQuery;
- Google Sheets.

## Gate obligatorio de simplicidad

Antes de crear archivo de producción, módulo, clase, adapter, workflow, tabla, dependencia o servicio:

1. ¿Cuál es el blocker exacto?
2. ¿Existe ya una función/capacidad que lo resuelva?
3. ¿Puede resolverse con una operación puntual?
4. ¿Cuál es el cambio más pequeño correcto?
5. ¿Qué fallo real observado justifica la complejidad?

Orden preferido:

```text
capacidad existente
> operación one-shot
> función/módulo existente
> cambio específico pequeño
> abstracción nueva
> infraestructura nueva
```

Para un solo blocker:

- más de 3 archivos de producción nuevos -> rediseñar;
- más de 500 líneas netas nuevas -> rediseñar;
- workflow nuevo para una tarea one-shot -> rediseñar;
- dependencia externa cuando `sqlite3`/stdlib basta -> rediseñar;
- abstracción con un solo consumidor -> evitarla.

## Persistencia mínima

La base única usa exactamente cinco tablas mientras resuelvan el MVP:

```text
supermarkets
locations
products
price_history
scrape_runs
```

No crear una base o tabla por ciudad.

Identidad fuente:

```text
supermarket_id + source_key_type + source_key
```

El estado comercial pertenece a producto + ubicación.

Estado actual:

```text
price_history.valid_to_utc IS NULL
```

Cada ejecución aceptada registra `scrape_runs`.

Para cada producto + ubicación:

```text
mismo estado
-> no crear historia

estado cambió
-> cerrar periodo actual
-> abrir periodo nuevo

producto nuevo
-> insertar producto
-> abrir primer periodo
```

Estado comercial mínimo:

```text
current_price
reported_regular_price
is_promotion
availability
```

Un snapshot incompleto/rechazado no modifica el último estado aceptado.

## Precio

```text
current_price          = precio efectivo observado
reported_regular_price = precio regular/tachado declarado por la fuente
previous_price         = current_price del periodo histórico aceptado anterior
```

`reported_regular_price` no sustituye a `previous_price`.

SQLite/Turso puede almacenar precios en centavos enteros.

## Disponibilidad

Estados mínimos:

```text
in_stock
out_of_stock
unknown
```

`availability` es útil para el MVP.

`available_quantity` es opcional y no bloquea el MVP.

No inferir `unknown -> out_of_stock` sin evidencia de la fuente.

## Evidencia SPS vigente

Usar como referencia operativa el artifact válido más reciente documentado en
`docs/PROJECT_STATE.md`, no el snapshot antiguo de 9,439 SKU.

No retroceder a datos viejos sólo porque ya estén cargados en Turso.

## TGU

TGU reutiliza el scraper operativo de SPS con su propia selección de ciudad.

No atribuir TGU a `la_colonia_sps`.

Un fallo parcial de TGU no convierte el run global en exitoso y sus datos parciales
no se persisten como estado aceptado.

## Turso

Base:

```text
precios-supermercados
```

La carga vieja conocida es una carga de prueba descartable.

No reemplazarla hasta tener:

```text
SPS válido
+
TGU válido
+
SQLite limpio validado
```

Antes de importar/verificar:

- `PRAGMA integrity_check`;
- foreign keys;
- una fila de supermercado;
- dos ubicaciones;
- conteos de productos/histórico/runs;
- precios;
- `location_id`;
- ausencia de periodos actuales duplicados.

## Tráfico live

Los markers/IDs versionados no conceden autorización nueva.

- no reutilizar autorizaciones consumidas;
- no generar solicitudes nuevas contra La Colonia sin autorización humana explícita vigente;
- artifacts y datos ya obtenidos pueden reutilizarse offline;
- no evadir CAPTCHA, login, 403, 429 ni controles anti-bot;
- una autorización puntual no autoriza recurrencia diaria.

## Desarrollo

```text
AUDITAR
-> IMPLEMENTAR
-> PROBAR
-> CORREGIR
-> CI
-> REVISAR
-> MERGE
-> VERIFICAR
-> SIGUIENTE BLOQUE
```

Fusionar sólo con CI verde.

No usar force push, reset destructivo ni rebase destructivo.

Actualizar documentación sólo con evidencia real.

## Deuda y visualización

BigQuery, Google Sheets, Cloudflare y código histórico pueden permanecer inactivos
si no bloquean el MVP.

La visualización se diseñará después, cuando existan más supermercados y se sepa
qué campos son realmente comparables entre fuentes.

**Cuando compitan una arquitectura más completa y el camino más corto correcto al
MVP, elegir el segundo.**
