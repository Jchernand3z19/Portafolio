# Walmart: probe demostrado, no catálogo completo

Autorización propia del usuario por 24 horas, registrada conservadoramente desde
2026-08-31 00:17:55 UTC hasta 2026-09-01 00:17:55 UTC. Respondía al preflight de
20 GET, hasta dos retries incluidos, concurrencia 1 y diez minutos. **No autoriza
full ni recurrencia.** No se ejecutó SQL Turso ni se modificó facturación.

## Resultado y evidencia

- 20 GET entre 00:21:23 y 00:28:39 UTC; 436.847 s hasta completar el último.
- 19 respuestas exitosas: 17 HTTP 200 y dos 206. Un 400 al comprobar página 51,
  conservado como evidencia de límite, sin retry. Cero 401/403/429 o CAPTCHA.
- Conexión/sesión reutilizada, concurrencia 1, al menos un segundo entre inicios,
  cero retries y cero URLs repetidas. Dos scripts esenciales enlazados por HTML.
- 7,902,798 bytes de cuerpos; 271 observaciones SKU, 170 SKU distintos: 8.5 SKU
  distintos por GET y 0.118 GET por SKU distinto. Incluye pruebas de contexto y
  paginación, no es una estimación de rendimiento de full. No se midió un contador
  de requests evitados; no se inventa. Ningún catálogo completo adquirido.
- Sin navegador, imágenes, CSS, fuentes, analytics, login, checkout, carrito,
  mutaciones de sesión ni endpoints privados. Las referencias en HTML no se abrieron.

`raw-capture.tar.gz` contiene los 20 cuerpos, `ledger.json` con URL/método/status/
fecha/SHA y el ejecutor puntual utilizado. Los cuerpos son los bytes después de
la decodificación HTTP de `requests`; no son el stream comprimido de transporte.
No se archivaron headers ni cookies. La fuente pública contiene configuración
del frontend y tokens públicos de precio de corta duración; no se usan como
credenciales ni se reproducen sus valores en el informe. No hay respuestas autenticadas.

`evidence.json` conserva 200 filas de las cuatro muestras de 50, los cuatro casos
sin precio de las páginas de partición, métricas y decisión comercial. **No tiene
el contrato de un snapshot persistible**. `verify.py` es un verificador puntual
de este reporte: no hace red, no es un scraper productivo ni un framework.

```bash
python precios-supermercados-sps/reports/walmart/2026-08-31-probe/verify.py --check
```

Reproduce hashes, HTML→tienda→región, identidad, precio visible, comparación TGU,
control de región y cardinalidades. Los tests también rechazan RAW alterado y una
oferta disponible con precio cero ambiguo. No ejecutar de nuevo el adquirente archivado.

## Fuente e identidad

El HTML propio confirma VTEX, cuenta `walmarthn`, cultura `es-HN`, HNL. La API
Legacy Search entregó un producto y 50 productos en siete departamentos, con dos
promociones. La [API pública Search](https://developers.vtex.com/docs/api-reference/search-api)
fue la primera hipótesis estructurada probada. Su vendedor genérico `1` no prueba ciudad.

Identidad propuesta: `walmart + item_id + items[].itemId`; conservar `productId`
como padre, EAN y referencia como evidencia, sin matching entre cadenas ni por nombre.
Las muestras tienen una variante por producto; esto no demuestra que todo Walmart
sea de variante única. Cualquier full debe recorrer todos los `items`, detectar
colisiones de SKU y no elegir arbitrariamente entre varias ofertas.

El primer SKU `37305`, Banano Maduro, tiene `Price=ListPrice=9.50`. El HTML del
producto confirma nombre, EAN y precio visible **L.9.50**. Aunque la API declara
`measurementUnit=kg`, `unitMultiplier=0.25` y `FullSellingPrice=2.37`, multiplicar
el precio daría un valor distinto del mostrado. Conservar los campos fuente sin
convertir unidades ni reemplazar `Price` por `FullSellingPrice`.

## Binding y decisión TGU

El selector publicado enumera cuatro tiendas; sólo una está etiquetada SPS y dos
TGU. Esto demuestra el selector de este ecommerce, no un censo exhaustivo de
establecimientos físicos. La Ceiba se observa en configuración global, pero no se
solicitó su catálogo. Las etiquetas departamento/zona filtran candidatos; no se
convierten automáticamente en ubicaciones distintas.

| Contexto comercial | sellerId publicado | Granularidad demostrada |
| --- | --- | --- |
| SPS Boulevard del Norte | `walmarthnwm947` | Contexto de esa tienda |
| TGU Boulevard FFAA / Fuerzas Armadas | `walmarthnwm4041` | Contexto de esa tienda |
| TGU Las Uvas / El Sauce | `walmarthnwm4410` | Contexto de esa tienda |

El frontend aplica faceta pública `accesscontrollist=<sellerId>` para membership
y `regionId=base64("SW#" + sellerId)` para región. La traducción a GET explícitos
está documentada en la [migración oficial a Intelligent Search v1](https://developers.vtex.com/docs/guides/migrating-to-intelligent-search-api-v1).
Se probaron esos parámetros públicos observados; no se creó o modificó una sesión,
ni se alteraron controles de acceso. No se utilizó el endpoint de regiones bajo
`checkout`, porque estaba fuera del probe acordado.

Los 50 productos por contexto se obtuvieron mediante GET
`/api/intelligent-search/v1/product-search/accesscontrollist/<sellerId>` con
`regionId`, `sc=1`, `locale=es-HN`, `country=HND`, `page=1`, `count=50`.
Las ofertas siguen rotuladas `sellerId=1`; **esa etiqueta no es el binding**.
Lo demuestran la configuración y la respuesta al cambiar únicamente `regionId`.

TGU comparte **41 SKU**, siete departamentos, con 40 promociones/1 normal en FFAA
y 39 promociones/2 normales en El Sauce. Quedan nueve SKU de cada muestra fuera
de la intersección: no se trataron como equivalentes ni como agotados.

| SKU `68100`, producto `4123576`, Enfriador Mainstays 12 L | Efectivo | Regular | Promoción |
| --- | ---: | ---: | --- |
| FFAA, muestra y búsqueda puntual | 1,895 | 2,195 | sí |
| El Sauce, muestra y búsqueda puntual | 1,895 | 1,895 | no |
| Control: misma faceta FFAA, sólo región cambia a El Sauce | 1,895 | 1,895 | no |

RAW 07/08: comparación; 09/10: reproducción por búsqueda acotada; 09/12: control
de una variable. Cambiar región cambió el precio regular manteniendo membership,
término y resto de parámetros. Decisión: **dos contextos comerciales TGU** por una
diferencia reproducible de regular/promoción, no por stock. No se afirma un precio
universal TGU ni que la muestra sea estadísticamente representativa del catálogo.
El nombre «Cascadas» no está confirmado por esta configuración actual.

Hay dos configuraciones HTML con el mismo sellerId El Sauce y postal codes
`441001`/`441005`; no se escogió una arbitrariamente. El GET demostrado utiliza
seller/región y no necesita esos códigos. El contexto no representa todas las zonas
de entrega de la ciudad.

## Precios no disponibles y persistencia pendiente

En la muestra regional, `Price` y `ListPrice` permiten comparar efectivo y regular;
`ListPrice > Price` demuestra promoción. `PriceWithoutDiscount` no sustituye al
regular: en el caso FFAA es 1,895 aunque `ListPrice` sea 2,195.

`AvailableQuantity=10000` es una señal de oferta disponible, **no stock físico
exacto**. Las cuatro ofertas de páginas de partición con Price/ListPrice/Quantity
en cero se conservan como `out_of_stock`, precio y promoción desconocidos, más los
ceros originales. No son productos gratis, no se eliminan del membership, no se
rellenan con precios de otra tienda y no se arrastra un precio anterior como actual.
Ausencia en una página/catálogo tampoco demuestra agotamiento.

El contrato persistible vigente exige precio y promoción no nulos y aún rechaza
Walmart por supermercado. **No está lista la persistencia Walmart.** Esta evidencia
justifica resolver la representación de oferta sin precio antes de aceptar la
carga, dentro de las cinco tablas y el hot path existente; no pasar cero artificial
ni omitir filas para hacer que el validador acepte. No se modifica SQL o esquema
en esta entrega de probe. El full puede capturar y reconciliar todos los registros
sin presentarlos prematuramente como snapshot aceptado.

## Paginación y presupuesto de full propuesto

| Contexto | Productos indexados | Particiones estimadas | Páginas a 50 |
| --- | ---: | ---: | ---: |
| SPS | 13,656 | 33 | 291 |
| TGU FFAA | 14,083 | 33 | 300 |
| TGU El Sauce | 13,989 | 33 | 299 |
| Total de observaciones por contexto, no productos únicos globales | 41,728 | 99 | 890 |

Son cardinalidades observadas, no catálogos descargados. La página 51 del listado
SPS dio 400. No basta iterar hasta el último enlace y declarar completo.
Los 20 departamentos suman el total por contexto. Sólo hogar excede 2,500:
2,577/2,601/2,567. En SPS, sus 14 subcategorías suman exactamente 2,577; ninguna
excede el límite. Las mismas claves, presentes en facetas globales TGU, suman sus
totales de hogar, pero la jerarquía contextual TGU debe confirmarse al iniciar full.
Usar sólo `category-2` global perdería **un producto por contexto**; por eso se
mantienen departamentos completos y se divide únicamente el departamento grande.

La partición SPS hogar/accesorios-para-cocina declara 409 productos: página 1
entrega 50 y página 9 entrega 9, sin intersección entre ambas. **No se descargaron
las siete intermedias ni se afirma ausencia de huecos en ese catálogo todavía.**
`count=50` está demostrado; un tamaño mayor no se probó. El presupuesto parte de
50 y puede reducirse sólo si una respuesta inicial demuestra mayor tamaño soportado.

**Solicitud full, todavía no autorizada:** hasta **1,000 GET nuevos totales**,
incluidos hasta **20 retries transitorios** (máximo uno por recurso), concurrencia
**1**, al menos un segundo entre inicios y **45 minutos** máximos. Mismo dominio
público Walmart; sin browser, assets, sesión mutable, carrito, checkout o Turso.
Incluye configuración/totales antes y después, como máximo dos pruebas acotadas
de page_size mayor, páginas por partición, verificación y recovery residual.
890 páginas + aproximadamente 12 metadatos + dos pruebas + 20 retries = 924;
el saldo es techo de contingencia, no tráfico obligatorio ni permiso de recrawl.

Criterios antes de aceptar full:

1. Confirmar en esa captura los tres bindings y facetas; si cambian, fallar cerrado.
2. Confirmar particiones sin huecos, con sumas al total. Si alguna no cabe, dividir
   sólo con facetas públicas demostradas y dentro del presupuesto; no truncarla.
3. Preservar cada página, fecha, parámetros, status, cuerpo y SHA antes del parseo.
   Capturar también headers de paginación/cache permitidos, nunca cookies/secretos.
4. Verificar tamaño por página, unión de IDs por partición, total declarado,
   ausencia de páginas repetidas, unión global y total antes/después. Conflictos,
   duplicados ambiguos o cambios de total quedan como residual/rechazo, no éxito.
5. Preservar variantes, ofertas sin precio y unknowns. El precio cero no se vuelve
   precio válido para pasar validación. Probar el contrato antes de persistir.
6. Reusar páginas RAW válidas de esa observación; repetir sólo fallos transitorios
   o residuales demostrados. Parser fallido se corrige offline. Detener ante
   401/403/429, CAPTCHA/login/anti-bot, presupuesto o deadline; no evadir límites.

Después: parser específico mínimo, catálogo reconciliado, adaptación del contrato
sin inventar datos, SQL productivo sobre SQLite, histórico/replay/rollback,
aislamiento en ambas direcciones con las dos cadenas existentes y costo N/2N/4N
si cambia SQL. Nada de persistencia remota, segunda observación o recurrencia
implícita. [Estado del proyecto](../../../docs/PROJECT_STATE.md).
