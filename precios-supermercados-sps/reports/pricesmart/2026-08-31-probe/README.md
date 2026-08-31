# PriceSmart Honduras — probe GET pausado en gate GraphQL

## Resultado

**Candidato viable para continuar la radiografía, todavía no apto para full ni
persistencia.** La web pública usa Nuxt/Vue Storefront y publica configuración de
un backend GraphQL de comercio, tres clubes hondureños y un esquema explícito de
precio, descuento y disponibilidad. Los GET no entregaron un precio confiablemente
ligado a la URL o al club; el cliente obtiene esos datos mediante un POST GraphQL
de sólo lectura fuera del dominio inicialmente autorizado.

El probe se pausó exactamente en ese gate. No hubo POST, mutación, login, cuenta,
carrito, browser, full crawl, scraper productivo, persistencia, cambio de modelo ni
acceso Turso.

## Autorización y tráfico

El usuario autorizó por 24 horas el probe propuesto. Ventana registrada:
**2026-08-31T21:53:50Z → 2026-09-01T21:53:50Z**. El alcance autorizado fue GET
público en `pricesmart.com`/`www.pricesmart.com`, máximo 30 intentos, 2 redirects,
3 retries transitorios, 4 assets, concurrencia 1 y 15 minutos. El preflight exigía
detenerse si aparecía POST/GraphQL o una mutación de contexto anónimo indispensable.

| Métrica | Resultado |
| --- | ---: |
| Intentos GET | 8 |
| HTTP 200 | 7 |
| Error antes de respuesta | 1 |
| Retry usado | 1 |
| Redirects | 0 |
| Assets Nuxt | 4/4 |
| Concurrencia | 1 |
| Gap mínimo observado | 8.849 s |
| Duración | 303.054 s |

El primer intento falló en la validación CA local antes de obtener respuesta. El
retry usó el CA instalado y recibió 200; se conserva el fallo en el ledger y se
cuenta dentro del presupuesto.

## Respuestas a la radiografía

1. **Sí existe una fuente pública estructurada usada por el sitio.** El estado Nuxt
   identifica `https://graphql-commerce.bloomreach.io`, tenant `pricesmart`, país
   `HND` y vista `HN`. Los assets enlazados contienen consultas `channels`,
   `productProjectionsSearch`, `inventoryEntries` y `products`.
2. **Sí existe GraphQL y estado embebido con contrato de precio/club.** El esquema
   observado incluye moneda, centavos, fracción, precio base, precio descontado,
   `discount.isActive`, stock y disponibilidad por channel. La configuración de
   discovery enumera `price`, `inventory`, `promoid`, `saving_amount_` y
   `original_price_without_saving_`.
3. **No es sólo catálogo/promociones estáticas.** La aplicación contiene contrato
   de comercio digital. Falta demostrar una respuesta pública de precio y el
   binding causal por club porque esa llamada es POST y no formó parte del permiso.

No se acepta todavía el precio `L 407.95` visto en el índice de búsqueda externo:
la ficha GET de SKU `516411` conserva identidad/título, pero no contiene `407.95`.

## Clubes y contexto

El estado público enumera:

| Clave fuente | Club | Ecommerce | Papel propuesto |
| --- | --- | --- | --- |
| `6602` | Florencia | Sí | TGU |
| `6603` | San Pedro Sula | Sí | SPS |
| `6604` | El Sauce | Sí | TGU |

`defaultClub=6602`. Esto identifica Florencia como club propio de Tegucigalpa y
El Sauce como otro contexto TGU; no demuestra que sus precios difieran. Comparables
de precio: **0**. Diferencias de efectivo, regular, promoción y sólo disponibilidad:
**no evaluables (`null`)**. Availability queda separada y no decidirá granularidad.

## Hallazgo de caché/binding

Los dos HTML de búsqueda no quedaron ligados a la query solicitada:

- se pidió `q=Bolsas` y el estado embebido respondió `q=Huevos`;
- se pidió `page=3&q=Vegetables` y respondió página 1 de `jabon dove`.

Por eso no se usó el HTML GET para formar muestra, estimar completitud o atribuir
precios. Repetir más GET no resuelve el contrato del cliente y sólo gastaría tráfico.

## Semántica comercial candidata

El GraphQL observado declara `ProductPrice.value` y `ProductPrice.discounted` con
`currencyCode`, `centAmount` y `fractionDigits`; el descuento declara `isActive`,
`validFrom` y `validUntil`. La interpretación a validar con respuesta real es:

```text
current_price = discounted.value si el descuento está activo; si no, value
reported_regular_price = value cuando existe discounted
is_promotion = discount.isActive
availability = channels[].availability.isOnStock
```

No se transforma esta hipótesis de contrato en datos aceptados antes del POST.

## Gate preciso pendiente

Se requiere ampliar el permiso con este alcance separado:

```text
método = POST de sólo lectura
endpoint = https://graphql-commerce.bloomreach.io/
operaciones observadas = channels, products, productProjectionsSearch
POST totales máximos = 8, incluidos hasta 2 retries
concurrencia = 1
pausa mínima = 1 segundo
timeout = 20 segundos
duración máxima = 10 minutos
```

Payloads: documentos GraphQL literales ya presentes en el asset público y variables
limitadas a país `HN`, moneda `HNL`, locale Honduras, claves `6602/6603/6604`, SKU
`516411` y una muestra de hasta 50 productos. Primero `channels` resolverá claves a
channel IDs; después `products`/`productProjectionsSearch` consultará precio,
descuento y disponibilidad. Se usará sólo configuración pública del cliente.

Se excluyen mutaciones, login, token de socio, cookies de cuenta, carrito, checkout,
browser, otros países, imágenes, full, recurrencia y Turso. Si el endpoint exige
credencial privada o estado de usuario, se detiene. El objetivo es obtener 20–50
identidades compartidas si el contrato lo permite y decidir si PriceSmart pasa a
un preflight de full separado.

## Evidencia y reproducción

- [evidence.json](evidence.json) contiene métricas, contrato, clubes y gate.
- [raw-capture.tar.gz](raw-capture.tar.gz) contiene ledger, manifest y ocho cuerpos
  publicados; SHA-256 `d0aec577880268de9633ac94eeec1802a31d54afcbdbb47d1206ced9794e3a7f`.
- [verify.py](verify.py) verifica hashes, presupuesto, pacing, redacciones, consultas,
  esquema, clubes y mismatches sin red.

Se redactaron tres apariciones de cada configuración pública con forma de credencial:
`brDiscoveryAuthKey`, Google Maps API key, PayPal client ID y Segment key. El
manifest conserva hashes original/publicado sin divulgar los valores.

```sh
python precios-supermercados-sps/reports/pricesmart/2026-08-31-probe/verify.py
```
