# Carga productiva controlada — supermercados terminados

El 2 de septiembre de 2026 se cargaron en `precios-supermercados` los snapshots
aceptados de Colonial, Walmart y PriceSmart, sin recrawl. La Colonia se conservó
exactamente. La base terminó con cuatro supermercados, ocho ubicaciones y las
cinco tablas del MVP.

## Resultado

| Cadena / contexto | Run productivo | SKU actuales |
|---|---|---:|
| La Colonia SPS | estado previo preservado | 9,472 |
| La Colonia TGU | estado previo preservado | 9,495 |
| Colonial SPS | `colonial-first-20260830-2f7861ff6dec` | 9,205 |
| Walmart SPS | `walmart-first-20260831-sps-d4cf99b97457` | 13,664 |
| Walmart TGU FFAA | `walmart-first-20260831-tgu-ffaa-f8dccd164fb3` | 14,091 |
| Walmart TGU El Sauce | `walmart-first-20260831-tgu-el-sauce-d9352cd3d137` | 13,997 |
| PriceSmart SPS 6603 | `pricesmart-first-20260901-sps-6603-9a352afa72b2` | 1,127 |
| PriceSmart Florencia 6602 | `pricesmart-first-20260901-tgu-6602-9b65f2451f02` | 1,127 |

PriceSmart sigue limitado al universo demostrado `G10D03 / Alimentos`. No se
cargó El Sauce 6604. Tampoco existen ubicaciones de Maxi Despensa, Despensa
Familiar o Paiz.

## Migraciones y preservación

El respaldo previo fue restaurado offline con `integrity_check=ok` y cero fallos
de foreign keys. Su SHA-256 es
`dc60f8ceb3aa94935d193426e01b39e27731dcc27f51180aa42e2ae46d104c16`.

La huella inicial
`d00fa5e684c68b4e6e9b28679d95cc816d40f089df6f4e212484a2e524bc3133`
coincidió con el preflight de Walmart. En el commit ejecutado, la función de
destino Walmart derivaba el esquema compartido vigente y alcanzó directamente la
huella final PriceSmart
`c971e706a2de9872b2351a1546041ef7c607f263afef39c3776c72b9bee1a46e`.
El preflight PriceSmart comprobó esa igualdad exacta y omitió correctamente una
segunda reconstrucción. Este PR congela el destino histórico Walmart en
`f09ea1cf63f3de159c87872f842babcc42e5d14f8e2c33067782dd272c1a36f4`
para que una instalación limpia futura conserve las dos migraciones explícitas.

La comparación offline de checkpoints encontró cero filas añadidas, retiradas o
alteradas en las cinco tablas para La Colonia y Colonial después de las cargas
posteriores. Los seis snapshots nuevos coinciden con producción en identidad y
estado comercial: cero faltantes, extras o diferencias de precio, precio regular,
promoción y availability. El resultado final tiene cero periodos actuales
duplicados, cero fallos FK e integridad correcta.

## Costo medido

Turso estaba operativo en plan `starter`, con overages deshabilitados. El contador
pasó de 241,809 a 2,029,820 filas leídas y de 31,636 a 545,341 filas escritas. La
operación completa consumió 1,788,011 lecturas y 513,705 escrituras. Quedan
497,970,180 lecturas y 9,454,659 escrituras antes del reset indicado por la CLI
para el 30 de septiembre de 2026 a las 18:00 CST.

| Checkpoint | Delta lecturas | Delta escrituras |
|---|---:|---:|
| Colonial + verificación | 224,826 | 92,073 |
| Migración Walmart + checkpoint | 120,420 | 88,857 |
| Tres cargas Walmart + verificaciones | 559,922 | 228,879 |
| Dos cargas PriceSmart + verificación final | 882,843 | 103,896 |

Los contadores son agregados: cada delta incluye la verificación/checkpoint
adyacente nombrado. Las escrituras crecieron de forma proporcional a las filas
procesadas; no reapareció un patrón cuadrático, scan global por SKU o N+1. El
checkpoint PriceSmart no se separó de la verificación final y por eso se publica
como un único delta medido, sin inventar una atribución más precisa.

Los valores completos, hashes y run IDs están en [evidence.json](evidence.json).
