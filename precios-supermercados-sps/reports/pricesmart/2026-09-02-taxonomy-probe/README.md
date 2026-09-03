# PriceSmart Honduras — probe live de taxonomía raíz

> Estado posterior: el probe Discovery ya midió las 25 raíces pendientes,
> demostró `rows=200` y calculó el full restante. Ver
> [`../2026-09-02-discovery-probe/README.md`](../2026-09-02-discovery-probe/README.md).

## Resultado

El probe autorizado ejecutó **dos POST** públicos de sólo lectura a
`/api/ct/getFacetCategories`: el inicial y un retry de recuperación después de
que un reinicio del entorno eliminara su worktree efímero antes de publicar el
RAW. Ambos recibieron HTTP 200 y devolvieron cuerpos byte a byte idénticos, con
SHA-256 `cd8a01f4b7f774e52c69f9fecd30fda4e778223691c54139c5809a111332e978`.
La recuperación terminó en 0.238 segundos.

```text
POST autorizados                  4
POST ejecutados                   2
HTTP 200                          2
retries                           1
presupuesto no consumido          2
Discovery/productos               0
browser/assets                    0
Turso                             0
```

La respuesta conservada devolvió 26 categorías con `parent=null` y
`ancestors=[]`. Como la página tuvo 26 resultados frente al límite de 200, fue
terminal y no correspondía solicitar `offset=200`. No hubo 403, 429, CAPTCHA,
autenticación requerida ni contrato inesperado.

El RAW recuperado tiene 5,159 bytes. El archivo publicable, que también conserva
el ledger de ambos intentos y la causa del retry, tiene SHA-256
`68267bbe876abc6efea726d23e7aa22bc8254bb3798f0f8a3e018d8bd5b34771`.

## Taxonomía raíz demostrada

La fuente declara estas 26 raíces, en su orden original:

| # | key | categoría |
|---:|---|---|
| 1 | `S10D45` | Productos de temporada |
| 2 | `G10D03` | Alimentos |
| 3 | `H30D22` | Hogar |
| 4 | `H20D09` | Salud y belleza |
| 5 | `G10D08014` | Licor, cerveza y vino |
| 6 | `P10D51` | Mascotas |
| 7 | `B10D27` | Bebé |
| 8 | `H10D21` | Ferretería y mejoras al hogar |
| 9 | `S30D26` | Deportes y fitness |
| 10 | `O20D30` | Exteriores |
| 11 | `E10D24` | Electrónicos |
| 12 | `S20D23` | Electrodomésticos |
| 13 | `C10D29` | Computadoras, tablets y accesorios |
| 14 | `M10D43` | Línea blanca |
| 15 | `F10D40` | Moda y accesorios |
| 16 | `F20D27` | Muebles |
| 17 | `O10D25` | Oficina |
| 18 | `R10D22` | Suministros para restaurantes |
| 19 | `A10D20` | Automotriz |
| 20 | `T10D46` | Juguetes y juegos |
| 21 | `L10D22` | Equipaje |
| 22 | `U10D72` | Óptica |
| 23 | `U11D13` | Audiología |
| 24 | `T20D42` | Películas, música y libros |
| 25 | `V10D79` | Tarjetas de Regalo |
| 26 | `J10D44` | Joyería y relojes |

Cada fila también conserva el UUID, slug y metadatos exactos. Los 26 UUID, keys
y slugs son únicos. Esta respuesta demuestra la capa raíz completa observada;
no demuestra todavía los subárboles, totales ni productos de las 25 raíces
distintas de Alimentos.

`G10D03 / Alimentos` coincide con la partición ya capturada: 1,124 productos y
1,127 SKU por club. Ese snapshot se reutilizará y no necesita recrawl. La
existencia de `S10D45 / Productos de temporada` puede implicar solapamiento con
departamentos permanentes; sin identidades de productos no se lo cuantifica ni se
asume que sea cero.

## Siguiente frontera medida

Para calcular el presupuesto full faltan `numFound` y facet por cada una de las
25 raíces restantes, y el tamaño máximo de página aceptado por Discovery. El
siguiente probe mínimo propuesto usa únicamente
`POST https://www.pricesmart.com/api/br_discovery/getProductsByKeyword`:

1. 25 requests con `start=0`, `rows=12`, uno por key pendiente, para obtener
   `numFound`, facet y una muestra de identidades;
2. hasta tres requests adaptativos sobre la raíz pendiente con mayor `numFound`
   de al menos 200, con `start=0` y `rows=200`, `100` o `50`, sólo hasta
   demostrar el máximo útil;
3. tres retries de reserva, incluidos en un techo de **31 POST**.

Se reutilizará exactamente el template público ya demostrado para SPS 6603,
cambiando sólo `q`, URL de categoría, `start` y `rows`; Florencia 6602 no hace
falta para medir taxonomía/paginación y El Sauce 6604 sigue excluido. El máximo
teórico de documentos retornados es 500: 300 en las 25 muestras y 200 en una
caracterización exitosa. Los intentos de tamaño inferiores sólo ocurrirían si el
anterior fuera rechazado limpiamente.

`G10D03 / Alimentos` queda excluida incluso de la caracterización del tamaño de
página para evitar recrawlearla por conveniencia. La propuesta mantiene
concurrencia 1 y duración máxima de 10 minutos. Un rechazo HTTP limpio por tamaño
de página sólo permitiría probar el siguiente tamaño; se detendría ante 403, 429,
CAPTCHA o autenticación. No incluye páginas posteriores, full crawl, El Sauce,
navegador/assets, login, membresía, carrito, checkout, mutaciones, Turso ni
recurrencia.

Con los 25 `numFound` y el tamaño de página se podrán enumerar las particiones,
calcular el número exacto de páginas por club y presentar el presupuesto full. El
solapamiento exacto entre raíces se medirá por identidad durante el full; no se
usará la suma bruta de categorías como afirmación de productos únicos.

## Reproducción offline

```bash
python reports/pricesmart/2026-09-02-taxonomy-probe/verify.py
```

El verificador abre [`raw-capture.tar.gz`](raw-capture.tar.gz), valida su manifiesto
y todos los hashes, comprueba el ledger y la igualdad de ambos cuerpos, reconstruye
las 26 raíces y compara el resultado con [`evidence.json`](evidence.json). No usa
red.
