# PriceSmart Honduras — GraphQL público sin binding de tenant

## Resultado

La extensión de descubrimiento cerró PriceSmart después de dos POST read-only. La
introspección limitada de `Query` fue rechazada por Apollo Server. La consulta
mínima autorizada `findChannels { __typename }` llegó al resolver, pero éste intentó
consultar:

```text
https://api.sphere.io/changeme/channels?offset=0&limit=500
```

El upstream respondió 404 `Not found` y `data.findChannels` fue `null`. El segmento
literal `changeme` demuestra que la ruta pública no está vinculada al proyecto
commercetools de PriceSmart con los headers observados. No es un catálogo vacío ni
un binding de los clubes `6602`, `6603` y `6604`.

El tercer POST quedó sin consumir: variar argumentos de `findChannels` no puede
reemplazar el tenant `changeme`. Corregirlo requeriría configuración, credencial,
otro endpoint o mecanismo no observado y excluido del alcance.

No hubo 403, 429, CAPTCHA, redirect, mutation, login, cookie, token, membresía,
carrito, producto, full, persistencia ni Turso.

## Autorización y ledger

Autorización registrada `2026-08-31T23:49:09Z`. Ventana live iniciada
`23:49:54.467853Z`, con deadline `23:54:54.467853Z`, y cerrada a
`23:50:11.900682Z`, tras 17.432829 s.

| Métrica | Resultado |
| --- | ---: |
| POST usados | 2/3 |
| POST no consumidos | 1 |
| Retries | 0/1 |
| Concurrencia | 1 |
| Introspección limitada | HTTP 400 / deshabilitada |
| `findChannels` | HTTP 200 / GraphQL `BAD_USER_INPUT` |
| Upstream | 404 / proyecto `changeme` |

Ambas solicitudes usaron únicamente headers públicos: `connector: commercetools`,
`br-acct-env: pricesmart`, `Origin: https://www.pricesmart.com` y JSON. No se envió
`Authorization`.

## Estado comercial

| Objetivo | Resultado |
| --- | --- |
| Binding reproducible de club | No demostrado |
| Identidades SKU compartidas | 0 |
| `current_price` | No evaluable |
| `reported_regular_price` | No evaluable |
| `is_promotion` | No evaluable |
| Availability separada | No evaluable |
| Florencia vs El Sauce | No evaluable |
| SPS independiente | No evaluable |
| Granularidad TGU | Sin decisión |
| Paginación/full | No estimable |

Los clubes y el contrato de precio permanecen demostrados sólo como configuración
del cliente Nuxt. Ninguna respuesta comercial pública los vinculó al resolver.
Availability no influyó en la decisión.

## Decisión

**PriceSmart queda bloqueado para price tracking web público con la superficie
reproducible observada.** No se crea parser, fixture comercial, scraper,
persistencia ni presupuesto de full. Para reabrir el candidato debe aparecer una
fuente pública que vincule realmente el tenant PriceSmart, o una autorización nueva
y específica para un mecanismo distinto. Una autorización temporal general no
convierte credenciales o configuración privada en fuente pública.

## Evidencia

- [raw-capture.tar.gz](raw-capture.tar.gz): dos requests, dos responses, ledger y
  manifest; SHA-256
  `34f0c772a1e8988de8cd29df5219539084628faa17ac0fb0c715c9eefe3196e8`.
- [evidence.json](evidence.json): resultado normalizado.
- [verify.py](verify.py): valida offline hashes, presupuestos, operaciones,
  introspección bloqueada, URL upstream `changeme`, null comercial y ausencia de
  mutation.

No hubo valores sensibles en la captura y no se necesitó redacción.
