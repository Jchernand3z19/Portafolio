# Walmart Honduras — primer full aceptado y SQL validado offline

**GO técnico para los tres catálogos y su persistencia offline.** No se ha cargado
Walmart en Turso, no existe segunda observación real ni se diseñó/activó recurrencia.
El full propio fue autorizado por el usuario por 24 horas desde
`2026-08-31T00:48:01Z` hasta `2026-09-01T00:48:01Z`, respondiendo al preflight de
1,000 GET totales, 20 retries incluidos, concurrencia 1 y 45 minutos. Esa ventana
no convierte una captura puntual en permiso recurrente. El adquirente está cerrado.

## Catálogos aceptados

| Contexto | Productos | SKU/variantes | Con precio | Sin precio | in_stock | out_of_stock |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPS Boulevard del Norte | 13,656 | 13,664 | 13,386 | 278 | 13,162 | 502 |
| TGU FFAA / Fuerzas Armadas | 14,083 | 14,091 | 13,106 | 985 | 13,106 | 985 |
| TGU Las Uvas / El Sauce | 13,989 | 13,997 | 13,663 | 334 | 13,322 | 675 |

Son 41,728 observaciones de producto y 41,752 de SKU **por contexto**; la unión
contiene 16,024 productos / 16,032 SKU distintos Walmart. No sumar tiendas y
presentarlo como identidades globales. Hay ocho variantes adicionales por contexto.
Las 1,597 ofertas sin precio conservan identidad, disponibilidad agotada y precio /
regular / promoción nulos, más los ceros declarados por la fuente.

Scope: ecommerce público del contexto seleccionado, no precio universal de ciudad
ni inventario físico. La diferencia regular/promoción del SKU `68100` sigue siendo
2,195/sí en FFAA y 1,895/no en El Sauce, efectivo 1,895 en ambos; confirma la
[decisión TGU previa al full](../2026-08-31-probe/README.md). No se duplicaron tiendas
por diferencias de stock. SPS sólo tiene un candidato en este selector, sin afirmar
un censo de establecimientos. Binding: `accesscontrollist` de la tienda y
`regionId=base64("SW#" + seller)`, según configuración pública capturada nuevamente.

`AvailableQuantity` sólo aporta señal de disponibilidad; 10,000 no se publica como
inventario exacto. Agotado con precio positivo conserva ese precio. Oferta agotada
con Price/ListPrice/Quantity cero no equivale a producto gratuito. Ausencia del
catálogo no cierra ni convierte el estado previo en agotado. No hay fallback de
precio entre tiendas, conversión de unidades ni previous_price inventado. Banano
SKU `37305` conserva L.9.50 aunque `unitMultiplier=0.25`; el probe contrastó ese
precio visible. Referencias ausentes y disponibilidad no demostrada quedan nulas /
unknown. El padre y todos sus items se conservan; múltiples sellers ambiguos fallan.

## Tráfico y completitud

514 GET nuevos, 513 HTTP 200 y un HTTP 400 esperado al probar `count=250`;
`count=100` quedó demostrado y se utilizó. Cero retries transitorios, concurrencia
1, sin browser, imágenes, JS extra, cookies archivadas, login, carrito, checkout,
mutaciones de sesión, endpoints privados ni SQL Turso. No hubo 401/403/429/CAPTCHA.

La captura duró 1,327.921 segundos, aproximadamente 22 min 8 s, incluyendo una
reanudación del ejecutor para recibir un plan sin reiniciar reloj ni presupuestos.
Primera solicitud 00:50:13 UTC; última 01:12:21 UTC del 31/8. Los timestamps indican
observación del cliente; Date/Age/Cache-Control fuente se conservan y no se afirma
que el backend no tenga cache. No se reutilizó cache comercial de una observación
previa. Las revisiones de metadata usan GET explícitos de verificación.

185 GET tienen scope SPS, 162 FFAA, 166 El Sauce y uno configuración general.
81.183 observaciones de producto/GET, 0.012318 GET/observación; promedio 171.333 GET
por catálogo completo incluyendo controles. El contador de solicitudes duplicadas
evitadas es 0: se conservaron páginas válidas al recuperar residuales, pero no se
inventa una cifra de ahorro hipotético. El tamaño de los cuerpos decodificados es
447,930,150 bytes, distinto de tráfico comprimido facturado. Métricas exactas en
[evidence.json](evidence.json).

20 departamentos suman cada catálogo; hogar se dividió en sus 14 subcategorías
contextuales, porque excedía el límite conservador de 2,500. No se usó category-2
global: el probe detectó que perdería un producto por contexto. Plan inicial:
474 páginas a 100. Se preservan las respuestas originales y dos reparaciones:

1. El Sauce, abarrotes, página 17: devolvió 99 de 100. Dos ventanas de 50 para el
   mismo intervalo recuperaron exactamente 100, incluyendo producto `4126934`,
   sin perder ningún ID anterior. Sólo esas ventanas sustituyen la página inválida.
2. SPS, ropa y zapatería: 1,092 filas pero sólo 1,091 productos; `4110363` repetido.
   Cuatro ventanas menores no resolvieron la unión (introducían otro solapamiento).
   Se preservó ese intento como **no aceptado**. Se consultaron facetas del
   departamento y sus seis subcategorías: 14 páginas entregaron 1,092 IDs únicos,
   incluyendo todos los originales. Se reemplazó únicamente ese departamento.

Resultado: 478 páginas aceptadas, unión de IDs sin huecos/solapamientos contra
cada partición, departamento y total por tienda; facetas antes/después estables.
Las pruebas rechazan el RAW primario si se omite cualquiera de las reparaciones.
Ningún conteo de filas por sí solo concede completitud. El parser que encontraba
una referencia sin Value se corrigió sobre el RAW sin nuevas solicitudes.

## Evidencia y reproducción offline

`raw-capture.tar.gz` contiene todos los cuerpos, incluso error e intentos residuales
fallidos; ledger con URL/método/status/fecha/SHA y headers públicos seleccionados;
planes originales, sustituciones y ejecutor puntual. No ejecutar de nuevo
`acquire.py`: es evidencia de esta autorización consumida, no un nuevo permiso ni
un servicio de scraping. Los scripts de adquisición conservan sus rutas de aquella
operación; la reproducción soportada usa el parser del proyecto, sin red.

Los cuerpos incluyen configuración y campos públicos de VTEX, entre ellos tokens
de ofertas emitidos públicamente. No son credenciales administrativas ni se usan
para autenticación. No se conservaron Set-Cookie, Authorization ni sesiones privadas.
Las URLs de imágenes dentro del RAW no se descargaron.

Los tres `walmart_*.json.gz` son snapshots persistibles con SHA, membership,
observaciones por página y semántica fuente. `evidence.json` fija sus hashes y el
del archivo RAW. Reproducción desde la raíz del repositorio con Python 3.12:

```bash
python -m tarfile -e precios-supermercados-sps/reports/walmart/2026-08-31-full/raw-capture.tar.gz /tmp/walmart-raw-verification
python precios-supermercados-sps/scripts/validar_captura_walmart.py --capture /tmp/walmart-raw-verification --output /tmp/walmart-snapshots-verification
PYTHONPATH=precios-supermercados-sps/src pytest precios-supermercados-sps/tests/test_walmart_capture.py precios-supermercados-sps/tests/test_walmart_persistence.py -q
```

Usar directorios de salida nuevos. Los tests verifican SHA antes de extraer con
filtro seguro, reconstruyen los tres JSON byte a byte con HTTP bloqueado, prueban
RAW alterado, ambas reparaciones necesarias, variantes y precios ambiguos. Los
tests sintéticos no se presentan como segunda observación real.

Suite completa local: 1,976 pruebas pasaron, Python 3.12 y dependencias fijadas;
compilación y CI GitHub se verifican en la entrega del PR antes de fusionar.

## Persistencia y migración mínima

Se reutiliza `actualizar_mvp_turso_la_colonia.py --supermarket walmart`; el CLI local
antiguo de La Colonia no se convierte en otro updater Walmart. La validación del
snapshot precede al SQL. Misma identidad `(supermarket_id, source_key_type,
source_key)` y cinco tablas persistentes, sin servicio, dependencia ni workflow nuevo.

Dos restricciones del esquema anterior impedían representar evidencia real:
`UNIQUE(supermarket_id, city_name)` bloqueaba los dos TGU; precio/promoción NOT NULL
obligaban a inventar datos o perder 1,597 ofertas. El nuevo esquema permite varias
ubicaciones Walmart por ciudad y nulos comerciales sólo para oferta Walmart agotada.
Un índice parcial conserva unicidad por ciudad para las demás cadenas; sus precios
y promociones siguen obligatorios. No se amplió la granularidad de las otras cadenas.

`migrar_mvp_walmart.py --sqlite <copia-local>` es una operación puntual, nunca diaria:
exige la huella exacta del esquema anterior, preserva las filas, reconstruye sólo
locations/price_history con SQL portátil, recrea sus índices, comprueba cantidades,
foreign keys y esquema **antes de commit**; rollback ante error y noop si ya está
migrada. Sigue el [procedimiento SQLite de cambio de esquema](https://www.sqlite.org/lang_altertable.html).
No usa ALTER COLUMN dependiente de una versión reciente. Se probaron tanto ejecución
SQLite local como el protocolo de batch condicional ya existente, con fallo inyectado
tras DROP y conservación de DDL/datos. El preflight Walmart consulta sólo tres filas
de esquema y **rechaza la base antigua antes de escribir**; no migra automáticamente.

La reconstrucción/backup tiene costo global **una sola vez**; no se mezcla con el
costo del hot path. El diario conserva lectura de scope, `delta` materializado una
vez, comparación null-safe, updates de metadata sólo cuando cambian y validación
del scope afectado. No se añadieron consultas por producto ni scans del histórico.

[Prueba completa local](offline-sql-summary.json): copia ya existente con snapshots
reales La Colonia SPS/TGU del artifact 9734740995 y Colonial aceptado, migración,
carga de las tres ubicaciones Walmart y replay exacto. Las cinco tablas terminaron
con 3 supermercados, 6 ubicaciones, 34,746 identidades, 69,923 periodos y 6 runs.
Hashes de todas las filas La Colonia/Colonial iguales antes y después; integrity ok,
foreign keys sin errores, cero periodos actuales duplicados. Cada replay no cambió
ninguna fila. CI también aplica todos los catálogos Walmart y Colonial usando el
SQL productivo sobre SQLite; los escenarios sintéticos cubren aislamiento inverso,
IDs coincidentes, cambios de precio/regular/promoción/disponibilidad, transiciones
con NULL, metadata, incompletos, duplicados, nuevos, ausentes, cronología y rollback.

Costo sintético Walmart con 25% de ofertas nulas:

| N | Instrucciones SQLite | Crecimiento |
| ---: | ---: | ---: |
| 128 | 31,200 | — |
| 256 | 62,400 | 2.00× |
| 512 | 125,300 | 2.01× |
| 128 + 10,000 periodos cerrados | 31,200 | sin aumento |

Run idéntico: sólo un scrape_run; cero writes de productos e histórico. Cambio de
metadata de una oferta sin precio: exactamente un producto actualizado, cero historia.
Planes usan índice de identidad e índice parcial `idx_price_history_current`.
Estas instrucciones VM son proxy local, no lecturas facturadas ni medición Turso.

Gate de simplicidad: tres archivos de producción nuevos por necesidades concretas:
parser/reconciliación Walmart, entrada offline pequeña y migración puntual de dos
restricciones demostradas. Se extiende el updater existente; no hay framework ni
adapter nuevo de producción. Los helpers de transporte pertenecen a pruebas.

## Primera carga Turso: operación pendiente

No se ejecutó SQL remoto. Último control de cuenta: Starter, 713.7 M/500 M lecturas,
overages deshabilitados, reset anunciado 31/8 18:00 Honduras. No se afirma que ya
ocurrió ni se cambió billing. Después del reset y bajo autorización vigente:

1. Confirmar acceso/reset y consumo inicial; verificar cronología/replay de los
   snapshots aceptados y preservar backup previo. No recrawl para probar SQL.
2. Leer esquema y comparar `LEGACY_FINGERPRINT`/target. Si difiere, detener sin
   modificar. Aplicar una sola migración transaccional usando `migration_steps()`
   y el `_run_batch` existente, tras la comprobación previa; verificar huella/FKs.
   Ante respuesta ambigua, reconciliar esquema antes de considerar otra escritura.
3. Descomprimir/verificar SHA y validar los tres snapshots antes de cualquier carga;
   usar el updater existente y run IDs estables, una ubicación por transacción.
   No reintentar escrituras inciertas; reconciliar por run_id + SHA como ya hace
   el updater. La carga de Colonial conserva su propio snapshot y cronología.
4. Verificar únicamente scopes afectados, medir consumo final y separar costo
   extraordinario de migración del de carga. No hacer runs de tuning remotos.
5. Primera carga verificada no sustituye segunda observación real posterior.
   Workflow sólo después de esa evidencia; recurrencia requiere permiso separado.

La validación offline deja código, datos y migración preparados; no certifica la
compatibilidad efectiva del servidor, su esquema actual, su cuota ni una escritura
remota que todavía no se ha realizado.
