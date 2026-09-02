# PriceSmart Honduras — full controlado SPS + Florencia

## Resultado

El full crawl autorizado quedó completo para los dos contextos comerciales
aceptados y únicamente para el universo medido en el preflight:

```text
categoría pública = G10D03 / Alimentos
SPS               = club 6603
TGU               = Florencia / club 6602
El Sauce 6604     = excluido
```

`G10D03` es un catálogo completo de Alimentos según el facet y `numFound` de la
fuente. No se afirma que incluya todos los departamentos del sitio de PriceSmart.

La captura hizo **188 POST**, 94 por club, todos HTTP 200. No hubo retry,
residual, 403, 429 ni CAPTCHA. Concurrencia 1; duración 107.833 s; quedaron 20
POST sin consumir del techo de 208. No se usó login, membresía, carrito,
checkout, mutación, El Sauce, Turso ni recurrencia.

## Completitud

| Contexto | Páginas | Productos `numFound` | Productos únicos | SKU/variantes | Con precio |
| --- | ---: | ---: | ---: | ---: | ---: |
| SPS 6603 | 94 | 1,124 | 1,124 | 1,127 | 1,080 |
| Florencia 6602 | 94 | 1,124 | 1,124 | 1,127 | 1,074 |

Cada contexto cubre los offsets `0..1116` con `rows=12`; la última página tiene
ocho productos. No hay duplicados ni huecos. Ambos clubes comparten las mismas
1,124 identidades de producto y 1,127 identidades SKU. Los requests contienen
únicamente campos `*_HN_6603` o `*_HN_6602`; el verificador rechaza `6604`.

## Semántica comercial

`price_HN_<club>` es entero en centavos HNL. El precio regular sólo se publica
cuando `original_price_without_saving_HN_<club>` existe. Una promoción se acepta
cuando la fuente declara a la vez precio regular mayor y
`saving_amount_HN_<club>` negativo consistente con la diferencia, tolerando un
centavo por el redondeo observado en productos por peso.

Para una oferta con precio cuyos campos regular/ahorro fueron solicitados pero no
devueltos, `is_promotion=false`. Para una variante sin precio,
`reported_regular_price=null` e `is_promotion=null`. Availability sigue separado:
sólo es `in_stock` cuando la fuente declara simultáneamente
`availability=true` e `inventory=in stock`; cualquier otra combinación observada
queda `out_of_stock`.

| Contexto | Promoción | No promoción con precio | Promoción desconocida sin precio | In stock | Out of stock |
| --- | ---: | ---: | ---: | ---: | ---: |
| SPS 6603 | 18 | 1,062 | 47 | 829 | 298 |
| Florencia 6602 | 17 | 1,057 | 53 | 844 | 283 |

La comparación entre ciudades encuentra 1,040 SKU con precio en ambos contextos:
110 diferencias de precio, tres de precio regular, 74 de estado de promoción y
203 de disponibilidad. De estas últimas, 130 son exclusivamente de availability.
Esto confirma que SPS y TGU deben persistirse como contextos independientes; no
reabre la decisión de El Sauce.

## Preflight TLS transparente

Antes de la captura hubo 21 intentos del cliente que fallaron localmente durante
la verificación del certificado (`CERTIFICATE_VERIFY_FAILED`). No se estableció
sesión TLS, no hubo respuesta HTTP y ningún body POST llegó al servidor. El runner
se corrigió para usar la CA de `certifi`; esos intentos se publican aparte como
fallos de transporte y no forman parte del ledger de 188 POST HTTP exitosos.

## Parser, fixtures y RAW

[`pricesmart.py`](../../../src/precios_supermercados/scrapers/pricesmart.py)
verifica endpoint, binding, request y response hashes, offsets, total estable,
facets, pertenencia, identidades de producto/variante, precio, promoción y
availability antes de producir snapshots.

Los fixtures bajo `tests/fixtures/pricesmart/` son documentos exactos derivados
del RAW y cubren promoción, no promoción, oferta sin precio y el único producto
con cuatro variantes. Las pruebas vuelven a vincularlos con sus páginas fuente.

- `raw-capture.tar.gz`: 382 archivos; 1,769,114 bytes; SHA-256
  `4613c634f584cc3ba157504f5b40cbb04aa94c7c14e65984672babe9e27d1b05`.
- `pricesmart_sps.json.gz`: snapshot persistible; JSON SHA-256
  `9a352afa72b2bef89404b03d81ef22494cee7c02af262098a89730b58bdbbff3`.
- `pricesmart_tgu.json.gz`: snapshot persistible; JSON SHA-256
  `9b65f2451f026e6591650e585fb14e9da5f1e206852e94869d4514734f092213`.
- `evidence.json`: resumen reproducible.
- `offline-sql-summary.json`: prueba de persistencia sin red.
- `verify.py`: reconstruye snapshots desde RAW y verifica todos los hashes.

## Persistencia productiva validada offline

La persistencia conserva exactamente las cinco tablas existentes. El único cambio
físico permite el mismo estado nulo ya aceptado para Walmart también a PriceSmart:
precio/promoción nulos exclusivamente cuando availability es `out_of_stock`.
[`migrar_mvp_pricesmart.py`](../../../scripts/migrar_mvp_pricesmart.py) transforma
una vez el fingerprint previo
`f09ea1cf63f3de159c87872f842babcc42e5d14f8e2c33067782dd272c1a36f4`
al nuevo
`c971e706a2de9872b2351a1546041ef7c607f263afef39c3776c72b9bee1a46e`.

La prueba offline cargó ambos snapshots completos:

```text
products PriceSmart          = 1,127
current PriceSmart SPS       = 1,127
current PriceSmart TGU       = 1,127
periodos abiertos duplicados = 0
foreign key violations       = 0
PRAGMA integrity_check       = ok
tablas                        = 5
```

El replay exacto no escribió filas. Los hashes lógicos de La Colonia, Colonial y
Walmart permanecieron iguales antes y después de cargar PriceSmart. La migración
preservó byte por byte el estado lógico previo en las cinco tablas y revierte ante
fallo DDL inyectado.

## Gate Turso

PriceSmart queda listo para su primera carga Turso, pero **Turso no fue ejecutado**.
La futura carga requiere autorización independiente y debe seguir este orden:

1. confirmar acceso/cuota y preservar backup;
2. comprobar fingerprint previo y cronología existente;
3. ejecutar una sola vez la migración PriceSmart;
4. validar ambos snapshots y sus SHA;
5. cargar primero SPS y después Florencia con run IDs distintos;
6. verificar conteos, ubicaciones, periodos abiertos, FK e integridad;
7. detenerse sin tuning remoto, recurrencia ni recrawl.

## Verificación offline

```bash
python reports/pricesmart/2026-09-01-full/verify.py
pytest -q tests/test_pricesmart_full_capture.py tests/test_pricesmart_persistence.py
```
