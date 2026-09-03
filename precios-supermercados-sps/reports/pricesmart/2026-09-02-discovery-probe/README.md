# PriceSmart Honduras — probe Discovery de raíces y page size

> Estado posterior: el intento de reutilizar ventanas parciales detectó un cambio
> de orden y se detuvo tras un POST. El presupuesto revisado está en
> [`../2026-09-02-remaining-full-abort/README.md`](../2026-09-02-remaining-full-abort/README.md).

## Resultado live

El probe autorizado consultó las 25 raíces distintas de `G10D03 / Alimentos`
con `start=0`, `rows=12` y proyección SPS 6603. Después probó `rows=200` una sola
vez sobre la raíz más grande, `H30D22 / Hogar`: la respuesta entregó 200 de 315
productos. No se consumieron las pruebas de 100 o 50.

```text
POST autorizados                  31
POST ejecutados                   26
HTTP 200                          26
retries                            0
presupuesto no consumido           5
documentos retornados            455
concurrencia                       1
duración                       16.381 s
```

No hubo 403, 429, CAPTCHA, autenticación ni cambio de contrato. No se consultó
Florencia 6602, El Sauce 6604, `G10D03`, páginas de producto, browser/assets ni
Turso. El `auth_key` público del cliente se eliminó de los requests publicados;
se conserva el hash del body original y un registro explícito de la redacción.
No hay cookies, headers `Authorization` ni credenciales en el artifact.

El RAW publicable tiene SHA-256
`b76f3910b19cc29d1c69baa1d70ac90298e8e95a7ba9d2e9be30643b3af5d848`.

## Totales y plan por raíz

El catálogo tiene 26 raíces. Veintitrés raíces pendientes tienen productos;
`U11D13 / Audiología` y `J10D44 / Joyería y relojes` reportaron cero. Los totales
pendientes suman 1,653 observaciones de producto. Al añadir los 1,124 productos
del snapshot completo de Alimentos, la suma bruta es 2,777 por club.

| key | categoría | numFound | páginas a 200 | POST nuevos SPS | POST nuevos Florencia |
|---|---|---:|---:|---:|---:|
| `S10D45` | Productos de temporada | 58 | 1 | 1 | 1 |
| `G10D03` | Alimentos | 1,124 | ya completo | 0 | 0 |
| `H30D22` | Hogar | 315 | 2 | 1 | 2 |
| `H20D09` | Salud y belleza | 186 | 1 | 1 | 1 |
| `G10D08014` | Licor, cerveza y vino | 97 | 1 | 1 | 1 |
| `P10D51` | Mascotas | 37 | 1 | 1 | 1 |
| `B10D27` | Bebé | 42 | 1 | 1 | 1 |
| `H10D21` | Ferretería y mejoras al hogar | 78 | 1 | 1 | 1 |
| `S30D26` | Deportes y fitness | 47 | 1 | 1 | 1 |
| `O20D30` | Exteriores | 80 | 1 | 1 | 1 |
| `E10D24` | Electrónicos | 72 | 1 | 1 | 1 |
| `S20D23` | Electrodomésticos | 83 | 1 | 1 | 1 |
| `C10D29` | Computadoras, tablets y accesorios | 33 | 1 | 1 | 1 |
| `M10D43` | Línea blanca | 32 | 1 | 1 | 1 |
| `F10D40` | Moda y accesorios | 213 | 2 | 2 | 2 |
| `F20D27` | Muebles | 46 | 1 | 1 | 1 |
| `O10D25` | Oficina | 16 | 1 | 1 | 1 |
| `R10D22` | Suministros para restaurantes | 21 | 1 | 1 | 1 |
| `A10D20` | Automotriz | 102 | 1 | 1 | 1 |
| `T10D46` | Juguetes y juegos | 25 | 1 | 1 | 1 |
| `L10D22` | Equipaje | 12 | 1 | 0 | 1 |
| `U10D72` | Óptica | 55 | 1 | 1 | 1 |
| `U11D13` | Audiología | 0 | 0 | 0 | 0 |
| `T20D42` | Películas, música y libros | 1 | 1 | 0 | 1 |
| `V10D79` | Tarjetas de Regalo | 2 | 1 | 0 | 1 |
| `J10D44` | Joyería y relojes | 0 | 0 | 0 | 0 |

Los 21 POST SPS reutilizan el probe: Hogar ya conserva `start=0, rows=200`;
las primeras 12 filas completan Equipaje, Películas y Tarjetas; y sirven como
prefijo para las demás raíces de hasta 200 productos. Moda se descargará desde
`start=0` en dos páginas porque reutilizar 12 filas no reduce su número de
requests. Florencia necesita 25 páginas nuevas a 200. El full restante tiene por
tanto 46 POST base, no 50.

La consulta de membresía usa `q=<categoría>`, `fq=[]` y `view_id=HN`; el club sólo
cambia los campos comerciales solicitados en `fl`. Por eso los mismos `numFound`
determinan las ventanas de ambos clubes. El full aun así validará cada total y la
identidad recuperada en Florencia antes de declarar completitud.

## Taxonomía y particiones

Los facets de las 25 respuestas contienen 442 observaciones y 427 nodos nuevos
únicos. Al unirlos con los 117 nodos de Alimentos y las dos raíces vacías, el
árbol observado tiene 546 nodos: 26 raíces, 89 nodos con hijos, 457 hojas,
profundidad máxima 3, cero huérfanos y cero colisiones estructurales.

La raíz más grande tiene 315 productos, `rows=200` fue aceptado y el full anterior
ya demostró que `start` avanza hasta 1,116 dentro de un padre más grande. Por eso
las 23 raíces no vacías restantes pueden recorrerse directamente. No existe
evidencia de truncamiento que justifique dividirlas en hijos. Las particiones
productivas mínimas son 24: Alimentos ya completo y 23 raíces restantes; las dos
raíces con cero productos quedan demostradas como vacías.

## Solapamientos observados

La muestra contiene 443 memberships de producto en las raíces y 440 identidades
únicas. Tres productos aparecen con identidad exacta en dos consultas raíz:

| producto | raíces |
|---|---|
| `502638` | Productos de temporada + Hogar |
| `509161` | Productos de temporada + Exteriores |
| `491504` | Muebles + Oficina |

A nivel SKU hay 806 memberships y 795 identidades únicas: 11 SKU compartidos.
Ninguno de los 440 productos ni 795 SKU observados coincide con Alimentos.

Los facets completos de las respuestas señalan además 11 observaciones asignadas
a una raíz regular desde otra consulta: seis desde Productos de temporada, una
desde Mascotas, una desde Exteriores y tres desde Oficina. Esto respalda un punto
estimado de 2,766 productos únicos por club frente al máximo bruto de 2,777. La
cantidad exacta sólo puede demostrarse uniendo todas las identidades durante el
full; no se presenta la suma bruta como conteo único.

La muestra de variantes proyecta aproximadamente 6,015 SKU por club, incluidos
los 1,127 SKU exactos de Alimentos. Es una estimación de baja confianza porque la
muestra de Moda tiene muchos productos con variantes. El full calculará el valor
exacto.

## Presupuesto inicial del full restante

```text
endpoint                 POST /api/br_discovery/getProductsByKeyword
clubs                    SPS 6603 + Florencia 6602
rows                     200
POST base SPS            21
POST base Florencia      25
POST base total          46
retries reservados        5
POST máximo total        51
concurrencia               1
duración máxima          10 minutos
documentos nuevos     2,875
recrawl Alimentos          0
Turso                      0
```

El plan exige que cada `numFound` permanezca igual. Una variación, página
repetida, hueco, truncamiento o contrato distinto detendrá la captura; no se
gastarán retries para ocultar un cambio de catálogo. Los cinco retries representan
aproximadamente el 10.9% de las 46 páginas base, en línea con el margen del full
anterior, que terminó sin usar ninguno.

Al ritmo medido por el probe, las 46 páginas base tardarían cerca de 29 segundos.
El máximo solicitado de 10 minutos cubre los cinco timeouts/retries reservados y
el guardado RAW sin convertirlo en una autorización recurrente.

Este presupuesto quedó invalidado específicamente en su reutilización de páginas
parciales: la primera continuación repitió una identidad y dejó un hueco. La
taxonomía, totales y page size siguen válidos; el full revisado debe comenzar cada
raíz en `start=0`.

## Reproducción offline

```bash
python reports/pricesmart/2026-09-02-discovery-probe/verify.py
```

El verificador comprueba el manifiesto y todos los hashes, reconstruye las 26
respuestas, los 546 nodos, los solapamientos por identidad y el plan página por
página. También valida los archivos versionados de Alimentos y taxonomía raíz.
El resultado íntegro está en [`evidence.json`](evidence.json).
