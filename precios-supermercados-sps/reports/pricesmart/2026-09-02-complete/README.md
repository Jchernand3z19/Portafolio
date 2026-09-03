# PriceSmart Honduras — catálogo público completo

## Resultado

El catálogo público quedó completo para los dos contextos productivos aceptados:

- San Pedro Sula, club `6603`;
- Tegucigalpa Florencia, club `6602`.

El Sauce `6604` no se consultó ni se incluyó. La captura restante usó solamente
`POST https://www.pricesmart.com/api/br_discovery/getProductsByKeyword`, con
`rows=200` y concurrencia 1. Fueron 50 POST, 50 respuestas HTTP 200 válidas,
cero retries, 3,306 documentos y 30.85 segundos. Al sumar el intento fail-closed
anterior, la fase consumió 51 POST. No hubo Turso.

Se reconstruyeron desde `start=0` las 23 raíces no vacías fuera de Alimentos. Se
reutilizó sin recrawl el full verificado de Alimentos. Hogar y Moda requirieron
los offsets 0 y 200; las otras 21 raíces requirieron sólo offset 0. Cada ventana
coincidió con su `numFound`, sin huecos ni repeticiones dentro de una raíz.

## Consolidación

Por club, las 24 raíces no vacías suman 2,777 membresías de producto y 6,115
membresías SKU. La taxonomía no es una partición: 11 productos aparecen en dos
raíces y explican 11 membresías de producto y 37 membresías SKU duplicadas. Los
documentos duplicados fueron idénticos. Después de deduplicar por `pid` y
`skuid`, cada club contiene:

- 2,766 productos únicos;
- 6,078 SKU únicos;
- cero solapamientos entre Alimentos reutilizado y las raíces restantes;
- la misma membresía de productos y SKU en SPS y Florencia.

El parser conserva todas las raíces de cada producto en `source_details` y usa
una categoría determinista en la fila persistible. La disponibilidad se mantiene
separada de precio y promoción.

## Comparación comercial

Los 6,078 SKU son compartidos. Hay 5,129 SKU con precio en ambos clubes y 115
precios efectivos distintos entre ellos. Además, el campo `current_price` difiere
en 493 SKU al incluir casos con precio en un club y sin precio en el otro. Se
observaron tres diferencias en `reported_regular_price`, 378 en `is_promotion` y
995 en disponibilidad; 833 de estas últimas son diferencias exclusivamente de
disponibilidad.

Las 115 diferencias de precio entre SKU simultáneamente cotizados demuestran una
diferencia comercial reproducible atribuible al club. Por eso se conservan SPS
6603 y Florencia 6602 como contextos productivos separados.

## Delta offline frente a producción

Producción contiene el alcance Alimentos previo: 1,127 SKU por ubicación. El
snapshot completo conserva esos 1,127 estados comerciales sin cambios y agrega,
por ubicación:

- 4,951 ofertas SKU nuevas;
- 1,642 productos fuente nuevos;
- 3,309 variantes adicionales dentro de esos productos;
- cero cambios comerciales en estados ya persistidos;
- cero cambios sólo de metadata;
- cero SKU previamente persistidos ausentes del snapshot nuevo.

La simulación ejecutó el mismo SQL productivo sobre las cinco tablas. Cada carga
completa abrió 4,951 estados y dejó 1,127 sin cambio; no cerró periodos. El replay
fue idempotente, `integrity_check` fue `ok`, no hubo violaciones FK ni estados
abiertos duplicados, y los datos centinela de La Colonia, Colonial y Walmart no
cambiaron. La ausencia futura de una identidad no se interpreta como
`out_of_stock`.

## RAW y secretos

`raw-capture.tar.gz` contiene las 50 parejas request/response completas, ledger,
resultado, autorización y script de captura. El `auth_key` público del cliente se
redactó antes de publicar; se conservaron los hashes originales de cada body para
provenance. No se publican cookies, encabezados `Authorization`, tokens,
credenciales, login ni datos de membresía.

## Reproducción

Desde la raíz del proyecto:

```bash
python reports/pricesmart/2026-09-02-complete/verify.py
pytest -q tests/test_pricesmart_complete_capture.py tests/test_pricesmart_full_capture.py tests/test_pricesmart_persistence.py
```

El verificador comprueba el manifiesto y hashes RAW, binding de club, paginación,
totales por raíz, deduplicación, snapshots, comparación comercial y persistencia
offline. La escritura del delta completo en Turso sigue pendiente de una
autorización separada.
