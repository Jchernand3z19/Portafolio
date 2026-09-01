# PriceSmart Honduras — captura CDP de la petición real

## Resultado

La carga real del catálogo reveló una fuente pública estructurada que los probes
GraphQL anteriores no habían encontrado:

```text
POST https://www.pricesmart.com/api/br_discovery/getProductsByKeyword
```

El navegador recibió HTTP 200 con 12 productos de 1,124 y el replay directo de la
misma operación recibió una respuesta idéntica byte a byte. No hizo falta cookie,
login, membresía, carrito ni header privado. Esto reabre PriceSmart como **fuente
pública de precio de catálogo Honduras** y deja intacto el hallazgo histórico de
que la ruta GraphQL externa estaba mal vinculada.

El objetivo completo no se alcanzó. La página anónima seguía mostrando
`Seleccionar entrega`; el payload sólo contiene `view_id: HN` y campos `*_HN`, sin
club, channel ni `6603`. La respuesta expone facets llamados `price_HN_6602`,
`price_HN_6603` y `price_HN_6604`, pero no devuelve esos valores por producto.
Esos nombres prueban dimensiones indexadas, no binding causal de SPS. Por tanto,
el precio observado no se atribuye a San Pedro Sula.

Además, el replay comenzó 27.209 s después del deadline y terminó 27.919 s tarde:
la ventana fue `03:29:20.765Z–03:34:20.765Z` y el replay terminó a
`03:34:48.684Z`. El conteo de requests sí quedó dentro de los máximos, pero el
probe no cumplió el límite temporal. Se cerró la instancia temporal y no hubo más
tráfico live.

**Outcome B: fuente HN demostrada parcialmente; binding SPS no demostrado y
protocolo temporal no conforme.** No se crea parser, fixture comercial, scraper,
full, presupuesto de full, persistencia, modelo, workflow ni acceso Turso.

## Petición observada y reproducida

Headers públicos necesarios:

```http
Accept: application/json, text/plain, */*
Content-Type: application/json
Referer: https://www.pricesmart.com/es-hn/categoria/Alimentos-G10D03/G10D03
```

No hubo header `Cookie`. Se eliminaron `newrelic`, `traceparent`, `tracestate`,
User-Agent y client hints porque son telemetría o fingerprint y el replay no los
necesitó. El `auth_key` se conserva: es un valor anónimo enviado por el navegador
público dentro del payload y fue necesario para reproducir la operación.

```json
[
  {
    "url": "https://www.pricesmart.com/es-hn/categoria/Alimentos-G10D03/G10D03",
    "start": 0,
    "q": "G10D03",
    "fq": [],
    "search_type": "category",
    "rows": 12,
    "account_id": "7024",
    "auth_key": "ev7libhybjg5h1d1",
    "request_id": 1788233361440,
    "domain_key": "pricesmart_bloomreach_io_es",
    "fl": "pid,title,price,thumb_image,brand,slug,skuid,currency,fractionDigits,master_sku,sold_by_weight_HN,weight_HN,weight_uom_description_HN,sign_price_HN,price_per_uom_HN,uom_description_HN,saving_amount_HN,original_price_without_saving_HN,availability_HN,price_HN,inventory_HN,inventory_HN,promoid_HN",
    "view_id": "HN"
  }
]
```

| Evidencia | Navegador | Replay |
| --- | ---: | ---: |
| HTTP | 200 | 200 |
| Content-Type | `application/json; charset=utf-8` | `application/json; charset=utf-8` |
| Productos devueltos | 12 | 12 |
| Total declarado | 1,124 | 1,124 |
| SHA-256 body | `70c92230d5d77ea85e842c043e4d0aa4dfea44a149ebaa477e768376a0cbe296` | igual |

## Producto de control

| Campo | Evidencia |
| --- | --- |
| SKU / PID / master SKU / variant SKU | `479223` |
| Producto | King Cheese Feta con Sabores 2 Unidades / 227 g / 8 oz |
| Moneda / decimales | HNL / 2 |
| `price_HN` | `35995` |
| `current_price` normalizado | **L 359.95** |
| Precio visible en navegador | **L 359.95** |
| `reported_regular_price` | `null`; el campo solicitado no fue devuelto |
| `is_promotion` | `null`; la fuente no declaró promoción de precio |
| Campaign IDs | `free-delivery`, `new arrival`, `pantry-refresh` |
| Availability | `availability_HN=true`, `inventory_HN=in stock` |

Los campaign IDs son etiquetas explícitas de campaña, pero ninguna declara ahorro,
precio regular o descuento. No se convierten en `is_promotion=true`. Availability
se registra aparte y no se usa para decidir granularidad.

## Clubes y granularidad

La respuesta contiene rangos de precio con estos conteos:

| Facet | Productos con bucket de precio |
| --- | ---: |
| `price_HN_6602` Florencia | 1,072 |
| `price_HN_6603` San Pedro Sula | 1,078 |
| `price_HN_6604` El Sauce | 1,061 |

El request no solicitó esos campos en `fl`; los 12 productos sólo tienen
`price_HN`, `availability_HN` e `inventory_HN`. En consecuencia:

- SKU comparables por club: **0**;
- diferencias de precio, regular, promoción y sólo disponibilidad: **no evaluables**;
- SPS como contexto independiente: **no demostrado**;
- Florencia vs El Sauce: **no evaluable**;
- granularidad TGU: **sin decisión**.

Un probe posterior tendría que capturar, dentro de una sesión conforme, una
petición cuyo payload o respuesta vincule explícitamente `6603` y devuelva el valor
de precio del SKU para ese club. No se presupone que cambiar `fl`, facets, cookies
o estado anónimo sea suficiente; cualquier nuevo tráfico requiere un alcance nuevo.

## Ledger

| Métrica | Resultado |
| --- | ---: |
| Sesiones de browser | 1/1 |
| Cargas/reloads | 1/2 |
| Requests CDP observados en la carga | 135 |
| XHR comercial seleccionado | 1 |
| Replays directos | 1/3 |
| Retries | 0 |
| Concurrencia | 1 |
| Duración | 327.919/300 s |
| Exceso | 27.919 s |

## Evidencia offline

- [raw-capture.tar.gz](raw-capture.tar.gz): request/response del navegador, replay,
  estado visible, ledger y manifest; SHA-256
  `cc6374a104f84eb2bf44ac9e4aa2123e052584a676debeb293f7e5cd13d5492c`.
- [evidence.json](evidence.json): resultado normalizado.
- [verify.py](verify.py): valida sin red la integridad, igualdad exacta, contrato,
  producto, semántica comercial, ausencia de cookie y falta de binding de club.

```bash
python precios-supermercados-sps/reports/pricesmart/2026-09-01-browser-request-probe/verify.py
```
