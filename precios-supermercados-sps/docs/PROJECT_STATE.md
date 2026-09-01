# Estado actual — Precios de Supermercados SPS

GitHub `main`, Pull Requests, Actions, artifacts y Turso son la fuente de verdad técnica.

## Objetivo activo

Maxi Despensa y Despensa Familiar permanecen **NO-GO TEMPORAL PARA PRICE TRACKING
WEB**. PriceSmart Honduras tiene una fuente pública de catálogo país reproducida
desde la petición real del navegador, pero sigue bloqueado por club: la petición
usa `view_id=HN`, no `6603`, y el probe excedió 27.919 s su ventana. No iniciar
Paiz, otras ciudades ni dashboard. Fuente país, binding de club, full y recurrencia
son gates separados.

Colonial conserva el catálogo demostrado de 9,199 productos / 9,205 variantes.
Su primera persistencia Turso y segunda observación real siguen pendientes.
Walmart conserva tres catálogos aceptados y SQL validado offline, incluidos dos
TGU por diferencias comerciales. **Ni Colonial ni Walmart están cerrados** en
operación remota. Maxi/DF quedan detenidos sin scraper, persistencia ni catálogo.
PriceSmart tiene una respuesta pública aceptada como evidencia técnica de precio
HN, pero no binding causal de club, muestra comparable entre clubes ni integración.

La Colonia conserva el alcance existente:

```text
La Colonia
├── San Pedro Sula
└── Tegucigalpa

database_name = precios-supermercados
storage = Turso
history = cambios comerciales por ubicación
dashboard = fuera del MVP actual
```

No ampliar La Colonia ni construir visualización. Su autorización recurrente no
cubre Colonial, Walmart, Maxi ni DF. Ver la
[fuente, catálogo y frontera operativa Colonial](supermercados/colonial-auditoria-preflight.md).

## Maxi Despensa + Despensa Familiar — NO-GO temporal cerrado

Auditoría previa: main `9592901c95aa2cb447effe1c514fe85eb5e74265`,
[PR #356](https://github.com/Jchernand3z19/Portafolio/pull/356) fusionado,
[CI main verde, 1,985 pruebas](https://github.com/Jchernand3z19/Portafolio/actions/runs/33355963991),
cero PRs abiertos. Biblioteca reusable sin cambios en
`252b245e0f416b57c324db97bc9cee868fc8124d`; seis skills web y
`production-data-engineering` aplicadas, sin copiar skills ni generalizar Walmart.

El usuario autorizó el primer probe conjunto por 24 horas, registrado
2026-08-31T04:20:37Z a 2026-09-01T04:20:37Z, dentro del techo de 40 GET/15 minutos.
**Probe cerrado temprano: 21 GET, 17 HTTP 200, dos 301 al inicio ya capturado,
dos timeouts al destino externo de compra, un retry, concurrencia 1, 273.325 s.**
No full, browser, imágenes, login, mutaciones ni SQL Turso.

La web comparte HTML y localizador de formatos: `4` Despensa / `6` Maxi Despensa,
71/28 entradas. Son marcadores de mapa sin store_id ni vínculo a precios. Hay
**97 filas candidatas / 96 códigos distintos** entre campaña y categoría regular,
pero ningún precio activo utilizable ni comparación de tienda. Los precios de
plantilla comentados `Q20.00`/`Q30.50` no son ofertas. **Cero productos aceptados.**
No se ha demostrado API común con Walmart, formato comercial por SKU, disponibilidad,
paginación ni completitud. El enlace público Compra en línea agotó un retry por
timeout; no se concluye login obligatorio ni bloqueo anti-bot.

**Radiografía mínima:** no existe una fuente estructurada pública observada que
entregue precios reales; tampoco API, JSON, GraphQL o estado embebido con precio
por producto/tienda. La superficie observada funciona como catálogo de campañas,
productos y localizador, sin precio digital utilizable. Cero SKU comparables por
tienda; diferencias de precio, regular, promoción y sólo disponibilidad no son
evaluables, no equivalen a cero diferencias. Los
29 candidatos geográficos son inferencias por dirección/coordenadas, no un censo
SPS/TGU cerrado. Ninguna tienda se consolida o separa ni se convierte en location
productiva. Las cuatro combinaciones de formato/ciudad siguen sin catálogo válido.

[RAW, evidencia reproducible y límites](../reports/maxi-df/2026-08-31-probe/README.md).
Ocho tests offline protegen la evidencia contra precio comentado, unknown como
igualdad, identidad inconsistente y RAW alterado. Se redactaron 28 valores CSRF de
formularios al publicar, con hashes originales/publicados separados. No cambios
a scraper, parser, fixture, SQL, esquema o workflow de las tres cadenas anteriores.
La regresión previa de persistencia pasó 53 tests; no valida persistencia Maxi/DF.

**Decisión final: NO-GO TEMPORAL PARA PRICE TRACKING WEB.** No buscar otra ruta en
el mismo sitio, forzar el destino enlazado, usar browser pesado, reconstruir precios
desde imágenes/PDF/OCR/fuentes indirectas, crear scraper vacío, persistencia, full
crawl ni modificar el modelo. Sólo una fuente digital pública nueva y demostrable,
tratada como trabajo nuevo, permitiría reevaluar ambas cadenas.
[Preflight y evidencia cerrada](supermercados/maxi-df-auditoria-preflight.md).

## PriceSmart Honduras — fuente HN reproducida, club sin demostrar

La captura CDP del `2026-09-01` observó la petición comercial real:
`POST https://www.pricesmart.com/api/br_discovery/getProductsByKeyword`. La carga
de una página devolvió 12/1,124 productos y un replay directo produjo el mismo body
SHA-256. Sólo fueron necesarios `Accept`, `Content-Type` y `Referer`; no hubo
cookie, login, membresía ni carrito. El SKU `479223` enlaza PID, master SKU y
variant SKU, declara HNL con dos decimales, `price_HN=35995`, y coincide con el
precio visible L 359.95. `availability_HN=true` e `inventory_HN=in stock` se
registran aparte. Los campos solicitados de precio regular/ahorro no aparecieron y
los campaign IDs no se interpretan como promoción de precio.

La página anónima mostraba `Seleccionar entrega` y el payload sólo tenía
`view_id=HN`; no existe `6603`, club ni channel en la petición. La respuesta sí
expone facets `price_HN_6602`, `price_HN_6603` y `price_HN_6604`, con 1,072, 1,078
y 1,061 productos en buckets respectivamente, pero los documentos no contienen
esos valores por SKU. No hay SKU comparable por club, diferencias comerciales ni
decisión TGU. Availability no cambia esa conclusión.

Ledger: una sesión, una carga de dos permitidas, una XHR comercial, un replay de
tres permitidos, cero retries y concurrencia 1. La ventana empezó
`03:29:20.765Z` y venció `03:34:20.765Z`; el replay terminó `03:34:48.684Z`,
27.919 s tarde. **Outcome B: fuente pública HN demostrada; binding SPS no
demostrado y protocolo temporal no conforme.** No parser, fixture, scraper, full,
presupuesto, persistencia, modelo, workflow ni Turso.
[RAW y decisión](../reports/pricesmart/2026-09-01-browser-request-probe/README.md).

### Historial GraphQL

Autorización registrada por 24 horas: 2026-08-31T21:53:50Z a
2026-09-01T21:53:50Z. El probe cerró su tramo GET en 8 intentos: 7 HTTP 200, un
fallo CA antes de respuesta seguido de un retry, cero redirects, cuatro assets,
concurrencia 1 y 303.054 s. No browser, POST, mutación, login, carrito, full,
persistencia ni SQL Turso.

El estado Nuxt identifica `https://graphql-commerce.bloomreach.io`, tenant
`pricesmart`, país `HND` y consultas públicas `channels`,
`productProjectionsSearch`, `inventoryEntries` y `products`. El esquema incluye
precio base/descontado, moneda/centavos, `discount.isActive` y disponibilidad por
channel. Clubes: `6602` Florencia (default), `6603` San Pedro Sula y `6604` El
Sauce; ecommerce habilitado en los tres.

Los HTML GET de búsqueda no son aceptables como datos: `Bolsas` devolvió estado de
`Huevos` y `page=3&q=Vegetables` devolvió página 1 de `jabon dove`. La ficha GET
conserva identidad `516411`, pero no contiene el precio `407.95`. Cero SKU con
precio comparable por club; diferencias de efectivo, regular, promoción y sólo
availability siguen `null`. No decidir granularidad TGU por availability.

El endpoint raíz se probó primero y cerró temprano: **1/8 POST, cero retries,
concurrencia 1, 0.2964 s**. `channels` recibió HTTP 404 `Cannot POST /`; esa
petición no alcanzó GraphQL.

La extensión posterior a `/graphql` también cerró en el primer request: **1/7
POST, 6 no consumidos, cero retries, concurrencia 1, 0.323184 s**. El servidor sí
validó GraphQL, pero respondió HTTP 400 `GRAPHQL_VALIDATION_FAILED`: no reconoce
`channels`, `Locale` ni `Point` y propone `findChannels`. No fue un error de auth
ni catálogo vacío. `findChannels` y una consulta adaptada no estaban autorizados,
por lo que no se enviaron `products` ni `productProjectionsSearch`.

La tercera extensión consumió **2/3 POST, cero retries, concurrencia 1 y 17.432829
s**. La introspección limitada recibió HTTP 400 porque Apollo Server la deshabilita.
`findChannels { __typename }` recibió HTTP 200 con `BAD_USER_INPUT`,
`data.findChannels = null` y upstream 404 a
`https://api.sphere.io/changeme/channels?offset=0&limit=500`. El placeholder
`changeme` demuestra ausencia de binding al proyecto PriceSmart con los headers
públicos observados; cambiar argumentos no lo corrige. El tercer POST quedó sin
usar.

Sigue habiendo cero SKU comparables y ninguna decisión de granularidad TGU. Precio
efectivo, regular, promoción, availability y paginación permanecen no evaluables.
**La superficie GraphQL externa queda bloqueada.** La captura CDP posterior
encontró otra API pública de catálogo país, pero no corrige el binding de esa ruta
ni demuestra un club. [RAW y cierre GraphQL](../reports/pricesmart/2026-08-31-graphql-schema-probe/README.md).

Última consulta de cuenta (auditoría previa): Starter, overages deshabilitados,
713.7 M / 500 M lecturas (143%). La CLI mostró reset **30/9/2026 18:00 CST**, frente
al 31/8 anterior: discrepancia sin causa ni habilitación SQL confirmadas. No se
repitió la consulta en este probe; no SQL, cambio de plan ni cobros.

## Walmart — primer full aceptado y persistencia validada offline

Auditoría previa al full: main `ced0ccff2dabec18f5784dd19c0cbfa635c826b7`, PR #353
fusionado, CI de main verde (33345451864), sin PRs abiertos. Biblioteca reusable
`252b245e0f416b57c324db97bc9cee868fc8124d`; se aplican las seis skills web y
production-data-engineering vigente, sin copiar skills ni construir infraestructura.

El probe de 20 GET demostró fuente VTEX pública y una diferencia reproducible de
regular/promoción en SKU `68100`: FFAA 2,195/sí, El Sauce 1,895/no, efectivo 1,895
ambos. Se mantienen **dos contextos TGU**, no por stock. SPS corresponde a Boulevard
del Norte; el selector no demuestra un censo físico ni precio universal de ciudad.
Binding por faceta `accesscontrollist` y `regionId`, según configuración pública.
[Probe y control causal de región](../reports/walmart/2026-08-31-probe/README.md).

**Decisión TGU final, después de comparar los fulls offline:** conservar FFAA y
El Sauce para persistencia productiva. 12,867 SKU compartidos, 12,042 comparables
con precios/promoción conocidos: 11,787 iguales y **255 con diferencia comercial**
(218 efectivo, 197 regular, 57 promoción; campos superpuestos). Los 255 figuran
in_stock en ambos contextos. **331 difieren sólo en disponibilidad** y no justifican
la separación. Otros 602 tienen precio sólo en El Sauce y 223 carecen de precio
en ambos: no se cuentan como igualdad ni diferencia comercial. Hay 933 diferencias
de disponibilidad en total, incluidas las 602 no comparables.

[Comparación completa y decisión](../reports/walmart/2026-08-31-full/TGU-COMPARISON.md):
28,088 filas TGU contrastadas con 319 páginas RAW, mismos SKU y unidades, cero
conflictos de identidad. CSV auditable para toda la intersección y evidencia por
cada diferencia. El control de región del SKU 68100 se reproduce en ambos fulls;
las capturas no simultáneas no equivalen a 255 experimentos causales individuales.
No nuevo tráfico live ni SQL Turso. La granularidad, snapshots y migración ya
preparados permanecen sin cambios; disponibilidad no determina la decisión.

El usuario autorizó expresamente el full por 24 horas desde **2026-08-31 00:48:01
UTC** hasta **2026-09-01 00:48:01 UTC**, respondiendo al preflight de 1,000 GET,
20 retries incluidos, concurrencia 1 y 45 minutos. Captura terminada/cerrada:
**514 GET**, 513 éxitos y un 400 de page_size, cero retries, **1,327.921 s**.
No browser, assets, sesión mutable, consultas Turso ni permiso recurrente.

| Contexto | Productos | SKU | Con precio | Sin precio |
| --- | ---: | ---: | ---: | ---: |
| `walmart_sps` | 13,656 | 13,664 | 13,386 | 278 |
| `walmart_tgu_ffaa` | 14,083 | 14,091 | 13,106 | 985 |
| `walmart_tgu_el_sauce` | 13,989 | 13,997 | 13,663 | 334 |

41,752 observaciones SKU por ubicación; unión Walmart 16,032 SKU distintos. Las
ofertas agotadas con precio cero conservan precio/regular/promoción NULL y ceros
fuente, sin gratis, descarte ni precio prestado. Cantidad disponible es sólo señal,
no inventario exacto. Se preservan todas las variantes y metadatos ausentes.

[Full, RAW, hashes, métricas y límites](../reports/walmart/2026-08-31-full/README.md).
478 páginas aceptadas contra facetas antes/después, unión por ID y total por tienda.
Dos residuales quedaron resueltos dentro del presupuesto: una página El Sauce de
99/100 y ropa SPS de 1,092 filas/1,091 IDs. RAW conserva intentos fallidos y reparación
mínima; los tests fallan si se elimina cualquiera de las sustituciones necesarias.
Los tres JSON se reproducen byte a byte sin HTTP. No se recrawleó por bugs del parser.

Se extiende el updater Turso existente, con exactamente cinco tablas. Migración
puntual preparada y validada localmente: permitir dos ubicaciones Walmart en TGU
y nulos de precio/promoción sólo para oferta Walmart agotada; se conservan las
restricciones de las otras cadenas. Exige huella de esquema conocida, comprueba
filas/FKs antes de commit y hace rollback ante error. Walmart rechaza el esquema
antiguo antes de escribir; ninguna migración automática en la operación diaria.

SQL productivo aplicado offline a los catálogos reales junto con La Colonia SPS/TGU
y Colonial: 3 cadenas, 6 ubicaciones, 34,746 identidades, 69,923 periodos, 6 runs.
Las filas de ambas cadenas anteriores permanecen iguales; replay exacto sin writes,
integridad correcta y cero duplicados actuales. Pruebas cubren aislamiento inverso,
IDs coincidentes, historia, NULL, metadata, incompletos, cronología y rollback.

Costo sintético Walmart N/2N/4N 128/256/512: **31,200/62,400/125,300 instrucciones
SQLite**. Añadir 10,000 periodos cerrados mantiene 31,200 para N=128. Sin cambios,
sólo scrape_run; delta una vez e índices existentes. No es consumo facturado Turso.
[Resultado completo](../reports/walmart/2026-08-31-full/offline-sql-summary.json).

**Objetivo de esta espera cumplido técnicamente: catálogo aceptado y SQL validado
offline, con datos/migración listos para primera carga controlada.** La verificación
remota depende del reset, backup, esquema actual y autorización vigente. Migrar una
vez tiene costo extraordinario separado del hot path. No existe segunda observación
real ni workflow Walmart. No activar recurrencia implícitamente.

Suite completa local: **1,976 pruebas pasaron** con Python 3.12 y dependencias del
proyecto. La entrega requiere CI del PR y main verdes; no se interpreta el resultado
local como ejecución GitHub ni persistencia Turso.

## Eficiencia compartida vigente — PR #351

El [PR #351](https://github.com/Jchernand3z19/Portafolio/pull/351) materializa `delta`
una vez, evita updates de metadata idéntica y limita la verificación diaria a
La Colonia SPS/TGU. No añade tablas persistentes ni cambia las cinco existentes.
Walmart reutiliza esta ruta; su evidencia específica se documenta arriba.

Revalidación offline de auditoría: 48 tests de persistencia, costo, Colonial RAW
y seguridad de workflows pasaron. N/2N/4N = 128/256/512 produjo 31,800/63,400/127,300
instrucciones SQLite (1.99× y 2.01×). Run sin cambios: un `scrape_run`, cero writes
de productos/histórico. El plan utiliza el índice parcial de periodos actuales;
no recorre todo `price_history`. Son datos sintéticos del updater existente, no
validación Walmart ni consumo facturado. Ver [criterio de costo](../reports/turso-cost-aware-persistence.md).

No ejecutar tuning remoto. Tras el reset y con autoridad vigente: medir consumo
inicial, persistencia controlada, medir consumo final y verificar el ámbito afectado.

## Colonial: primer catálogo aceptado, Turso bloqueado

Autorización de 24 horas registrada el 2026-08-30 a las 20:10:18 UTC; vence el
2026-08-31 a las 20:10:18 UTC. No autoriza recurrencia ni cambios de facturación.
El catálogo público corresponde a `colonial_sps`; no se inventan sucursales ni
inventario físico. JSON de variantes + botones HTML para stock + sitemaps para
membership: 9,199 productos y 9,205 variantes, 7,726 in_stock / 1,473 out_of_stock /
6 unknown. Las seis variantes sin botón propio conservan disponibilidad unknown.

Full: 426 GET nuevos + 7 respuestas reutilizadas = 433 recursos; cero fallos y
retries, concurrencia 1, sin imágenes ni browser. 439 GET nuevos contando los dos
probes. La corrección de un caso precio-mínimo/variante se hizo sobre RAW, sin
repetir el crawl. [Snapshot y RAW reproducibles](../reports/colonial/2026-08-30/README.md),
con fechas fuente 20:11:03–20:31:00 UTC y SHA del snapshot
`2f7861ff6decd0f7e95a82c321d71e1cd7fe2e6440b6794bbe94c6457b41e2fd`.

Implementación específica sin dependencias nuevas. El updater Turso existente
admite `--supermarket colonial` y registra `colonial` / `colonial_sps` dentro de
la transacción. Mantiene las cinco tablas, histórico por cambios y validación
antes de cualquier SQL. Pruebas offline cubren los trece escenarios requeridos,
replay, rollback e identidades coincidentes entre cadenas. El catálogo completo
aplicado al SQL productivo sobre SQLite junto a SPS/TGU conserva La Colonia e
integridad; **no equivale a persistencia Turso ni segundo run real**.

Suite completa local con Python 3.12 y dependencias fijadas del proyecto:
1,905 passed, 21 skipped. Incluye reproducción de la captura íntegra con HTTP
bloqueado. CI de PR y main deben confirmar la revisión publicada.

Entrega en [PR #349](https://github.com/Jchernand3z19/Portafolio/pull/349).
El primer CI pasó todos los casos Colonial, pero detectó una carrera en un fixture
antiguo del selector: su timer de 1.8 s podía vencer antes del primer click.
Se reprodujo offline y se cambió sólo el fixture para que el primer click siempre
sea noop; se mantienen las aserciones de reintento y el código productivo intacto.

Revisión adicional de convivencia: el verificador diario de La Colonia filtraba
periodos abiertos de todas las cadenas y los comparaba con sólo SPS/TGU. Se acota
esa consulta por `supermarket_id='la_colonia'` para que `colonial_sps` no provoque
un falso fallo después de persistir. La prueba ejecuta el SQL extraído del YAML
contra ambas cadenas: falla antes del filtro y pasa con él. Revisión de seguridad:
sin nuevos triggers, permisos, secretos, acciones, requests ni workflow Colonial.

Bloqueo observado durante el cierre Colonial: Turso plan Starter, 713.7 M / 500 M
lecturas (143%), overages deshabilitados. Entonces la CLI anunció reset
31/8/2026 18:00 CST, después del vencimiento live
(31/8 14:10:18 CST). No se cambió facturación ni se intentó sortear el bloqueo.
La auditoría Maxi/DF arriba registra una fecha diferente; no usar ésta como vigente.
Siguiente: restablecer lecturas, primera carga y verificación, segunda observación
real autorizada sin cache comercial anterior, persistir/verificar y sólo entonces
workflow mínimo. No se construyó ni activó workflow Colonial anticipadamente.

## Persistencia MVP

El modelo usa exactamente cinco tablas:

```text
supermarkets
locations
products
price_history
scrape_runs
```

Identidad de producto:

```text
supermarket_id + source_key_type + source_key
```

Estado comercial histórico por producto + ubicación:

```text
current_price
reported_regular_price
is_promotion
availability
```

Reglas vigentes:

```text
mismo estado -> registrar scrape_run, no abrir historia nueva
estado cambió -> cerrar periodo actual y abrir periodo nuevo
producto nuevo -> insertar producto y abrir periodo inicial
replay exacto -> no duplicar
snapshot inválido/incompleto -> no mutar estado aceptado
```

`actualizar_mvp_sqlite_la_colonia.py` prueba estas reglas offline y
`actualizar_mvp_turso_la_colonia.py` las aplica directamente en Turso mediante el
protocolo HTTP de Turso, sin subir de nuevo el archivo SQLite y sin agregar otra
dependencia.

## Base limpia inicial SPS + TGU

La base se reconstruyó desde los dos primeros snapshots completos aceptados:

```text
workflow_run_id = 33151305834
artifact_id = 9677798005
artifact_digest = sha256:81494e24a162d0f0d83bb9151b63c8933a00ff7acaa27a471783698a6f06af86
sqlite_sha256 = 9da2a6665b1a8d466ed59bb58730c52bd0b55f6bb1c6793a668adaaeb504cf14

supermarkets = 1
locations = 2
products = 9509
price_history = 18966
scrape_runs = 2
open_price_history = 18966
duplicate_open_periods = 0
```

Snapshot inicial SPS:

```text
workflow_run_id = 33143530292
artifact_id = 9675011477
location_id = la_colonia_sps
catalog_products_reported = 9469
skus_extracted = 9471
in_stock = 7093
out_of_stock = 2378
sps_region_fingerprint = d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7
json_sha256 = 9c1b3015da39cd283d97bd66d694e5719700c58b5063d797934235c4ff7a6581
```

Snapshot inicial TGU:

```text
workflow_run_id = 33150113253
artifact_id = 9677584556
location_id = la_colonia_tgu
catalog_products_reported = 9493
skus_extracted = 9495
in_stock = 7584
out_of_stock = 1911
json_sha256 = 97c688290b5b1d00580c908d20164fa41f0282cb2f133e95e73030ac16bc0595
```

La unión inicial contiene 9,509 identidades SKU únicas. SPS y TGU comparten la
identidad del producto y conservan estado comercial independiente por ubicación.

## Turso — base limpia y persistencia directa comprobadas

Base única:

```text
precios-supermercados
```

La carga vieja de prueba fue eliminada el `2026-08-28`, la base fue recreada desde
el SQLite limpio y `TURSO_AUTH_TOKEN` fue renovado en GitHub.

La persistencia directa GitHub -> Turso quedó implementada en `main` mediante el PR
#340. Mantiene las cinco tablas y usa transacción fail-closed para cada snapshot.

## Segunda observación real — aceptada

Ejecución conjunta:

```text
workflow_run_id = 33197121042
artifact_id = 9697218431
artifact_digest = sha256:d6d5196dc7f52b6fa00da691c516d41fd5e4e456276ca5c898140caad2ad049e
```

SPS:

```text
scrape_run_id = 33197121042-sps
catalog_products_reported = 9469
skus_extracted = 9471
json_sha256 = 2aca3c7b4ee89ed77c750654be1c3d2c5ae6f98b7e8ff020a1de0886706cb55a
history_opened = 793
history_closed = 793
```

TGU:

```text
scrape_run_id = 33197121042-tgu
catalog_products_reported = 9493
skus_extracted = 9495
json_sha256 = b3c4c9390a3a5da8467a041d0c4cfcb7df4ed1cf8255aef8e94304a380ebaa36
history_opened = 555
history_closed = 555
```

Estado de Turso después de aceptar ambos snapshots:

```text
products = 9509
price_history = 20314
scrape_runs = 4
open_price_history = 18966
duplicate_open_periods = 0
```

Un timeout HTTP del cliente ocurrió después de que Turso había confirmado el commit
de SPS. El estado se reconcilió por `scrape_run_id` + SHA antes de continuar; no se
repitió una escritura incierta.

## Tercera observación real — aceptada e idempotente

Ejecución conjunta:

```text
workflow_run_id = 33202545775
artifact_id = 9698730415
artifact_digest = sha256:fcb11c5a5aea8ac17568eb881839d02ac7563b3f1da85fc446b4a131c50720ab
```

SPS:

```text
scrape_run_id = 33202545775-sps
catalog_products_reported = 9469
skus_extracted = 9471
json_sha256 = 1cfa1bd6500928f0f5c5259cd09b23601c1260f0f22d748990f17b9d7fb353d8
history_opened = 0
history_closed = 0
```

TGU:

```text
scrape_run_id = 33202545775-tgu
catalog_products_reported = 9493
skus_extracted = 9495
json_sha256 = edff6d902ab63f9b9119f10869abee5d718d1822d72448980efc9397e1343d3d
history_opened = 0
history_closed = 0
```

La verificación posterior desde GitHub Actions (`33203720746`) confirmó ambos runs
y el estado final:

```text
products = 9509
price_history = 20314
scrape_runs = 6
open_price_history = 18966
duplicate_open_periods = 0

la_colonia_sps:
  in_stock = 7093
  out_of_stock = 2378

la_colonia_tgu:
  in_stock = 7790
  out_of_stock = 1705
```

La tercera observación demuestra la idempotencia real requerida: los dos
`scrape_runs` se registraron, pero `price_history` no aumentó porque el estado
comercial era igual al aceptado en la segunda observación.

## Flujo MVP

PR #343 integró el único flujo permanente de actualización y PR #344 eliminó los
conteos fijos de catálogo de su verificación final. `main` quedó en
`53b7c3222a10b089f6c101c0909c559f1d3644fb` con CI verde.

```text
workflow_dispatch autorizado o schedule diario autorizado
-> SPS completo read-only
-> TGU completo read-only
-> validar ambos snapshots
-> persistir SPS en Turso
-> persistir TGU en Turso
-> reconciliar cada commit por run_id + SHA
-> validar estados abiertos contra los conteos de los snapshots aceptados
-> exigir cero periodos abiertos duplicados
-> publicar artifact de evidencia
```

No agrega servicios, tablas ni un segundo mecanismo de scraping. Los timeouts
ambiguos de escritura se resuelven únicamente con una comprobación read-only
acotada del commit; no se reintenta una escritura de estado desconocido. Los
conteos diarios se derivan de los snapshots aceptados para permitir crecimiento
normal del catálogo sin tocar el workflow.

## Ejecución diaria autorizada

El usuario autorizó explícitamente el `2026-08-28T19:53:13Z` el paso de ejecución
diaria recurrente para terminar el MVP de La Colonia, manteniendo el alcance sin
sobreingeniería.

```text
scope = La Colonia SPS + TGU
mode = full catalog read-only + validación + persistencia Turso
cadence = daily
cron_utc = 17 11 * * *
local_time = 05:17 America/Tegucigalpa
status = authorized until revoked
```

El workflow está en `main`, conserva `workflow_dispatch` para operación manual
autorizada y usa el mismo job para el `schedule`; no existe un pipeline paralelo.

Las ramas `ops/la-colonia-24h-validation-20260828`,
`feature/la-colonia-mvp-manual-production` y `fix/la-colonia-daily-dynamic-counts`
fueron reconciliadas con `main`, por lo que ya no conservan workflows temporales ni
código divergente del cierre.

## Precio

```text
current_price          = precio efectivo observado
reported_regular_price = precio regular/tachado declarado por la fuente
previous_price         = current_price del periodo histórico aceptado anterior
```

Los precios persistidos se almacenan en centavos enteros.

## Seguridad y live

```text
ACTIVE_AUTHORIZATION_IDS = []
```

Ese campo conserva únicamente autorizaciones puntuales one-shot; no representa la
autorización recurrente diaria documentada arriba.

La autorización temporal de 24 horas usada para las observaciones #2 y #3 sigue
siendo evidencia histórica y no se interpreta como autorización abierta.

La autorización recurrente anterior cubre únicamente el schedule diario de La
Colonia SPS + TGU. Cualquier tráfico live fuera de ese alcance requiere autorización humana explícita vigente.
Los artifacts existentes pueden analizarse, verificarse y persistirse sin volver a
consultar el sitio cuando su identidad y SHA están comprobados.

## Schedule observado — bloqueo compartido de Turso

La auditoría del 2026-08-30 sobre `main`
`f34a324b2cb177baa77ce788c360476268af0f01` encontró dos ejecuciones por
`schedule`, ambas fallidas; por tanto, no se declara cierre operativo:

- [33260860123](https://github.com/Jchernand3z19/Portafolio/actions/runs/33260860123):
  timeout de catálogo TGU; el PR #346 añadió retry acotado y fue fusionado con CI
  verde. No se repite esa corrección.
- [33319436863](https://github.com/Jchernand3z19/Portafolio/actions/runs/33319436863):
  ambos catálogos completos, pero el preflight de persistencia SPS y TGU recibió
  de Turso `BLOCKED`: `SQL read operations are forbidden`. La verificación final
  también fue rechazada. El error precede al batch de mutación; este run no
  demuestra nuevas escrituras ni permite certificar el estado actual de Turso.
- [33422772623](https://github.com/Jchernand3z19/Portafolio/actions/runs/33422772623):
  ambos downloads SPS/TGU terminaron, pero la aceptación falló antes de persistir
  con `SnapshotError("snapshot_sku_count_mismatch")`. Todas las etapas Turso y sus
  verificaciones quedaron omitidas. Artifact `9770327081`, digest
  `b9a7978055290e0e8a535c333beeebe6709c58ae5397be67fdfcf7dc37221d3`.
  Este estado no autoriza inferir cuota restablecida ni corregir el incidente dentro
  del cierre Maxi/DF/PriceSmart.

La consulta read-only `turso plan show` de aquella auditoría confirmó plan `starter`,
excedentes deshabilitados y 713.7M filas leídas sobre una cuota de 500M (143%). La CLI
indicó entonces reinicio el 2026-08-31 a las 18:00 CST; la auditoría Maxi/DF registra
arriba una fecha distinta sin confirmar acceso SQL. No se cambió billing, storage
ni credenciales.
El bloqueo afecta también a la futura persistencia de Colonial. `turso db inspect
precios-supermercados --queries` no devolvió estadísticas por consulta; no permite
atribuir una cifra exacta facturada a cada sentencia.

Se reprodujo offline un defecto del SQL aplicable a la futura integración Colonial:
`close_history` recorría toda la tabla temporal `incoming` por cada periodo sin
cambios. El [PR #348](https://github.com/Jchernand3z19/Portafolio/pull/348) añade sólo
un índice único de identidad mediante `UNIQUE(source_key_type, source_key)` en esa
tabla TEMP existente. Con 1,000 productos la comprobación pasó de aproximadamente
13,018,000 a 34,000 instrucciones SQLite. La regresión falla sin el cambio y pasa
con él; ocho tests de persistencia pasan offline. Esto no restablece la cuota ni
demuestra todavía ahorro facturado en Turso.

Los snapshots del segundo schedule se verificaron offline con el validador de
`main`, sin repetir tráfico al supermercado:

```text
artifact_id = 9734740995
artifact_sha256 = 722c3aeb5adeffd5d4f9ff6db2c1cd05fc9c2289ed2e74e1f9a230de53ed90ef
SPS = 9469 productos / 9471 SKU / 7091 in_stock / 2380 out_of_stock
SPS_json_sha256 = ccf36e969d4c33973125690715d7a12c6c20300cd26d7bcad68a3e47095232e6
TGU = 9493 productos / 9495 SKU / 7820 in_stock / 1675 out_of_stock
TGU_json_sha256 = d8c583d112fa3874ba56f44c186fee774b5d32abf0ef51acbbb15c6e606b8a2a
```

El artifact existente permite recuperar esas observaciones sin recrawl después
de resolver el acceso y comprobar cronología/replay contra Turso. Los conteos
históricos anteriores siguen siendo evidencia de sus runs, no una lectura actual.

## Pendiente operativo

```text
1. tras reset Turso, medir consumo, comprobar esquema/cronología y preservar backup
2. migrar una vez las restricciones demostradas y cargar observaciones aceptadas bajo autorización vigente
3. verificar primera carga y consumo de Colonial/Walmart, sin runs de tuning remotos
4. obtener segunda observación real posterior bajo autorización propia; recurrencia separada
5. comprobar una ejecución diaria íntegramente correcta de La Colonia
```

En paralelo, Maxi/DF queda cerrado como NO-GO temporal y PriceSmart bloqueado sin
binding público del tenant. No probar productos, credenciales, configuración u otro
endpoint de PriceSmart sin una fuente pública nueva o autorización específica para
un mecanismo distinto. No esperar a Turso ni reutilizar autorizaciones o POST no
consumidos de alcances anteriores.
La espera de cuota no justifica activar cobros ni ampliar la arquitectura.

## Fuera del alcance actual

No trabajar ahora en:

- dashboard;
- supermercados distintos de La Colonia, Colonial, Walmart y el preflight PriceSmart;
- ciudades distintas de SPS/TGU;
- recurrencia nueva para Colonial, Walmart o PriceSmart;
- reabrir Maxi Despensa o Despensa Familiar sin fuente digital pública nueva;
- Paiz;
- BigQuery;
- Google Sheets;
- Cloudflare;
- APIs públicas;
- microservicios;
- comparación entre supermercados;
- inventario exacto;
- normalización perfecta.

La deuda histórica que no bloquee el MVP puede permanecer hasta después del cierre
de La Colonia.
